"""Loads roster.json and builds name/alias lookup indexes."""

import json
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Roster:
    teams: list          # list[list[str]], canonical member names per team, roster order preserved
    name_lookup: dict     # lowercase canonical name -> canonical name
    alias_lookup: dict    # lowercase alias phrase -> canonical name
    person_to_team: dict  # canonical name -> team index (into teams)
    adjustments: dict     # canonical name -> flat count adjustment (e.g. manual corrections)
    exclusions: list      # list of {person?, date?, filename_contains?} rules; matching photos never count
    late_upload_deadline: Optional[dict]  # {cutoff_hour, timezone} or None to disable the late-upload rule
    flagged_overrides: list  # list of {person?, date?, filename_contains?} rules; reviewed OK despite a bad filename date, count normally


def load_roster(path: str) -> Roster:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    teams = [team["members"] for team in data["teams"]]

    name_lookup = {}
    person_to_team = {}
    for team_index, members in enumerate(teams):
        for name in members:
            name_lookup[name.lower()] = name
            person_to_team[name] = team_index

    alias_lookup = {alias.lower(): canonical for alias, canonical in data["aliases"].items()}
    adjustments = data.get("adjustments", {})
    exclusions = data.get("exclusions", [])
    late_upload_deadline = data.get("late_upload_deadline")
    flagged_overrides = data.get("flagged_overrides", [])

    return Roster(
        teams=teams,
        name_lookup=name_lookup,
        alias_lookup=alias_lookup,
        person_to_team=person_to_team,
        adjustments=adjustments,
        exclusions=exclusions,
        late_upload_deadline=late_upload_deadline,
        flagged_overrides=flagged_overrides,
    )
