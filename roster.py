"""Loads roster.json and builds name/alias lookup indexes."""

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class Roster:
    teams: list          # list[list[str]], canonical member names per team, roster order preserved
    name_lookup: dict     # lowercase canonical name -> canonical name
    alias_lookup: dict    # lowercase alias phrase -> canonical name
    person_to_team: dict  # canonical name -> team index (into teams)
    adjustments: dict     # canonical name -> flat count adjustment (e.g. manual corrections)


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

    return Roster(
        teams=teams,
        name_lookup=name_lookup,
        alias_lookup=alias_lookup,
        person_to_team=person_to_team,
        adjustments=adjustments,
    )
