#!/bin/bash

set -e

docker build -t batch_dev ./batch
docker-compose -f docker-compose.dev.yml up
