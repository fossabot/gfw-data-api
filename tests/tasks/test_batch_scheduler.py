import os
from time import sleep
from typing import Any, Awaitable, Dict, Optional
from uuid import UUID

import boto3
import pytest
import requests
from sqlalchemy.sql.ddl import CreateSchema

import app.tasks.batch as batch
from app.application import ContextEngine, db
from app.crud import assets, datasets, tasks, versions
from app.models.pydantic.jobs import (
    GdalPythonExportJob,
    GdalPythonImportJob,
    PostgresqlClientJob,
    TileCacheJob,
)
from app.settings.globals import (
    API_URL,
    AWS_REGION,
    READER_USERNAME,
    WRITER_DBNAME,
    WRITER_HOST,
    WRITER_PASSWORD,
    WRITER_PORT,
    WRITER_USERNAME,
)
from tests.tasks import check_callbacks, poll_jobs

writer_secrets = [
    {"name": "PGPASSWORD", "value": str(WRITER_PASSWORD)},
    {"name": "PGHOST", "value": WRITER_HOST},
    {"name": "PGPORT", "value": WRITER_PORT},
    {"name": "PGDATABASE", "value": WRITER_DBNAME},
    {"name": "PGUSER", "value": WRITER_USERNAME},
]

GEOJSON_NAME = "test.geojson"
GEOJSON_PATH = os.path.join(os.path.dirname(__file__), "..", "fixtures", GEOJSON_NAME)
BUCKET = "test-bucket"


# @pytest.mark.skip(reason="Needs to be updated for new task behavior")
@pytest.mark.asyncio
async def test_batch_scheduler(batch_client, httpd):
    _, logs = batch_client
    httpd_port = httpd.server_port

    job_env = writer_secrets + [
        {"name": "STATUS_URL", "value": f"http://app_test:{httpd_port}/tasks"}
    ]

    batch.POLL_WAIT_TIME = 1

    s3_client = boto3.client(
        "s3", region_name=AWS_REGION, endpoint_url="http://motoserver:5000"
    )

    s3_client.create_bucket(Bucket=BUCKET)
    s3_client.upload_file(GEOJSON_PATH, BUCKET, GEOJSON_NAME)

    dataset = "test"
    version = "v1.1.1"
    input_data = {
        "source_type": "vector",
        "source_uri": [f"s3://{BUCKET}/{GEOJSON_NAME}"],
        "creation_options": {"src_driver": "GeoJSON", "zipped": False},
        "metadata": {},
    }

    async with ContextEngine("WRITE"):
        await datasets.create_dataset(dataset)
        await db.status(CreateSchema(dataset))
        await db.status(f"GRANT USAGE ON SCHEMA {dataset} TO {READER_USERNAME};")
        await db.status(
            f"ALTER DEFAULT PRIVILEGES IN SCHEMA {dataset} GRANT SELECT ON TABLES TO {READER_USERNAME};"
        )
        await versions.create_version(dataset, version, **input_data)
        new_asset = await assets.create_asset(
            dataset,
            version,
            asset_type="Database table",
            asset_uri="s3://path/to/file",
        )

    job1 = PostgresqlClientJob(
        job_name="job1",
        command=["test_mock_s3_awscli.sh", "-s", f"s3://{BUCKET}/{GEOJSON_NAME}"],
        environment=job_env,
    )
    job2 = GdalPythonImportJob(
        job_name="job2",
        command=[
            "test_mock_s3_ogr2ogr.sh",
            "-d",
            "test",
            "-v",
            "v1.0.0",
            "-s",
            f"s3://{BUCKET}/{GEOJSON_NAME}",
            "-l",
            "test",
            "-f",
            GEOJSON_NAME,
        ],
        environment=job_env,
        parents=[job1.job_name],
    )
    job3 = GdalPythonExportJob(
        job_name="job3",
        command=["test_mock_s3_awscli.sh", "-s", f"s3://{BUCKET}/{GEOJSON_NAME}"],
        # command=[
        #     "test_mock_s3_ogr2ogr.sh",
        #     "-d",
        #     "test",
        #     "-v",
        #     "v1.0.0",
        #     "-s",
        #     f"s3://{BUCKET}/{GEOJSON_NAME}",
        #     "-l",
        #     "test",
        #     "-f",
        #     GEOJSON_NAME,
        # ],
        environment=job_env,
        parents=[job2.job_name],
    )
    job4 = TileCacheJob(
        job_name="job4",
        command=["test_mock_s3_awscli.sh", "-s", f"s3://{BUCKET}/{GEOJSON_NAME}"],
        environment=job_env,
        parents=[job3.job_name],
    )

    async def callback(
        task_id: Optional[UUID], message: Dict[str, Any]
    ) -> Awaitable[None]:
        async with ContextEngine("WRITE"):
            if task_id:
                _ = await tasks.create_task(
                    task_id, asset_id=new_asset.asset_id, change_log=[message]
                )
            return await assets.update_asset(new_asset.asset_id, change_log=[message])

    log = await batch.execute([job1, job2, job3, job4], callback)
    assert log.status == "pending"

    tasks_rows = await tasks.get_tasks(new_asset.asset_id)

    task_ids = [str(task.task_id) for task in tasks_rows]

    # make sure, all jobs completed
    status = await poll_jobs(task_ids)
    assert status == "saved"

    check_callbacks(task_ids, httpd.server_port)


#
# def test_s3(moto_s3):
#     # import boto3
#     # boto3.client("s3", region_name="us-east-1", endpoint_url="http://motoserver:5000") #
#
#     client = app.utils.aws.get_s3_client()
#
#     client.create_bucket(Bucket="my_bucket_name")
#     more_binary_data = b"Here we have some more data"
#
#     client.put_object(
#         Body=more_binary_data,
#         Bucket="my_bucket_name",
#         Key="my/key/including/anotherfilename.txt",
#     )
#     assert moto_s3.called
#     assert moto_s3.call_count == 1
