from typing import Any, Dict, List
from uuid import UUID

from asyncpg import UniqueViolationError
from fastapi.encoders import jsonable_encoder

from ..errors import RecordAlreadyExistsError, RecordNotFoundError
from ..models.enum.sources import SourceType
from ..models.orm.assets import Asset as ORMAsset
from ..models.orm.datasets import Dataset as ORMDataset
from ..models.orm.versions import Version as ORMVersion
from ..models.pydantic.creation_options import (
    CreationOptions,
    TableDrivers,
    VectorDrivers,
    asset_creation_option_factory,
)
from . import datasets, update_all_metadata, update_data, update_metadata, versions


async def get_assets(dataset: str, version: str) -> List[ORMAsset]:
    rows: List[ORMAsset] = await ORMAsset.query.where(
        ORMAsset.dataset == dataset
    ).where(ORMAsset.version == version).order_by(ORMAsset.created_on).gino.all()
    if not rows:
        raise RecordNotFoundError(
            f"No assets for version with name {dataset}.{version} found"
        )

    d: ORMDataset = await datasets.get_dataset(dataset)
    v: ORMVersion = await versions.get_version(dataset, version)

    v = update_metadata(v, d)

    return update_all_metadata(rows, v)


async def get_all_assets() -> List[ORMAsset]:
    assets = await ORMAsset.query.gino.all()

    return await _update_all_asset_metadata(assets)


async def get_assets_by_type(asset_type: str) -> List[ORMAsset]:
    assets = await ORMAsset.query.where(ORMAsset.asset_type == asset_type).gino.all()
    return await _update_all_asset_metadata(assets)


async def get_asset(asset_id: UUID) -> ORMAsset:

    row: ORMAsset = await ORMAsset.get([asset_id])
    if row is None:
        raise RecordNotFoundError(f"Could not find requested asset {asset_id}")

    dataset: ORMDataset = await datasets.get_dataset(row.dataset)
    version: ORMVersion = await versions.get_version(row.dataset, row.version)
    version = update_metadata(version, dataset)

    return update_metadata(row, version)


async def create_asset(dataset, version, **data) -> ORMAsset:

    data = _validate_creation_options(**data)
    jsonable_data = jsonable_encoder(data)
    try:
        new_asset: ORMAsset = await ORMAsset.create(
            dataset=dataset, version=version, **jsonable_data
        )
    except UniqueViolationError:
        raise RecordAlreadyExistsError(
            f"Cannot create asset of type {data['asset_type']}. "
            f"Asset uri must be unique. An asset with uri {data['asset_uri']} already exists"
        )

    d: ORMDataset = await datasets.get_dataset(dataset)
    v: ORMVersion = await versions.get_version(dataset, version)
    v = update_metadata(v, d)

    return update_metadata(new_asset, v)


async def update_asset(asset_id: UUID, **data) -> ORMAsset:

    data = _validate_creation_options(**data)
    jsonable_data = jsonable_encoder(data)

    row: ORMAsset = await get_asset(asset_id)
    row = await update_data(row, jsonable_data)

    dataset: ORMDataset = await datasets.get_dataset(row.dataset)
    version: ORMVersion = await versions.get_version(row.dataset, row.version)
    version = update_metadata(version, dataset)

    return update_metadata(row, version)


async def delete_asset(asset_id: UUID) -> ORMAsset:
    row: ORMAsset = await get_asset(asset_id)
    await ORMAsset.delete.where(ORMAsset.asset_id == asset_id).gino.status()

    dataset: ORMDataset = await datasets.get_dataset(row.dataset)
    version: ORMVersion = await versions.get_version(row.dataset, row.version)
    version = update_metadata(version, dataset)

    return update_metadata(row, version)


async def _update_all_asset_metadata(assets):
    new_rows = list()
    for row in assets:
        dataset: ORMDataset = await datasets.get_dataset(row.dataset)
        version: ORMVersion = await versions.get_version(row.dataset, row.version)
        version = update_metadata(version, dataset)
        update_metadata(row, version)
        new_rows.append(row)

    return new_rows


def _validate_creation_options(**data) -> Dict[str, Any]:
    """Validate if submitted creation options match asset type."""

    if "creation_options" in data.keys() and "asset_type" in data.keys():
        asset_type = data["asset_type"]
        creation_options = data["creation_options"]

        co_model: CreationOptions = _creation_option_factory(
            asset_type, creation_options
        )

        data["creation_options"] = co_model.dict(by_alias=True)

    return data


def _creation_option_factory(asset_type, creation_options) -> CreationOptions:
    """Create creation options pydantic model based on asset type."""

    driver = creation_options.get("src_driver", None)
    table_drivers: List[str] = [t.value for t in TableDrivers]
    vector_drivers: List[str] = [v.value for v in VectorDrivers]

    source_type = None
    if driver in table_drivers:
        source_type = SourceType.table
    elif driver in vector_drivers:
        source_type = SourceType.vector

    return asset_creation_option_factory(source_type, asset_type, creation_options)
