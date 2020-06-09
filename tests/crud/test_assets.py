import json
from datetime import datetime
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi import HTTPException

from app.application import ContextEngine
from app.crud.assets import (
    create_asset,
    delete_asset,
    get_all_assets,
    get_asset,
    get_assets,
    get_assets_by_type,
    update_asset,
)
from app.crud.datasets import create_dataset
from app.crud.versions import create_version
from app.models.pydantic.change_log import ChangeLog
from app.models.pydantic.metadata import DatabaseTableMetadata


@pytest.mark.asyncio
async def test_assets():
    """
    Testing all CRUD operations on dataset in one go
    """

    dataset_name = "test"
    version_name = "v1.1.1"

    # Add a dataset
    async with ContextEngine("PUT"):
        new_dataset = await create_dataset(dataset_name)
        new_version = await create_version(
            dataset_name, version_name, source_type="table"
        )
    assert new_dataset.dataset == dataset_name
    assert new_version.dataset == dataset_name
    assert new_version.version == version_name

    # There should be no assert for current version
    # This will throw an error b/c when initialized correctly,
    # there will be always a default asset
    result = ""
    status_code = 200
    try:
        await get_assets(dataset_name, version_name)
    except HTTPException as e:
        result = e.detail
        status_code = e.status_code

    assert result == f"Version with name {dataset_name}.{version_name} does not exist"
    assert status_code == 404

    # Writing to DB using context engine with "READ" shouldn't work
    async with ContextEngine("READ"):
        result = ""
        try:
            await create_asset(
                dataset_name,
                version_name,
                asset_type="Database table",
                asset_uri="s3://path/to/file",
            )
        except asyncpg.exceptions.InsufficientPrivilegeError as e:
            result = str(e)

        assert result == "permission denied for table assets"

    # Using context engine with "PUT" should work
    async with ContextEngine("PUT"):
        new_row = await create_asset(
            dataset_name,
            version_name,
            asset_type="Database table",
            asset_uri="s3://path/to/file",
        )
    assert isinstance(new_row.asset_id, UUID)
    assert new_row.dataset == dataset_name
    assert new_row.version == version_name
    assert new_row.asset_type == "Database table"
    assert new_row.asset_uri == "s3://path/to/file"
    assert new_row.status == "pending"
    assert new_row.is_managed is True
    assert new_row.creation_options == {}
    assert new_row.metadata == {}
    assert new_row.change_log == []

    # This shouldn't work a second time
    async with ContextEngine("PUT"):
        result = ""
        status_code = 200
        try:
            await create_asset(
                dataset_name,
                version_name,
                asset_type="Database table",
                asset_uri="s3://path/to/file",
            )
        except HTTPException as e:
            result = e.detail
            status_code = e.status_code

        assert result == (
            "A similar Asset already exist."
            "Dataset versions can only have one instance of asset type."
            "Asset uri must be unique."
        )
        assert status_code == 400

    # There should be an entry now
    rows = await get_assets(dataset_name, version_name)
    assert isinstance(rows, list)
    assert len(rows) == 1
    assert rows[0].dataset == dataset_name
    assert rows[0].version == version_name
    assert isinstance(rows[0].asset_id, UUID)
    asset_id = rows[0].asset_id

    # There should be an entry now
    rows = await get_all_assets()
    assert isinstance(rows, list)
    assert len(rows) == 1
    assert rows[0].dataset == dataset_name
    assert rows[0].version == version_name

    # There should be an entry now
    rows = await get_assets_by_type("Database table")
    assert isinstance(rows, list)
    assert len(rows) == 1
    assert rows[0].dataset == dataset_name
    assert rows[0].version == version_name

    # There should be no such entry
    rows = await get_assets_by_type("Vector tile cache")
    assert isinstance(rows, list)
    assert len(rows) == 0

    # It should be possible to access the asset by asset id
    row = await get_asset(asset_id)
    assert row.dataset == dataset_name
    assert row.version == version_name

    # But only if the asset exists
    result = ""
    status_code = 200
    _asset_id = uuid4()
    try:
        await get_asset(_asset_id)
    except HTTPException as e:
        result = e.detail
        status_code = e.status_code

    assert result == f"Could not find requested asset {_asset_id}"
    assert status_code == 404

    # It should be possible to update a dataset using a context engine
    metadata = DatabaseTableMetadata(title="Test Title", tags=["tag1", "tag2"])
    logs = ChangeLog(date_time=datetime.now(), status="saved", message="all good")
    async with ContextEngine("PUT"):
        row = await update_asset(
            asset_id, metadata=metadata.dict(), change_log=[logs.dict()]
        )
    assert row.metadata["title"] == "Test Title"
    assert row.metadata["tags"] == ["tag1", "tag2"]
    assert row.change_log[0]["date_time"] == json.loads(logs.json())["date_time"]
    assert row.change_log[0]["status"] == logs.dict()["status"]
    assert row.change_log[0]["message"] == logs.dict()["message"]

    # When deleting a dataset, method should return the deleted object
    async with ContextEngine("DELETE"):
        row = await delete_asset(asset_id)
    assert row.dataset == dataset_name
    assert row.version == version_name

    # After deleting the dataset, there should be an empty DB
    rows = await get_all_assets()
    assert isinstance(rows, list)
    assert len(rows) == 0