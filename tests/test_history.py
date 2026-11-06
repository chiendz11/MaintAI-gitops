import json
import unittest
from unittest.mock import patch

from localdev.workloads import resources


class HistoryWiring(unittest.TestCase):
    def config(self):
        return {"enabled": True, "issuer": "http://127.0.0.1:18091/maintai-history",
                "service_subject": "verified-service-subject", "signing_key_id": "fixture-key-v1",
                "adapter_image": "maintai-local/dev-tools:image-" + "a" * 64,
                "jwks": {"keys": [{"kty": "RSA", "n": "fixture", "e": "AQAB", "alg": "RS256", "use": "sig", "kid": "fixture-key-v1"}]}}

    def test_only_business_can_mount_the_private_signing_key(self):
        with patch("localdev.history.selection", return_value=self.config()):
            business, _ = resources("business-api", {}, 5, "b" * 40)
            processing, configs = resources("processing-read-api", {}, 5, "b" * 40)
        bpod = business[0]["spec"]["template"]["spec"]
        ppod = processing[0]["spec"]["template"]["spec"]
        bsecrets = {v.get("secret", {}).get("secretName") for v in bpod["volumes"]}
        psecrets = {v.get("secret", {}).get("secretName") for v in ppod["volumes"]}
        self.assertIn("local-business-history-keys", bsecrets)
        self.assertNotIn("local-business-history-keys", psecrets)
        self.assertIn("local-processing-history-keys", psecrets)
        settings = dict(x.split("=", 1) for x in configs[0]["literals"])
        self.assertEqual(settings["PROCESSING_RETENTION_ENABLED"], "false")
        self.assertEqual(settings["PROCESSING_CLEANER_DRY_RUN"], "true")
        bridge = json.loads(configs[1]["literals"][0].split("=", 1)[1])
        jwks = next(x for x in bridge["http"] if x["port"] == 18091)
        self.assertEqual(jwks["bind"], "127.0.0.1")
        self.assertNotIn("oauth", jwks)
        self.assertIn(18091, {x["port"] for x in business[1]["spec"]["ports"]})

    def test_no_new_workload_or_history_when_disabled(self):
        with patch("localdev.history.selection", return_value=None):
            docs, configs = resources("business-api", {}, 5, "b" * 40)
        self.assertEqual([x["kind"] for x in docs], ["Deployment", "Service"])
        settings = dict(x.split("=", 1) for x in configs[0]["literals"])
        self.assertNotIn("BUSINESS_HISTORY_ENABLED", settings)

    def test_raw_archive_uses_same_lineage_as_reader_and_preserves_catalog(self):
        config = {**self.config(), "raw_bucket": "maintai-raw-fixture", "archive_group_prefix": "local-fixture-", "archive_replicas": 3}
        with patch("localdev.history.selection", return_value=config):
            docs, configs = resources("storage-consumer", {}, 5, "b" * 40)
            _, reader = resources("processing-read-api", {}, 5, "b" * 40)
        storage = dict(x.split("=", 1) for x in configs[0]["literals"])
        processing = dict(x.split("=", 1) for x in reader[0]["literals"])
        self.assertEqual(docs[0]["spec"]["replicas"], 3)
        self.assertEqual(storage["KAFKA_GROUP_PREFIX"], "local-fixture-")
        self.assertEqual(storage["S3_RAW_BUCKET"], processing["PROCESSING_HISTORY_RAW_BUCKET"])
        self.assertEqual(storage["STORAGE_CATALOG_ENABLED"], "true")
        self.assertEqual(storage["STORAGE_CATALOG_POLL_SECONDS"], "0.5")
        self.assertEqual(storage["S3_ALLOW_UNVERSIONED"], "false")
        self.assertEqual(storage["STORAGE_ARCHIVE_OUTCOMES"], "false")
        self.assertEqual([x["kind"] for x in docs], ["Deployment", "Service"])
