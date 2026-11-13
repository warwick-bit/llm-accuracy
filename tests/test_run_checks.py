"""Exercise the public calculation CLI and its displayed-precision contract."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = (Path(__file__).resolve().parents[1] / "plugins" / "llm-accuracy"
          / "skills" / "verify" / "scripts" / "run_checks.py")


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-B", str(SCRIPT), *args], capture_output=True,
        text=True, timeout=20,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )


def calculate(equations, places=None):
    args = ["calculate"]
    if places is not None:
        args.extend(["--places", str(places)])
    for equation in equations:
        args.append("--check=" + equation)
    completed = run_cli(*args)
    assert completed.returncode in (0, 1), completed.stderr
    return completed.returncode, json.loads(completed.stdout)


@pytest.mark.parametrize("places,statuses,precisions,code", [
    ("shown", ["pass", "pass"], [2, 3], 0),
    (2, ["pass", "fail"], [2, 2], 1),
    (None, ["fail", "pass"], [None, None], 1),
])
def test_mixed_precision_modes(places, statuses, precisions, code):
    exit_code, result = calculate(["1/3=0.33", "1/8=0.125"], places)
    assert exit_code == code
    assert [r["status"] for r in result["checks"]] == statuses
    assert [r["decimal_places"] for r in result["checks"]] == precisions
    assert all("tie_pass" not in r for r in result["checks"])


@pytest.mark.parametrize("equation,precision,status,tie", [
    ("1/3=33%", 0, "pass", None),
    ("1/3=33.3%", 1, "pass", None),
    ("1/8=0.12", 2, "pass", None),
    ("1/8=0.13", 2, "pass", "half_up"),
    ("-1/8=-0.12", 2, "pass", None),
    ("-1/8=-0.13", 2, "pass", "half_up"),
    ("5/2=2", 0, "pass", None),
    ("5/2=3", 0, "pass", "half_up"),
    ("-5/2=-3", 0, "pass", "half_up"),
    ("1/3=0.34", 2, "fail", None),
    ("1/3=1/3", None, "pass", None),
    ("1000=1e3", None, "pass", None),
    ("1/3=0.3333333333333", None, "fail", None),
    ("1/8=0.1250000000000", None, "pass", None),
    ("100/3=33.", 0, "pass", None),
    ("1/8= .125 ", 3, "pass", None),
    ("1/8=+0.1250", 4, "pass", None),
    ("1/8= 12.5 % ", 1, "pass", None),
    ("1/3=0.333333333333", 12, "pass", None),
    ("1/8=13%", 0, "pass", "half_up"),
    ("-1/8=-13%", 0, "pass", "half_up"),
    ("3/8=0.38", 2, "pass", None),
])
def test_shown_precision_and_ties(equation, precision, status, tie):
    code, result = calculate([equation], "shown")
    row = result["checks"][0]
    assert row["status"] == result["status"] == status
    assert code == (0 if status == "pass" else 1)
    assert row["decimal_places"] == precision
    assert row.get("tie_pass") == tie
    if tie:
        assert row["computed_display_exact"] == row["reported_display_exact"]


@pytest.mark.parametrize("places", [None, 2])
def test_half_up_remains_opt_in(places):
    _, result = calculate(["1/8=0.13", "-1/8=-0.13"], places)
    assert all(r["status"] == "fail" and "tie_pass" not in r
               for r in result["checks"])


@pytest.mark.parametrize("places", [0, 12])
def test_numeric_precision_endpoints(places):
    _, result = calculate(["1=1"], places)
    assert result["status"] == "pass"
    assert result["checks"][0]["decimal_places"] == places


@pytest.mark.parametrize("value", ["-1", "13", "2.5", "other"])
def test_invalid_places(value):
    result = run_cli("calculate", "--places", value, "--check", "1=1")
    assert result.returncode == 2
    assert "--places" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("args", [("-h",), ("calculate", "-h")])
def test_help(args):
    result = run_cli(*args)
    assert result.returncode == 0, result.stderr
    assert "%" in result.stdout
