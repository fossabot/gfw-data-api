#!/bin/bash

set -e

echo "$@"

# Default values
POSITIONAL=()
GEOMETRY_NAME="geom"
FID_NAME="gfw_fid"

# extracting cmd line arguments
while [[ $# -gt 0 ]]
do
  key="$1"

  case $key in
      -d|--dataset)
      DATASET="$2"
      shift # past argument
      shift # past value
      ;;
      -v|--version)
      VERSION="$2"
      shift # past argument
      shift # past value
      ;;
      -s|--source)
      SRC="$2"
      shift # past argument
      shift # past value
      ;;
      -l|--source_layer)
      SRC_LAYER="$2"
      shift # past argument
      shift # past value
      ;;
      -f|--file)
      LOCAL_FILE="$2"
      shift # past argument
      shift # past value
      ;;
      -g|--geometry_name)
      GEOMETRY_NAME="$2"
      shift # past argument
      shift # past value
      ;;
      -i|--fid_name)
      FID_NAME="$2"
      shift # past argument
      shift # past value
      ;;
      -x|--index_type)
      INDEX_TYPE="$2"
      shift # past argument
      shift # past value
      ;;
      -c|--column_name)
      COLUMN_NAME="$2"
      shift # past argument
      shift # past value
      ;;
      -Z|--min_zoom)
      MIN_ZOOM="$2"
      shift # past argument
      shift # past value
      ;;
      -z|--max_zoom)
      MAX_ZOOM="$2"
      shift # past argument
      shift # past value
      ;;
      -t|--tile_strategy)
      TILE_STRATEGY="$2"
      shift # past argument
      shift # past value
      ;;
      *)    # unknown option
      POSITIONAL+=("$1") # save it in an array for later
      shift # past argument
      ;;
  esac
done
set -- "${POSITIONAL[@]}" # restore positional parameters

#
## Extract aurora secrets
#PGPASSWORD=$(jq '.password' <<< "$DB_WRITER_SECRET")
#PGHOST=$(jq '.host' <<< "$DB_WRITER_SECRET")
#PGPORT=$(jq '.port' <<< "$DB_WRITER_SECRET")
#PGDATABASE=$(jq '.dbname' <<< "$DB_WRITER_SECRET")
#PGUSER=$(jq '.username' <<< "$DB_WRITER_SECRET")
