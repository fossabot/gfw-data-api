from typing import List

from asyncpg import UniqueViolationError
from fastapi import HTTPException

from . import update_data
from ..application import db
from ..models.orm.queries.datasets import all_datasets
from ..models.orm.dataset import Dataset as ORMDataset
from ..models.pydantic.dataset import DatasetUpdateIn


async def get_datasets() -> List[ORMDataset]:
    """
    Get list of all datasets
    """
    rows = await db.status(all_datasets)
    return rows[1]


async def get_dataset(dataset: str) -> ORMDataset:
    row: ORMDataset = await ORMDataset.get(dataset)
    if row is None:
        raise HTTPException(
            status_code=404, detail=f"Dataset with name {dataset} does not exist"
        )

    return row


async def create_dataset(dataset: str, **data) -> ORMDataset:
    try:
        new_dataset: ORMDataset = await ORMDataset.create(dataset=dataset, **data)
    except UniqueViolationError:
        raise HTTPException(
            status_code=400, detail=f"Dataset with name {dataset} already exists"
        )
    return new_dataset


async def update_dataset(dataset: str, data: DatasetUpdateIn):
    row: ORMDataset = await get_dataset(dataset)

    return await update_data(row, data)


async def delete_dataset(dataset: str) -> ORMDataset:
    row: ORMDataset = await get_dataset(dataset)
    await ORMDataset.delete.where(ORMDataset.dataset == dataset).gino.status()

    return row
