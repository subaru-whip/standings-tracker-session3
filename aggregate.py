"""ParsedPhoto list -> dedupe -> per-person/team tallies + unmatched list.

No filename-parsing or filesystem knowledge lives here — this module only
works on already-parsed ParsedPhoto objects.
"""

import datetime
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

from parser import ParsedPhoto
from roster import Roster


@dataclass
class TeamResult:
    members: list
    counts: dict
    total: int
    roster_number: int  # stable "NO. 01" style position from roster.json, independent of current rank


@dataclass
class AggregateResult:
    teams: list                # list[TeamResult], sorted by total descending
    unmatched: list             # list[ParsedPhoto], deduped
    excluded: list               # list[ParsedPhoto], deduped, matched a roster.exclusions rule
    late: list                    # list[ParsedPhoto], deduped, uploaded after the deadline
    flagged: list                  # list[ParsedPhoto], deduped, suspicious filename_date — needs manual review
    total_scanned: int
    total_after_dedup: int
    total_matched: int
    total_unmatched: int
    total_excluded: int
    total_late: int
    total_flagged: int


def _rule_matches(photo: ParsedPhoto, rule: dict) -> bool:
    if "person" in rule and photo.person != rule["person"]:
        return False
    if "date" in rule and photo.date != rule["date"]:
        return False
    needle = rule.get("filename_contains")
    if needle and needle.lower() not in photo.filename.lower():
        return False
    return True


def _is_excluded(photo: ParsedPhoto, exclusions: list) -> bool:
    return any(_rule_matches(photo, rule) for rule in exclusions)


def _upload_status(photo: ParsedPhoto, deadline_config: dict) -> str:
    """Returns "on_time", "late", or "flagged" relative to noon-the-next-day
    (or whatever cutoff_hour/timezone is configured) after the photo's filename date.

    Photos without a filename_date (legacy formats, fallback-to-mtime dates) can't
    be checked against a deadline defined relative to that date, so they're always
    "on_time". A filename_date in a different year than the real upload (mtime) is
    almost certainly a bad date (e.g. a camera with its clock set wrong) rather than
    a genuinely years-late upload — those get "flagged" for manual review instead of
    being auto-excluded as "late". Photos uploaded before deadline_config's
    "effective_from" are grandfathered in as "on_time" — the deadline only applies
    to photos landing in the folder from that point forward.
    """
    if deadline_config is None or photo.filename_date is None:
        return "on_time"
    tz = ZoneInfo(deadline_config.get("timezone", "America/New_York"))
    uploaded_at = datetime.datetime.fromtimestamp(photo.mtime, tz=tz)

    effective_from = deadline_config.get("effective_from")
    if effective_from and uploaded_at < datetime.datetime.fromisoformat(effective_from):
        return "on_time"

    if photo.filename_date.year != uploaded_at.year:
        return "flagged"
    cutoff_hour = deadline_config.get("cutoff_hour", 12)
    deadline = datetime.datetime(
        photo.filename_date.year,
        photo.filename_date.month,
        photo.filename_date.day,
        cutoff_hour,
        0,
        tzinfo=tz,
    ) + datetime.timedelta(days=1)
    return "late" if uploaded_at > deadline else "on_time"


def aggregate(photos: list, roster: Roster) -> AggregateResult:
    seen = {}
    for photo in photos:
        seen.setdefault(photo.dedup_key, photo)
    deduped = list(seen.values())

    person_counts = {name: 0 for name in roster.person_to_team}
    unmatched = []
    excluded = []
    late = []
    flagged = []

    for photo in deduped:
        if photo.person is None:
            unmatched.append(photo)
            continue
        if _is_excluded(photo, roster.exclusions):
            excluded.append(photo)
            continue
        status = _upload_status(photo, roster.late_upload_deadline)
        if status == "late":
            late.append(photo)
        elif status == "flagged":
            flagged.append(photo)
        else:
            person_counts[photo.person] += 1

    for name, delta in roster.adjustments.items():
        if name in person_counts:
            person_counts[name] = max(0, person_counts[name] + delta)

    teams = []
    for roster_index, members in enumerate(roster.teams):
        counts = {name: person_counts[name] for name in members}
        teams.append(
            TeamResult(
                members=members,
                counts=counts,
                total=sum(counts.values()),
                roster_number=roster_index + 1,
            )
        )
    teams.sort(key=lambda t: t.total, reverse=True)

    unmatched.sort(key=lambda p: p.filename.lower())
    excluded.sort(key=lambda p: p.filename.lower())
    late.sort(key=lambda p: p.filename.lower())
    flagged.sort(key=lambda p: p.filename.lower())

    return AggregateResult(
        teams=teams,
        unmatched=unmatched,
        excluded=excluded,
        late=late,
        flagged=flagged,
        total_scanned=len(photos),
        total_after_dedup=len(deduped),
        total_matched=len(deduped) - len(unmatched) - len(excluded) - len(late) - len(flagged),
        total_unmatched=len(unmatched),
        total_excluded=len(excluded),
        total_late=len(late),
        total_flagged=len(flagged),
    )
