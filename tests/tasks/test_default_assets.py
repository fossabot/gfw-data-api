from typing import List
from uuid import UUID

import pendulum
import pytest
import requests
from pendulum.parsing.exceptions import ParserError

from app.application import ContextEngine, db
from app.crud import assets, tasks, versions
from app.models.enum.assets import AssetStatus, AssetType
from app.models.orm.geostore import Geostore
from app.utils.aws import get_s3_client

from .. import BUCKET, GEOJSON_NAME, PORT, SHP_NAME, TSV_NAME, TSV_PATH
from ..utils import create_default_asset


@pytest.mark.asyncio
async def test_vector_source_asset(batch_client, async_client):

    _, logs = batch_client

    ############################
    # Setup test
    ############################

    dataset = "test"
    sources = (SHP_NAME, GEOJSON_NAME)

    for i, source in enumerate(sources):
        version = f"v1.1.{i}"
        input_data = {
            "creation_options": {
                "source_type": "vector",
                "source_uri": [f"s3://{BUCKET}/{source}"],
                "source_driver": "GeoJSON",
                "zipped": False,
                "create_dynamic_vector_tile_cache": True,
            },
            "metadata": {},
        }

        # we only need to create the dataset once
        if i > 0:
            skip_dataset = True
        else:
            skip_dataset = False
        asset = await create_default_asset(
            dataset,
            version,
            version_payload=input_data,
            async_client=async_client,
            logs=logs,
            execute_batch_jobs=True,
            skip_dataset=skip_dataset,
        )
        asset_id = asset["asset_id"]

        await _check_version_status(dataset, version)
        await _check_asset_status(dataset, version, 1)
        await _check_task_status(asset_id, 7, "inherit_from_geostore")

        # There should be a table called "test"."v1.1.1" with one row
        async with ContextEngine("READ"):
            count = await db.scalar(
                db.text(f'SELECT count(*) FROM {dataset}."{version}"')
            )
        assert count == 1

        # The geometry should also be accessible via geostore
        async with ContextEngine("READ"):
            rows: List[Geostore] = await Geostore.query.gino.all()

        assert len(rows) == 1 + i
        assert rows[0].gfw_geostore_id == UUID("23866dd0-9b1a-d742-a7e3-21dd255481dd")

        await _check_dynamic_vector_tile_cache_status(dataset, version)

        requests.delete(f"http://localhost:{PORT}")


@pytest.mark.asyncio
async def test_table_source_asset(batch_client, async_client):

    _, logs = batch_client

    ############################
    # Setup test
    ############################
    #
    # s3_client = get_s3_client()
    #
    # s3_client.create_bucket(Bucket=BUCKET)
    # s3_client.upload_file(TSV_PATH, BUCKET, TSV_NAME)

    dataset = "table_test"
    version = "v202002.1"

    # define partition schema
    partition_schema = list()
    years = range(2018, 2021)
    for year in years:
        for week in range(1, 54):
            try:
                name = f"y{year}_w{week:02}"
                start = pendulum.parse(f"{year}-W{week:02}").to_date_string()
                end = pendulum.parse(f"{year}-W{week:02}").add(days=7).to_date_string()
                partition_schema.append(
                    {"partition_suffix": name, "start_value": start, "end_value": end}
                )

            except ParserError:
                # Year has only 52 weeks
                pass

    input_data = {
        "creation_options": {
            "source_type": "table",
            "source_uri": [f"s3://{BUCKET}/{TSV_NAME}"],
            "source_driver": "text",
            "delimiter": "\t",
            "has_header": True,
            "latitude": "latitude",
            "longitude": "longitude",
            "cluster": {"index_type": "gist", "column_name": "geom_wm"},
            "partitions": {
                "partition_type": "range",
                "partition_column": "alert__date",
                "partition_schema": partition_schema,
            },
            "indices": [
                {"index_type": "gist", "column_name": "geom"},
                {"index_type": "gist", "column_name": "geom_wm"},
                {"index_type": "btree", "column_name": "alert__date"},
            ],
            "table_schema": [
                {
                    "field_name": "rspo_oil_palm__certification_status",
                    "field_type": "text",
                },
                {"field_name": "per_forest_concession__type", "field_type": "text"},
                {"field_name": "idn_forest_area__type", "field_type": "text"},
                {"field_name": "alert__count", "field_type": "integer"},
                {"field_name": "adm1", "field_type": "integer"},
                {"field_name": "adm2", "field_type": "integer"},
            ],
        },
        "metadata": {},
    }

    #####################
    # Test asset creation
    #####################

    asset = await create_default_asset(
        dataset,
        version,
        version_payload=input_data,
        execute_batch_jobs=True,
        logs=logs,
        async_client=async_client,
    )
    asset_id = asset["asset_id"]

    await _check_version_status(dataset, version)
    await _check_asset_status(dataset, version, 1)
    await _check_task_status(asset_id, 14, "cluster_partitions_3")

    # There should be a table called "table_test"."v202002.1" with 99 rows.
    # It should have the right amount of partitions and indices
    async with ContextEngine("READ"):
        count = await db.scalar(
            db.text(
                f"""
                    SELECT count(*)
                        FROM "{dataset}"."{version}";"""
            )
        )
        partition_count = await db.scalar(
            db.text(
                f"""
                    SELECT count(i.inhrelid::regclass)
                        FROM pg_inherits i
                        WHERE  i.inhparent = '"{dataset}"."{version}"'::regclass;"""
            )
        )
        index_count = await db.scalar(
            db.text(
                f"""
                    SELECT count(indexname)
                        FROM pg_indexes
                        WHERE schemaname = '{dataset}' AND tablename like '{version}%';"""
            )
        )
        cluster_count = await db.scalar(
            db.text(
                """
                    SELECT count(relname)
                        FROM   pg_class c
                        JOIN   pg_index i ON i.indrelid = c.oid
                        WHERE  relkind = 'r' AND relhasindex AND i.indisclustered"""
            )
        )

    assert count == 99
    assert partition_count == len(partition_schema)
    assert index_count == partition_count * len(
        input_data["creation_options"]["indices"]
    )
    assert cluster_count == len(partition_schema)


@pytest.mark.asyncio
async def test_table_source_asset_parallel(batch_client, async_client):
    _, logs = batch_client

    ############################
    # Setup test
    ############################
    #
    # s3_client = get_s3_client()
    #
    # s3_client.create_bucket(Bucket=BUCKET)
    # s3_client.upload_file(TSV_PATH, BUCKET, TSV_NAME)

    dataset = "table_test"
    version = "v202002.1"

    # define partition schema
    partition_schema = list()
    years = range(2018, 2021)
    for year in years:
        for week in range(1, 54):
            try:
                name = f"y{year}_w{week:02}"
                start = pendulum.parse(f"{year}-W{week:02}").to_date_string()
                end = pendulum.parse(f"{year}-W{week:02}").add(days=7).to_date_string()
                partition_schema.append(
                    {"partition_suffix": name, "start_value": start, "end_value": end}
                )

            except ParserError:
                # Year has only 52 weeks
                pass

    input_data = {
        "creation_options": {
            "source_type": "table",
            "source_uri": [f"s3://{BUCKET}/{TSV_NAME}"]
            + [f"s3://{BUCKET}/test_{i}.tsv" for i in range(2, 101)],
            "source_driver": "text",
            "delimiter": "\t",
            "has_header": True,
            "latitude": "latitude",
            "longitude": "longitude",
            "cluster": {"index_type": "gist", "column_name": "geom_wm"},
            "partitions": {
                "partition_type": "range",
                "partition_column": "alert__date",
                "partition_schema": partition_schema,
            },
            "indices": [
                {"index_type": "gist", "column_name": "geom"},
                {"index_type": "gist", "column_name": "geom_wm"},
                {"index_type": "btree", "column_name": "alert__date"},
            ],
            "table_schema": [
                {
                    "field_name": "rspo_oil_palm__certification_status",
                    "field_type": "text",
                },
                {"field_name": "per_forest_concession__type", "field_type": "text"},
                {"field_name": "idn_forest_area__type", "field_type": "text"},
                {"field_name": "alert__count", "field_type": "integer"},
                {"field_name": "adm1", "field_type": "integer"},
                {"field_name": "adm2", "field_type": "integer"},
            ],
        },
        "metadata": {},
    }

    #####################
    # Test asset creation
    #####################

    asset = await create_default_asset(
        dataset,
        version,
        version_payload=input_data,
        execute_batch_jobs=True,
        logs=logs,
        async_client=async_client,
    )
    asset_id = asset["asset_id"]

    await _check_version_status(dataset, version)
    await _check_asset_status(dataset, version, 1)
    await _check_task_status(asset_id, 26, "cluster_partitions_3")

    # There should be a table called "table_test"."v202002.1" with 99 rows.
    # It should have the right amount of partitions and indices
    async with ContextEngine("READ"):
        count = await db.scalar(
            db.text(
                f"""
                    SELECT count(*)
                        FROM "{dataset}"."{version}";"""
            )
        )
        partition_count = await db.scalar(
            db.text(
                f"""
                    SELECT count(i.inhrelid::regclass)
                        FROM pg_inherits i
                        WHERE  i.inhparent = '"{dataset}"."{version}"'::regclass;"""
            )
        )
        index_count = await db.scalar(
            db.text(
                f"""
                    SELECT count(indexname)
                        FROM pg_indexes
                        WHERE schemaname = '{dataset}' AND tablename like '{version}%';"""
            )
        )
        cluster_count = await db.scalar(
            db.text(
                """
                    SELECT count(relname)
                        FROM   pg_class c
                        JOIN   pg_index i ON i.indrelid = c.oid
                        WHERE  relkind = 'r' AND relhasindex AND i.indisclustered"""
            )
        )

    assert count == 99
    assert partition_count == len(partition_schema)
    assert index_count == partition_count * len(
        input_data["creation_options"]["indices"]
    )
    assert cluster_count == len(partition_schema)


def _assert_fields(field_list, field_schema):
    count = 0
    for field in field_list:
        for schema in field_schema:
            if (
                field["field_name_"] == schema["field_name"]
                and field["field_type"] == schema["field_type"]
            ):
                count += 1
        if field["field_name_"] in ["geom", "geom_wm", "gfw_geojson", "gfw_bbox"]:
            assert not field["is_filter"]
            assert not field["is_feature_info"]
        else:
            assert field["is_filter"]
            assert field["is_feature_info"]
    assert count == len(field_schema)


async def _check_version_status(dataset, version):
    row = await versions.get_version(dataset, version)

    # in this test we don't set the final version status to saved or failed
    assert row.status == "saved"

    # in this test we only see the logs from background task, not from batch jobs
    print(f"TABLE SOURCE VERSION LOGS: {row.change_log}")
    assert len(row.change_log) == 3
    assert row.change_log[0]["message"] == "Successfully scheduled batch jobs"


async def _check_asset_status(dataset, version, nb_assets):
    rows = await assets.get_assets(dataset, version)
    assert len(rows) == 2

    # in this test we don't set the final asset status to saved or failed
    assert rows[0].status == "saved"
    assert rows[0].is_default is True

    # in this test we only see the logs from background task, not from batch jobs
    print(f"TABLE SOURCE ASSET LOGS: {rows[0].change_log}")
    assert len(rows[0].change_log) == nb_assets * 2


async def _check_task_status(asset_id, nb_jobs, last_job_name):
    rows = await tasks.get_tasks(asset_id)
    assert len(rows) == nb_jobs

    for row in rows:
        # in this test we don't set the final asset status to saved or failed
        assert row.status == "pending"
    # in this test we only see the logs from background task, not from batch jobs
    assert rows[-1].change_log[0]["message"] == (f"Scheduled job {last_job_name}")


async def _check_dynamic_vector_tile_cache_status(dataset, version):
    rows = await assets.get_assets(dataset, version)
    asset_row = rows[0]

    # SHP files have one additional attribute (fid)
    if asset_row.version == "v1.1.0":
        assert len(asset_row.fields) == 10
    else:
        assert len(asset_row.fields) == 9

    rows = await assets.get_assets(dataset, version)
    v = await versions.get_version(dataset, version)
    print(v.change_log)

    assert len(rows) == 2
    assert rows[0].asset_type == AssetType.geo_database_table
    assert rows[1].asset_type == AssetType.dynamic_vector_tile_cache
    assert rows[1].status == AssetStatus.saved
