from enum import Enum

from app.models.enum.sources import SourceType


class AssetStatus(str, Enum):
    saved = "saved"
    pending = "pending"
    failed = "failed"


class AssetType(str, Enum):
    dynamic_vector_tile_cache = "Dynamic vector tile cache"
    static_vector_tile_cache = "Static vector tile cache"
    static_raster_tile_cache = "Static raster tile cache"
    raster_tile_set = "Raster tile set"
    database_table = "Database table"
    shapefile = "Shapefile"
    geopackage = "Geopackage"
    ndjson = "ndjson"
    csv = "csv"
    tsv = "tsv"
    # esri_map_service = "ESRI Map Service"
    # esri_feature_service = "ESRI Feature Service"
    # esri_image_service = "ESRI Image Service"
    # esri_vector_service = "ESRI Vector Service"
    # arcgis_online_item = "ArcGIS Online item"
    # carto_item = "Carto item"
    # mapbox_item = "Mapbox item"


def default_asset_type(source_type: str) -> str:
    if source_type == SourceType.table or source_type == SourceType.vector:
        asset_type = AssetType.database_table
    elif source_type == SourceType.raster:
        asset_type = AssetType.raster_tile_set
    else:
        raise NotImplementedError("Not a supported input source")
    return asset_type
