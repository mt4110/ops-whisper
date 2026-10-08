"""Real-rg and subprocess-boundary tests using retained synthetic fixtures."""

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ops_whisper import cli


ROOT = Path(__file__).resolve().parents[1]


class SearchTests(unittest.TestCase):
    def setUp(self):
        # No automatic deletion: fixtures contain synthetic data and remain in temp.
        self.work = Path(tempfile.mkdtemp(prefix="ops-whisper-test-"))

    def write(self, name, text):
        path = self.work / name
        path.write_text(text, encoding="utf-8")
        return path

    def command(self, query, root=None, *extra, env=None):
        return subprocess.run([sys.executable, str(ROOT / "ops-whisper"), "search",
                               "--root", str(root or self.work), "--json", *extra, "--", query],
                              capture_output=True, text=True, env=env, timeout=5)

    def test_literal_unicode_crlf_and_source_preservation(self):
        source = self.work / "日本語.txt"
        source.write_bytes("前置き\r\n対象.* 対象.*\r\n対象.*".encode())
        before = hashlib.sha256(source.read_bytes()).digest()
        result = self.command("対象.*", source, "--context", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["stats"]["matched_lines"], 2)
        self.assertEqual(payload["stats"]["occurrences"], 3)
        self.assertEqual([r["line"] for r in payload["lines"]], [1, 2, 3])
        self.assertEqual(payload["lines"][1]["text"], "対象.* 対象.*")
        self.assertEqual(before, hashlib.sha256(source.read_bytes()).digest())

    def test_glob_hidden_ignore_and_link_scope(self):
        (self.work / ".git").mkdir()
        self.write(".gitignore", "ignored.txt\n")
        self.write("a.py", "needle\n")
        self.write("b.txt", "needle\n")
        self.write("ignored.txt", "needle\n")
        self.write(".hidden.py", "needle\n")
        (self.work / ".private").mkdir()
        self.write(".private/visible.py", "needle\n")
        outside = Path(tempfile.mkdtemp(prefix="ops-whisper-outside-")) / "outside.py"
        outside.write_text("needle\n")
        (self.work / "linked.py").symlink_to(outside)
        result = self.command("needle", self.work, "--glob", "*.py")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["stats"]["matched_lines"], 1)
        self.assertEqual([r["path"] for r in payload["lines"]], ["./a.py"])

    def test_configuration_file_is_not_executed(self):
        source = self.write("case.txt", "needle\nNEEDLE\n")
        config = self.write("rg-config.txt", "--ignore-case\n--pre\nnonexistent-command\n")
        env = dict(os.environ, RIPGREP_CONFIG_PATH=str(config))
        result = self.command("needle", source, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["stats"]["matched_lines"], 1)

    def test_positive_glob_can_include_ignored_visible_files(self):
        (self.work / ".git").mkdir()
        self.write(".gitignore", "ignored.py\n")
        self.write("visible.py", "needle\n")
        self.write("ignored.py", "needle\n")
        plain = json.loads(self.command("needle").stdout)
        explicit = json.loads(self.command("needle", self.work, "--glob", "*.py").stdout)
        self.assertEqual(plain["stats"]["matched_lines"], 1)
        self.assertEqual(explicit["stats"]["matched_lines"], 2)

    def test_metadata_over_budget_returns_no_result(self):
        source = self.write("short.txt", "needle\n")
        result = self.command("needle" + "x" * 2000, source, "--max-chars", "512")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertIn("output_limit", result.stderr)

    def test_context_does_not_cross_files(self):
        self.write("a.txt", "needle\nend\n")
        self.write("b.txt", "start\nneedle\n")
        payload = json.loads(self.command("needle", self.work, "--context", "1").stdout)
        self.assertEqual([(r["path"], r["line"]) for r in payload["lines"]],
                         [("./a.txt", 1), ("./a.txt", 2), ("./b.txt", 1), ("./b.txt", 2)])

    def test_match_limit_keeps_exact_total(self):
        source = self.write("many.txt", "needle\n" * 100)
        result = self.command("needle", source, "--max-results", "3", "--context", "0")
        payload = json.loads(result.stdout)
        self.assertEqual(payload["stats"]["matched_lines"], 100)
        self.assertEqual(payload["display"]["returned_match_lines"], 3)
        self.assertEqual(payload["display"]["omitted_match_lines"], 97)
        self.assertTrue(payload["display"]["truncated"])
        self.assertTrue(payload["scan_completed"])

    def test_context_can_include_a_nonselected_match_without_bad_counts(self):
        source = self.write("context.txt", "before\nneedle\nneedle\nafter\n")
        result = self.command("needle", source, "--max-results", "1", "--context", "1")
        payload = json.loads(result.stdout)
        self.assertEqual([r["line"] for r in payload["lines"]], [1, 2, 3])
        self.assertEqual(payload["display"]["selected_match_lines"], 1)
        self.assertEqual(payload["display"]["returned_match_lines"], 2)
        self.assertEqual(payload["display"]["omitted_match_lines"], 0)
        self.assertTrue(payload["display"]["truncated"])

    def test_whole_json_response_budget(self):
        source = self.write("budget.txt", ("needle " + "x" * 300 + "\n") * 25)
        result = self.command("needle", source, "--max-chars", "1000", "--context", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLessEqual(len(result.stdout), 1000)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["display"]["truncated"])
        self.assertEqual(payload["stats"]["matched_lines"], 25)
        self.assertEqual(payload["display"]["returned_match_lines"] +
                         payload["display"]["omitted_match_lines"], 25)

    def test_text_output_budget(self):
        source = self.write("text.txt", ("needle " + "x" * 400 + "\n") * 20)
        result = subprocess.run([sys.executable, str(ROOT / "ops-whisper"), "search", "needle",
                                 "--root", str(source), "--max-chars", "700"],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLessEqual(len(result.stdout), 700)
        self.assertIn("truncated=true", result.stdout)

    def test_excerpt_centers_on_a_late_unicode_match(self):
        source = self.write("long.txt", "あ" * 2000 + "needle" + "い" * 300 + "\n")
        result = self.command("needle", source, "--line-chars", "64")
        row = json.loads(result.stdout)["lines"][0]
        self.assertTrue(row["clipped"])
        self.assertIn("needle", row["text"])
        self.assertEqual(row["column_start"], 1980)
        self.assertEqual(len(row["text"]), 64)

    def test_terminal_controls_are_visible(self):
        source = self.write("control\x1b.txt", "needle\x1b[31m\u202evalue\tend\n")
        result = self.command("needle", source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("\x1b", result.stdout)
        self.assertNotIn("\u202e", result.stdout)
        self.assertIn(r"\u001b", json.loads(result.stdout)["lines"][0]["text"])
        self.assertIn(r"\u202e", json.loads(result.stdout)["lines"][0]["text"])

    def test_no_matches_is_a_complete_empty_result(self):
        source = self.write("empty.txt", "other\n")
        result = self.command("needle", source)
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["lines"], [])
        self.assertTrue(payload["scan_completed"])

    def test_escaped_path_names_remain_distinct(self):
        self.write("control\x1b.txt", "needle\n")
        self.write(r"control\u001b.txt", "needle\n")
        result = self.command("needle", self.work, "--context", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["stats"]["matched_lines"], 2)
        self.assertEqual(payload["display"]["returned_match_lines"], 2)
        self.assertEqual(len({item["path"] for item in payload["lines"]}), 2)
        self.assertFalse(payload["display"]["truncated"])

    def test_invalid_arguments_do_not_echo_values(self):
        for args in (["--max-results", "DEMO_ARGUMENT_SECRET"], ["--timeout", "nan"],
                     ["--max-chars", "100"], ["--context", "11"]):
            with self.subTest(args=args):
                result = self.command("needle", self.work, *args)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertNotIn("DEMO_ARGUMENT_SECRET", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_leading_dash_is_literal_and_not_an_option(self):
        source = self.write("dash.txt", "--help\n")
        result = self.command("--help", source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["stats"]["matched_lines"], 1)

    def test_root_link_fifo_and_missing_are_rejected(self):
        source = self.write("root.txt", "needle\n")
        link = self.work / "link.txt"
        link.symlink_to(source)
        fifo = self.work / "fifo"
        os.mkfifo(fifo)
        for root in (link, fifo, self.work / "DEMO_MISSING_SECRET"):
            with self.subTest(root=root):
                result = self.command("needle", root)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertNotIn("DEMO_MISSING_SECRET", result.stderr)

    def test_invalid_utf8_match_does_not_return_partial_text(self):
        source = self.work / "bytes.txt"
        source.write_bytes(b"needle good\nneedle \xff\n")
        result = self.command("needle", source)
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, "")
        self.assertIn("unsupported_text", result.stderr)

    def test_binary_match_does_not_return_partial_text(self):
        source = self.work / "binary.txt"
        source.write_bytes(b"needle good\nneedle\x00bad\n")
        result = self.command("needle", source)
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, "")

    def test_large_backend_record_is_rejected(self):
        source = self.write("huge.txt", "needle " + "x" * cli.MAX_EVENT_BYTES + "\n")
        result = self.command("needle", source)
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, "")
        self.assertIn("event_limit", result.stderr)

    def fake(self, body):
        fake = self.write("fake-rg", "#!/usr/bin/env python3\nimport json, os, sys, time\n" + body)
        fake.chmod(0o700)
        return fake

    def call_fake(self, body, *args):
        fake = self.fake(body)
        out, err = io.StringIO(), io.StringIO()
        with patch.object(cli.shutil, "which", return_value=str(fake)), redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["search", "needle", "--root", str(self.work), *args])
        return code, out.getvalue(), err.getvalue()

    def test_backend_failure_diagnostics_are_suppressed(self):
        code, out, err = self.call_fake("sys.stderr.write('DEMO_BACKEND_SECRET' * 10000)\nsys.exit(2)\n")
        self.assertEqual(code, 3)
        self.assertEqual(out, "")
        self.assertNotIn("DEMO_BACKEND_SECRET", err)
        self.assertIn("backend_failure", err)

    def test_malformed_backend_output_is_suppressed(self):
        code, out, err = self.call_fake("print('DEMO_MALFORMED_SECRET')\n")
        self.assertEqual(code, 3)
        self.assertEqual(out, "")
        self.assertNotIn("DEMO_MALFORMED_SECRET", err)
        self.assertIn("invalid_backend_output", err)

    def test_unfinished_summary_is_not_a_success(self):
        code, out, err = self.call_fake("sys.exit(0)\n")
        self.assertEqual(code, 3)
        self.assertEqual(out, "")
        self.assertIn("invalid_backend_output", err)

    def test_mismatched_summary_returns_no_result(self):
        body = "print(json.dumps({'type': 'summary', 'data': {'stats': {'matched_lines': 1, 'matches': 1}}}))\n"
        code, out, err = self.call_fake(body)
        self.assertEqual(code, 3)
        self.assertEqual(out, "")
        self.assertIn("invalid_backend_output", err)

    def test_timeout_reaps_child_and_returns_no_excerpts(self):
        processes = []
        real_popen = subprocess.Popen

        def capture(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            processes.append(process)
            return process

        with patch.object(cli.subprocess, "Popen", side_effect=capture):
            code, out, err = self.call_fake("time.sleep(10)\n", "--timeout", "0.2")
        self.assertEqual(code, 3)
        self.assertEqual(out, "")
        self.assertIn("timeout", err)
        self.assertIsNotNone(processes[0].poll())
        with self.assertRaises(ProcessLookupError):
            os.kill(processes[0].pid, 0)

    def test_closed_output_pipe_exits_without_diagnostics(self):
        source = self.write("pipe.txt", "needle\n")
        process = subprocess.Popen([sys.executable, str(ROOT / "ops-whisper"), "search",
                                    "needle", "--root", str(source)],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            process.stdout.close()
            self.assertEqual(process.wait(timeout=5), 141)
            self.assertEqual(process.stderr.read(), b"")
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
            process.stderr.close()

    def test_keyboard_interrupt_reaps_child(self):
        fake = self.fake("time.sleep(10)\n")
        processes = []
        real_popen = subprocess.Popen

        def capture(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            processes.append(process)
            return process

        out, err = io.StringIO(), io.StringIO()
        with patch.object(cli.shutil, "which", return_value=str(fake)), \
             patch.object(cli.subprocess, "Popen", side_effect=capture), \
             patch.object(cli.selectors.SelectSelector, "select", side_effect=KeyboardInterrupt), \
             patch.object(cli.selectors, "DefaultSelector", cli.selectors.SelectSelector), \
             redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["search", "needle", "--root", str(self.work)])
        self.assertEqual(code, 130)
        self.assertEqual(out.getvalue(), "")
        self.assertIsNotNone(processes[0].poll())

    def test_missing_rg_has_a_clear_error(self):
        with patch.object(cli.shutil, "which", return_value=None), self.assertRaises(cli.SearchError) as raised:
            cli.search(cli.Options("needle", self.work))
        self.assertEqual(raised.exception.code, "backend_unavailable")


if __name__ == "__main__":
    if shutil.which("rg") is None:
        raise SystemExit("Install rg before running the integration tests.")
    unittest.main()
