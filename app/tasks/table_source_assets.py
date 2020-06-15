import json
from typing import Any, Dict, List, Optional

from app.application import ContextEngine
from app.crud import assets
from app.models.pydantic.assets import AssetTaskCreate
from app.models.pydantic.change_log import ChangeLog
from app.models.pydantic.creation_options import (
    Index,
    Partitions,
    TableSourceCreationOptions,
)
from app.models.pydantic.jobs import Job, PostgresqlClientJob
from app.models.pydantic.metadata import DatabaseTableMetadata
from app.settings.globals import CHUNK_SIZE
from app.tasks import update_asset_field_metadata, update_asset_status, writer_secrets
from app.tasks.batch import execute


async def table_source_asset(
    dataset,
    version,
    source_uris: List[str],
    creation_options,
    metadata: Dict[str, Any],
) -> ChangeLog:
    options = TableSourceCreationOptions(**creation_options)

    # Register asset in database
    data = AssetTaskCreate(
        asset_type="Database table",
        dataset=dataset,
        version=version,
        asset_uri=f"/{dataset}/{version}/features",
        is_managed=True,
        creation_options=options,
        metadata=DatabaseTableMetadata(**metadata),
    )

    async with ContextEngine("PUT"):
        new_asset = await assets.create_asset(**data.dict())

    # Create table schema
    command = [
        "create_tabular_schema.sh",
        "-d",
        dataset,
        "-v",
        version,
        "-s",
        source_uris[0],
        "-m",
        json.dumps(options.dict()["table_schema"]),
    ]
    if options.partitions:
        command.extend(
            [
                "-p",
                options.partitions.partition_type,
                "-c",
                options.partitions.partition_column,
            ]
        )

    create_table_job = PostgresqlClientJob(
        job_name="create_table", command=command, environment=writer_secrets,
    )

    # Create partitions
    if options.partitions:
        partition_jobs: List[Job] = _create_partition_jobs(
            dataset, version, options.partitions, [create_table_job.job_name]
        )
    else:
        partition_jobs = list()

    # Load data
    load_data_jobs: List[Job] = list()

    parents = [create_table_job.job_name]
    parents.extend([job.job_name for job in partition_jobs])

    for i, uri in enumerate(source_uris):
        load_data_jobs.append(
            PostgresqlClientJob(
                job_name=f"load_data_{i}",
                command=[
                    "load_tabular_data.sh",
                    "-d",
                    dataset,
                    "-v",
                    version,
                    "-s",
                    uri,
                    "-D",
                    options.delimiter.encode(
                        "unicode_escape"
                    ).decode(),  # Need to escape special characters such as TAB for batch job payload
                ],
                environment=writer_secrets,
                parents=parents,
            )
        )

    # Add geometry columns and update geometries
    geometry_jobs: List[Job] = list()
    if options.latitude and options.longitude:
        geometry_jobs.append(
            PostgresqlClientJob(
                job_name="add_point_geometry",
                command=[
                    "add_point_geometry.sh",
                    "-d",
                    dataset,
                    "-v",
                    version,
                    "--lat",
                    options.latitude,
                    "--lng",
                    options.longitude,
                ],
                environment=writer_secrets,
                parents=[job.job_name for job in load_data_jobs],
            ),
        )

    # Add indicies
    index_jobs: List[Job] = list()
    parents = [job.job_name for job in load_data_jobs]
    parents.extend([job.job_name for job in geometry_jobs])

    for index in options.indices:
        index_jobs.append(
            PostgresqlClientJob(
                job_name=f"create_index_{index.column_name}_{index.index_type}",
                command=[
                    "create_index.sh",
                    "-d",
                    dataset,
                    "-v",
                    version,
                    "-c",
                    index.column_name,
                    "-x",
                    index.index_type,
                ],
                parents=parents,
                environment=writer_secrets,
            )
        )

    parents = [job.job_name for job in load_data_jobs]
    parents.extend([job.job_name for job in geometry_jobs])
    parents.extend([job.job_name for job in index_jobs])

    if options.cluster:
        cluster_jobs: List[Job] = _create_cluster_jobs(
            dataset, version, options.partitions, options.cluster, parents
        )
    else:
        cluster_jobs = list()

    async def callback(message: Dict[str, Any]) -> None:
        async with ContextEngine("PUT"):
            await assets.update_asset(new_asset.asset_id, change_log=[message])

    log: ChangeLog = await execute(
        [
            create_table_job,
            *partition_jobs,
            *load_data_jobs,
            *geometry_jobs,
            *index_jobs,
            *cluster_jobs,
        ],
        callback,
    )

    await update_asset_field_metadata(
        dataset, version, new_asset.asset_id,
    )
    await update_asset_status(new_asset.asset_id, log.status)

    return log


def _create_partition_jobs(
    dataset: str, version: str, partitions: Partitions, parents
) -> List[PostgresqlClientJob]:
    """
    Create partition job depending on the partition type.
    For large partition number, it will break the job into sub jobs
    """

    partition_jobs: List[PostgresqlClientJob] = list()

    if isinstance(partitions.partition_schema, list):
        chunks = _chunk_list([schema.dict() for schema in partitions.partition_schema])
        for i, chunk in enumerate(chunks):
            partition_schema: str = json.dumps(chunk)
            job: PostgresqlClientJob = _partition_job(
                dataset,
                version,
                partitions.partition_type,
                partition_schema,
                parents,
                i,
            )

            partition_jobs.append(job)
    else:

        partition_schema = json.dumps(partitions.partition_schema.dict())
        job = _partition_job(
            dataset, version, partitions.partition_type, partition_schema, parents,
        )
        partition_jobs.append(job)

    return partition_jobs


def _partition_job(
    dataset: str,
    version: str,
    partition_type: str,
    partition_schema: str,
    parents: List[str],
    suffix: int = 0,
) -> PostgresqlClientJob:
    return PostgresqlClientJob(
        job_name=f"create_partitions_{suffix}",
        command=[
            "create_partitions.sh",
            "-d",
            dataset,
            "-v",
            version,
            "-p",
            partition_type,
            "-P",
            partition_schema,
        ],
        environment=writer_secrets,
        parents=parents,
    )


def _create_cluster_jobs(
    dataset: str,
    version: str,
    partitions: Optional[Partitions],
    cluster: Index,
    parents: List[str],
) -> List[PostgresqlClientJob]:
    # Cluster tables. This is a full lock operation.
    cluster_jobs: List[PostgresqlClientJob] = list()

    if partitions:
        # When using partitions we need to cluster each partition table separately.
        # Playing it save and cluster partition tables one after the other.
        # TODO: Still need to test if we can cluster tables which are part of the same partition concurrently.
        #  this would speed up this step by a lot. Partitions require a full lock on the table,
        #  but I don't know if the lock is aquired for the entire partition or only the partition table.

        if isinstance(partitions.partition_schema, list):
            chunks = _chunk_list(
                [schema.dict() for schema in partitions.partition_schema]
            )
            for i, chunk in enumerate(chunks):
                partition_schema: str = json.dumps(chunk)
                job: PostgresqlClientJob = _cluster_partition_job(
                    dataset,
                    version,
                    partitions.partition_type,
                    partition_schema,
                    cluster.column_name,
                    cluster.index_type,
                    parents,
                    i,
                )
                cluster_jobs.append(job)
                parents = [job.job_name]

        else:
            partition_schema = json.dumps(partitions.partition_schema.dict())

            job = _cluster_partition_job(
                dataset,
                version,
                partitions.partition_type,
                partition_schema,
                cluster.column_name,
                cluster.index_type,
                parents,
            )
            cluster_jobs.append(job)

    else:
        # Without partitions we can cluster the main table directly
        job = PostgresqlClientJob(
            job_name="cluster_table",
            command=[
                "cluster_table.sh",
                "-d",
                dataset,
                "-v",
                version,
                "-c",
                cluster.column_name,
                "-x",
                cluster.index_type,
            ],
            environment=writer_secrets,
            parents=parents,
        )
        cluster_jobs.append(job)
    return cluster_jobs


def _cluster_partition_job(
    dataset: str,
    version: str,
    partition_type: str,
    partition_schema: str,
    column_name: str,
    index_type: str,
    parents: List[str],
    index: int = 0,
):
    return PostgresqlClientJob(
        job_name=f"cluster_partitions_{index}",
        command=[
            "cluster_partitions.sh",
            "-d",
            dataset,
            "-v",
            version,
            "-p",
            partition_type,
            "-P",
            partition_schema,
            "-c",
            column_name,
            "-x",
            index_type,
        ],
        environment=writer_secrets,
        parents=parents,
    )


def _chunk_list(data: List[Any], chunk_size: int = CHUNK_SIZE) -> List[List[Any]]:
    """
    Split list into chunks of fixed size.
    """
    return [data[x : x + chunk_size] for x in range(0, len(data), chunk_size)]
