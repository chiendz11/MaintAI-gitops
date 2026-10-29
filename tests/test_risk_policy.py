"""Offline source/ConfigMap tests; fixture policies and receipts are not releases."""

import copy
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from localdev import release, risk_policy
from localdev.common import ROOT, load


def fixture_receipt(name):
    return {
        "schema_version": "1.0.0",
        "component": name,
        "image": "maintai-local/" + name + ":image-" + "a" * 64,
        "image_id": "sha256:" + "a" * 64,
        "source_git_sha": "b" * 40,
        "source_dirty": False,
        "source_snapshot_sha256": "c" * 64,
        "dockerfile": "fixture/Dockerfile",
        "dockerfile_sha256": "d" * 64,
        "build_context": ".",
        "imported_context": "k3d-maintai-local",
    }


class RiskPolicyRelease(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.app = Path(temporary.name)
        self.directory = self.app / risk_policy.POLICY_DIRECTORY
        self.directory.mkdir(parents=True)
        for arguments in (
            ["init", "-q"],
            ["config", "user.email", "fixture@maintai.invalid"],
            ["config", "user.name", "Policy fixture"],
        ):
            self.git(*arguments)
        self.policy = {
            "policy_version": "fixture-risk-v1",
            "thresholds": {"watch": 0.4, "high": 0.65, "critical": 0.85},
            "create_alert_for": ["HIGH", "CRITICAL"],
        }
        # Synthetic schema exercises the selection boundary; the app owns the real schema.
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "required": ["policy_version", "thresholds", "create_alert_for"],
        }
        (self.directory / "risk-policy.schema.json").write_text(json.dumps(schema))
        self.publish(self.policy)
        patcher = patch.object(
            risk_policy,
            "load",
            side_effect=lambda name: (
                self.selection if name.endswith("risk-policy.lock.json") else self.source
            ),
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def git(self, *arguments):
        return subprocess.check_output(["git", "-C", str(self.app), *arguments], text=True).strip()

    def publish(self, policy):
        raw = (json.dumps(policy, indent=2) + "\n").encode()
        path = self.directory / "fixture-policy.json"
        path.write_bytes(raw)
        canonical = json.dumps(
            policy, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
        file_sha, policy_sha = (
            hashlib.sha256(raw).hexdigest(),
            hashlib.sha256(canonical).hexdigest(),
        )
        manifest = {
            "schema_version": "1.0.0",
            "schema_path": "risk-policy.schema.json",
            "schema_sha256": hashlib.sha256(
                (self.directory / "risk-policy.schema.json").read_bytes()
            ).hexdigest(),
            "policies": {
                policy["policy_version"]: {
                    "path": path.name,
                    "sha256": file_sha,
                    "policy_sha256": policy_sha,
                    "usage": "demo",
                    "calibration_status": "fixture_only",
                }
            },
        }
        (self.directory / "manifest.json").write_text(json.dumps(manifest))
        self.git("add", ".")
        self.git("commit", "-qm", "fixture policy")
        sha = self.git("rev-parse", "HEAD")
        self.source = {
            "schema_version": "1.0.0",
            "source_repository": "chiendz11/MaintAI",
            "source_git_sha": sha,
            "files": {
                p.relative_to(self.app).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.directory.glob("*.json")
            },
        }
        self.selection = {
            "schema_version": "1.0.0",
            "source_repository": "chiendz11/MaintAI",
            "source_git_sha": sha,
            "policy_version": policy["policy_version"],
            "path": path.relative_to(self.app).as_posix(),
            "sha256": file_sha,
            "policy_sha256": policy_sha,
        }

    def worker_profile(self):
        profile = load("profiles/local.example.json")
        enabled = {"business-api", "processing-worker", "ml-service"}
        for name in enabled:
            profile["components"][name].update(enabled=True, runtime_reviewed=True)
        profile["components"]["processing-worker"]["files"] = {
            "model_identity": {"path": "/local/fixtures/model-identity.json", "sha256": "a" * 64}
        }
        profile["components"]["ml-service"]["files"] = {
            "model": {"path": "/local/models/fixture/pipeline.joblib", "sha256": "a" * 64}
        }
        profile["evidence"].update(
            owner_migrations_applied=True,
            runtime_grants_applied=True,
            machines_provisioned=True,
            ordering_activated=True,
            model_identity_reviewed=True,
        )
        return profile, {name: fixture_receipt(name) for name in enabled | {"dev-tools"}}

    def prepared(self):
        profile, receipts = self.worker_profile()
        captured = {}
        with patch.object(
            release,
            "write",
            side_effect=lambda path, value: captured.__setitem__(
                Path(path).relative_to(ROOT), value
            ),
        ):
            release.prepare_apps(profile, receipts, self.app)
        return captured

    def test_selected_source_bytes_and_runtime_hash_are_preserved(self):
        text, metadata = risk_policy.read_policy(self.app)
        self.assertEqual(json.loads(text), self.policy)
        self.assertEqual(metadata["policy_sha256"], self.selection["policy_sha256"])
        self.assertEqual(metadata["usage"], "demo")

    def test_tampered_worktree_is_rejected_before_materialization(self):
        (self.directory / "fixture-policy.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "interface drift"):
            risk_policy.read_policy(self.app)

    def test_selector_cannot_change_file_canonical_hash_revision_or_path(self):
        original = copy.deepcopy(self.selection)
        for key, value in [
            ("sha256", "0" * 64),
            ("policy_sha256", "0" * 64),
            ("source_git_sha", "0" * 40),
            ("path", "../outside.json"),
            ("policy_version", "missing-version"),
            ("policy_version", []),
            ("sha256", "incomplete"),
        ]:
            with self.subTest(key=key):
                self.selection = {**original, key: value}
                with self.assertRaises(ValueError):
                    risk_policy.read_policy(self.app)
        self.selection = original

    def test_unordered_thresholds_are_rejected_even_when_all_hashes_match(self):
        policy = copy.deepcopy(self.policy)
        policy["thresholds"]["critical"] = 0.2
        self.publish(policy)
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            risk_policy.read_policy(self.app)

    def test_duplicate_keys_and_nonfinite_json_are_rejected(self):
        for raw in ('{"version":1,"version":2}', '{"probability":NaN}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                risk_policy.strict_document(raw)

    def test_missing_app_source_refuses_worker_before_writing_any_file(self):
        profile, receipts = self.worker_profile()
        with patch.object(release, "write") as write:
            with self.assertRaisesRegex(ValueError, "app-root"):
                release.prepare_apps(profile, receipts)
            write.assert_not_called()

    def test_private_policy_and_environment_override_cannot_replace_app_source(self):
        profile, receipts = self.worker_profile()
        profile["components"]["processing-worker"]["files"]["risk_policy"] = {
            "path": "/local/fixtures/risk-policy.json",
            "sha256": "a" * 64,
        }
        with self.assertRaisesRegex(ValueError, "legacy risk_policy"):
            release.validate_profile(profile, receipts)
        profile, receipts = self.worker_profile()
        profile["components"]["processing-worker"]["env"]["PROCESSING_RISK_POLICY_FILE"] = (
            "/local/fixtures/other.json"
        )
        with self.assertRaisesRegex(ValueError, "ConfigMap"):
            release.validate_profile(profile, receipts)

    def test_prepare_emits_exact_policy_and_read_only_configmap_mount(self):
        captured = self.prepared()
        kustomization = captured[Path("environments/local/apps/kustomization.yaml")]
        generator = next(
            item
            for item in kustomization["configMapGenerator"]
            if item["name"] == risk_policy.POLICY_CONFIGMAP
        )
        self.assertEqual(
            generator["literals"],
            ["risk-policy.json=" + (self.directory / "fixture-policy.json").read_text()],
        )
        docs = list(
            yaml.safe_load_all(
                captured[Path("environments/local/apps/generated/processing-worker.yaml")]
            )
        )
        pod = docs[0]["spec"]["template"]
        volume = next(value for value in pod["spec"]["volumes"] if value["name"] == "risk-policy")
        self.assertEqual(volume["configMap"]["name"], risk_policy.POLICY_CONFIGMAP)
        mount = next(
            value
            for value in pod["spec"]["containers"][0]["volumeMounts"]
            if value["name"] == "risk-policy"
        )
        self.assertEqual(
            mount, {"name": "risk-policy", "mountPath": "/local/config", "readOnly": True}
        )
        self.assertEqual(
            pod["metadata"]["annotations"]["maintai.io/risk-policy-sha256"],
            self.selection["policy_sha256"],
        )
        record = json.loads(captured[Path("environments/local/apps/release.json")])
        self.assertEqual(record["risk_policy"]["source_git_sha"], self.source["source_git_sha"])

    @unittest.skipUnless(
        shutil.which("kubectl"), "offline Kustomize requires kubectl; installed by CI"
    )
    def test_changed_policy_changes_hashed_configmap_and_worker_pod_reference(self):
        def render():
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                for path, value in self.prepared().items():
                    target = root / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(
                        yaml.safe_dump(value, sort_keys=False) if isinstance(value, dict) else value
                    )
                raw = subprocess.check_output(
                    ["kubectl", "kustomize", str(root / "environments/local/apps")], text=True
                )
                documents = list(yaml.safe_load_all(raw))
                config = next(
                    value
                    for value in documents
                    if value["kind"] == "ConfigMap"
                    and value["metadata"]["name"].startswith(risk_policy.POLICY_CONFIGMAP + "-")
                )
                worker = next(
                    value
                    for value in documents
                    if value["kind"] == "Deployment"
                    and value["metadata"]["name"] == "processing-worker"
                )
                reference = next(
                    value
                    for value in worker["spec"]["template"]["spec"]["volumes"]
                    if value["name"] == "risk-policy"
                )["configMap"]["name"]
                self.assertEqual(reference, config["metadata"]["name"])
                self.assertEqual(
                    json.loads(config["data"]["risk-policy.json"])["policy_version"],
                    self.selection["policy_version"],
                )
                return reference

        first = render()
        changed = copy.deepcopy(self.policy)
        changed["policy_version"] = "fixture-risk-v2"
        changed["thresholds"]["high"] = 0.7
        self.publish(changed)
        self.assertNotEqual(first, render())


if __name__ == "__main__":
    unittest.main()
