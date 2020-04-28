import logging
from typing import List, Dict, Any

from asyncpg.exceptions import UniqueViolationError
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import ORJSONResponse
from sqlalchemy.schema import CreateSchema, DropSchema


from . import dataset_dependency, update_data
from ..models.orm.dataset import Dataset as ORMDataset
from ..models.orm.version import Version as ORMVersion
from ..models.orm.queries.datasets import all_datasets
from ..models.pydantic.dataset import Dataset, DatasetCreateIn, DatasetUpdateIn
from ..application import db
from ..settings.globals import READER_USERNAME

router = APIRouter()


@router.get("/", response_class=ORJSONResponse, tags=["Dataset"], response_model=List[Dataset])
async def get_datasets():
    """
    Get list of all datasets
    """
    rows = await db.status(all_datasets)
    return rows[1]


@router.get("/{dataset}", response_class=ORJSONResponse, tags=["Dataset"], response_model=Dataset)
async def get_dataset(*, dataset: str = Depends(dataset_dependency)):
    """
    Get basic metadata and available versions for a given dataset
    """
    row: ORMDataset = await ORMDataset.get(dataset)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Dataset with name {dataset} does not exist")

    return await _dataset_response(dataset, row)


@router.put("/{dataset}", response_class=ORJSONResponse, tags=["Dataset"], response_model=Dataset)
async def create_dataset(*, dataset: str = Depends(dataset_dependency), request: DatasetCreateIn):
    """
    Create or update a dataset
    """
    try:
        new_dataset: ORMDataset = await ORMDataset.create(dataset=dataset, **request.dict())
    except UniqueViolationError:
        raise HTTPException(status_code=400, detail=f"Dataset with name {dataset} already exists")

    await db.status(CreateSchema(dataset))
    await db.status(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {dataset} GRANT SELECT ON TABLES TO {READER_USERNAME};")

    return await _dataset_response(dataset, new_dataset)


@router.patch("/{dataset}", response_class=ORJSONResponse, tags=["Dataset"], response_model=Dataset)
async def update_dataset_metadata(*, dataset: str = Depends(dataset_dependency), request: DatasetUpdateIn):
    """
    Partially update a dataset. Only metadata field can be updated. All other fields will be ignored.
    """

    row: ORMDataset = await ORMDataset.get(dataset)

    if row is None:
        raise HTTPException(status_code=404, detail=f"Dataset with name {dataset} does not exists")

    row = await update_data(row, request)

    return await _dataset_response(dataset, row)


@router.delete("/{dataset}", response_class=ORJSONResponse, tags=["Dataset"], response_model=Dataset)
async def delete_dataset(*, dataset: str = Depends(dataset_dependency)):
    """
    Delete a dataset
    """

    row: ORMDataset = await ORMDataset.get(dataset)
    await ORMDataset.delete.where(ORMDataset.dataset == dataset).gino.status()
    await db.status(DropSchema(dataset))

    return await _dataset_response(dataset, row)


async def _dataset_response(dataset: str, data: ORMDataset) -> Dict[str, Any]:

    versions: List[ORMVersion] = await ORMVersion.select("version").where(ORMVersion.dataset == dataset).gino.all()
    response = Dataset.from_orm(data).dict(by_alias=True)
    response["versions"] = [version[0] for version in versions]

    return response
