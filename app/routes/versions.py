from typing import List, Dict, Any, Optional, Iterator, Tuple, Union
from typing.io import BinaryIO, IO

from asyncpg.exceptions import UniqueViolationError
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, BackgroundTasks
from fastapi.responses import ORJSONResponse

from app.routes import dataset_dependency, version_dependency, update_data

from ..models.orm.asset import Asset as ORMAsset
from ..models.orm.version import Version as ORMVersion
from ..models.pydantic.version import Version, VersionCreateIn, VersionUpdateIn
from ..settings.globals import BUCKET
from ..tasks.datalake import inject_file

router = APIRouter()


@router.get(
    "/{dataset}/{version}",
    response_class=ORJSONResponse,
    tags=["Version"],
    response_model=Version,
)
async def get_version(
    *,
    dataset: str = Depends(dataset_dependency),
    version: str = Depends(version_dependency),
):
    """
    Get basic metadata for a given version
    """
    row: ORMVersion = await ORMVersion.get([dataset, version])
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Version with name {dataset}/{version} does not exist",
        )

    return await _version_response(dataset, version, row)


@router.put(
    "/{dataset}/{version}",
    response_class=ORJSONResponse,
    tags=["Version"],
    response_model=Version,
)
async def add_new_version(
    *,
    dataset: str = Depends(dataset_dependency),
    version: str = Depends(version_dependency),
    request: VersionCreateIn,
    files: Optional[List[UploadFile]] = File(None),
    background_tasks: BackgroundTasks,
):
    """
    Create or update a version for a given dataset
    """

    input_data, file_uris = _prepare_sources(dataset, version, request, files)

    # Register version with DB
    try:
        new_version: ORMVersion = await ORMVersion.create(
            dataset=dataset, version=version, **input_data
        )
    except UniqueViolationError:
        raise HTTPException(
            status_code=400, detail=f"Dataset with name {dataset} already exists"
        )

    # Inject appended files, if any
    for file_obj, uri in file_uris:
        if file_obj is not None:
            background_tasks.add_task(inject_file, file_obj, uri)

    return await _version_response(dataset, version, new_version)


@router.patch(
    "/{dataset}/{version}",
    response_class=ORJSONResponse,
    tags=["Version"],
    response_model=Version,
)
async def update_version(
    *,
    dataset: str = Depends(dataset_dependency),
    version: str = Depends(version_dependency),
    request: Optional[VersionUpdateIn],
    files: Optional[List[UploadFile]] = File(None),
    background_tasks: BackgroundTasks,
):
    """
    Partially update a version of a given dataset.
    When using PATCH and uploading files,
    this will overwrite the existing source(s) and trigger a complete update of all managed assets
    """
    row: ORMVersion = await _get_version(dataset, version)

    input_data, file_uris = _prepare_sources(dataset, version, request, files)

    row = await update_data(row, input_data)

    # TODO: If files is not None, delete all files in RAW folder

    # Inject appended files, if any
    for file_obj, uri in file_uris:
        if file_obj is not None:
            background_tasks.add_task(inject_file, file_obj, uri)

    # TODO: If files is not None, delete and recreate all Assets based on new input files

    return await _version_response(dataset, version, row)


@router.delete(
    "/{dataset}/{version}",
    response_class=ORJSONResponse,
    tags=["Version"],
    response_model=Version,
)
async def delete_version(
    *,
    dataset: str = Depends(dataset_dependency),
    version: str = Depends(version_dependency),
):
    """
    Delete a version
    """
    row: ORMVersion = await _get_version(dataset, version)
    await ORMVersion.delete.where(ORMVersion.dataset == dataset).where(
        ORMVersion.version == version
    ).gino.status()

    # TODO:
    #  Delete all managed assets and raw data

    return await _version_response(dataset, version, row)


async def _get_version(dataset: str, version: str) -> ORMVersion:
    row: ORMVersion = await ORMVersion.get([dataset, version])
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Version with name {dataset}/{version} does not exists",
        )
    return row


async def _version_response(
    dataset: str, version: str, data: ORMVersion
) -> Dict[str, Any]:
    assets: List[ORMAsset] = await ORMAsset.select("asset_type", "asset_uri").where(
        ORMAsset.dataset == dataset
    ).where(ORMAsset.version == version).gino.all()
    response = Version.from_orm(data).dict(by_alias=True)
    response["assets"] = [(asset[0], asset[1]) for asset in assets]

    return response


def _prepare_sources(
    dataset: str,
    version: str,
    request: Union[VersionCreateIn, Optional[VersionUpdateIn]],
    files: Optional[List[UploadFile]],
) -> Tuple[Dict[str, Any], Iterator[Tuple[Optional[IO], str]]]:

    if request is None:
        input_data = {}
    else:
        # Check if either files or source_uri are set, but not both
        if not _true_xor(bool(files), bool(request.source_uri)):
            raise HTTPException(
                status_code=400,
                detail="Either source_uri must be set, or files need to be attached",
            )
        input_data: Dict[str, Any] = request.dict()


    file_uris: Iterator[Tuple[Optional[IO], str]] = zip()

    # If files were uploaded, override source_uri and prepare data lake injection
    if files is not None:
        uris = list()
        file_objs = list()
        input_data["source_uri"] = list()
        for f in files:
            uri = f"{dataset}/{version}/raw/{f.filename}"
            input_data["source_uri"].append(f"s3://{BUCKET}/{uri}")
            uris.append(uri)
            file_objs.append(f.file)
        file_uris = zip(file_objs, uris)

    # TODO: verify content itself
    #  This may be an asynchronous task. But in that case we would need to have a status field for version
    #  which updates once source files are validated.
    #  - Raster sources should be either geotiffs
    #  (alternatively readable by `gdalinfo` but need to verify if this works with rasterio),
    #  or a geojson which features describe remote geotiffs
    #  - Vector data should a source readable by `orginfo`

    return input_data, file_uris


def _true_xor(*args):
    return sum(args) == 1
