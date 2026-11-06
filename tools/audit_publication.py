#!/usr/bin/env python3
"""Fail closed on unexpected files and recognizable sensitive source content."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys

MANIFEST = "PUBLICATION_SHA256.json"
MAX_FILE_BYTES = 256 * 1024
PATTERNS = (
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----")),
    ("AWS access key format", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("GitHub token format", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{30,}\b")),
    ("bearer credential", re.compile(r"authorization\s*[:=]\s*['\"]?bearer\s+[A-Za-z0-9._~+/-]{16,}", re.I)),
    ("personal home path", re.compile(r"/(?:var/)?home/[A-Za-z0-9_][A-Za-z0-9_.-]*/")),
    ("Steam account ID format", re.compile(r"\b7656119[0-9]{10}\b")),
    ("email address", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
    ("credential assignment", re.compile(r"\b(?:api_key|access_token|client_secret|password)\s*[:=]\s*['\"][^'\"\n]{12,}['\"]", re.I)),
)
FORBIDDEN_PARTS = {".directmesh", "local-notes", ".aws", ".codex", ".agents", ".ssh",
                   ".env", "logs", "downloads", "crash-reports", "__pycache__"}


def check_text(name, data):
    issues = []
    if len(data) > MAX_FILE_BYTES:
        return [name + ": exceeds source-file size limit"]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return [name + ": binary/non-UTF-8 content"]
    if "\x00" in text:
        issues.append(name + ": NUL byte in source")
    for label, pattern in PATTERNS:
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            issues.append(f"{name}:{line}: {label} (value withheld)")
    return issues


def valid_name(name):
    if not isinstance(name, str):
        return False
    path = PurePosixPath(name)
    return (isinstance(name, str) and bool(name) and not path.is_absolute()
            and ".." not in path.parts and str(path) == name
            and bool(re.fullmatch(r"[A-Za-z0-9_./-]+", name))
            and not any(part in FORBIDDEN_PARTS or part.startswith(".env.") for part in path.parts)
            and not any(part.startswith(".") and part not in (".gitignore", ".containerignore") for part in path.parts)
            and (path.suffix in (".md", ".py", ".sh", ".json")
                 or name in ("Containerfile", ".gitignore", ".containerignore")))


def ignore_rules(names):
    rules = ["# Deny by default. New public files require explicit review and export.", "*"]
    directories = {parent.as_posix() for name in names for parent in PurePosixPath(name).parents if str(parent) != "."}
    rules += ["!/" + name + "/" for name in sorted(directories, key=lambda name: (name.count("/"), name))]
    rules += ["!/" + name for name in sorted(names)]
    return "\n".join(rules) + "\n"


def audit(root):
    issues = []
    path = root / MANIFEST
    if path.is_symlink() or not path.is_file():
        return ["Missing regular publication manifest"]
    if path.stat().st_size > MAX_FILE_BYTES:
        return ["Publication manifest exceeds size limit"]
    try:
        manifest = json.loads(path.read_text())
        if set(manifest) != {"schema_version", "generated_at", "files"} or manifest["schema_version"] != 1:
            raise ValueError("schema")
        files = manifest["files"]
        if not isinstance(files, dict) or not files:
            raise ValueError("files")
        for name, digest in files.items():
            if not valid_name(name) or name == MANIFEST or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("entry")
    except (OSError, ValueError, TypeError):
        return ["Invalid publication manifest; do not publish"]
    expected = set(files) | {MANIFEST}
    directories = {str(parent) for name in expected for parent in PurePosixPath(name).parents if str(parent) != "."}
    seen = set()
    for base, names, filenames in os.walk(root, followlinks=False):
        relative = Path(base).relative_to(root)
        for name in list(names):
            item = Path(base) / name
            rel = (relative / name).as_posix()
            if item.is_symlink():
                issues.append(rel + ": directory symlink forbidden")
                names.remove(name)
            elif relative == Path(".") and name == ".git":
                names.remove(name)  # Git history is explicitly outside this working-tree audit.
            elif rel not in directories:
                issues.append(rel + ": unexpected directory")
                names.remove(name)
        for name in filenames:
            item = Path(base) / name
            rel = (relative / name).as_posix()
            if rel not in expected:
                issues.append(rel + ": unexpected file")
                continue
            seen.add(rel)
            metadata = item.lstat()
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                issues.append(rel + ": must be a regular file without hardlinks")
                continue
            if metadata.st_size > MAX_FILE_BYTES:
                issues.append(rel + ": exceeds source-file size limit")
                continue
            data = item.read_bytes()
            issues.extend(check_text(rel, data))
            if rel in files and hashlib.sha256(data).hexdigest() != files[rel]:
                issues.append(rel + ": changed since export; review and refresh the snapshot")
    issues.extend(name + ": missing file" for name in sorted(expected - seen))
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    issues = audit(args.root.resolve())
    if issues:
        for issue in issues:
            print("FAIL: " + issue, file=sys.stderr)
        return 1
    print("PASS: explicit source list, file hashes, file types and sensitive-content pattern checks.")
    print("Working tree only. This is not a guarantee; Git history and remote state were not checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
