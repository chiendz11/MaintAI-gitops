"""Local profile safety and compatibility gates; fixtures are not image evidence."""

import copy
import tempfile
import unittest
from pathlib import Path

import yaml
from jsonschema.exceptions import ValidationError

from localdev.common import ROOT, assert_local, identity, load
from localdev.release import validate_profile


def receipt(name):
    return {"schema_version": "1.0.0", "component": name,
            "image": "maintai-local/" + name + ":image-" + "a" * 64, "image_id": "sha256:" + "a" * 64,
            "source_git_sha": "b" * 40, "source_dirty": False, "source_snapshot_sha256": "c" * 64,
            "dockerfile": "fixture/Dockerfile", "dockerfile_sha256": "d" * 64, "build_context": ".",
            "imported_context": "k3d-maintai-local"}


class LocalReleaseSafety(unittest.TestCase):
    def test_platform_configuration_precedes_its_consumers_in_argo_waves(self):
        namespace = yaml.safe_load((ROOT / "platform/namespaces/local/namespace.yaml").read_text())
        base = yaml.safe_load((ROOT / "local/platform/kustomization.yaml").read_text())
        namespace_wave = int(namespace["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"])
        config_wave = int(base["generatorOptions"]["annotations"]["argocd.argoproj.io/sync-wave"])
        self.assertLess(namespace_wave, config_wave)
        for path in (ROOT / "local/platform").glob("*.yaml"):
            if path.name == "kustomization.yaml":
                continue
            for document in yaml.safe_load_all(path.read_text()):
                wave = int(document["metadata"].get("annotations", {}).get("argocd.argoproj.io/sync-wave", "0"))
                self.assertGreater(wave, config_wave, path.name)

    def test_image_alias_cannot_claim_a_different_actual_image(self):
        value = receipt("dev-tools")
        value["image_id"] = "sha256:" + "e" * 64
        with self.assertRaises(ValueError):
            identity(value, "dev-tools")

    def test_release_writer_rejects_production_and_path_escape(self):
        for target in ("environments/production/workloads/kustomization.yaml", "environments/local/../production/config.yaml"):
            with self.assertRaises(ValueError):
                assert_local(Path(__file__).resolve().parents[1] / target)

    def test_default_profile_contains_no_enabled_or_fabricated_runtime(self):
        profile = load("profiles/local.example.json")
        self.assertEqual(validate_profile(profile, {"dev-tools": receipt("dev-tools")}), set())

    def test_alert_consumer_cannot_be_enabled_without_processing_evidence_provider(self):
        profile = load("profiles/local.example.json")
        profile["components"]["business-consumer"]["enabled"] = True
        with self.assertRaises(ValueError):
            validate_profile(profile, {"dev-tools": receipt("dev-tools"), "business-consumer": receipt("business-consumer")})

    def test_credentials_and_production_namespace_are_rejected(self):
        profile = load("profiles/local.example.json")
        profile["namespace"] = "production"
        with self.assertRaises((ValueError, ValidationError)):
            validate_profile(profile, {})
        profile = load("profiles/local.example.json")
        profile["components"]["ingestion-api"].update(enabled=True, env={"API_KEY": "must-never-be-written"})
        with self.assertRaises(ValueError):
            validate_profile(profile, {"dev-tools": receipt("dev-tools"), "ingestion-api": receipt("ingestion-api")})

    def test_ml_runtime_does_not_become_available_from_a_placeholder_receipt(self):
        profile = load("profiles/local.example.json")
        profile["components"]["ml-service"]["enabled"] = True
        with self.assertRaises(ValueError):
            validate_profile(profile, {"dev-tools": receipt("dev-tools"), "ml-service": receipt("ml-service")})


if __name__ == "__main__":
    unittest.main()
