# Standings Tracker (Session 3)

Scans the "Session 3 Uploaded" Dropbox folder, counts photo submissions
per person, rolls them up into teams of three, and publishes a static
leaderboard page.

## How it works

- `scan.py` reads filenames from the Dropbox `Uploaded` folder (not the
  submissions root — only files that have actually made it into `Uploaded`
  count).
- `parser.py` extracts a name, date, and department from each filename,
  tolerating the real messy formats found in the folder (missing dates,
  missing departments, broken separators, raw phone-default names).
- Filenames are matched to people using `roster.json` — exact (case-insensitive)
  name matching plus a small alias table for known name variants (e.g.
  "Laina Stapleton" -> "Laina"). Anything that can't be matched shows up in
  the "Unmatched — needs review" panel on the page instead of being dropped
  or guessed at.
- `aggregate.py` de-duplicates accidental re-uploads (files like
  `IMG_5218 (1).jpeg` next to `IMG_5218.jpeg`) and tallies totals per person
  and per team.
- `render.py` writes the result to `docs/index.html` + `docs/style.css`.
- `publish.py` commits and pushes `docs/` to GitHub so GitHub Pages serves
  the updated page.

## Editing the roster

Edit `roster.json` directly — it's just team member lists plus an alias
table:

```json
{
  "teams": [ { "members": ["Laura", "Sophie", "Maddie"] }, ... ],
  "aliases": { "Laina Stapleton": "Laina" }
}
```

Add a new entry to `aliases` any time someone's filenames don't match their
roster name (check the "Unmatched — needs review" panel on the live page to
spot these).

## Running manually

```
cd /Users/digi3dprinter/Developer/standings-tracker-session3
python3 scan.py            # dry run — writes docs/ locally, doesn't touch git
open docs/index.html       # eyeball it before publishing
python3 scan.py --publish  # writes docs/ AND commits + pushes to GitHub
```

Always safe to re-run — re-scanning and re-publishing just overwrites
`docs/` with the latest counts.

## One-time setup

### 1. Run the test suite

```
python3 -m unittest tests.test_parser -v
```

### 2. GitHub repo + Pages

1. Create a **public** GitHub repo (e.g. `standings-tracker-session3`).
2. From this folder:
   ```
   git init
   git remote add origin <your-repo-url>
   git add .
   git commit -m "Initial standings tracker"
   git branch -M main
   git push -u origin main
   ```
3. In the repo's Settings -> Pages, set source to branch `main`, folder `/docs`.
4. GitHub will give you a URL like `https://<you>.github.io/standings-tracker-session3/`
   — that's the link to share.

### 3. First real run

```
python3 scan.py --publish
```

Confirm the Pages URL shows the live standings (may take a minute or two
after the first push for Pages to build).

### 4. Install the daily auto-refresh (10:00 AM)

```
launchctl bootstrap gui/$(id -u) /Users/digi3dprinter/Developer/standings-tracker-session3/com.calder.standingstracker.plist
```

Check it's loaded:

```
launchctl print gui/$(id -u)/com.calder.standingstracker-session3
```

To remove it later:

```
launchctl bootout gui/$(id -u)/com.calder.standingstracker-session3
```

Logs land in `~/Library/Logs/standings-tracker-session3.log` and
`~/Library/Logs/standings-tracker-session3-err.log`.

**Caveats:** the job only runs if the Mac is on and awake around 10 AM. If
it's asleep, macOS generally catches up shortly after wake, but if the Mac
is fully off that day's run is simply skipped — just run
`python3 scan.py --publish` by hand whenever you notice it's stale.
