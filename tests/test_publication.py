"""Publication boundary tests; fixtures contain synthetic data only."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("publication_audit", ROOT / "tools/audit_publication.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="bc250-publication-")
        self.root = Path(self.temporary.name)
        self.files = {"README.md": b"Source fixture.\n", "docs/decision.md": b"Decision fixture.\n"}
        for name, data in self.files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.manifest()

    def tearDown(self):
        self.temporary.cleanup()

    def manifest(self):
        data = {"schema_version": 1, "generated_at": "fixture", "files":
                {name: hashlib.sha256(data).hexdigest() for name, data in self.files.items()}}
        (self.root / audit.MANIFEST).write_text(json.dumps(data))

    def test_known_source_passes(self):
        self.assertEqual(audit.audit(self.root), [])

    def test_hidden_unknown_files_and_private_directories_fail(self):
        (self.root / ".env").write_text("fixture")
        (self.root / "local-notes").mkdir()
        issues = "\n".join(audit.audit(self.root))
        self.assertIn(".env: unexpected file", issues)
        self.assertIn("local-notes: unexpected directory", issues)

    def test_modified_file_fails_even_without_a_secret_pattern(self):
        (self.root / "README.md").write_text("An unreviewed edit\n")
        self.assertTrue(any("changed since export" in issue for issue in audit.audit(self.root)))

    def test_symlink_and_hardlink_are_rejected(self):
        path = self.root / "README.md"
        path.unlink()
        path.symlink_to(self.root / "docs/decision.md")
        self.assertTrue(any("regular file" in issue for issue in audit.audit(self.root)))
        path.unlink()
        os.link(self.root / "docs/decision.md", path)
        self.assertTrue(any("hardlinks" in issue for issue in audit.audit(self.root)))

    def test_binary_and_recognizable_credentials_are_rejected_without_echoing_values(self):
        token = "ghp_" + "z" * 36
        data = ("fixture: " + token).encode()
        messages = "\n".join(audit.check_text("fixture.py", data))
        self.assertIn("GitHub token format", messages)
        self.assertNotIn(token, messages)
        self.assertTrue(audit.check_text("fixture.py", b"\x00\xff"))
        self.assertTrue(audit.check_text("fixture.md", ("/home/" + "sample_user" + "/private").encode()))

    def test_manifest_cannot_whitelist_private_or_escaping_paths(self):
        for name in ("../outside.md", ".directmesh/secret.md", "local-notes/memory.md", "/absolute.md"):
            self.files[name] = b"fixture"
            self.manifest()
            self.assertEqual(audit.audit(self.root), ["Invalid publication manifest; do not publish"])
            del self.files[name]

    def test_git_deny_by_default_rules_keep_new_files_out(self):
        allowed = set(self.files) | {".gitignore", audit.MANIFEST}
        (self.root / ".gitignore").write_text(audit.ignore_rules(allowed))
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        subprocess.run(["git", "init", "--quiet", str(self.root)], env=env, check=True)
        for name in ("README.md", "docs/decision.md", audit.MANIFEST):
            result = subprocess.run(["git", "-C", str(self.root), "check-ignore", "--no-index", "--quiet", name], env=env)
            self.assertEqual(result.returncode, 1, name)
        for name in (".env", ".directmesh/session.json", "local-notes/memory.md", "new.txt", "docs/raw.log"):
            result = subprocess.run(["git", "-C", str(self.root), "check-ignore", "--no-index", "--quiet", name], env=env)
            self.assertEqual(result.returncode, 0, name)


if __name__ == "__main__":
    unittest.main()
