#!/usr/bin/env python3
"""Verify an application-local Deck Benchmark Core by behavior, not its version label."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any


MINIMUM_VERSION = (2, 1, 0)
CONTRACT_ID = "deck-benchmark-core-v2"
CONTRACT_SHA256 = "4d493a15259dc1a94c896959b1671ade66413fd5b55ff73ba9231d2d6144f332"
REQUIRED_CAPABILITIES = {
    "decision_roles",
    "check_definition_enrichment",
    "macro_feature_scoring",
    "quality_policy_thresholds",
    "canonical_dual_reports",
    "human_answer_actual_evidence",
    "agent_repair_contract",
    "assertion_level_comparison",
    "comparison_compatibility_guards",
}


def version_tuple(value: Any) -> tuple[int, int, int]:
    try:
        parts = [int(item) for item in str(value).split(".")[:3]]
    except ValueError:
        return (0, 0, 0)
    return tuple((parts + [0, 0, 0])[:3])  # type: ignore[return-value]


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: check_core.py /path/to/benchmark/scripts/deck_benchmark.py")
    dispatcher = Path(sys.argv[1]).expanduser().resolve()
    reasons: list[str] = []
    payload: dict[str, Any] = {}
    if not dispatcher.is_file():
        reasons.append(f"Core dispatcher does not exist: {dispatcher}")
    else:
        proc = subprocess.run([sys.executable, str(dispatcher), "core-check"], text=True, capture_output=True)
        try:
            value = json.loads(proc.stdout)
            payload = value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            reasons.append("Core does not return a JSON conformance result")
        if proc.returncode != 0:
            reasons.append(f"Core self-check exited {proc.returncode}: {proc.stderr.strip() or 'behavioral probe failed'}")
    if payload:
        if payload.get("ok") is not True:
            reasons.append("Core behavioral probes did not all pass")
        if version_tuple(payload.get("benchmarkCoreVersion")) < MINIMUM_VERSION:
            reasons.append(f"Core {payload.get('benchmarkCoreVersion')} is older than 2.1.0")
        if str(payload.get("reportContractVersion")) != "2":
            reasons.append("Report contract must be version 2")
        if payload.get("contractId") != CONTRACT_ID:
            reasons.append(f"Unexpected Core contract: {payload.get('contractId')}")
        if payload.get("contractSha256") != CONTRACT_SHA256:
            reasons.append(f"Unexpected Core contract fingerprint: {payload.get('contractSha256')}")
        capabilities = {name for name, enabled in payload.get("capabilities", {}).items() if enabled is True}
        missing = sorted(REQUIRED_CAPABILITIES - capabilities)
        if missing:
            reasons.append(f"Missing Core capabilities: {', '.join(missing)}")
        failed_probes = sorted(name for name, probe in payload.get("probes", {}).items() if not isinstance(probe, dict) or probe.get("ok") is not True)
        if failed_probes:
            reasons.append(f"Failed Core probes: {', '.join(failed_probes)}")
    result = {
        "ok": not reasons,
        "dispatcher": str(dispatcher),
        "requiredContract": CONTRACT_ID,
        "minimumCoreVersion": ".".join(map(str, MINIMUM_VERSION)),
        "actualCoreVersion": payload.get("benchmarkCoreVersion"),
        "contractSha256": payload.get("contractSha256"),
        "reasons": reasons,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
