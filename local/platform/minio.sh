#!/bin/sh
set -eu
export MC_CONFIG_DIR=/tmp/mc
mc alias set local http://minio:9000 "$(cat /secrets/root_access_key)" "$(cat /secrets/root_secret_key)" >/dev/null
mc mb --ignore-existing local/maintai-raw >/dev/null
mc version enable local/maintai-raw >/dev/null
mc mb --ignore-existing local/maintai-processed >/dev/null
mc version enable local/maintai-processed >/dev/null
mc mb --ignore-existing local/maintai-models >/dev/null
mc version enable local/maintai-models >/dev/null
mc mb --ignore-existing local/maintai-approved >/dev/null
mc version enable local/maintai-approved >/dev/null
mc mb --ignore-existing local/maintai-manuals >/dev/null
mc version enable local/maintai-manuals >/dev/null
mc mb --ignore-existing local/maintai-drift >/dev/null
mc version enable local/maintai-drift >/dev/null
mc mb --ignore-existing local/maintai-mlflow >/dev/null
mc version enable local/maintai-mlflow >/dev/null
mc admin user add local maintai-storage "$(cat /secrets/storage_password)" >/dev/null
mc admin policy create local maintai-storage /policies/storage.json >/dev/null
mc admin policy attach local maintai-storage --user maintai-storage >/dev/null
mc admin user add local maintai-processing "$(cat /secrets/processing_password)" >/dev/null
mc admin policy create local maintai-processing /policies/processing.json >/dev/null
mc admin policy attach local maintai-processing --user maintai-processing >/dev/null
mc admin user add local maintai-inference "$(cat /secrets/inference_password)" >/dev/null
mc admin policy create local maintai-inference /policies/inference.json >/dev/null
mc admin policy attach local maintai-inference --user maintai-inference >/dev/null
mc admin user add local maintai-training "$(cat /secrets/training_password)" >/dev/null
mc admin policy create local maintai-training /policies/training.json >/dev/null
mc admin policy attach local maintai-training --user maintai-training >/dev/null
mc admin user add local maintai-rag "$(cat /secrets/rag_password)" >/dev/null
mc admin policy create local maintai-rag /policies/rag.json >/dev/null
mc admin policy attach local maintai-rag --user maintai-rag >/dev/null
mc admin user add local maintai-drift "$(cat /secrets/drift_password)" >/dev/null
mc admin policy create local maintai-drift /policies/drift.json >/dev/null
mc admin policy attach local maintai-drift --user maintai-drift >/dev/null
mc admin user add local maintai-mlflow "$(cat /secrets/mlflow_password)" >/dev/null
mc admin policy create local maintai-mlflow /policies/mlflow.json >/dev/null
mc admin policy attach local maintai-mlflow --user maintai-mlflow >/dev/null
mc admin user add local maintai-processing-reader "$(cat /secrets/processing-reader_password)" >/dev/null
mc admin policy create local maintai-processing-reader /policies/processing-reader.json >/dev/null
mc admin policy attach local maintai-processing-reader --user maintai-processing-reader >/dev/null
echo 'Seven versioned buckets and scoped local users initialized; no lifecycle deletion configured.'
