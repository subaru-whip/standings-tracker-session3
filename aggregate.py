"""ParsedPhoto list -> dedupe -> per-person/team tallies + unmatched list.

No filename-parsing or filesystem knowledge lives here — this module only
works on already-parsed ParsedPhoto objects.
"""

from dataclasses import dataclass, field

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
    total_scanned: int
    total_after_dedup: int
    total_matched: int
    total_unmatched: int


def aggregate(photos: list, roster: Roster) -> AggregateResult:
    seen = {}
    for photo in photos:
        seen.setdefault(photo.dedup_key, photo)
    deduped = list(seen.values())

    person_counts = {name: 0 for name in roster.person_to_team}
    unmatched = []

    for photo in deduped:
        if photo.person is not None:
            person_counts[photo.person] += 1
        else:
            unmatched.append(photo)

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

    return AggregateResult(
        teams=teams,
        unmatched=unmatched,
        total_scanned=len(photos),
        total_after_dedup=len(deduped),
        total_matched=len(deduped) - len(unmatched),
        total_unmatched=len(unmatched),
    )
