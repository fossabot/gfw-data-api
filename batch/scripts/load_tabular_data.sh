#!/bin/bash

set -e

# requires arguments
# -d | --dataset
# -v | --version
# -s | --source
# -D | --delimiter
ME=$(basename "$0")
. get_arguments.sh "$@"


# Unescape TAB character
if [ "$DELIMITER" == "\t" ]; then
  DELIMITER=$(echo -e "\t")
fi

aws s3 cp "${SRC}" - | psql -c "COPY \"$DATASET\".\"$VERSION\" FROM STDIN WITH (FORMAT CSV, DELIMITER '$DELIMITER', HEADER)"

