#!/bin/bash

set -e

docker build -t batch_test ./batch
docker-compose -f docker-compose.test.yml run --rm app