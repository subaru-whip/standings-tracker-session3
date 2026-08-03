#!/usr/bin/env python3
"""Finds burst-style near-duplicate photos (same scene/moment, not byte-identical)
and trims each group down to the first photos in camera sequence order, moving
the rest into a review folder. Never deletes anything itself.

Photos are first bucketed by (name-or-guess, department, date) parsed from the
filename — reusing the same parser as the standings tracker — so visual
comparison only ever happens between photos that were already very likely
taken in the same moment. Within a bucket, photos are grouped by perceptual
similarity (dHash). How many survive per group is size-tiered: a pair (2
near-identical shots) is trimmed to 1 keeper, since there's no meaningful
variety to preserve in a pair; groups of 3 or more are trimmed to 2 keepers.

Usage:
  python3 cull_bursts.py --target "<folder>"            # dry run: report only, touches nothing
  python3 cull_bursts.py --target "<folder>" --apply    # actually move the extras aside
"""

import argparse
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image

from parser import parse_filename
from roster import load_roster

BLOCKED_FOLDER_NAME = "Session 3 Uploaded"
REVIEW_FOLDER_NAME = "Duplicates - safe to delete"
SHARED_REVIEW_DIR = (
    "/Users/digi3dprinter/Dropbox/File requests/Session 3 Submissions - 2026/"
    "Calder Filtering/Duplicates - safe to delete"
)
SKIP_FOLDER_NAMES = {REVIEW_FOLDER_NAME, "Blurry - safe to delete"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic"}
DEFAULT_HASH_SIZE = 8
DEFAULT_THRESHOLD = 14  # max Hamming distance (out of 64 bits) to call two photos "the same scene"
DEFAULT_MAX_SEQ_GAP = 15  # max camera sequence-number gap to still count as the same burst
SEQ_RE = re.compile(r"(\d+)(?!.*\d)")  # last run of digits in the filename


def _dhash(path, hash_size=DEFAULT_HASH_SIZE):
    img = Image.open(path).convert("L").resize((hash_size + 1, hash_size), Image.LANCZOS)
    pixels = list(img.getdata())
    bits = 0
    for row in range(hash_size):
        for col in range(hash_size):
            idx = row * (hash_size + 1) + col
            bits = (bits << 1) | (1 if pixels[idx] > pixels[idx + 1] else 0)
    return bits


def _hamming(a, b):
    return bin(a ^ b).count("1")


def _sequence_number(filename):
    stem, _ext = os.path.splitext(filename)
    match = SEQ_RE.search(stem)
    return int(match.group(1)) if match else None


def _iter_image_files(target):
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_FOLDER_NAMES]
        for name in files:
            if name.startswith("."):
                continue
            if os.path.splitext(name)[1].lower() in IMAGE_EXTENSIONS:
                yield os.path.join(root, name)


def _bucket_key(filename, roster, mtime):
    parsed = parse_filename(filename, roster, mtime)
    person = parsed.person or parsed.unmatched_guess or "unknown"
    return (person, parsed.department, parsed.date)


def _fits_cluster(h, seq, cluster, threshold, max_seq_gap):
    # Hash-similar to at least one existing member (single-linkage on look).
    if not any(_hamming(h, ch) <= threshold for ch in cluster["hashes"]):
        return False
    # But the cluster's *overall* sequence range must never exceed max_seq_gap,
    # not just each pairwise link — otherwise a long chain of individually-close
    # links can drift the group across frames from different moments (e.g. a
    # repeated pose or backdrop later in the same shoot).
    known_seqs = [s for s in cluster["seqs"] if s is not None]
    if seq is not None and known_seqs:
        candidate_min = min(known_seqs + [seq])
        candidate_max = max(known_seqs + [seq])
        if candidate_max - candidate_min > max_seq_gap:
            return False
    return True


def _cluster_by_similarity(items, threshold, max_seq_gap=DEFAULT_MAX_SEQ_GAP):
    """items: list of (path, hash, seq). Returns list of clusters (each a list of paths)."""
    clusters = []  # list of {"hashes": [...], "seqs": [...], "paths": [...]}
    for path, h, seq in items:
        placed = False
        for cluster in clusters:
            if _fits_cluster(h, seq, cluster, threshold, max_seq_gap):
                cluster["hashes"].append(h)
                cluster["seqs"].append(seq)
                cluster["paths"].append(path)
                placed = True
                break
        if not placed:
            clusters.append({"hashes": [h], "seqs": [seq], "paths": [path]})
    return [c["paths"] for c in clusters]


def _keep_count(group_size):
    # A pair has no meaningful variety to preserve; larger bursts keep 2.
    return 1 if group_size == 2 else 2


def _sort_key(path):
    seq = _sequence_number(os.path.basename(path))
    # Sort real sequence numbers first (ascending), unknowns last by mtime.
    return (0, seq) if seq is not None else (1, os.path.getmtime(path))


def _unique_destination(review_dir, filename):
    dest = os.path.join(review_dir, filename)
    if not os.path.exists(dest):
        return dest
    stem, ext = os.path.splitext(filename)
    n = 1
    while True:
        dest = os.path.join(review_dir, f"{stem} (extra{n}){ext}")
        if not os.path.exists(dest):
            return dest
        n += 1


def main():
    parser_args = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser_args.add_argument("--target", required=True, help="folder to scan for burst-style near-duplicates")
    parser_args.add_argument("--apply", action="store_true", help="actually move the extras (default: dry run/report only)")
    parser_args.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD, help=f"similarity threshold, 0-64 (default {DEFAULT_THRESHOLD}; lower = stricter)")
    parser_args.add_argument("--max-seq-gap", type=int, default=DEFAULT_MAX_SEQ_GAP, help=f"max camera sequence-number gap to still count as the same burst (default {DEFAULT_MAX_SEQ_GAP})")
    args = parser_args.parse_args()

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

    roster_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "roster.json")
    roster = load_roster(roster_path)

    print(f"Scanning: {target}")
    buckets = {}
    scanned = 0
    for path in _iter_image_files(target):
        filename = os.path.basename(path)
        mtime = os.path.getmtime(path)
        key = _bucket_key(filename, roster, mtime)
        buckets.setdefault(key, []).append(path)
        scanned += 1
        if scanned % 500 == 0:
            print(f"  ...{scanned} files bucketed so far")

    print(f"Scanned {scanned} images -> {len(buckets)} (name, department, date) buckets")
    print("Hashing and clustering by visual similarity...")

    trim_groups = []
    hashed = 0
    for key, paths in buckets.items():
        if len(paths) < 2:
            continue
        items = []
        for path in paths:
            try:
                items.append((path, _dhash(path), _sequence_number(os.path.basename(path))))
                hashed += 1
            except Exception as e:
                print(f"  skipping (couldn't read image): {path} ({e})")
        clusters = _cluster_by_similarity(items, args.threshold, args.max_seq_gap)
        for cluster_paths in clusters:
            if len(cluster_paths) >= 2:
                trim_groups.append((key, sorted(cluster_paths, key=_sort_key)))

    print(f"Hashed {hashed} images in buckets with 2+ photos")
    print()

    total_extra = 0
    moves = []
    for group_index, (key, paths) in enumerate(trim_groups, start=1):
        keep_n = _keep_count(len(paths))
        keep = paths[:keep_n]
        extra = paths[keep_n:]
        if not extra:
            continue
        total_extra += len(extra)
        for path in extra:
            moves.append((group_index, key, keep, path))

    print(f"Found {len(trim_groups)} similar-photo groups -> {total_extra} extra photos")
    print()

    if not moves:
        print("No groups needed trimming. Nothing to do.")
        return

    if not args.apply:
        print("DRY RUN (no --apply flag) — nothing was moved. Preview:")
        shown_groups = set()
        for group_index, key, keep, extra in moves:
            if group_index not in shown_groups:
                shown_groups.add(group_index)
                print(f"  Group {group_index} {key}: keeping {[os.path.basename(p) for p in keep]}")
            print(f"    MOVE  {os.path.relpath(extra, target)}")
        print()
        print("Re-run with --apply to move the extras into a review folder.")
        return

    review_dir = SHARED_REVIEW_DIR
    os.makedirs(review_dir, exist_ok=True)

    moved = 0
    for group_index, key, keep, extra in moves:
        dest = _unique_destination(review_dir, os.path.basename(extra))
        shutil.move(extra, dest)
        moved += 1

    print(f"Moved {moved} extra photos into: {review_dir}")
    print("Review them there, then delete the folder yourself via Finder or Dropbox once you're confident.")


if __name__ == "__main__":
    main()
