"""Builds the standings HTML page from an AggregateResult. No filesystem access."""

import html

RANK_LABELS = {0: "1st place", 1: "2nd place", 2: "3rd place"}


def _team_heading(members):
    if len(members) <= 1:
        return ", ".join(members)
    return ", ".join(members[:-1]) + " & " + members[-1]


def _member_rows(team):
    rows = []
    sorted_members = sorted(team.members, key=lambda m: team.counts[m], reverse=True)
    for member in sorted_members:
        count = team.counts[member]
        pct = 0 if team.total == 0 else round((count / team.total) * 100)
        pct = max(pct, 4) if count > 0 else 0
        rows.append(
            f'<div class="member-row">'
            f'<span class="name">{html.escape(member)}</span>'
            f'<span class="meter"><span style="width:{pct}%"></span></span>'
            f'<span class="count">{count}</span>'
            f"</div>"
        )
    return "\n".join(rows)


def _team_card(rank, team):
    card_class = f" rank-{rank + 1}" if rank in RANK_LABELS else ""
    badge = f'<div class="rank-badge">{RANK_LABELS[rank]}</div>' if rank in RANK_LABELS else ""
    heading = _team_heading(team.members)
    return f"""
<div class="team-card{card_class}">
  {badge}
  <h2>{html.escape(heading)}</h2>
  <div class="total">{team.total} <span>photo{'s' if team.total != 1 else ''}</span></div>
  <details>
    <summary>Member breakdown</summary>
    {_member_rows(team)}
  </details>
</div>"""


def _unmatched_section(unmatched):
    if not unmatched:
        return ""
    items = []
    for photo in unmatched:
        guess = html.escape(photo.unmatched_guess or "?")
        dept = html.escape(photo.department)
        items.append(
            f"<li><code>{html.escape(photo.filename)}</code> "
            f"&mdash; best guess: <strong>{guess}</strong>, department: {dept}, date: {photo.date}</li>"
        )
    return f"""
<details class="unmatched-panel">
  <summary>Unmatched files &mdash; needs review ({len(unmatched)})</summary>
  <ul>
    {''.join(items)}
  </ul>
</details>"""


def render(aggregate_result, generated_at_str):
    cards = "\n".join(
        _team_card(rank, team)
        for rank, team in enumerate(aggregate_result.teams)
    )
    unmatched_html = _unmatched_section(aggregate_result.unmatched)

    total_people = sum(len(team.members) for team in aggregate_result.teams)
    total_teams = len(aggregate_result.teams)
    photos_str = f"{aggregate_result.total_after_dedup:,}"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Session 3 Campanion Standings</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Anton&display=swap" rel="stylesheet">
<link rel="stylesheet" href="style.css">
</head>
<body>
<header class="hero">
  <h1>Session 3 Campanion Standings</h1>
  <div class="stats-badge">
    <span class="accent">{photos_str}</span> photos so far &middot; {total_people} people &middot; {total_teams} teams &middot; 1 camp
  </div>
  <p class="last-updated">Last updated: {html.escape(generated_at_str)}</p>
</header>
<main>
  <div class="leaderboard">
    {cards}
  </div>
  {unmatched_html}
</main>
</body>
</html>
"""
