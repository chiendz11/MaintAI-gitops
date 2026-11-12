"""Offline signer cutover checks for future GitOps CI; no AWS/Docker/cluster calls."""

import copy
import unittest

from automation.common import read_json
from automation.verify_image import expected_publisher


class MLflowImageOwnership(unittest.TestCase):
    def setUp(self):
        self.groups = read_json("config/image-groups.json")["groups"]
        self.intent = {
            "image_group": "mlflow",
            "source_repository": "chiendz11/MaintAI",
            "source_sha": "a" * 40,
        }

    def test_mlflow_requires_app_actor_workflow_and_source_annotation(self):
        actor, identity, annotations = expected_publisher(self.intent, self.groups)
        self.assertEqual(actor, "app")
        self.assertEqual(identity, "https://github.com/chiendz11/MaintAI/"
                         ".github/workflows/maintai-publish.yml@refs/heads/main")
        self.assertIn("source_repository=chiendz11/MaintAI", annotations)
        self.assertIn("image_group=mlflow", annotations)
        self.assertIn("git_sha=" + self.intent["source_sha"], annotations)

    def test_legacy_gitops_mlflow_producer_is_rejected(self):
        legacy = {**self.intent, "source_repository": "chiendz11/MaintAI-gitops"}
        with self.assertRaisesRegex(ValueError, "ownership mismatch"):
            expected_publisher(legacy, self.groups)

    def test_gitops_automation_keeps_its_existing_producer(self):
        intent = {**self.intent, "image_group": "automation",
                  "source_repository": "chiendz11/MaintAI-gitops"}
        actor, identity, _ = expected_publisher(intent, self.groups)
        self.assertEqual(actor, "automation")
        self.assertIn("MaintAI-gitops/.github/workflows/publish-platform-images.yml", identity)

    def test_unknown_group_or_unreviewed_workflow_is_rejected(self):
        with self.assertRaises(ValueError):
            expected_publisher({**self.intent, "image_group": "unknown"}, self.groups)
        groups = copy.deepcopy(self.groups)
        groups["mlflow"]["publisher_workflow"] = "../../untrusted.yml"
        with self.assertRaises(ValueError):
            expected_publisher(self.intent, groups)


if __name__ == "__main__":
    unittest.main()
