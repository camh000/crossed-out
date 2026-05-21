"""CRAP (Change Risk Anti-Patterns) gate.

Runs the test suite under coverage in a subprocess, computes per-function
CRAP scores, and asserts no function exceeds its pinned baseline or
introduces a new above-threshold offender.

The gate auto-skips if invoked from inside an existing coverage run
(detected via the RUNNING_CRAP_GATE env var the script sets) — otherwise
we'd recurse forever.

Adjusting the baseline:
    python scripts/check_crap.py --write-baseline
"""
import os
import shutil
import subprocess
import sys

import pytest


SKIP_REASON = "Disable with CRAP_GATE_SKIP=1; auto-skipped inside coverage."


def _should_skip() -> bool:
    if os.environ.get("CRAP_GATE_SKIP") == "1":
        return True
    # When the script subprocesses pytest under coverage, it sets this
    # env var so the child run skips re-entry.
    if os.environ.get("RUNNING_CRAP_GATE") == "1":
        return True
    # No coverage / radon installed? Skip rather than fail.
    if shutil.which("python") is None:
        return True
    try:
        import radon  # noqa: F401
        import coverage  # noqa: F401
    except ImportError:
        return True
    return False


@pytest.mark.skipif(_should_skip(), reason=SKIP_REASON)
def test_crap_gate() -> None:
    """Every non-render function must (a) be ≤30 CRAP, or (b) appear in
    .crap_baseline.json with a ceiling ≥ its current score. Regression
    in either dimension fails the gate."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    script = os.path.join(root, "scripts", "check_crap.py")
    result = subprocess.run(
        [sys.executable, script],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        pytest.fail(
            "CRAP gate failed. See stdout below.\n\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )
