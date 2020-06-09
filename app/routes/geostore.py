from uuid import UUID

from fastapi import APIRouter, Depends, Path
from fastapi.responses import ORJSONResponse

from app.routes import dataset_dependency, version_dependency

router = APIRouter()
description = """Retrieve a geometry using its mb5 hash for a given dataset,
                  user defined geometries in the datastore"""


@router.post(
    "/geostore", response_class=ORJSONResponse, tags=["Geostore"],
)
async def add_new_geostore():
    """Add geostore feature to User geostore."""
    pass


@router.get(
    "/geostore/{geostore_id}", response_class=ORJSONResponse, tags=["Geostore"],
)
async def get_geostore_root(*, geostore_id: UUID = Path(..., title="geostore_id")):
    """
    Retrieve GeoJSON representation for a given geostore ID of any dataset
    """
    pass


@router.get(
    "/{dataset}/{version}/geostore/{geostore_id}",
    response_class=ORJSONResponse,
    tags=["Geostore"],
)
async def get_geostore(
    *,
    dataset: str = Depends(dataset_dependency),
    version: str = Depends(version_dependency),
    geostore_id: UUID = Path(..., title="geostore_id")
):
    """

    Retrieve GeoJSON representation for a given geostore ID of a dataset version.
    Obtain geostore ID from feature attributes.

    """
    pass
