"""Closed config3 contracts are opt-in; published config2 bytes stay immutable."""

import hashlib
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


class ProcessingOrderingContracts(unittest.TestCase):
    def test_frozen_config2_and_integration_copies(self):
        expected = {
            "processing-worker": "14da7ccebf6b783f6c74ebaafa73dc2dfde33ff7406efc454afe85a718b7a981",
            "processing-outbox-relay": "e7e695872f989a4d41366d106754ef1bf674445773fbe9901f465a93bc1808e9",
        }
        for runtime, digest in expected.items():
            path = ROOT / f"contracts/runtime-config/{runtime}-2.0.0.schema.json"
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
            new = ROOT / f"contracts/runtime-config/{runtime}-3.0.0.schema.json"
            mirror = ROOT / "integrations/MaintAI/release/contracts" / new.name
            self.assertEqual(new.read_bytes(), mirror.read_bytes())

    def test_worker_contract_requires_real_callback_bindings_and_rejects_extra_keys(self):
        schema = json.loads((ROOT / "contracts/runtime-config/processing-worker-3.0.0.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        state = json.loads((ROOT / "state/production/workloads.json").read_text())
        config = dict(state["components"]["processing-worker"]["runtime_config"])
        config.update({
            "PROCESSING_EXECUTION_MODE": "keyed",
            "PROCESSING_HANDLER_FACTORY": "maintai_processing.handlers:make_handler",
            "PROCESSING_PREPARE_CALLBACK": "fixture:prepare",
            "PROCESSING_PERSIST_CALLBACK": "fixture:persist",
            "PROCESSING_MAX_ACTIVE_KEYS": "8",
            "PROCESSING_MAX_PENDING_RECORDS": "512",
            "PROCESSING_MAX_PENDING_BYTES": "16777216",
            "PROCESSING_MAX_PENDING_PER_KEY": "64",
            "PROCESSING_MAX_UNCOMMITTED_PER_PARTITION": "128",
            "PROCESSING_RESUME_LOW_WATERMARK": "0.5",
            "PROCESSING_HANDLER_TIMEOUT_SECONDS": "15",
            "PROCESSING_DRAIN_TIMEOUT_SECONDS": "30",
        })
        validator = Draft202012Validator(schema)
        self.assertTrue(validator.is_valid(config))
        del config["PROCESSING_PREPARE_CALLBACK"]
        self.assertFalse(validator.is_valid(config))
        config["PROCESSING_PREPARE_CALLBACK"] = "fixture:prepare"
        config["UNREVIEWED_KEY"] = "value"
        self.assertFalse(validator.is_valid(config))

    def test_draft_profile_does_not_silently_upgrade_active_config(self):
        profile = json.loads((ROOT / "config/processing-ordering.json").read_text())
        state = json.loads((ROOT / "state/production/workloads.json").read_text())
        self.assertEqual(profile["activation_status"], "NOT_ACTIVATED")
        for runtime, reference in profile["schemas"].items():
            self.assertEqual(state["components"][runtime]["runtime_config_version"], "2.0.0")
            raw = (ROOT / reference["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(raw).hexdigest(), reference["sha256"])
            Draft202012Validator.check_schema(json.loads(raw))


if __name__ == "__main__":
    unittest.main()
