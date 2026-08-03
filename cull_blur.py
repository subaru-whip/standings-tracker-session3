#!/usr/bin/env python3
"""Finds blurry photos (Laplacian-variance sharpness score) and moves anything
at or below the threshold into a review folder. Never deletes anything itself.

Score is the variance of a Laplacian filter over a grayscale, size-normalized
copy of the image — low variance means few sharp edges (blurry), high
variance means lots of fine detail (sharp). The image is downscaled to a
consistent max dimension first so scores are comparable across photos from
different cameras/resolutions.

Calibrated against real examples:
  - Needs Attention/7.22[]KC[]Bunk IMG_9977.jpeg (~100.5) — whole-frame blur
    (camera shake / out of focus), confirmed too blurry.
  - Calder Filtering/7.22[]KC[]Sports IMG_9792/9797/9802.jpeg (207-270) —
    motion blur on a moving subject with a comparatively sharp background,
    also confirmed too blurry.
The default threshold of 270 catches both categories, with the second (motion
blur) driving the number up substantially since the score is a whole-image
average and can't isolate a blurry subject from a sharp background. There's
no clean gap in the real score distribution, so treat this as a starting
point to refine further after reviewing what gets flagged.

Usage:
  python3 cull_blur.py --target "<folder>"            # dry run: report only, touches nothing
  python3 cull_blur.py --target "<folder>" --apply    # actually move the blurry ones aside
"""

import argparse
import os
import shutil
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

BLOCKED_FOLDER_NAME = "Session 3 Uploaded"
REVIEW_FOLDER_NAME = "Blurry - safe to delete"
OTHER_REVIEW_FOLDER_NAME = "Duplicates - safe to delete"
SKIP_FOLDER_NAMES = {REVIEW_FOLDER_NAME, OTHER_REVIEW_FOLDER_NAME}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic"}
DEFAULT_THRESHOLD = 270  # scores at or below this are considered too blurry
MAX_DIM = 800  # downscale long edge to this before scoring, for consistency


def blur_score(path, max_dim=MAX_DIM):
    img = Image.open(path).convert("L")
    if max(img.size) > max_dim:
        scale = max_dim / max(img.size)
        img = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)
    arr = np.asarray(img, dtype=np.float64)
    return float(ndimage.laplace(arr).var())


def _iter_image_files(target):
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_FOLDER_NAMES]
        for name in files:
            if name.startswith("."):
                continue
            if os.path.splitext(name)[1].lower() in IMAGE_EXTENSIONS:
                yield os.path.join(root, name)


def _unique_destination(review_dir, filename):
    dest = os.path.join(review_dir, filename)
    if not os.path.exists(dest):
        return dest
    stem, ext = os.path.splitext(filename)
    n = 1
    while True:
        dest = os.path.join(review_dir, f"{stem} (blurry{n}){ext}")
        if not os.path.exists(dest):
            return dest
        n += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", required=True, help="folder to scan for blurry photos")
    parser.add_argument("--apply", action="store_true", help="actually move blurry photos (default: dry run/report only)")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD, help=f"blur score cutoff, at-or-below is culled (default {DEFAULT_THRESHOLD})")
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
    blurry = []
    scanned = 0
    for path in _iter_image_files(target):
        try:
            score = blur_score(path)
        except Exception as e:
            print(f"  skipping (couldn't read image): {path} ({e})")
            continue
        scanned += 1
        if scanned % 200 == 0:
            print(f"  ...{scanned} files scored so far")
        if score <= args.threshold:
            blurry.append((score, path))
    blurry.sort()

    print(f"Scanned {scanned} images -> {len(blurry)} at or below blur threshold {args.threshold}")
    print()

    if not blurry:
        print("No blurry photos found. Nothing to do.")
        return

    if not args.apply:
        print("DRY RUN (no --apply flag) — nothing was moved. Preview:")
        for score, path in blurry[:25]:
            print(f"  MOVE ({score:.1f})  {os.path.relpath(path, target)}")
        if len(blurry) > 25:
            print(f"  ...and {len(blurry) - 25} more")
        print()
        print("Re-run with --apply to move the blurry photos into a review folder.")
        return

    review_dir = os.path.join(target, REVIEW_FOLDER_NAME)
    os.makedirs(review_dir, exist_ok=True)

    moved = 0
    for score, path in blurry:
        dest = _unique_destination(review_dir, os.path.basename(path))
        shutil.move(path, dest)
        moved += 1

    print(f"Moved {moved} blurry photos into: {review_dir}")
    print("Review them there, then delete the folder yourself via Finder or Dropbox once you're confident.")


if __name__ == "__main__":
    main()
