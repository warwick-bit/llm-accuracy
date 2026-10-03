#!/usr/bin/env python3
"""Native CI installation and live QA, with fixed output and no login-file copy."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path

from check_compatibility import (
    CI_TARGETS,
    ROOT,
    INSTALL_CHECKS,
    installation_errors,
    target_checks,
    target_identity,
    validate,
)
import claude_bundle_smoke as bundle


def usable_bash(path):
    if not path:
        return False
    # Windows' WSL launcher can print GNU Bash's version without being Git Bash.
    candidate = Path(path)
    if candidate.name.lower() == "bash.exe" and candidate.parent.name.lower() in (
        "system32", "sysnative", "syswow64", "windowsapps"
    ):
        return False
    try:
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in bundle.smoke.CONTROL_VARS
        }
        result = subprocess.run(
            [str(path), "--version"], env=env, capture_output=True, timeout=15
        )
        return result.returncode == 0 and b"GNU bash" in result.stdout
    except (OSError, subprocess.SubprocessError):
        return False


def host_checks(target):
    if bundle.smoke.platform_label() != target_identity(target)[0]:
        raise ValueError("ci_host_mismatch")
    if not target.startswith("code-windows-"):
        return {}
    git = shutil.which("git")
    roots = [Path("C:/Program Files/Git"), Path("C:/Program Files (x86)/Git")]
    if git:
        roots.append(Path(git).parent.parent)
    paths = [shutil.which("bash"), os.environ.get("CLAUDE_CODE_GIT_BASH_PATH")]
    paths.extend(
        root / suffix
        for root in roots
        for suffix in ("bin/bash.exe", "usr/bin/bash.exe")
    )
    present = any(usable_bash(path) for path in paths)
    expected = target == "code-windows-git-bash"
    if present != expected or (
        not expected and os.environ.get("CLAUDE_CODE_GIT_BASH_PATH")
    ):
        raise ValueError("ci_bash_mode_mismatch")
    return {"git_bash_present" if expected else "git_bash_absent": True}


def live_receipt(report, target, proof):
    if (
        report.get("status") != "pass"
        or report.get("partial") is not False
        or report.get("isolated_cleanup") is not True
        or report.get("scope") != "code_bundle_registration_accuracy_delivery"
        or report.get("platform") != target_identity(target)[0]
    ):
        raise ValueError("ci_live_smoke_failed")
    platform, kind = target_identity(target)
    row = {
        "outcome": "pass",
        "platform": platform,
        "host_kind": kind,
        "host_version": report.get("host_version"),
        "python_version": report.get("python_version"),
        "packages": report.get("packages"),
        "checks": {**{key: report.get('checks', {}).get(key) for key in target_checks(target)
                      if not key.startswith('git_bash_')}, **proof},
    }
    candidate = json.loads(
        (ROOT / "docs/validation/compatibility-candidate.json").read_text()
    )
    candidate["targets"][target] = row
    if validate(ROOT, candidate) or set(row["checks"]) != set(target_checks(target)):
        raise ValueError("ci_live_receipt_invalid")
    return {
        "schema_version": 1,
        "target": target,
        "source_commit": report["source_commit"],
        "row": row,
    }


def installation_receipt(report, target, proof):
    checks = report.get('checks', {})
    if (report.get('status') != 'partial' or report.get('partial') is not True
            or report.get('isolated_cleanup') is not True
            or report.get('scope') != 'code_bundle_registration_accuracy_delivery'
            or any(checks.get(key) is not True for key in INSTALL_CHECKS)):
        raise ValueError('ci_installation_smoke_failed')
    row = {'outcome': 'installed', 'platform': report.get('platform'), 'host_kind': 'code',
           'host_version': report.get('host_version'), 'python_version': report.get('python_version'),
           'packages': report.get('packages'), 'checks': {**{key: checks[key] for key in INSTALL_CHECKS}, **proof},
           'live_delivery': 'not_tested', 'isolated_cleanup': report['isolated_cleanup']}
    candidate = json.loads((ROOT / 'docs/validation/compatibility-candidate.json').read_text())
    if installation_errors(row, target, candidate['packages']):
        raise ValueError('ci_installation_smoke_failed')
    return {'schema_version': 2, 'target': target, 'source_commit': report['source_commit'],
            'run_id': os.environ.get('GITHUB_RUN_ID', 'local'), 'row': row}


def run(options):
    proof = host_checks(options.target)
    if options.live:
        present = [
            name
            for name in ("ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")
            if os.environ.get(name, "").strip()
        ]
        if len(present) != 1:
            raise ValueError("ci_authentication_required")
    report = bundle.run_smoke(
        options.claude, options.baseline, live=options.live, ci_auth=True
    )
    if options.live:
        return live_receipt(report, options.target, proof)
    return installation_receipt(report, options.target, proof)


def main(arguments=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=CI_TARGETS, required=True)
    parser.add_argument("--claude", required=True)
    parser.add_argument("--baseline", default="v0.6.5")
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--live", action="store_true")
    options = parser.parse_args(arguments)
    try:
        receipt = run(options)
        options.receipt.parent.mkdir(parents=True, exist_ok=True)
        options.receipt.write_text(
            json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
        )
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        subprocess.SubprocessError,
    ) as error:
        allowed = {
            "ci_authentication_required",
            "ci_host_mismatch",
            "ci_bash_mode_mismatch",
            "ci_live_smoke_failed",
            "ci_live_receipt_invalid",
            "ci_installation_smoke_failed",
        }
        label = (
            str(error)
            if isinstance(error, ValueError) and str(error) in allowed
            else "ci_installed_qa_failed"
        )
        print(json.dumps({"status": "fail", "error": label}))
        return 1
    print(
        json.dumps(
            {
                "status": "pass" if options.live else "installation_only",
                "target": options.target,
                "partial": not options.live,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
