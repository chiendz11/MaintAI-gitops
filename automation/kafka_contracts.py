"""Check the checked-in application Kafka contract pin, without a sibling checkout."""

from __future__ import annotations

import hashlib
import json

import yaml

from .common import ROOT, read_json


def encoded(document):
    return (json.dumps(document, indent=2) + "\n").encode()


def verify_kafka_contracts():
    pin = read_json("config/kafka-contracts.json")
    manifest, topology = pin["manifest"], pin["topology"]
    if hashlib.sha256(encoded(manifest)).hexdigest() != pin["manifest_sha256"]:
        raise ValueError("Kafka contract manifest pin checksum differs")
    if hashlib.sha256(encoded(topology)).hexdigest() != manifest["sha256"]["kafka/topology.json"]:
        raise ValueError("Kafka topology differs from the pinned application bundle")
    protocols = read_json("config/protocols.json")
    if protocols["kafka_contract_manifest_sha256"] != pin["manifest_sha256"]:
        raise ValueError("Protocol metadata differs from the Kafka bundle pin")
    if protocols["kafka_contract_bundle_version"] != manifest["bundle_version"]:
        raise ValueError("Protocol metadata differs from the Kafka bundle version")
    metadata = {
        "sensor_event_contract": "sensor.readings",
        "sensor_rejected_schema_version": "sensor.rejected",
        "inference_results_schema_version": "inference.results",
        "alert_signals_schema_version": "alert.signals",
    }
    for field, topic in metadata.items():
        if protocols[field] != topology["topics"][topic]["writer_version"]:
            raise ValueError("Protocol writer differs from the pinned Kafka topology")
    if set(protocols["inference_results_reader_versions"]) != set(
        topology["topics"]["inference.results"]["reader_schemas"]
    ):
        raise ValueError("Protocol reader versions differ from the pinned Kafka topology")
    for topic, specification in topology["topics"].items():
        filename = "topic-" + topic.replace(".", "-") + ".yaml"
        document = yaml.safe_load((ROOT / "platform/kafka" / filename).read_text())
        spec = document["spec"]
        expected = {
            "min.insync.replicas": specification["min_insync_replicas"],
            "retention.ms": specification["retention_ms"],
            "max.message.bytes": specification["max_message_bytes"],
        }
        if spec["partitions"] != specification["partitions"] or spec["replicas"] != specification["replicas"]:
            raise ValueError("KafkaTopic partition/replication differs from the contract pin")
        if spec["topicName"] != topic:
            raise ValueError("KafkaTopic name differs from the contract pin")
        for name, value in expected.items():
            if int(spec["config"][name]) != value:
                raise ValueError("KafkaTopic config differs from the contract pin")
