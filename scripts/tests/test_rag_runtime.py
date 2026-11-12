"""Groq wiring and shared cache are source checks, not live provider evidence."""

import unittest
from unittest.mock import patch

from localdev import rag_job
from localdev.workloads import resources
from test_local_release import receipt


class RagRuntime(unittest.TestCase):
    def test_wait_for_consumer_cache_cannot_block_datastore_bootstrap_waves(self):
        import yaml
        from localdev.common import ROOT
        claim = yaml.safe_load((ROOT / "local/platform/rag-cache.yaml").read_text())
        self.assertGreaterEqual(int(claim["metadata"]["annotations"]["argocd.argoproj.io/sync-wave"]), 0)

    def test_deployment_uses_scoped_secret_and_writable_cache_only(self):
        docs, configs = resources("rag-service", {"env": {}}, 5, "b" * 40)
        pod = docs[0]["spec"]["template"]["spec"]
        container = pod["containers"][0]
        self.assertEqual(
            container["env"][0],
            {
                "name": "GROQ_API_KEY",
                "valueFrom": {
                    "secretKeyRef": {"name": "rag-groq", "key": "GROQ_API_KEY"}
                },
            },
        )
        self.assertTrue(container["securityContext"]["readOnlyRootFilesystem"])
        mount = next(
            value
            for value in container["volumeMounts"]
            if value["name"] == "embedding-cache"
        )
        self.assertFalse(mount.get("readOnly", False))
        claim = next(
            value for value in pod["volumes"] if value["name"] == "embedding-cache"
        )
        self.assertEqual(
            claim["persistentVolumeClaim"]["claimName"], "local-rag-embedding-cache"
        )
        env = dict(value.split("=", 1) for value in configs[0]["literals"])
        self.assertEqual(env["MODEL_LOCAL_FILES_ONLY"], "true")
        self.assertEqual(len(env["EMBEDDING_REVISION"]), 40)
        self.assertFalse(any(key.startswith("OLLAMA_") for key in env))
        self.assertEqual(container["startupProbe"]["httpGet"]["path"], "/health/live")
        self.assertEqual(
            container["readinessProbe"]["httpGet"]["path"], "/health/ready"
        )

    def test_knowledge_job_uses_same_cache_but_no_groq_credential(self):
        real_load = rag_job.load

        def selected(name):
            if name == "config/local/app-source.lock.json":
                return {
                    "source_git_sha": "b" * 40,
                    "files": {"rag-service/knowledge-demo.json": "c" * 64},
                }
            return real_load(name)

        with patch.object(rag_job, "load", side_effect=selected):
            job = rag_job.preparation_job(receipt("rag-service"))
        pod = job["spec"]["template"]["spec"]
        container = pod["containers"][0]
        self.assertEqual(
            container["command"], ["python", "-m", "ingestion.prepare_demo"]
        )
        self.assertFalse(
            any(value["name"].startswith("GROQ_") for value in container["env"])
        )
        self.assertEqual(
            next(
                value for value in container["env"] if value["name"] == "DATABASE_URL"
            )["valueFrom"]["secretKeyRef"]["name"],
            "local-knowledge-owner",
        )
        self.assertEqual(
            pod["volumes"][0]["persistentVolumeClaim"]["claimName"],
            "local-rag-embedding-cache",
        )
        self.assertFalse(pod["automountServiceAccountToken"])
        self.assertEqual(job["spec"]["backoffLimit"], 0)

    def test_unimported_or_unreviewed_image_cannot_seed(self):
        for changed in (
            {"source_git_sha": "f" * 40},
            {"imported_context": None},
            {"source_dirty": True},
        ):
            value = receipt("rag-service")
            value.update(changed)
            with self.assertRaises(Exception):
                rag_job.preparation_job(value)

    def test_old_provider_and_embedding_overrides_are_rejected(self):
        for env in (
            {"OLLAMA_BASE_URL": "http://localhost"},
            {"MODEL_LOCAL_FILES_ONLY": "false"},
            {"EMBEDDING_REVISION": "main"},
        ):
            with self.assertRaises(ValueError):
                resources("rag-service", {"env": env}, 5, "b" * 40)
