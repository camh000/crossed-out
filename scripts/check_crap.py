"""Compute per-function CRAP (Change Risk Anti-Patterns) scores.

CRAP(m) = comp(m)^2 * (1 - cov(m))^3 + comp(m)

where comp(m) is cyclomatic complexity and cov(m) is fractional test
coverage (0..1). A function with high complexity AND low coverage is
"crappy" — risky to change without breaking it.

Usage:

    # As a script — runs the suite under coverage, prints a report,
    # exits with code 0 on success or code 1 if anything regressed.
    python scripts/check_crap.py
    python scripts/check_crap.py --threshold 30   # only flag > 30
    python scripts/check_crap.py --top 20         # limit report rows

    # Inside Python — `compute_crap()` returns the list directly
    # (skipping the subprocess + JSON read). Used by
    # tests/test_code_quality.py to gate against a baseline.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass

# Importable from tests/. Bail loudly if a dev's environment is missing
# either tool — both are listed in the project's requirements.
try:
    from radon.visitors import ComplexityVisitor
except ImportError as e:
    raise SystemExit(
        "radon is required for CRAP analysis: pip install radon"
    ) from e


# Source paths we measure. Tests, scripts, and __init__ files are
# intentionally excluded — they're either gating logic themselves or
# trivial.
SOURCE_FILES: tuple[str, ...] = (
    "main.py",
    "systems/cardsystem.py",
    "systems/roguelite.py",
    "game/board.py",
    "game/opponent.py",
    "game/player.py",
    "renders/rendering.py",
    "save/savesetup.py",
    "config/cards.py",
    "config/bosses.py",
)

# Default CRAP threshold per the literature — Alberto Savoia /
# CRAP4J set 30 as the "definitely crappy" line. Anything above
# means high complexity that isn't proven safe by tests.
DEFAULT_THRESHOLD = 30.0


@dataclass(frozen=True)
class CrapRow:
    crap: float
    complexity: int
    coverage_pct: float
    path: str
    name: str
    lineno: int

    @property
    def key(self) -> str:
        # Stable identifier for baseline pinning: path:funcname.
        # Line number is intentionally NOT in the key — moving a
        # function around shouldn't trip the gate.
        return f"{self.path}:{self.name}"


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_coverage(extra_pytest_args: list[str]) -> dict:
    """Run the test suite under coverage and return the parsed JSON
    report. Strips any pre-existing .coverage data file so the run
    starts clean."""
    root = _project_root()
    cov_data = os.path.join(root, ".coverage.crap")
    if os.path.exists(cov_data):
        os.remove(cov_data)
    env = os.environ.copy()
    env["COVERAGE_FILE"] = cov_data
    # Avoid recursion: the CRAP gate test sets this env var so its
    # subprocess child knows to skip itself.
    env["RUNNING_CRAP_GATE"] = "1"
    # Coverage's --source takes module names (no extensions). Map each
    # source file to its top-level package or stem so coverage tracks
    # the right tree.
    sources: set[str] = set()
    for p in SOURCE_FILES:
        head = p.split("/")[0]
        sources.add(head[:-3] if head.endswith(".py") else head)
    cmd = [
        sys.executable, "-m", "coverage", "run",
        f"--source={','.join(sorted(sources))}",
        "-m", "pytest", "-q", *extra_pytest_args,
    ]
    subprocess.run(cmd, check=True, cwd=root, env=env)
    json_path = os.path.join(root, "coverage.crap.json")
    subprocess.run(
        [sys.executable, "-m", "coverage", "json", "-o", json_path, "--quiet"],
        check=True, cwd=root, env=env,
    )
    with open(json_path) as f:
        data = json.load(f)
    # Tidy up temporary artefacts so they don't end up tracked.
    for p in (cov_data, json_path):
        if os.path.exists(p):
            os.remove(p)
    return data


def compute_crap(coverage_data: dict | None = None) -> list[CrapRow]:
    """Return CRAP scores for every function in SOURCE_FILES, sorted
    descending. If `coverage_data` is None, runs the suite under
    coverage first."""
    if coverage_data is None:
        coverage_data = _run_coverage([])
    root = _project_root()
    rows: list[CrapRow] = []
    files = coverage_data.get("files", {})
    for rel in SOURCE_FILES:
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            continue
        with open(path) as f:
            code = f.read()
        executed = set(files.get(rel, {}).get("executed_lines", []))
        visitor = ComplexityVisitor.from_code(code)
        functions = list(visitor.functions)
        for cls in visitor.classes:
            functions.extend(cls.methods)
        for fn in functions:
            body_lines = set(range(fn.lineno, fn.endline + 1))
            covered = body_lines & executed
            cov_pct = (len(covered) / max(1, len(body_lines))) * 100
            comp = fn.complexity
            crap = comp * comp * ((1 - cov_pct / 100) ** 3) + comp
            rows.append(CrapRow(
                crap=crap,
                complexity=comp,
                coverage_pct=cov_pct,
                path=rel,
                name=fn.name,
                lineno=fn.lineno,
            ))
    rows.sort(key=lambda r: r.crap, reverse=True)
    return rows


def is_render_function(row: CrapRow) -> bool:
    """Render functions can't be meaningfully covered by the test
    harness (pygame is mocked at the conftest level, so the rendering
    pipeline never really runs). They get artificially-low coverage
    and inflated CRAP scores. We surface them in reports but exempt
    them from the gate."""
    if row.path == "renders/rendering.py":
        return True
    if row.name.startswith("_draw_") or row.name == "draw":
        return True
    return False


def print_report(rows: list[CrapRow], top: int = 25) -> None:
    print(f"{'CRAP':>8}  {'CC':>4}  {'COV%':>6}  Location")
    print("-" * 80)
    for r in rows[:top]:
        marker = " [render]" if is_render_function(r) else ""
        print(
            f"{r.crap:>8.1f}  {r.complexity:>4d}  {r.coverage_pct:>6.1f}  "
            f"{r.path}:{r.lineno} {r.name}{marker}"
        )
    above = sum(1 for r in rows if r.crap > DEFAULT_THRESHOLD)
    logic_above = sum(
        1 for r in rows if r.crap > DEFAULT_THRESHOLD and not is_render_function(r)
    )
    print()
    print(f"Total functions analyzed: {len(rows)}")
    print(f"Above CRAP={DEFAULT_THRESHOLD} (all):      {above}")
    print(f"Above CRAP={DEFAULT_THRESHOLD} (logic only): {logic_above}")


BASELINE_PATH = os.path.join(_project_root(), ".crap_baseline.json")


def load_baseline() -> dict[str, float]:
    """Return the pinned per-function ceilings, or {} if no baseline
    has been written yet."""
    if not os.path.exists(BASELINE_PATH):
        return {}
    with open(BASELINE_PATH) as f:
        return json.load(f)


def write_baseline(rows: list[CrapRow], threshold: float) -> None:
    """Pin every non-render function with CRAP > `threshold` to its
    current score. Render functions are skipped — they're not gated."""
    data = {
        r.key: round(r.crap, 1)
        for r in rows
        if r.crap > threshold and not is_render_function(r)
    }
    with open(BASELINE_PATH, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
    print(f"Wrote baseline with {len(data)} entries to {BASELINE_PATH}")


def check_against_baseline(
    rows: list[CrapRow], threshold: float,
) -> list[str]:
    """Return a list of human-readable failures, empty if all clear.

    Rules:
        - Every non-render function with CRAP > threshold must have a
          baseline entry. New code above threshold is a failure.
        - Every baselined function's current CRAP must be ≤ its
          baseline value. Regressions fail.
    """
    baseline = load_baseline()
    failures: list[str] = []
    for r in rows:
        if is_render_function(r):
            continue
        if r.crap <= threshold:
            continue
        pinned = baseline.get(r.key)
        if pinned is None:
            failures.append(
                f"NEW: {r.key} CRAP={r.crap:.1f} (>{threshold:.0f}, "
                f"complexity={r.complexity}, cov={r.coverage_pct:.1f}%). "
                f"Refactor it, add tests, or run "
                f"`python scripts/check_crap.py --write-baseline` if "
                f"this is intentional."
            )
        elif round(r.crap, 1) > pinned:
            # Baseline values are rounded to 1dp, so compare at the
            # same precision — otherwise float noise from coverage
            # makes a stable run look like a regression.
            failures.append(
                f"REGRESSED: {r.key} CRAP={r.crap:.1f} > baseline "
                f"{pinned:.1f} (complexity={r.complexity}, "
                f"cov={r.coverage_pct:.1f}%)"
            )
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--threshold", type=float, default=DEFAULT_THRESHOLD,
        help="Below this score, a function is considered safe.",
    )
    parser.add_argument(
        "--top", type=int, default=25,
        help="Number of rows to print in the report.",
    )
    parser.add_argument(
        "--include-render", action="store_true",
        help="Apply the threshold to render functions too.",
    )
    parser.add_argument(
        "--write-baseline", action="store_true",
        help="Pin every above-threshold function's current CRAP into "
             "the baseline file. Use after an intentional refactor "
             "or a planned new addition.",
    )
    args = parser.parse_args(argv)

    rows = compute_crap()
    print_report(rows, top=args.top)

    if args.write_baseline:
        write_baseline(rows, args.threshold)
        return 0

    failures = check_against_baseline(rows, args.threshold)
    if failures:
        print()
        print("=== CRAP gate FAILED ===")
        for f in failures:
            print(f"  {f}")
        return 1
    print()
    print(f"OK: all functions within baseline at threshold {args.threshold}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
