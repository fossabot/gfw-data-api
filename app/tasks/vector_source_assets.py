import os
from typing import Any, Awaitable, Dict, List, Optional
from uuid import UUID

from app.application import ContextEngine
from app.crud import assets, tasks
from app.models.pydantic.assets import AssetTaskCreate
from app.models.pydantic.change_log import ChangeLog
from app.models.pydantic.creation_options import VectorSourceCreationOptions
from app.models.pydantic.jobs import GdalPythonImportJob, Job, PostgresqlClientJob
from app.models.pydantic.metadata import DatabaseTableMetadata
from app.tasks import update_asset_field_metadata, update_asset_status, writer_secrets
from app.tasks.batch import execute


async def vector_source_asset(
    dataset,
    version,
    source_uris: List[str],
    creation_options,
    metadata: Dict[str, Any],
) -> ChangeLog:

    if len(source_uris) != 1:
        raise AssertionError("Vector sources only support one input file")

    options = VectorSourceCreationOptions(**creation_options)

    # source_uri: str = gdal_path(source_uris[0], options.zipped)
    source_uri = source_uris[0]
    local_file = os.path.basename(source_uri)

    if options.layers:
        layers = options.layers
    else:
        layer, _ = os.path.splitext(os.path.basename(source_uri))
        layers = [layer]

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

    asset_id = new_asset.asset_id
    if asset_id is None:
        raise Exception("Asset_id is None!")
    job_env = writer_secrets + [{"name": "ASSET_ID", "value": str(asset_id)}]

    from fastapi.logger import logger

    logger.debug(f"DEBUG: job_env: {job_env}")

    create_vector_schema_job = GdalPythonImportJob(
        job_name="import_vector_data",
        command=[
            "create_vector_schema.sh",
            "-d",
            dataset,
            "-v",
            version,
            "-s",
            source_uri,
            "-l",
            layers[0],
            "-f",
            local_file,
        ],
        environment=job_env,
    )

    load_vector_data_jobs: List[Job] = list()
    for layer in layers:
        load_vector_data_jobs.append(
            GdalPythonImportJob(
                job_name="load_vector_data",
                command=[
                    "load_vector_data.sh",
                    "-d",
                    dataset,
                    "-v",
                    version,
                    "-s",
                    source_uri,
                    "-l",
                    layer,
                    "-f",
                    local_file,
                ],
                parents=[create_vector_schema_job.job_name],
                environment=job_env,
            )
        )

    gfw_attribute_job = PostgresqlClientJob(
        job_name="enrich_gfw_attributes",
        command=["add_gfw_fields.sh", "-d", dataset, "-v", version],
        parents=[job.job_name for job in load_vector_data_jobs],
        environment=job_env,
    )

    index_jobs: List[Job] = list()

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
                parents=[gfw_attribute_job.job_name],
                environment=job_env,
            )
        )

    inherit_geostore_job = PostgresqlClientJob(
        job_name="inherit_from_geostore",
        command=["inherit_geostore.sh", "-d", dataset, "-v", version],
        parents=[job.job_name for job in index_jobs],
        environment=job_env,
    )

    async def callback(
        task_id: Optional[UUID], message: Dict[str, Any]
    ) -> Awaitable[None]:
        async with ContextEngine("PUT"):
            if task_id:
                _ = await tasks.create_task(
                    task_id, asset_id=new_asset.asset_id, change_log=[message]
                )
            return await assets.update_asset(new_asset.asset_id, change_log=[message])

    log: ChangeLog = await execute(
        [
            create_vector_schema_job,
            *load_vector_data_jobs,
            gfw_attribute_job,
            *index_jobs,
            inherit_geostore_job,
        ],
        callback,
    )

    await update_asset_field_metadata(
        dataset, version, new_asset.asset_id,
    )
    await update_asset_status(new_asset.asset_id, log.status)

    return log
