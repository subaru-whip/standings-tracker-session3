#!/usr/bin/env python3
"""Finds exact-duplicate files (identical content, not just similar names) in a
folder and moves the extras into a shared "Duplicates - safe to delete"
folder for manual review. Never deletes anything itself.

Usage:
  python3 cull_duplicates.py --target "<folder>"            # dry run: report only, touches nothing
  python3 cull_duplicates.py --target "<folder>" --apply    # actually move duplicates aside

Refuses to run against the "Session 3 Uploaded" folder, since that's the
folder the standings tracker scores from and duplicates there are already
excluded from scoring by filename matching.
"""

import argparse
import hashlib
import os
import shutil
import sys

BLOCKED_FOLDER_NAME = "Session 3 Uploaded"
REVIEW_FOLDER_NAME = "Duplicates - safe to delete"
SHARED_REVIEW_DIR = (
    "/Users/digi3dprinter/Dropbox/File requests/Session 3 Submissions - 2026/"
    "Calder Filtering/Duplicates - safe to delete"
)
SKIP_FOLDER_NAMES = {REVIEW_FOLDER_NAME, "Blurry - safe to delete"}
HASH_CHUNK_SIZE = 1024 * 1024


def _hash_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(HASH_CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _has_dup_suffix(filename):
    stem, _ext = os.path.splitext(filename)
    stripped = stem.rstrip()
    return stripped.endswith(")") and "(" in stripped[stripped.rfind("(") :]


def _iter_files(target):
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_FOLDER_NAMES]
        for name in files:
            if name.startswith("."):
                continue
            yield os.path.join(root, name)


def _pick_keeper(paths):
    no_suffix = [p for p in paths if not _has_dup_suffix(os.path.basename(p))]
    candidates = no_suffix if no_suffix else paths
    return min(candidates, key=lambda p: os.path.getmtime(p))


def _human_size(num_bytes):
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _unique_destination(review_dir, filename):
    dest = os.path.join(review_dir, filename)
    if not os.path.exists(dest):
        return dest
    stem, ext = os.path.splitext(filename)
    n = 1
    while True:
        dest = os.path.join(review_dir, f"{stem} (dup{n}){ext}")
        if not os.path.exists(dest):
            return dest
        n += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", required=True, help="folder to scan for exact-duplicate files")
    parser.add_argument("--apply", action="store_true", help="actually move duplicates (default: dry run/report only)")
    args = parser.parse_args()

    target = os.path.abspath(args.target)

    if not os.path.isdir(target):
        print(f"ERROR: not a folder: {target}", file=sys.stderr)
        sys.exit(1)

    if BLOCKED_FOLDER_NAME.lower() in target.lower():
        print(
            f"ERROR: refusing to run against a path containing '{BLOCKED_FOLDER_NAME}'. "
            "That's the folder the standings tracker scores from and shouldn't be touched here.",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Scanning: {target}")
    hashes = {}
    scanned = 0
    for path in _iter_files(target):
        try:
            file_hash = _hash_file(path)
        except OSError as e:
            print(f"  skipping (couldn't read): {path} ({e})")
            continue
        hashes.setdefault(file_hash, []).append(path)
        scanned += 1
        if scanned % 500 == 0:
            print(f"  ...{scanned} files hashed so far")

    duplicate_groups = {h: paths for h, paths in hashes.items() if len(paths) > 1}

    total_dup_files = 0
    reclaimable_bytes = 0
    moves = []

    for file_hash, paths in duplicate_groups.items():
        keeper = _pick_keeper(paths)
        dupes = [p for p in paths if p != keeper]
        total_dup_files += len(dupes)
        for dupe in dupes:
            reclaimable_bytes += os.path.getsize(dupe)
            moves.append((keeper, dupe))

    print()
    print(f"Scanned {scanned} files -> {len(duplicate_groups)} duplicate sets -> {total_dup_files} duplicate files")
    print(f"Reclaimable space: {_human_size(reclaimable_bytes)}")
    print()

    if not moves:
        print("No exact duplicates found. Nothing to do.")
        return

    if not args.apply:
        print("DRY RUN (no --apply flag) — nothing was moved. Preview:")
        for keeper, dupe in moves[:25]:
            print(f"  KEEP  {os.path.relpath(keeper, target)}")
            print(f"  MOVE  {os.path.relpath(dupe, target)}")
        if len(moves) > 25:
            print(f"  ...and {len(moves) - 25} more")
        print()
        print("Re-run with --apply to move the duplicates into a review folder.")
        return

    review_dir = SHARED_REVIEW_DIR
    os.makedirs(review_dir, exist_ok=True)

    moved = 0
    for keeper, dupe in moves:
        dest = _unique_destination(review_dir, os.path.basename(dupe))
        shutil.move(dupe, dest)
        moved += 1

    print(f"Moved {moved} duplicate files into: {review_dir}")
    print("Review them there, then delete the folder yourself via Finder or Dropbox once you're confident.")


if __name__ == "__main__":
    main()
