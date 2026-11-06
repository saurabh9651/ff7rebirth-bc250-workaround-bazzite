#!/usr/bin/env python3
"""Bundle and validate the small private runtime used by this Mesa build."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

LIBRARIES = ("libdrm.so.2", "libdrm_amdgpu.so.1", "libexpat.so.1")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_version(value):
    if not re.fullmatch(r"\d+\.\d+\.\d+", value):
        raise ValueError("Invalid libdrm version: " + value)
    if tuple(map(int, value.split("."))) < (2, 4, 133):
        raise ValueError("This Mesa build requires libdrm 2.4.133 or later.")


def bundle(source, destination, version):
    check_version(version)
    # Check inputs before changing an existing bundle.
    for name in LIBRARIES:
        path = source / name
        with path.open("rb") as stream:
            if stream.read(5) != b"\x7fELF\x02":
                raise ValueError("Expected a 64-bit ELF library: " + str(path))
    libraries = destination / "lib"
    libraries.mkdir(parents=True, exist_ok=True)
    for name in LIBRARIES:
        shutil.copyfile(source / name, libraries / name)
    manifest = {
        "libdrm_version": version,
        "source_directory": str(source.resolve()),
        "source_files": {name: str((source / name).resolve()) for name in LIBRARIES},
        "libraries": {name: digest(libraries / name) for name in LIBRARIES},
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("Bundled libdrm " + version + " and matching expat in " + str(libraries))


def verify(destination):
    manifest = json.loads((destination / "manifest.json").read_text())
    check_version(manifest["libdrm_version"])
    if set(manifest["libraries"]) != set(LIBRARIES):
        raise ValueError("Runtime manifest has an unexpected library list.")
    for name in LIBRARIES:
        if digest(destination / "lib" / name) != manifest["libraries"][name]:
            raise ValueError("Private runtime library changed: " + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="action", required=True)
    bundler = subcommands.add_parser("bundle")
    bundler.add_argument("source", type=Path)
    bundler.add_argument("destination", type=Path)
    bundler.add_argument("--libdrm-version", required=True)
    verifier = subcommands.add_parser("verify")
    verifier.add_argument("destination", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "bundle":
            bundle(args.source, args.destination, args.libdrm_version)
        verify(args.destination)
    except (OSError, ValueError, KeyError) as exc:
        sys.exit("Private driver runtime unavailable or invalid: " + str(exc) +
                 ". Run ./setup-driver.sh to export the matching build libraries.")


if __name__ == "__main__":
    main()
