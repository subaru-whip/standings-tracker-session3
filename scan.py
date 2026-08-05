#!/usr/bin/env python3
"""CLI entry point: scan -> parse -> aggregate -> render -> (optional) publish.

Usage:
  python3 scan.py            # dry run: writes docs/ locally, does not touch git
  python3 scan.py --publish  # dry run steps, then commits + pushes docs/ to GitHub Pages
"""

import argparse
import datetime
import os
import sys

from aggregate import aggregate
from parser import parse_filename
from publish import publish
from render import render_site
from roster import load_roster

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ROSTER_PATH = os.path.join(PROJECT_ROOT, "roster.json")
DOCS_DIR = os.path.join(PROJECT_ROOT, "docs")

SOURCE_DIR = (
    "/Users/digi3dprinter/Dropbox/File requests/Session 3 Submissions - 2026/"
    "Session 3 Uploaded"
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic"}


def collect_filenames(source_dir):
    if not os.path.isdir(source_dir):
        print(f"ERROR: source folder not found: {source_dir}", file=sys.stderr)
        sys.exit(1)

    names = []
    for entry in os.listdir(source_dir):
        if entry.startswith("."):
            continue
        ext = os.path.splitext(entry)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            names.append(entry)
    return names


def main():
    parser_args = argparse.ArgumentParser(description="Build and optionally publish the standings site.")
    parser_args.add_argument(
        "--publish", action="store_true", help="commit and push docs/ after rendering"
    )
    args = parser_args.parse_args()

    roster = load_roster(ROSTER_PATH)
    filenames = collect_filenames(SOURCE_DIR)

    photos = []
    for filename in filenames:
        full_path = os.path.join(SOURCE_DIR, filename)
        mtime = os.path.getmtime(full_path)
        photos.append(parse_filename(filename, roster, mtime))

    result = aggregate(photos, roster)

    now = datetime.datetime.now()
    generated_at_str = now.strftime("%B %-d, %Y at %-I:%M %p")

    render_site(result, generated_at_str, DOCS_DIR)

    print(
        f"Scanned {result.total_scanned} files -> {result.total_after_dedup} unique after dedup "
        f"-> {result.total_matched} matched, {result.total_unmatched} unmatched, "
        f"{result.total_excluded} excluded, {result.total_late} late, {result.total_flagged} flagged"
    )
    print(f"Wrote {os.path.join(DOCS_DIR, 'index.html')}")

    if result.flagged:
        print()
        print(f"⚠ {result.total_flagged} file(s) FLAGGED for manual review — filename date doesn't")
        print("  match the year they were actually uploaded (likely a bad camera clock or similar).")
        print("  Not counted toward anyone's total yet. Review and either fix the date, or add an")
        print("  entry to roster.json's \"exclusions\" once you've confirmed what to do with them:")
        for photo in result.flagged:
            print(f"    {photo.filename}  (person={photo.person}, filename_date={photo.filename_date})")

    if args.publish:
        publish(PROJECT_ROOT, generated_at_str)
    else:
        print("Dry run only (no --publish flag) — open docs/index.html locally to review.")


if __name__ == "__main__":
    main()
