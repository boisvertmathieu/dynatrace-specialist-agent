#!/usr/bin/env python3
"""Bounded, read-only dtctl collection and evidence-aware metric comparison."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid

SKILL = Path(__file__).resolve().parents[1]
UTC = dt.timezone.utc
FIELD = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*\Z")
KEY = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*\Z")
SENSITIVE = re.compile(r"(?i)(password|passwd|secret|authorization|access.token|refresh.token|api.key|cookie)")
DEFAULT_LIMITS = {"scan_gbytes": 1, "records": 500, "result_bytes": 2000000,
                  "timeout_seconds": 60, "max_window_hours": 24, "query_budget": 20}
HARD_LIMITS = {"scan_gbytes": 10, "records": 5000, "result_bytes": 10000000,
               "timeout_seconds": 180, "max_window_hours": 168, "query_budget": 50}


class InvestigationError(ValueError):
    pass


def timestamp(value: str) -> dt.datetime:
    try:
        result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvestigationError("Use an ISO-8601 timestamp with an explicit UTC offset.") from exc
    if result.tzinfo is None:
        raise InvestigationError("A timezone offset is required; resolve local time before collecting.")
    return result.astimezone(UTC)


def iso(value: dt.datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def window(start: str, end: str, limits: dict) -> tuple[str, str]:
    left, right = timestamp(start), timestamp(end)
    if right <= left or (right - left).total_seconds() > limits["max_window_hours"] * 3600:
        raise InvestigationError("Window must be positive and within max_window_hours.")
    return iso(left), iso(right)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def configuration(path: Path) -> dict:
    data = load_json(path)
    if not isinstance(data, dict) or data.get("version") != 1 or not isinstance(data.get("contexts"), dict) or not isinstance(data.get("services"), dict):
        raise InvestigationError("Expected version 1, contexts and services objects.")
    if not isinstance(data.get("limits", {}), dict):
        raise InvestigationError("limits must be an object.")
    limits = {**DEFAULT_LIMITS, **data.get("limits", {})}
    if set(limits) != set(DEFAULT_LIMITS):
        raise InvestigationError("Unknown limit setting.")
    for key, value in limits.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 < value <= HARD_LIMITS[key]:
            raise InvestigationError("Invalid bounded limit: " + key)
        if key != "scan_gbytes" and int(value) != value:
            raise InvestigationError("Integer limit required: " + key)
    data["limits"] = limits
    for name, context in data["contexts"].items():
        if not KEY.fullmatch(name) or not isinstance(context, dict) or not isinstance(context.get("dtctl_context"), str) or not KEY.fullmatch(context["dtctl_context"]):
            raise InvestigationError("Invalid context mapping.")
    for name, service in data["services"].items():
        if not KEY.fullmatch(name) or not isinstance(service, dict) or service.get("context") not in data["contexts"]:
            raise InvestigationError("Invalid service or unknown context.")
        signals = service.get("selectors", {})
        if not isinstance(signals, dict):
            raise InvestigationError("selectors must be an object.")
        for signal, selectors in signals.items():
            if signal not in {"metrics", "logs", "spans", "events", "problems"} or not isinstance(selectors, list) or not selectors:
                raise InvestigationError("Invalid signal selectors.")
            for selector in selectors:
                if (not isinstance(selector, dict) or not isinstance(selector.get("field"), str) or not FIELD.fullmatch(selector["field"])
                    or not isinstance(selector.get("value"), str) or not selector["value"]
                    or selector.get("operator", "eq") not in {"eq", "contains"}):
                    raise InvestigationError("Invalid selector; use a field, literal value and eq/contains.")
        if "interval" in service and (not isinstance(service["interval"], str) or not re.fullmatch(r"[1-9][0-9]*(s|m|h)", service["interval"])):
            raise InvestigationError("Invalid timeseries interval.")
        metric_settings = service.get("metrics", {})
        if not isinstance(metric_settings, dict) or not set(metric_settings) <= {"response_time", "request_count", "failure_count"}:
            raise InvestigationError("Use response_time, request_count or failure_count metric mappings.")
        for key in metric_settings.values():
            if not isinstance(key, str) or not KEY.fullmatch(key):
                raise InvestigationError("Invalid metric key.")
    return data


def resolve(data: dict, service_name: str) -> tuple[dict, str]:
    # Aliases are resolved by the language-model agent, never by fuzzy matching here.
    if service_name not in data["services"]:
        raise InvestigationError("Unknown service. Choose an exact configured service key.")
    service = data["services"][service_name]
    return service, data["contexts"][service["context"]]["dtctl_context"]


def literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render(data: dict, service_name: str, template: str) -> str:
    service, _ = resolve(data, service_name)
    manifest = load_json(SKILL / "queries" / "catalog.json")
    if template not in manifest:
        raise InvestigationError("Unknown template.")
    signal = manifest[template]["signal"]
    selectors = service.get("selectors", {}).get(signal)
    if not selectors:
        raise InvestigationError("No verified " + signal + " selector for this service. Discover and configure it first.")
    predicates = []
    for selector in selectors:
        field, value = selector["field"], literal(selector["value"])
        if selector.get("operator", "eq") == "contains":
            predicates.append("in(" + value + ", " + field + ")")
        else:
            predicates.append(field + " == " + value)
    metrics = {"response_time": "dt.service.request.response_time",
               "request_count": "dt.service.request.count",
               "failure_count": "dt.service.request.failure_count", **service.get("metrics", {})}
    values = {"FILTER": " and ".join("(" + p + ")" for p in predicates),
              "INTERVAL": service.get("interval", "1m"),
              "DIMENSION": selectors[0]["field"],
              **{k.upper(): "`" + v + "`" for k, v in metrics.items()}}
    text = (SKILL / "queries" / (template + ".dql")).read_text(encoding="utf-8")
    text = re.sub(r"@@([A-Z_]+)@@", lambda match: values[match[1]], text)
    validate_dql(text)
    return text


def validate_dql(text: str):
    if not text.strip() or len(text.encode("utf-8")) > 64000:
        raise InvestigationError("DQL must be nonempty and smaller than 64 KB.")
    # Token masking handles quoted literals, quoted identifiers and comments, so
    # words inside a log-message predicate cannot be mistaken for source parameters.
    token = re.compile(r'"(?:\\.|[^"\\])*"|\x27(?:\\.|[^\x27\\])*\x27|`[^`]*`|//[^\n]*|/\*[\s\S]*?\*/')
    code = token.sub(" ", text)
    if re.search(r"\b(from|to|timeframe|scanLimitGBytes|samplingRatio)\s*:", code, re.I):
        raise InvestigationError("Use CLI start/end and limits, not DQL timeframe/scan/sampling overrides.")
    if re.search(r"\b(shift|timeShift)\s*[:(]", code, re.I):
        raise InvestigationError("Use a separate baseline query rather than a shifted source window.")
    if "{{" in text or "@@" in text:
        raise InvestigationError("Unresolved query template.")


def redact(value):
    if isinstance(value, dict):
        return {k: "[REDACTED]" if SENSITIVE.search(k) else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        value = re.sub(r"dt0[a-z][0-9]{2}\.[A-Za-z0-9._-]+", "[REDACTED_TOKEN]", value)
        value = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*", "Bearer [REDACTED]", value)
        value = re.sub(r"(?i)\b(password|passwd|secret|api[_-]?key|token)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]", value)
        value = re.sub(r"[A-Za-z0-9.!#$%&'*+/=?^_~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[REDACTED_EMAIL]", value)
    return value


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive write protects existing evidence against accidental replacement.
    with path.open("x", encoding="utf-8") as output:
        json.dump(value, output, indent=2, ensure_ascii=False, allow_nan=False)
        output.write("\n")
    try:
        path.chmod(0o600)
    except OSError:
        pass  # Windows users must restrict the parent directory's ACL separately.


class Collector:
    def __init__(self, executable: str, config_file: Path, context: str, limits: dict):
        resolved = shutil.which(executable)
        if not resolved:
            raise InvestigationError("dtctl executable missing. Install the official release first.")
        self.executable = str(Path(resolved).resolve())
        self.config_file = config_file.expanduser().resolve()
        if not self.config_file.is_file():
            raise InvestigationError("Provide an existing explicit dtctl config file outside the public repository.")
        self.context, self.limits, self.queries = context, limits, 0
        self.base = [self.executable, "--config", str(self.config_file),
                     "--context", context, "--no-agent", "--plain", "-o", "json"]

    def invoke(self, args: list[str], query: str | None = None) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        # Explicit config/context and output flags win; detach optional ambient
        # shaping/spill settings so a caller never silently receives a file manifest.
        for key in ("DTCTL_CONFIG", "DTCTL_CONTEXT", "DTCTL_SPILL", "DTCTL_SPILL_DIR", "DTCTL_AGENT"):
            env.pop(key, None)
        with tempfile.TemporaryDirectory(prefix="dt-investigate-") as cwd:
            return subprocess.run(self.base + args, input=query, text=True, encoding="utf-8",
                                  capture_output=True, timeout=self.limits["timeout_seconds"] + 10,
                                  cwd=cwd, env=env, shell=False, check=False)

    def doctor(self) -> dict:
        # Local capability checks; do not query the tenant or initiate authentication.
        info = self.invoke(["version"])
        query_help = self.invoke(["query", "--help"])
        verify_help = self.invoke(["verify", "query", "--help"])
        required = ["--default-timeframe-start", "--default-timeframe-end", "--default-scan-limit-gbytes",
                    "--max-result-records", "--max-result-bytes", "--fetch-timeout-seconds",
                    "--metadata", "--no-progress", "--spill", "--series", "--precision", "--compact",
                    "--enforce-query-consumption-limit", "--default-sampling-ratio"]
        missing = [flag for flag in required if flag not in query_help.stdout]
        if info.returncode or query_help.returncode or verify_help.returncode or missing:
            raise InvestigationError("Unsupported dtctl capabilities; use tested v0.40.0 or compatible. Missing: " + ", ".join(missing))
        description = self.invoke(["config", "describe-context", self.context])
        # v0.40.0 prints this safe description as text even with -o json.
        # Fail closed if a future version changes its shape.
        if description.returncode or not re.search(r"^Safety Level:\s+readonly\s*$", description.stdout, re.M):
            raise InvestigationError("The explicitly selected dtctl context must have safety-level readonly.")
        return {"dtctl": redact(info.stdout.strip()), "context": self.context,
                "capabilities": "ready", "safety_level": "readonly", "tenant_connection": "not_tested"}

    def collect(self, query: str, start: str, end: str, service: str, label: str, path: Path) -> dict:
        if path.exists():
            raise InvestigationError("Evidence output already exists; choose a new path before querying.")
        validate_dql(query)
        start, end = window(start, end, self.limits)
        if self.queries >= self.limits["query_budget"]:
            raise InvestigationError("Investigation query budget exhausted.")
        self.queries += 1
        evidence = {"schema_version": 1, "id": str(uuid.uuid4()), "service": service,
                    "context": self.context, "label": label, "start": start, "end": end,
                    "collected_at": iso(dt.datetime.now(UTC)), "query": redact(query),
                    "query_sha256": hashlib.sha256(query.encode()).hexdigest(),
                    "limits": self.limits, "status": "error", "warnings": [],
                    "redacted": True, "records": [], "metadata": {}}
        try:
            verified = self.invoke(["verify", "query", "-f", "-"], query)
            evidence["verification"] = {"exit_code": verified.returncode,
                                        "output": redact(verified.stdout.strip()),
                                        "warnings": redact(verified.stderr.strip())}
            if verified.returncode:
                raise InvestigationError("DQL verification failed; inspect the saved verification evidence.")
            args = ["query", "-f", "-", "--default-timeframe-start", start,
                    "--default-timeframe-end", end, "--timezone", "UTC",
                    "--default-scan-limit-gbytes", str(self.limits["scan_gbytes"]),
                    "--max-result-records", str(int(self.limits["records"])),
                    "--max-result-bytes", str(int(self.limits["result_bytes"])),
                    "--fetch-timeout-seconds", str(int(self.limits["timeout_seconds"])),
                    "--default-sampling-ratio", "1", "--enforce-query-consumption-limit",
                    "--metadata=all", "--include-types", "--series=full", "--precision", "0",
                    "--compact=false", "--spill=never", "--no-progress"]
            result = self.invoke(args, query)
            evidence["warnings"] = [redact(result.stderr.strip())] if result.stderr.strip() else []
            if result.returncode:
                raise InvestigationError("dtctl query failed: " + redact(result.stderr.strip() or result.stdout.strip()))
            payload = json.loads(result.stdout)
            if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
                raise InvestigationError("Unexpected dtctl result shape; no result was accepted.")
            if payload.get("metadata") is not None and not isinstance(payload["metadata"], dict):
                raise InvestigationError("Unexpected query metadata shape.")
            if any(not isinstance(record, dict) for record in payload["records"]):
                raise InvestigationError("Unexpected record shape.")
            evidence["records"] = redact(payload["records"])
            evidence["metadata"] = redact(payload.get("metadata") or {})
            evidence["types"] = payload.get("types", [])
            # Conservative: warnings, sampling or approximation require review.
            # Silence does NOT establish exhaustiveness; query-level limits remain.
            uncertain = bool(evidence["warnings"]) or len(evidence["records"]) >= self.limits["records"]
            uncertain |= bool(evidence["metadata"].get("approximations"))
            uncertain |= bool(evidence["metadata"].get("notifications"))
            uncertain |= evidence["metadata"].get("sampled") is True
            evidence["status"] = "review_required" if uncertain else "ok"
            evidence["coverage"] = "bounded_result; inspect metadata, query limits and instrumentation"
        except (InvestigationError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            evidence["error"] = redact(str(exc))
        digest = json.dumps(evidence["records"], sort_keys=True, ensure_ascii=False, allow_nan=False)
        evidence["records_sha256"] = hashlib.sha256(digest.encode()).hexdigest()
        write_json(path, evidence)
        return evidence


def numeric(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (ValueError, TypeError) as exc:
        raise InvestigationError("Expected scalar numbers; aggregate timeseries explicitly first.") from exc
    if not math.isfinite(result):
        raise InvestigationError("Non-finite value cannot be compared.")
    return result


def compare(baseline: dict, current: dict, dimensions: list[str], field: str, unit: str) -> dict:
    for item in (baseline, current):
        if item.get("schema_version") != 1 or item.get("status") != "ok":
            raise InvestigationError("Only successful evidence without review flags can be compared automatically.")
        if not isinstance(item.get("records"), list):
            raise InvestigationError("Missing records.")
    if (baseline["context"], baseline["service"], baseline["query_sha256"]) != (current["context"], current["service"], current["query_sha256"]):
        raise InvestigationError("Comparisons require the same context, service and DQL definition.")
    durations = [(timestamp(item["end"]) - timestamp(item["start"])).total_seconds() for item in (baseline, current)]
    if durations[0] <= 0 or durations[0] != durations[1]:
        raise InvestigationError("Equal positive window lengths required; normalize rates separately otherwise.")
    if max(timestamp(baseline["start"]), timestamp(current["start"])) < min(timestamp(baseline["end"]), timestamp(current["end"])):
        raise InvestigationError("Overlapping windows are not an independent baseline.")

    def index(rows):
        result = {}
        for row in rows:
            if any(key not in row or row[key] is None for key in dimensions):
                raise InvestigationError("Missing dimension; do not merge unidentified series.")
            key = tuple(json.dumps(row[key], sort_keys=True) for key in dimensions)
            if key in result:
                raise InvestigationError("Duplicate dimensions; aggregate before comparing.")
            result[key] = row
        return result

    left, right = index(baseline["records"]), index(current["records"])
    rows = []
    for key in sorted(set(left) | set(right)):
        a, b = left.get(key), right.get(key)
        old, new = numeric(a.get(field)) if a else None, numeric(b.get(field)) if b else None
        comparable = old is not None and new is not None
        delta = new - old if comparable else None
        rows.append({"dimensions": {name: json.loads(value) for name, value in zip(dimensions, key)},
                     "baseline": old, "current": new, "delta": delta,
                     "delta_pct": delta / old * 100 if comparable and old != 0 else None,
                     "state": "matched" if comparable else "missing_data",
                     "reason": "zero_baseline" if comparable and old == 0 else None})
    return {"schema_version": 1, "field": field, "unit": unit, "records": rows,
            "delta_unit": "percentage_points" if unit == "percent" else unit,
            "baseline_evidence": baseline["id"], "current_evidence": current["id"],
            "interpretation": "Descriptive delta; seasonality, volume, sampling and causality require investigation."}


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    for command in ("doctor", "render", "query", "triage"):
        child = sub.add_parser(command)
        child.add_argument("--config", type=Path, required=True, help="Private service catalog JSON")
        child.add_argument("--service", required=True)
        if command != "render":
            child.add_argument("--dtctl", default="dtctl")
            child.add_argument("--dtctl-config", type=Path, required=True)
        if command in {"query", "triage"}:
            child.add_argument("--start", required=True)
            child.add_argument("--end", required=True)
            child.add_argument("--out", type=Path, required=True)
        if command in {"render", "query"}:
            choices = child.add_mutually_exclusive_group(required=True)
            choices.add_argument("--template")
            choices.add_argument("--file", type=Path)
        if command == "triage":
            child.add_argument("--baseline-start")
            child.add_argument("--baseline-end")
    child = sub.add_parser("compare")
    child.add_argument("--baseline", type=Path, required=True)
    child.add_argument("--current", type=Path, required=True)
    child.add_argument("--dimensions", nargs="+", required=True)
    child.add_argument("--field", required=True)
    child.add_argument("--unit", required=True, help="Verified metric unit; use percent for rates expressed as 0..100.")
    child.add_argument("--out", type=Path, required=True)
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "compare":
            comparison = compare(load_json(args.baseline), load_json(args.current), args.dimensions, args.field, args.unit)
            write_json(args.out, comparison)
            print(json.dumps({"status": "ok", "out": str(args.out)}, ensure_ascii=False))
            return 0
        data = configuration(args.config)
        service, context = resolve(data, args.service)
        if args.command in {"render", "query"}:
            query = render(data, args.service, args.template) if args.template else args.file.read_text(encoding="utf-8-sig")
            validate_dql(query)
            if args.command == "render":
                print(query)
                return 0
        collector = Collector(args.dtctl, args.dtctl_config, context, data["limits"])
        preflight = collector.doctor()
        if args.command == "doctor":
            print(json.dumps(preflight, ensure_ascii=False))
            return 0
        start, end = window(args.start, args.end, data["limits"])
        if args.command == "query":
            evidence = collector.collect(query, start, end, args.service, args.template or args.file.name, args.out)
            print(json.dumps({"status": evidence["status"], "id": evidence["id"], "out": str(args.out)}))
            return 1 if evidence["status"] == "error" else 0
        if bool(args.baseline_start) != bool(args.baseline_end):
            raise InvestigationError("Provide both baseline timestamps.")
        windows = [("current", start, end)]
        if args.baseline_start:
            bs, be = window(args.baseline_start, args.baseline_end, data["limits"])
            if timestamp(be) - timestamp(bs) != timestamp(end) - timestamp(start):
                raise InvestigationError("Triage baseline and current windows must have equal lengths.")
            if max(timestamp(bs), timestamp(start)) < min(timestamp(be), timestamp(end)):
                raise InvestigationError("Triage baseline must not overlap the current window.")
            windows.append(("baseline", bs, be))
        args.out.mkdir(parents=True, exist_ok=False)
        manifest = {"schema_version": 1, "service": args.service, "preflight": preflight, "evidence": [], "skipped": []}
        catalog = load_json(SKILL / "queries" / "catalog.json")
        for label, left, right in windows:
            for template in ("red", "log-errors", "slow-spans", "events", "problems"):
                if not service.get("selectors", {}).get(catalog[template]["signal"]):
                    manifest["skipped"].append({"label": label, "template": template, "reason": "selector_not_configured"})
                    continue
                evidence = collector.collect(render(data, args.service, template), left, right, args.service,
                                             label + ":" + template, args.out / (label + "-" + template + ".json"))
                manifest["evidence"].append({"id": evidence["id"], "file": label + "-" + template + ".json", "status": evidence["status"]})
                if evidence["status"] == "error":
                    # No retry storm, no fan-out after a permission/network failure.
                    manifest["stopped"] = "A collection failed; inspect evidence before continuing."
                    write_json(args.out / "manifest.json", manifest)
                    print(json.dumps({"status": "incomplete", "out": str(args.out)}))
                    return 1
        write_json(args.out / "manifest.json", manifest)
        incomplete = bool(manifest["skipped"]) or any(e["status"] != "ok" for e in manifest["evidence"])
        print(json.dumps({"status": "review_required" if incomplete else "collected", "out": str(args.out)}))
        return 0
    except (InvestigationError, OSError, json.JSONDecodeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"status": "error", "message": redact(str(exc))}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
