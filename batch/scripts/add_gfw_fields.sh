#!/bin/bash

set -e

# requires arguments
# -d | --dataset
# -v | --version
ME=$(basename "$0")
. get_arguments.sh "$@"

# Add GFW specific layers
echo "PSQL: ALTER TABLE \"$DATASET\".\"$VERSION\". Add GFW columns"
psql -c "ALTER TABLE \"$DATASET\".\"$VERSION\" ADD COLUMN ${GEOMETRY_NAME}_wm geometry(MultiPolygon,3857);
         ALTER TABLE \"$DATASET\".\"$VERSION\" ALTER COLUMN ${GEOMETRY_NAME}_wm SET STORAGE EXTERNAL;
         ALTER TABLE \"$DATASET\".\"$VERSION\" ADD COLUMN gfw_area__ha NUMERIC;
         ALTER TABLE \"$DATASET\".\"$VERSION\" ADD COLUMN gfw_geostore_id UUID;
         ALTER TABLE \"$DATASET\".\"$VERSION\" ADD COLUMN gfw_geojson character varying COLLATE pg_catalog.\"default\";
         ALTER TABLE \"$DATASET\".\"$VERSION\" ADD COLUMN gfw_bbox geometry(Polygon,4326);
         ALTER TABLE \"$DATASET\".\"$VERSION\" ADD COLUMN created_on timestamp without time zone DEFAULT now();
         ALTER TABLE \"$DATASET\".\"$VERSION\" ADD COLUMN updated_on timestamp without time zone DEFAULT now();"

# Update GFW columns
echo "PSQL: UPDATE \"$DATASET\".\"$VERSION\". Set GFW attributes"
psql -c "UPDATE \"$DATASET\".\"$VERSION\" SET ${GEOMETRY_NAME}_wm = ST_Transform($GEOMETRY_NAME, 3857),
                                      gfw_area__ha = ST_Area($GEOMETRY_NAME::geography)/10000,
                                      gfw_geostore_id = md5(ST_asgeojson($GEOMETRY_NAME))::uuid,
                                      gfw_geojson = ST_asGeojson($GEOMETRY_NAME),
                                      gfw_bbox = ST_Envelope($GEOMETRY_NAME);"

# Set gfw_geostore_id not NULL to be compliant with GEOSTORE
echo "PSQL: ALTER TABLE \"$DATASET\".\"$VERSION\". SET gfw_geostore_id SET NOT NULL"
psql -c "ALTER TABLE \"$DATASET\".\"$VERSION\" ALTER COLUMN gfw_geostore_id SET NOT NULL;"