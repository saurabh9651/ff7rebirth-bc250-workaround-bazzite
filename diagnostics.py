#!/usr/bin/env python3
"""Local session timing, crash evidence, and shareable BC-250 reports."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

HEARTBEAT_SECONDS = 15
TAIL_BYTES = 4 * 1024 * 1024
SIGNATURES = {
    "vulkan_device_lost": r"VK_ERROR_DEVICE_LOST",
    "gpu_reset": r"GPU reset|amdgpu.*reset|drm.*reset",
    "gpu_fault_or_timeout": r"VM fault|GPU fault|ring .*timeout|job timedout|amdgpu.*page fault",
    "out_of_memory": r"out of memory|oom-kill|VK_ERROR_OUT_OF_(?:DEVICE|HOST)_MEMORY",
    "unhandled_exception": r"unhandled exception|segmentation fault|segfault|assertion .*failed|fatal error",
    "wine_assertion": r"\bEXCEPTION_WINE_ASSERTION\b",
    "exception_dispatch_failure": r"Exception frame is not in stack limits|unable to dispatch exception",
}
ERROR_LINE = re.compile(r"err:|\berror\b|fatal|VK_ERROR|assert|segfault|unhandled exception|GPU reset|VM fault|timedout", re.I)
SOURCE_FILES = (
    "README.md", "COMMUNITY_GUIDE.md", "Containerfile", ".containerignore",
    "setup-driver.sh", "container-build.sh", "check-driver.sh",
    "launch-rebirth.sh", "runtime-libraries.py", "diagnostics.py",
    "test_diagnostics.py",
)


def now():
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def write_json(path, value):
    """Atomic heartbeat, flushed before replacing the previous record."""
    descriptor, temporary = tempfile.mkstemp(prefix=".session-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def boot_id():
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return "unknown"


def process_ticks(pid):
    try:
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return None


def snapshot(root, command):
    work = root / ".directmesh"
    provenance = read_json(work / "provenance.json")
    runtime = read_json(work / "runtime/manifest.json")
    os_info = {}
    try:
        for line in Path("/etc/os-release").read_text().splitlines():
            key, _, value = line.partition("=")
            if key in ("NAME", "VERSION_ID", "BUILD_ID"):
                os_info[key] = value.strip('"')
    except OSError:
        pass
    proton = "unknown"
    for argument in command:
        if Path(argument).name in ("proton", "proton.py"):
            try:
                proton = (Path(argument).parent / "version").read_text().strip()[:120]
            except OSError:
                pass
            break
    build_id = "unknown"
    install = os.environ.get("STEAM_COMPAT_INSTALL_PATH")
    steamapps = (Path(install).parent.parent if install else
                 Path.home() / ".local/share/Steam/steamapps")
    try:
        text = (steamapps / "appmanifest_2909400.acf").read_text()
        match = re.search(r'"buildid"\s+"(\d+)"', text)
        if match:
            build_id = match[1]
    except OSError:
        pass
    return {
        "os": os_info, "kernel": os.uname().release,
        "mesa_version": provenance.get("mesa_version", "unknown"),
        "directmesh_release": provenance.get("release", "unknown"),
        "driver_sha256": provenance.get("library_sha256", "unknown"),
        "patch_sha256": provenance.get("patch_sha256", "unknown"),
        "libdrm_version": runtime.get("libdrm_version", "unknown"),
        "proton_version": proton, "game_build_id": build_id,
        "directmesh_enabled": os.environ.get("RADV_DIRECTMESH") == "1",
    }


def capture_journal(logs, record):
    """Only relevant kernel messages and coredump metadata; never binary cores."""
    statuses = {}
    until = record.get("ended_at") or now()
    # journalctl accepts an sd-id128 hex boot descriptor, not /proc's UUID form.
    recorded_boot = record.get("boot_id", "")
    compact_boot = recorded_boot.replace("-", "") if isinstance(recorded_boot, str) else ""
    if not re.fullmatch(r"[0-9a-fA-F]{32}", compact_boot):
        for label in ("kernel", "coredumps"):
            (logs / (label + "-access.log")).write_text("No valid recorded boot ID; refusing an unscoped journal query.\n")
        return {"kernel": "unavailable", "coredumps": "unavailable"}
    environment = dict(os.environ)
    for key in ("LD_PRELOAD", "LD_LIBRARY_PATH", "LD_AUDIT"):
        environment.pop(key, None)
    for label, extra, pattern in (
        ("kernel", ["--dmesg"], r"amdgpu|\bdrm\b|\bgpu\b|oom|out of memory|segfault|killed process"),
        ("coredumps", ["SYSLOG_IDENTIFIER=systemd-coredump"], r"rebirth|ff7|end-win64|wine|proton"),
    ):
        command = ["journalctl", "--no-pager", "--output=short-iso",
                   "--since=" + record["started_at"], "--until=" + until]
        command.append("--boot=" + compact_boot)
        try:
            result = subprocess.run(command + extra, capture_output=True, text=True, timeout=8, env=environment)
            selected = [line for line in result.stdout.splitlines() if re.search(pattern, line, re.I)]
            (logs / (label + ".log")).write_text("\n".join(selected) + ("\n" if selected else ""))
            statuses[label] = "ok" if result.returncode == 0 else "unavailable"
            if re.search(r"not seeing messages|permission|access denied", result.stderr, re.I):
                statuses[label] = "restricted"
            (logs / (label + "-access.log")).write_text(result.stderr)
        except (OSError, subprocess.TimeoutExpired) as exc:
            statuses[label] = "unavailable"
            (logs / (label + "-access.log")).write_text(type(exc).__name__ + "\n")
    return statuses


def extract_errors(logs):
    """Scan bounded tails; counts indicate evidence, not a crash diagnosis."""
    counts = {name: 0 for name in SIGNATURES}
    snippets = []
    for path in sorted(logs.glob("*.log")):
        if path.is_symlink() or path.name.endswith("-access.log") or path.name == "errors.log":
            continue
        try:
            with path.open("rb") as stream:
                stream.seek(0, os.SEEK_END)
                stream.seek(max(0, stream.tell() - TAIL_BYTES))
                text = stream.read(TAIL_BYTES).decode(errors="replace")
        except OSError:
            continue
        for name, pattern in SIGNATURES.items():
            counts[name] += len(re.findall(pattern, text, re.I))
        snippets.extend(path.name + ": " + line[:2000] for line in text.splitlines() if ERROR_LINE.search(line))
    (logs / "errors.log").write_text("\n".join(snippets[-120:]) + ("\n" if snippets else ""))
    return counts


def monitor(root, logs, command, heartbeat=HEARTBEAT_SECONDS, collector=capture_journal):
    logs.mkdir(parents=True, exist_ok=True, mode=0o700)
    logs.chmod(0o700)
    started = time.monotonic()
    record = {
        "schema_version": 1, "session_id": logs.name, "started_at": now(),
        "last_heartbeat_at": now(), "elapsed_seconds": 0.0, "status": "running",
        "supervisor_pid": os.getpid(), "supervisor_start_ticks": process_ticks(os.getpid()),
        "boot_id": boot_id(), "environment": snapshot(root, command),
        "timing_scope": "wrapper lifetime, including loading, menus, and pauses",
    }
    path = logs / "session.json"
    write_json(path, record)
    child = None
    received = []

    def forward(signum, _frame):
        received.append(signum)
        if child is not None:
            try:
                os.killpg(child.pid, signum)
            except ProcessLookupError:
                pass

    previous = {sig: signal.signal(sig, forward) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    code = None
    try:
        with (logs / "console.log").open("ab", buffering=0) as output:
            try:
                child = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
            except OSError as exc:
                record.update(status="failed_to_start", launch_errno=exc.errno)
                output.write((str(exc) + "\n").encode())
                code = 127
            if child is not None:
                record["child_pid"] = child.pid
                for signum in received:
                    try:
                        os.killpg(child.pid, signum)
                    except ProcessLookupError:
                        pass
                while True:
                    try:
                        code = child.wait(timeout=heartbeat)
                        break
                    except subprocess.TimeoutExpired:
                        record.update(elapsed_seconds=round(time.monotonic() - started, 3), last_heartbeat_at=now())
                        try:
                            write_json(path, record)
                        except OSError:
                            # A logging failure must not terminate a running game.
                            pass
                record["status"] = "exited_zero" if code == 0 else "nonzero_exit"
                if code < 0:
                    record["status"] = "signal_exit"
                    record["exit_signal"] = -code
        record.update(ended_at=now(), elapsed_seconds=round(time.monotonic() - started, 3),
                      exit_code=code, received_signals=received)
        # Save the exit result before any diagnostic command that could time out.
        write_json(path, record)
        try:
            record["journal_access"] = collector(logs, record)
            record["error_signatures"] = extract_errors(logs)
        except Exception as exc:
            record["diagnostic_collection_error"] = type(exc).__name__
        write_json(path, record)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return 128 - code if code is not None and code < 0 else (code if code is not None else 1)


def sessions(root):
    return [(path.parent, read_json(path)) for path in sorted(
        (root / ".directmesh/logs/proton").glob("*/session.json")) if not path.is_symlink()]


def effective_status(record):
    if record.get("status") != "running":
        return record.get("status", "unknown")
    if (record.get("boot_id") == boot_id() and record.get("supervisor_start_ticks") and
            process_ticks(record.get("supervisor_pid")) == record["supervisor_start_ticks"]):
        return "running"
    return "incomplete"


def choose(root, identifier):
    entries = sessions(root)
    if identifier == "latest" and entries:
        return entries[-1]
    for directory, record in entries:
        if directory.name == identifier:
            return directory, record
    raise ValueError("No matching tracked session. Launch Rebirth with the updated launcher first.")


def public_report(record):
    # Explicit fields only: never copy command arguments, raw logs, home paths,
    # Steam IDs, boot IDs, process IDs, environment dumps, or crash memory.
    fields = ("schema_version", "session_id", "started_at", "ended_at", "last_heartbeat_at",
              "elapsed_seconds", "exit_code", "exit_signal", "timing_scope",
              "journal_access", "error_signatures", "diagnostic_collection_error")
    report = {key: record[key] for key in fields if key in record}
    report["status"] = effective_status(record)
    environment = record.get("environment", {})
    allowed_environment = ("kernel", "mesa_version", "directmesh_release", "driver_sha256",
                           "patch_sha256", "libdrm_version", "proton_version", "game_build_id",
                           "directmesh_enabled")
    report["environment"] = {key: environment[key] for key in allowed_environment if key in environment}
    report["environment"]["os"] = {key: environment.get("os", {})[key]
        for key in ("NAME", "VERSION_ID", "BUILD_ID") if key in environment.get("os", {})}
    report["notes"] = ["Elapsed time includes loading, menus, and pauses.",
                       "An incomplete session records a lower bound, not an exact end time.",
                       "Exit codes and error signatures alone do not prove a game crash."]
    return report


def community_bundle(root):
    destination = root / "community"
    destination.mkdir(exist_ok=True)
    archive = destination / "ff7rebirth-bc250-source.tar.gz"
    prepared = root / "github-repo"
    source = prepared if (prepared / "PUBLICATION_SHA256.json").is_file() else root
    manifest_path = source / "PUBLICATION_SHA256.json"
    with tempfile.TemporaryDirectory(prefix="bc250-share-") as temporary:
        stage = Path(temporary)
        names = list(SOURCE_FILES)
        if manifest_path.exists():
            if manifest_path.is_symlink() or manifest_path.stat().st_size > 256 * 1024:
                raise ValueError("Invalid source publication manifest")
            manifest = read_json(manifest_path)
            if not isinstance(manifest.get("files"), dict):
                raise ValueError("Invalid source publication manifest")
            names = sorted(set(manifest["files"]) | {"PUBLICATION_SHA256.json"})
        for name in names:
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts or relative.as_posix() != name:
                raise ValueError("Invalid source archive path")
            path = source / relative
            if (not path.is_file() or path.is_symlink() or path.stat().st_nlink != 1
                    or path.stat().st_size > 256 * 1024
                    or not path.resolve().is_relative_to(source.resolve())
                    or any(parent.is_symlink() for parent in path.parents if parent.is_relative_to(source))):
                raise ValueError("Missing, linked or oversized source file: " + name)
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            target.chmod(path.stat().st_mode & 0o777)
        if manifest_path.exists():
            auditor = stage / "tools/audit_publication.py"
            if not auditor.is_file():
                raise ValueError("Reviewed source archive is missing its audit tool")
            subprocess.run([sys.executable, "-B", str(auditor), "--root", str(stage)], check=True)
        with tarfile.open(archive, "w:gz") as output:
            for name in names:
                path = stage / name
                info = output.gettarinfo(str(path), arcname="ff7rebirth-bc250/" + name)
                info.uid = info.gid = 0
                info.uname = info.gname = ""
                with path.open("rb") as stream:
                    output.addfile(info, stream)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(archive.suffix + ".sha256").write_text(checksum + "  " + archive.name + "\n")
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    sub = parser.add_subparsers(dest="action", required=True)
    run = sub.add_parser("run", help="Used by launch-rebirth.sh")
    run.add_argument("--log-dir", type=Path, required=True)
    run.add_argument("command", nargs=argparse.REMAINDER)
    sub.add_parser("stats", help="Show accumulated tracked session time")
    for name in ("report", "recover"):
        command = sub.add_parser(name)
        command.add_argument("session", nargs="?", default="latest")
    sub.add_parser("bundle", help="Create a source-only community archive locally")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.action == "run":
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        if not command:
            parser.error("run requires a command after --")
        return monitor(root, args.log_dir, command)
    if args.action == "stats":
        total = 0.0
        entries = sessions(root)
        for directory, record in entries:
            seconds = record.get("elapsed_seconds", 0.0)
            total += seconds
            print(f"{directory.name}  {seconds / 60:.1f} min  {effective_status(record)}")
        print(f"Tracked sessions: {len(entries)}; recorded time: {total / 3600:.2f} hours ({total / 60:.1f} minutes).")
        print("Includes loading, menus and pauses; interrupted/running sessions use their last saved heartbeat.")
    elif args.action == "bundle":
        print(community_bundle(root))
    else:
        logs, record = choose(root, args.session)
        if args.action == "recover":
            if effective_status(record) == "running":
                raise ValueError("Session is still running; recovery is for a stopped session.")
            record["journal_access"] = capture_journal(logs, record)
            record["error_signatures"] = extract_errors(logs)
            record["recovered_at"] = now()
            write_json(logs / "session.json", record)
            print("Recovered available journal evidence. An unknown end time remains unknown.")
        else:
            reports = root / ".directmesh/reports"
            reports.mkdir(exist_ok=True)
            destination = reports / (logs.name + ".json")
            write_json(destination, public_report(record))
            print(destination)
            print("Structured summary only; raw logs and binary dumps are excluded. Review before sharing.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        sys.exit(str(error))
