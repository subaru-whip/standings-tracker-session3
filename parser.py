"""Pure filename-parsing logic: filename string -> ParsedPhoto.

No filesystem or git access happens here, which keeps this module fully
unit-testable against literal filename strings (see tests/test_parser.py).
"""

import os
import re
from dataclasses import dataclass
from typing import Optional

from roster import Roster

DUP_SUFFIX_RE = re.compile(r"\s*\(\d+\)$")

MEDIA_ID_RE = re.compile(
    r"IMG_\d+"
    r"|C73A\d+"  # Canon DSLR default naming seen in real data (e.g. C73A1405)
    r"|7N3A\d+"  # second Canon DSLR body seen in real data (e.g. 7N3A2012)
    r"|\d{8}_\d{6}"
    r"|[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}(?:_\d+_\d+_c)?"
)

# Tolerates "7.13" (clean) and "07[]12" (broken separator seen in real data).
DATE_RE = re.compile(r"\b(\d{1,2})[.\[\]]+(\d{1,2})\b")

# Some Session 3 filenames carry a redundant leading ISO date, e.g.
# "2026-08-01 - 8.1 - Name - Dept IMG_1234.jpg" — strip it before parsing so
# it doesn't leak into the department field or get picked as unmatched_guess.
ISO_DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\s*-\s*")

NON_WORD_RE = re.compile(r"[^A-Za-z0-9]+")


@dataclass
class ParsedPhoto:
    filename: str
    person: Optional[str]        # canonical roster name, or None if unmatched
    unmatched_guess: Optional[str]  # raw name-like token when person is None
    department: str
    date: str                    # "M/D" display string
    date_from_filename: bool
    dedup_key: tuple


def _normalize(text: str) -> str:
    text = NON_WORD_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _remove_token(normalized: str, token: str) -> str:
    pattern = r"\b" + re.escape(token) + r"\b"
    return re.sub(pattern, " ", normalized, count=1, flags=re.IGNORECASE)


def parse_filename(filename: str, roster: Roster, mtime: float) -> ParsedPhoto:
    stem, _ext = os.path.splitext(filename)
    cleaned_stem = DUP_SUFFIX_RE.sub("", stem)

    media_match = MEDIA_ID_RE.search(cleaned_stem)
    blob = cleaned_stem[: media_match.start()] if media_match else cleaned_stem
    blob = blob.strip(" -")
    blob = ISO_DATE_PREFIX_RE.sub("", blob, count=1)

    date_match = DATE_RE.search(blob)
    if date_match:
        month, day = int(date_match.group(1)), int(date_match.group(2))
        date_str = f"{month}/{day}"
        date_from_filename = True
        blob = blob[: date_match.start()] + blob[date_match.end():]
    else:
        import datetime

        dt = datetime.datetime.fromtimestamp(mtime)
        date_str = f"{dt.month}/{dt.day}"
        date_from_filename = False

    normalized = _normalize(blob)

    person = None
    unmatched_guess = None

    for alias_phrase, canonical in roster.alias_lookup.items():
        if re.search(r"\b" + re.escape(alias_phrase) + r"\b", normalized, re.IGNORECASE):
            person = canonical
            normalized = re.sub(
                r"\b" + re.escape(alias_phrase) + r"\b", " ", normalized, count=1, flags=re.IGNORECASE
            )
            break

    if person is None:
        for token in normalized.split():
            canonical = roster.name_lookup.get(token.lower())
            if canonical:
                person = canonical
                normalized = _remove_token(normalized, token)
                break

    if person is None:
        tokens = normalized.split()
        if tokens:
            unmatched_guess = tokens[0]
            normalized = _remove_token(normalized, tokens[0])

    department = _normalize(normalized) or "Unknown"

    dedup_key = (person or unmatched_guess or "unknown", cleaned_stem.lower())

    return ParsedPhoto(
        filename=filename,
        person=person,
        unmatched_guess=unmatched_guess,
        department=department,
        date=date_str,
        date_from_filename=date_from_filename,
        dedup_key=dedup_key,
    )
