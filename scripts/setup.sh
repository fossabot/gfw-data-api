#!/bin/bash

set -e

detect-secrets scan > .secrets.baseline
pre-commit install
