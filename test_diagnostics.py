"""Exercise tracking and sharing with small processes, without launching a game."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("diagnostics", ROOT / "diagnostics.py")
diagnostics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostics)


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="bc250-diagnostics-")
        self.root = Path(self.temporary.name)
        self.logs = self.root / ".directmesh/logs/proton/test-session"

    def tearDown(self):
        self.temporary.cleanup()

    def run_child(self, code):
        return diagnostics.monitor(self.root, self.logs, [sys.executable, "-B", "-c", code],
            heartbeat=0.03, collector=lambda *_: {"kernel": "unavailable"})

    def test_normal_exit_measures_time_without_calling_it_gameplay(self):
        self.assertEqual(self.run_child("import time; time.sleep(0.15); print('finished')"), 0)
        data = diagnostics.read_json(self.logs / "session.json")
        self.assertEqual(data["status"], "exited_zero")
        self.assertGreaterEqual(data["elapsed_seconds"], 0.15)
        self.assertIn("menus", data["timing_scope"])
        self.assertIn("finished", (self.logs / "console.log").read_text())
        self.assertEqual(self.logs.stat().st_mode & 0o777, 0o700)

    def test_nonzero_exit_retains_error_and_exit_code(self):
        self.assertEqual(self.run_child("import sys; print('VK_ERROR_DEVICE_LOST',file=sys.stderr); sys.exit(7)"), 7)
        data = diagnostics.read_json(self.logs / "session.json")
        self.assertEqual(data["status"], "nonzero_exit")
        self.assertEqual(data["exit_code"], 7)
        self.assertEqual(data["error_signatures"]["vulkan_device_lost"], 1)
        self.assertIn("VK_ERROR_DEVICE_LOST", (self.logs / "errors.log").read_text())

    def test_signal_exit_is_distinct_from_normal_exit(self):
        self.assertEqual(self.run_child("import os,signal; os.kill(os.getpid(),signal.SIGTERM)"), 143)
        data = diagnostics.read_json(self.logs / "session.json")
        self.assertEqual(data["status"], "signal_exit")
        self.assertEqual(data["exit_signal"], signal.SIGTERM)

    def test_wine_assertion_is_reported_even_when_wrapper_exits_zero(self):
        self.assertEqual(self.run_child("print('EXCEPTION_WINE_ASSERTION exception raised'); print('Exception frame is not in stack limits => unable to dispatch exception.')"), 0)
        data = diagnostics.read_json(self.logs / "session.json")
        self.assertEqual(data["status"], "exited_zero")
        self.assertEqual(data["error_signatures"]["wine_assertion"], 1)
        self.assertGreater(data["error_signatures"]["exception_dispatch_failure"], 0)

    def test_journal_boot_descriptor_and_environment_work_outside_steam(self):
        self.logs.mkdir(parents=True)
        (self.logs / "kernel-access.log").write_text("old failure")
        record = {"started_at": diagnostics.now(), "ended_at": diagnostics.now(),
                  "boot_id": "11111111-2222-3333-4444-555555555555"}
        result = subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with mock.patch.dict(os.environ, {"LD_PRELOAD": "fixture", "LD_LIBRARY_PATH": "fixture", "LD_AUDIT": "fixture"}):
            with mock.patch.object(diagnostics.subprocess, "run", return_value=result) as runner:
                statuses = diagnostics.capture_journal(self.logs, record)
        self.assertEqual(statuses, {"kernel": "ok", "coredumps": "ok"})
        self.assertEqual(runner.call_count, 2)
        for call in runner.call_args_list:
            self.assertIn("--boot=11111111222233334444555555555555", call.args[0])
            for key in ("LD_PRELOAD", "LD_LIBRARY_PATH", "LD_AUDIT"):
                self.assertNotIn(key, call.kwargs["env"])
        self.assertEqual((self.logs / "kernel-access.log").read_text(), "")

    def test_invalid_boot_id_does_not_collect_from_the_wrong_boot(self):
        self.logs.mkdir(parents=True)
        with mock.patch.object(diagnostics.subprocess, "run") as runner:
            statuses = diagnostics.capture_journal(self.logs, {"started_at": diagnostics.now(), "boot_id": "unknown"})
        runner.assert_not_called()
        self.assertEqual(statuses["kernel"], "unavailable")

    def test_missing_executable_is_recorded(self):
        code = diagnostics.monitor(self.root, self.logs, ["/nonexistent/bc250-command"],
            collector=lambda *_: {})
        self.assertEqual(code, 127)
        self.assertEqual(diagnostics.read_json(self.logs / "session.json")["status"], "failed_to_start")

    def test_interrupted_session_is_not_fabricated_as_a_completed_crash(self):
        record = {"status": "running", "boot_id": "a-previous-boot", "elapsed_seconds": 45.0}
        self.assertEqual(diagnostics.effective_status(record), "incomplete")
        report = diagnostics.public_report(record)
        self.assertNotIn("ended_at", report)
        self.assertEqual(report["elapsed_seconds"], 45.0)

    def test_share_report_excludes_private_fields_and_raw_errors(self):
        record = {"status": "nonzero_exit", "exit_code": 7, "raw_log": "private-token",
            "command": ["private-token"], "boot_id": "private-token", "supervisor_pid": 42,
            "environment": {"kernel": "test", "HOME": "private-token",
                            "os": {"NAME": "Bazzite", "HOSTNAME": "private-token"}},
            "error_signatures": {"vulkan_device_lost": 1}}
        report = diagnostics.public_report(record)
        self.assertNotIn("private-token", json.dumps(report))
        self.assertNotIn("supervisor_pid", report)
        self.assertEqual(report["error_signatures"]["vulkan_device_lost"], 1)

    def test_source_archive_excludes_logs_binaries_and_personal_tar_owners(self):
        for name in diagnostics.SOURCE_FILES:
            (self.root / name).write_text("source fixture\n")
        self.logs.mkdir(parents=True)
        (self.logs / "secret.log").write_text("private-token")
        archive = diagnostics.community_bundle(self.root)
        with tarfile.open(archive) as bundle:
            self.assertEqual({Path(m.name).name for m in bundle.getmembers()}, set(diagnostics.SOURCE_FILES))
            self.assertTrue(all(m.uid == m.gid == 0 and m.uname == m.gname == "" for m in bundle.getmembers()))

    def test_supervisor_forwards_stop_and_writes_final_record(self):
        # Exercise the actual CLI and forwarding, without crashing any real app.
        process = subprocess.Popen([sys.executable, "-B", str(ROOT / "diagnostics.py"),
            "--root", str(self.root), "run", "--log-dir", str(self.logs), "--",
            sys.executable, "-B", "-c", "import time; print('ready',flush=True); time.sleep(30)"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if (self.logs / "console.log").exists() and "ready" in (self.logs / "console.log").read_text():
                    break
                time.sleep(0.02)
            else:
                self.fail("Test child did not start")
            process.send_signal(signal.SIGTERM)
            self.assertEqual(process.wait(timeout=22), 143)
            data = diagnostics.read_json(self.logs / "session.json")
            self.assertIn(signal.SIGTERM, data["received_signals"])
            self.assertEqual(data["status"], "signal_exit")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()


if __name__ == "__main__":
    unittest.main()
