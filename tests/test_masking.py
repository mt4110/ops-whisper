"""Masking contracts tested with retained synthetic files and isolated workers."""

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from ops_whisper import cli, masking


ROOT = Path(__file__).resolve().parents[1]


class MaskingTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="ops-whisper-mask-test-"))

    def write(self, name, text):
        path = self.work / name
        path.write_text(text, encoding="utf-8")
        return path

    def policy(self, patterns=(), builtins=None):
        body = "schema_version = 1\n"
        if builtins is not None:
            body += "builtins = " + json.dumps(builtins) + "\n"
        for i, pattern in enumerate(patterns):
            body += "\n[[rules]]\nid = \"demo-" + str(i) + "\"\n"
            body += "pattern = " + json.dumps(pattern) + '\naction = "mask"\n'
        return self.write("policy.toml", body)

    def command(self, query, source, policy, *extra):
        return subprocess.run([sys.executable, str(ROOT / "ops-whisper"), "search", "--root", str(source),
                               "--mask-rules", str(policy), "--json", *extra, "--", query],
                              capture_output=True, text=True, timeout=6)

    def invoke(self, query, source, policy, *extra):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["search", query, "--root", str(source), "--mask-rules", str(policy), "--json", *extra])
        return code, out.getvalue(), err.getvalue()

    def test_builtins_mask_context_and_preserve_source(self):
        source = self.write("input.txt", "needle\nAuthorization: Bearer DEMO-BEARER\npassword='DEMO PASSWORD'\n")
        before = hashlib.sha256(source.read_bytes()).digest()
        result = self.command("needle", source, self.policy())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("DEMO-BEARER", result.stdout)
        self.assertNotIn("DEMO PASSWORD", result.stdout)
        data = json.loads(result.stdout)
        self.assertEqual(data["stats"]["matched_lines"], 1)
        self.assertEqual(data["scope"]["query"], "[WITHHELD]")
        self.assertEqual(data["masking"]["spans"], 2)
        self.assertTrue(data["redacted"])
        self.assertEqual([row["line"] for row in data["lines"]], [1, 2, 3])
        self.assertEqual(before, hashlib.sha256(source.read_bytes()).digest())

    def test_private_key_middle_without_markers_is_masked(self):
        source = self.write("key.txt", "-----BEGIN PRIVATE KEY-----\nDEMO-FIRST\nDEMO-MIDDLE\n-----END PRIVATE KEY-----\n")
        result = self.command("DEMO-MIDDLE", source, self.policy(), "--context", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(len(data["lines"]), 1)
        self.assertEqual(data["lines"][0]["line"], 3)
        self.assertEqual(data["lines"][0]["text"], "*" * len("DEMO-MIDDLE"))
        self.assertNotIn("DEMO-MIDDLE", result.stdout)

    def test_unclosed_private_key_masks_to_end_of_file(self):
        source = self.write("key.txt", "-----BEGIN RSA PRIVATE KEY-----\nDEMO-UNCLOSED\nneedle\n")
        result = self.command("needle", source, self.policy(), "--context", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["lines"][0]["text"], "******")

    def test_custom_multiline_rule_runs_before_excerpt(self):
        source = self.write("custom.txt", "BEGIN-DEMO\nSECRET-LINE\nEND-DEMO\n")
        result = self.command("SECRET-LINE", source, self.policy([r"BEGIN-DEMO[\s\S]*?END-DEMO"], []),
                              "--context", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["lines"][0]["text"], "*" * 11)

    def test_overlapping_rules_union_whole_matches(self):
        source = self.write("overlap.txt", "DEMO-SECRET-TAIL\n")
        result = self.command("SECRET", source, self.policy(["DEMO-SECRET", "SECRET-TAIL"], []))
        data = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data["lines"][0]["text"], "*" * 16)
        self.assertEqual(data["masking"]["spans"], 1)
        self.assertEqual(data["masking"]["characters"], 16)

    def test_late_match_clipping_does_not_escape_a_mask(self):
        source = self.write("long.txt", "x" * 100 + "BEGIN-DEMO" + "a" * 400 + "needle" + "END-DEMO\n")
        result = self.command("needle", source, self.policy(["BEGIN-DEMO.*END-DEMO"], []),
                              "--context", "0", "--line-chars", "32")
        data = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data["lines"][0]["column_start"], 501)
        self.assertEqual(data["lines"][0]["text"], "*" * 24)
        self.assertTrue(data["lines"][0]["clipped"])

    def test_unicode_crlf_and_unicode_separator_keep_line_positions(self):
        source = self.work / "unicode.txt"
        source.write_bytes("前置\u2028needle\r\npassword=架空秘密\r\n終わり".encode())
        result = self.command("needle", source, self.policy())
        data = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([row["line"] for row in data["lines"]], [1, 2, 3])
        self.assertEqual(data["lines"][1]["text"], "*" * len("password=架空秘密"))

    def test_escaped_and_unclosed_quoted_credentials(self):
        source = self.write("quoted.txt", 'needle\n"password": "DEMO\\\" QUOTED SECRET"\npassword="DEMO UNCLOSED\n')
        result = self.command("needle", source, self.policy())
        self.assertEqual(result.returncode, 0, result.stderr)
        for secret in ("DEMO", "QUOTED", "UNCLOSED"):
            self.assertNotIn(secret, result.stdout)

    def test_custom_flags_and_disabled_rule(self):
        policy = self.write("flags.toml", '''schema_version = 1
builtins = []
[[rules]]
id = "active"
pattern = 'OTHER'
action = "mask"
flags = ["IGNORECASE"]
[[rules]]
id = "disabled"
pattern = 'DEMO'
action = "mask"
enabled = false
''')
        source = self.write("flags.txt", "DEMO other\n")
        result = self.command("other", source, policy)
        data = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(data["lines"][0]["text"], "DEMO *****")
        self.assertEqual(data["masking"]["rule_count"], 1)

    def test_no_matches_still_applies_valid_policy(self):
        source = self.write("no-hit.txt", "other\n")
        result = self.command("needle", source, self.policy())
        self.assertEqual(result.returncode, 1, result.stderr)
        data = json.loads(result.stdout)
        self.assertTrue(data["redacted"])
        self.assertEqual(data["masking"]["files_checked"], 0)

    def test_invalid_policy_has_no_fallback_or_values_in_diagnostics(self):
        source = self.write("source.txt", "needle DEMO-SOURCE-SECRET\n")
        cases = [
            'schema_version = true',
            'schema_version = 1\nunknown = "DEMO-CONFIG-SECRET"',
            'schema_version = 1\nbuiltins = ["DEMO-CONFIG-SECRET"]',
            'schema_version = 1\nbuiltins = []',
            'schema_version = 1\nbuiltins = ["bearer", "bearer"]',
            'schema_version = 1\n[[rules]]\nid = "bearer"\npattern = "x"\naction = "mask"',
            'schema_version = 1\n[[rules]]\nid = "demo"\npattern = "x"\naction = "alias"',
            'schema_version = 1\n[[rules]]\nid = "demo"\npattern = "x"\naction = "mask"\nenabled = "true"',
            'schema_version = 1\n[[rules]]\nid = "demo"\npattern = "x"\naction = "mask"\nflags = [false]',
            'schema_version = 1\n[[rules]]\nid = "demo"\npattern = "x"\naction = "mask"\nflags = ["IGNORECASE", "IGNORECASE"]',
            'schema_version = 1\nDEMO-CONFIG-SECRET = [',
        ]
        for i, body in enumerate(cases):
            with self.subTest(case=i):
                result = self.command("needle", source, self.write(f"invalid-{i}.toml", body + "\n"))
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertNotIn("DEMO-CONFIG-SECRET", result.stderr)
                self.assertNotIn("DEMO-SOURCE-SECRET", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_invalid_and_zero_width_regex_rejected_even_without_hits(self):
        source = self.write("source.txt", "needle DEMO-SECRET\n")
        for i, pattern in enumerate(("(", "a*", "(?=needle)")):
            policy = self.write(f"regex-{i}.toml", 'schema_version = 1\n[[rules]]\nid = "demo"\naction = "mask"\npattern = ' + json.dumps(pattern) + "\n")
            result = self.command("needle" if i == 2 else "absent", source, policy)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertNotIn("DEMO-SECRET", result.stderr)

    def test_binary_or_invalid_utf8_outside_excerpt_rejects_whole_result(self):
        policy = self.policy()
        for i, suffix in enumerate((b"\x00", b"\xff")):
            source = self.work / f"bad-{i}.txt"
            source.write_bytes(b"needle\n" + b"other\n" * 10 + suffix)
            result = self.command("needle", source, policy, "--context", "0")
            self.assertEqual(result.returncode, 3)
            self.assertEqual(result.stdout, "")

    def test_size_and_total_limits_return_no_partial_result(self):
        policy = self.policy()
        source = self.write("a.txt", "needle\n")
        with patch.object(masking, "MAX_FILE_BYTES", 6):
            code, out, err = self.invoke("needle", source, policy)
        self.assertEqual(code, 3)
        self.assertEqual(out, "")
        self.assertIn("mask_input_limit", err)
        self.write("b.txt", "needle\n")
        with patch.object(masking, "MAX_TOTAL_BYTES", 10):
            code, out, err = self.invoke("needle", self.work, policy, "--glob", "*.txt")
        self.assertEqual(code, 3)
        self.assertEqual(out, "")
        self.assertIn("mask_input_limit", err)

    def test_span_limit_has_no_partial_result(self):
        source = self.write("many.txt", "needle\n" + "x" * (masking.MAX_SPANS + 1))
        result = self.command("needle", source, self.policy(["x"], []), "--context", "0")
        self.assertEqual(result.returncode, 3, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("mask_span_limit", result.stderr)

    def test_search_source_mismatch_returns_no_result(self):
        source = self.write("changed.txt", "needle DEMO-CHANGED\n")
        policy = self.policy()
        previous = masking.FileMask(["needle old\n"], ["****** ***\n"], 11, 1, 9)
        with patch.object(masking, "mask_file", return_value=previous):
            code, out, err = self.invoke("needle", source, policy)
        self.assertEqual(code, 3)
        self.assertEqual(out, "")
        self.assertIn("mask_input_changed", err)
        self.assertNotIn("DEMO-CHANGED", err)

    def test_policy_link_fifo_and_excessive_file_are_refused(self):
        policy = self.policy()
        link = self.work / "policy-link.toml"
        link.symlink_to(policy)
        fifo = self.work / "policy-fifo"
        os.mkfifo(fifo)
        huge = self.write("huge.toml", "x" * (masking.MAX_CONFIG_BYTES + 1))
        source = self.write("source.txt", "needle\n")
        for path in (link, fifo, huge):
            with self.subTest(path=path.name):
                result = self.command("needle", source, path)
                self.assertEqual(result.returncode, 3)
                self.assertEqual(result.stdout, "")

    def test_regex_deadline_reaps_worker_and_rg_without_result(self):
        source = self.write("slow.txt", "needle\n" + "a" * 50 + "!\n")
        policy = self.policy(["(a+)+$"], [])
        processes = []
        real_popen = subprocess.Popen

        def capture(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            processes.append(process)
            return process

        with patch.object(masking.subprocess, "Popen", side_effect=capture):
            code, out, err = self.invoke("needle", source, policy, "--timeout", "0.7")
        self.assertEqual(code, 3)
        self.assertEqual(out, "")
        self.assertIn("mask_timeout", err)
        self.assertGreaterEqual(len(processes), 1)
        for process in processes:
            self.assertIsNotNone(process.poll())
            with self.assertRaises(ProcessLookupError):
                os.kill(process.pid, 0)

    def test_worker_bad_spans_and_stderr_are_not_forwarded(self):
        real_popen = subprocess.Popen
        body = "import sys; sys.stdin.read(); sys.stderr.write('DEMO-STDERR-SECRET'); print('{\"spans\":[[0,999]]}')"

        def fake(*args, **kwargs):
            return real_popen([sys.executable, "-c", body], **kwargs)

        with patch.object(masking.subprocess, "Popen", side_effect=fake), self.assertRaises(masking.MaskError) as caught:
            masking.run_worker(masking.Policy((masking.Rule("demo", "x"),)), "DEMO", time.monotonic() + 5)
        self.assertEqual(caught.exception.code, "mask_worker")
        self.assertNotIn("DEMO", str(caught.exception))

    def test_worker_interrupt_reaps_child(self):
        real_popen = subprocess.Popen
        processes = []

        def interrupted(*args, **kwargs):
            process = real_popen(*args, **kwargs)
            communicate = process.communicate
            called = False

            def once(*call_args, **call_kwargs):
                nonlocal called
                if not called:
                    called = True
                    raise KeyboardInterrupt
                return communicate(*call_args, **call_kwargs)

            process.communicate = once
            processes.append(process)
            return process

        with patch.object(masking.subprocess, "Popen", side_effect=interrupted), self.assertRaises(KeyboardInterrupt):
            masking.run_worker(masking.Policy((masking.Rule("demo", "x"),)), "demo", time.monotonic() + 5)
        self.assertIsNotNone(processes[0].poll())

    def test_changed_source_metadata_is_rejected(self):
        source = self.write("identity.txt", "needle\n")
        view = masking.mask_file(source, masking.Policy((masking.Rule("demo", "needle"),)),
                                 time.monotonic() + 5, masking.MAX_FILE_BYTES)
        # A stale fingerprint simulates a detected replacement without editing files.
        view.identity = (0, 0, 0, 0, 0)
        with self.assertRaises(masking.MaskError) as caught:
            view.verify_source(source, time.monotonic() + 5)
        self.assertEqual(caught.exception.code, "mask_input_changed")

    def test_packaged_synthetic_policy_is_valid(self):
        policy = masking.load_policy(ROOT / "examples/masking.synthetic.toml", time.monotonic() + 5)
        self.assertEqual(policy.active_count, 4)

    def test_quoted_credential_middle_is_masked_with_or_without_end_quote(self):
        policy = self.policy()
        for i, ending in enumerate(('DEMO-END"\n', "DEMO-END\\")):
            source = self.write(f"quoted-block-{i}.txt", 'password="DEMO-START\nDEMO-MIDDLE\n' + ending)
            result = self.command("DEMO-MIDDLE", source, policy, "--context", "0")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("DEMO-MIDDLE", result.stdout)
            self.assertEqual(json.loads(result.stdout)["lines"][0]["text"], "*" * 11)

    def test_masked_json_still_obeys_whole_response_budget(self):
        source = self.write("budget.txt", ("needle password=DEMO-SECRET\n") * 50)
        result = self.command("needle", source, self.policy(), "--max-chars", "1600", "--context", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLessEqual(len(result.stdout), 1600)
        self.assertNotIn("DEMO-SECRET", result.stdout)
        data = json.loads(result.stdout)
        self.assertEqual(data["stats"]["matched_lines"], 50)
        self.assertEqual(data["display"]["returned_match_lines"] + data["display"]["omitted_match_lines"], 50)
        self.assertTrue(data["display"]["truncated"])


if __name__ == "__main__":
    unittest.main()
