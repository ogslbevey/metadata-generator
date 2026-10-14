#!/bin/bash
echo 'starting mlflow server...'

exec mlflow server \
    --backend-store-uri $DB_URL \
    --artifacts-destination s3://mlflow \
    --host :: \
    --port ${PORT:-5000}