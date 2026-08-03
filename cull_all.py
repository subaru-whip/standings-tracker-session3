#!/usr/bin/env python3
"""Runs the culling passes (exact duplicates, burst near-duplicates) against a
target folder in sequence, and prints one consolidated report of how many
were culled by each. Never deletes anything itself — see the individual
scripts (cull_duplicates.py, cull_bursts.py) for details; this is just a
convenience wrapper around them.

Blur detection (cull_blur.py) is intentionally not included here — it proved
unreliable (whole-frame and per-region sharpness both failed to separate real
blurry photos from sharp ones with a plain background) and was dropped from
the automatic pipeline. Run cull_blur.py directly if you want to experiment
with it further.

Usage:
  python3 cull_all.py --target "<folder>"            # dry run: report only, touches nothing
  python3 cull_all.py --target "<folder>" --apply    # actually move everything flagged aside
"""

import argparse
import re
import subprocess
import sys

SCRIPT_DIR = __file__.rsplit("/", 1)[0] or "."

PASSES = [
    ("Exact duplicates", "cull_duplicates.py", r"Moved (\d+) duplicate files"),
    ("Burst near-duplicates", "cull_bursts.py", r"Moved (\d+) extra photos"),
]

DRY_RUN_PATTERNS = {
    "cull_duplicates.py": r"-> (\d+) duplicate files",
    "cull_bursts.py": r"-> (\d+) extra photos",
}


def run_pass(script, target, apply_):
    cmd = [sys.executable, f"{SCRIPT_DIR}/{script}", "--target", target]
    if apply_:
        cmd.append("--apply")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"--- {script} failed ---")
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", required=True, help="folder to run all culling passes against")
    parser.add_argument("--apply", action="store_true", help="actually move flagged files (default: dry run/report only)")
    args = parser.parse_args()

    counts = {}
    for label, script, moved_pattern in PASSES:
        print(f"=== {label} ({script}) ===")
        output = run_pass(script, args.target, args.apply)
        print(output.strip())
        print()

        if args.apply:
            match = re.search(moved_pattern, output)
        else:
            match = re.search(DRY_RUN_PATTERNS[script], output)
        counts[label] = int(match.group(1)) if match else 0

    verb = "culled" if args.apply else "found (dry run — nothing moved)"
    print("=== Summary ===")
    for label, _script, _pattern in PASSES:
        print(f"{label}: {counts[label]} {verb}")
    print(f"Total: {sum(counts.values())} {verb}")


if __name__ == "__main__":
    main()
