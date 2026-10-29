#!/bin/bash
set -euo pipefail
/opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists --topic sensor.readings --partitions 12 --replication-factor 1 --config min.insync.replicas=1 --config retention.ms=604800000 --config max.message.bytes=1048576
actual=$(/opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --describe --topic sensor.readings)
[[ "$actual" == *"PartitionCount: 12"* ]] || { echo "Topic partition count mismatch; no automatic repartition" >&2; exit 1; }
/opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists --topic sensor.rejected --partitions 12 --replication-factor 1 --config min.insync.replicas=1 --config retention.ms=604800000 --config max.message.bytes=1048576
actual=$(/opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --describe --topic sensor.rejected)
[[ "$actual" == *"PartitionCount: 12"* ]] || { echo "Topic partition count mismatch; no automatic repartition" >&2; exit 1; }
/opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists --topic inference.results --partitions 12 --replication-factor 1 --config min.insync.replicas=1 --config retention.ms=604800000 --config max.message.bytes=1048576
actual=$(/opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --describe --topic inference.results)
[[ "$actual" == *"PartitionCount: 12"* ]] || { echo "Topic partition count mismatch; no automatic repartition" >&2; exit 1; }
/opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --create --if-not-exists --topic alert.signals --partitions 12 --replication-factor 1 --config min.insync.replicas=1 --config retention.ms=604800000 --config max.message.bytes=1048576
actual=$(/opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --describe --topic alert.signals)
[[ "$actual" == *"PartitionCount: 12"* ]] || { echo "Topic partition count mismatch; no automatic repartition" >&2; exit 1; }
