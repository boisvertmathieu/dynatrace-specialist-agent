import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".agents" / "skills" / "dynatrace-specialist" / "scripts" / "dt_investigator.py"
spec = importlib.util.spec_from_file_location("investigator", SCRIPT)
agent = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent)


def result(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess([], returncode, stdout, stderr)


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.catalog = agent.configuration(ROOT / "config" / "services.example.json")

    def test_context_is_resolved_per_service(self):
        self.assertEqual(agent.resolve(self.catalog, "checkout-prod")[1], "prod-readonly")
        self.assertEqual(agent.resolve(self.catalog, "checkout-staging")[1], "staging-readonly")
        with self.assertRaises(agent.InvestigationError):
            agent.resolve(self.catalog, "checkout")

    def test_render_escapes_literal_instead_of_injecting_query(self):
        malicious = 'api" | fetch logs //'
        self.catalog["services"]["checkout-prod"]["selectors"]["metrics"][0]["value"] = malicious
        rendered = agent.render(self.catalog, "checkout-prod", "red")
        self.assertIn(json.dumps(malicious), rendered)
        self.assertNotIn("@@", rendered)
        self.assertIn("arraySum(requests)", rendered)
        self.assertIn("else: null", rendered)

    def test_all_templates_render_with_configured_signal(self):
        service = self.catalog["services"]["checkout-prod"]
        service["selectors"]["events"] = [{"field": "service.name", "value": "checkout-api"}]
        service["selectors"]["problems"] = [{"field": "affected_entity_ids", "value": "SERVICE-EXAMPLE", "operator": "contains"}]
        for template in agent.load_json(agent.SKILL / "queries" / "catalog.json"):
            with self.subTest(template=template):
                self.assertNotIn("@@", agent.render(self.catalog, "checkout-prod", template))

    def test_missing_selector_never_falls_back_to_unfiltered_read(self):
        with self.assertRaises(agent.InvestigationError):
            agent.render(self.catalog, "checkout-prod", "events")

    def test_untrusted_field_and_unbounded_limits_are_rejected(self):
        for mutate in ("field", "limit"):
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as tmp:
                data = copy.deepcopy(self.catalog)
                if mutate == "field":
                    data["services"]["checkout-prod"]["selectors"]["logs"][0]["field"] = "x | fetch logs"
                else:
                    data["limits"]["scan_gbytes"] = 0
                path = Path(tmp) / "catalog.json"
                path.write_text(json.dumps(data))
                with self.assertRaises(agent.InvestigationError):
                    agent.configuration(path)


class WindowAndQueryTests(unittest.TestCase):
    def test_offset_is_normalized_and_timezone_is_required(self):
        self.assertEqual(agent.iso(agent.timestamp("2026-10-14T12:00:00-04:00")), "2026-10-14T16:00:00Z")
        with self.assertRaises(agent.InvestigationError):
            agent.timestamp("2026-10-14T12:00:00")

    def test_invalid_or_oversized_windows_fail(self):
        for left, right in (("2026-10-14T12:00:00Z", "2026-10-14T12:00:00Z"),
                            ("2026-10-14T12:00:00Z", "2026-10-16T12:00:00Z")):
            with self.assertRaises(agent.InvestigationError):
                agent.window(left, right, agent.DEFAULT_LIMITS)

    def test_source_overrides_are_rejected_but_literal_words_are_safe(self):
        for query in ("fetch logs, from: now()-30d", "fetch logs, scanLimitGBytes:100",
                      "fetch spans, samplingRatio:100", "timeseries avg(x), shift:-7d"):
            with self.subTest(query=query), self.assertRaises(agent.InvestigationError):
                agent.validate_dql(query)
        agent.validate_dql('fetch logs | filter content == "from: now()-30d" // scanLimitGBytes: 999')

    def test_credentials_and_emails_are_redacted(self):
        data = agent.redact({"Authorization": "sensitive", "content": "Bearer abcd.def token=unsafe a@example.com dt0s16.abc.secret"})
        self.assertEqual(data["Authorization"], "[REDACTED]")
        for secret in ("abcd.def", "unsafe", "a@example.com", "dt0s16.abc.secret"):
            self.assertNotIn(secret, data["content"])


class CollectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.config = self.folder / "dtctl.yaml"
        self.config.write_text("test configuration")
        self.collector = agent.Collector(sys.executable, self.config, "prod-readonly", dict(agent.DEFAULT_LIMITS))
        self.evidence = self.folder / "evidence.json"
        self.calls = []

    def tearDown(self):
        self.tmp.cleanup()

    def run_fake(self, args, **kwargs):
        self.calls.append((args, kwargs))
        self.assertFalse(kwargs["shell"])
        self.assertEqual(args[args.index("--context") + 1], "prod-readonly")
        self.assertEqual(args[args.index("--config") + 1], str(self.config.resolve()))
        self.assertIn("--no-agent", args)
        self.assertTrue(Path(kwargs["cwd"]).is_dir())
        self.assertNotIn("DTCTL_CONTEXT", kwargs["env"])
        if "verify" in args:
            return result('{"valid": true}')
        return result(json.dumps({"records": [{"value": "42", "authorization": "unsafe"}],
                                  "metadata": {"sampled": False, "approximations": None, "notifications": []}}))

    def collect(self):
        return self.collector.collect("fetch logs | summarize value=count()", "2026-10-14T12:00:00Z",
                                      "2026-10-14T13:00:00Z", "checkout-prod", "test", self.evidence)

    def test_verified_read_only_query_has_explicit_limits_and_evidence(self):
        with patch.dict(os.environ, {"DTCTL_CONTEXT": "wrong", "DTCTL_SPILL": "always"}), patch.object(agent.subprocess, "run", side_effect=self.run_fake):
            evidence = self.collect()
        self.assertEqual(evidence["status"], "ok")
        self.assertEqual(evidence["records"][0]["authorization"], "[REDACTED]")
        self.assertEqual(agent.load_json(self.evidence)["id"], evidence["id"])
        args, kwargs = self.calls[1]
        self.assertEqual(kwargs["input"], "fetch logs | summarize value=count()")
        for flag in ("--max-result-records", "--max-result-bytes", "--default-scan-limit-gbytes",
                     "--fetch-timeout-seconds", "--enforce-query-consumption-limit",
                     "--metadata=all", "--spill=never", "--compact=false"):
            self.assertIn(flag, args)
        self.assertNotIn("apply", args)
        self.assertNotIn("exec", args)

    def test_failed_verification_does_not_execute_query(self):
        with patch.object(self.collector, "invoke", return_value=result('{"valid":false}', returncode=1)) as invoke:
            evidence = self.collect()
        self.assertEqual(invoke.call_count, 1)
        self.assertEqual(evidence["status"], "error")

    def test_partial_sampled_and_capped_results_require_review(self):
        cases = [({"sampled": True}, "", [{}]), ({"approximations": ["rollup"]}, "", [{}]),
                 ({"notifications": [{"severity": "WARN"}]}, "", [{}]), ({}, "scan limit reached", [{}]),
                 ({}, "", [{}] * agent.DEFAULT_LIMITS["records"])]
        for i, (metadata, warning, records) in enumerate(cases):
            with self.subTest(case=i):
                target = self.folder / (str(i) + ".json")
                with patch.object(self.collector, "invoke", side_effect=[result("{}"), result(json.dumps({"records": records, "metadata": metadata}), warning)]):
                    evidence = self.collector.collect("fetch logs", "2026-10-14T12:00:00Z",
                                                     "2026-10-14T13:00:00Z", "service", "test", target)
                self.assertEqual(evidence["status"], "review_required")

    def test_empty_result_is_not_rewritten_as_zero(self):
        with patch.object(self.collector, "invoke", side_effect=[result("{}"), result('{"records": [], "metadata": {}}')]):
            evidence = self.collect()
        self.assertEqual(evidence["records"], [])
        self.assertIn("instrumentation", evidence["coverage"])

    def test_timeout_or_malformed_payload_is_saved_as_error(self):
        for i, response in enumerate((subprocess.TimeoutExpired("dtctl", 70), result('{"records":"csv text"}'))):
            with self.subTest(case=i), patch.object(self.collector, "invoke", side_effect=[result("{}"), response]):
                evidence = self.collector.collect("fetch logs", "2026-10-14T12:00:00Z",
                                                 "2026-10-14T13:00:00Z", "service", "test", self.folder / (str(i) + ".json"))
                self.assertEqual(evidence["status"], "error")

    def test_budget_and_existing_file_fail_before_new_collection(self):
        self.collector.queries = self.collector.limits["query_budget"]
        with patch.object(self.collector, "invoke") as invoke:
            with self.assertRaises(agent.InvestigationError):
                self.collect()
            invoke.assert_not_called()
        self.evidence.write_text("preserve")
        with self.assertRaises(agent.InvestigationError):
            self.collect()
        self.assertEqual(self.evidence.read_text(), "preserve")

    def test_readwrite_context_is_rejected_by_doctor(self):
        flags = " ".join(["--default-timeframe-start", "--default-timeframe-end", "--default-scan-limit-gbytes",
                         "--max-result-records", "--max-result-bytes", "--fetch-timeout-seconds", "--metadata",
                         "--no-progress", "--spill", "--series", "--precision", "--compact",
                         "--enforce-query-consumption-limit", "--default-sampling-ratio"])
        with patch.object(self.collector, "invoke", side_effect=[result("0.40.0"), result(flags), result("help"),
                                                               result("Safety Level: readwrite-all\n")]):
            with self.assertRaises(agent.InvestigationError):
                self.collector.doctor()


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.baseline = {"schema_version": 1, "id": "baseline", "status": "ok", "context": "prod-readonly",
                         "service": "checkout-prod", "query_sha256": "same-query",
                         "start": "2026-10-14T12:00:00Z", "end": "2026-10-14T13:00:00Z",
                         "records": [{"endpoint": "a", "value": "100"}, {"endpoint": "zero", "value": 0},
                                     {"endpoint": "gone", "value": 5}]}
        self.current = {**copy.deepcopy(self.baseline), "id": "current",
                        "start": "2026-10-14T13:00:00Z", "end": "2026-10-14T14:00:00Z",
                        "records": [{"endpoint": "a", "value": 125}, {"endpoint": "zero", "value": 4},
                                    {"endpoint": "new", "value": 9}]}

    def compare(self):
        return agent.compare(self.baseline, self.current, ["endpoint"], "value", "requests")

    def test_numeric_strings_zero_baseline_and_disappeared_series(self):
        rows = {row["dimensions"]["endpoint"]: row for row in self.compare()["records"]}
        self.assertEqual(rows["a"]["delta_pct"], 25)
        self.assertIsNone(rows["zero"]["delta_pct"])
        self.assertEqual(rows["zero"]["reason"], "zero_baseline")
        self.assertEqual(rows["gone"]["state"], "missing_data")
        self.assertIsNone(rows["new"]["baseline"])

    def test_incompatible_evidence_is_rejected(self):
        for key, value in (("context", "other"), ("service", "other"), ("query_sha256", "other"),
                           ("status", "review_required"), ("end", "2026-10-14T15:00:00Z"),
                           ("start", "2026-10-14T12:30:00Z")):
            with self.subTest(key=key):
                original = copy.deepcopy(self.current)
                self.current[key] = value
                with self.assertRaises(agent.InvestigationError):
                    self.compare()
                self.current = original

    def test_duplicate_dimensions_and_non_scalar_values_fail(self):
        self.current["records"].append({"endpoint": "a", "value": 1})
        with self.assertRaises(agent.InvestigationError):
            self.compare()
        self.current["records"] = [{"endpoint": "a", "value": [1, 2]}]
        with self.assertRaises(agent.InvestigationError):
            self.compare()


class WorkflowTests(unittest.TestCase):
    def test_triage_stops_after_failure_and_records_skipped_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "case"
            config = Path(tmp) / "dtctl.yaml"
            config.write_text("dummy")
            with patch.object(agent.Collector, "doctor", return_value={"tenant_connection": "not_tested"}), patch.object(agent.Collector, "invoke", return_value=result("forbidden", returncode=2)) as invoke:
                code = agent.main(["triage", "--config", str(ROOT / "config" / "services.example.json"),
                                  "--service", "checkout-prod", "--dtctl", sys.executable,
                                  "--dtctl-config", str(config), "--start", "2026-10-14T12:00:00Z",
                                  "--end", "2026-10-14T13:00:00Z", "--out", str(out)])
            self.assertEqual(code, 1)
            self.assertEqual(invoke.call_count, 1)
            manifest = agent.load_json(out / "manifest.json")
            self.assertIn("stopped", manifest)
            self.assertEqual(manifest["evidence"][0]["status"], "error")

    def test_specialist_can_be_installed_without_network_and_preserves_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            command = [sys.executable, str(ROOT / "tools" / "install_skills.py"),
                       "--specialist-only", "--destination", tmp]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            self.assertTrue((Path(tmp) / "dynatrace-specialist" / "queries" / "red.dql").is_file())
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(second.returncode, 1)
            self.assertIn("Existing skill preserved", second.stdout)


if __name__ == "__main__":
    unittest.main()
