# Smoke test

`tests/smoke.py` loads a build in a headless, iPhone-sized Chromium with an empty profile and checks:

- the build meta, the Today hero (title + photo), the manifest and its icons
- that each bottom tab (Today, Closet, Ideas, Shop) opens its panel
- that "Mark worn" survives a reload
- that the outfit of the day stays the same when the app is opened again
- that no owner personal data ships in the page
- that no new element id is looked up by the JS without existing in the page
- that there are no JS errors and no 4xx/5xx from the site itself

Requests to `*.workers.dev` (sync and render queue) are **blocked**, so a run never creates a sync account, uploads data or queues a render.

A second Playwright check, `tests/test_restore59.py`, boots a simulated .57/.58 profile against a **local mock** of the sync protocol (never the production worker) and asserts the .59 closet restore plus the Home chevron and bottom-nav first-paint geometry.

Run it locally:

    pip install playwright && python -m playwright install chromium
    python -m http.server 8000 &          # from the repo root
    python tests/smoke.py                  # or: python tests/smoke.py https://dyacobs-tech.github.io/wardrobe/
    python tests/test_restore59.py          # local mock worker; never hits production
    python tests/test_feet.py               # cut-out shoes are opaque on both feet (needs ffmpeg)

`tests/smoke_baseline.json` lists issues known on 17 Nov 2026. They report `KNOWN` instead of failing. When one starts passing the run prints `FIXED?`; delete it from the baseline then. Any other failure fails the run.

The GitHub Action (`.github/workflows/smoke.yml`) runs on every push to `main`, on pull requests, daily against the live site, and on demand.

## Every test file

    python3 tests/run_all.py            # serves this checkout, runs every test_*.py + smoke.py
    python3 tests/run_all.py --only safety update

Tests read the build under test from `sw.js` (`tests/buildinfo.py`), never a hard-coded build number. `tests/quarantine.json` lists tests that run but cannot fail CI, each with the reason and what un-quarantines it. Safety tests: `test_safety1119.py` (no accidental deletes in any synced collection; a dislike never deletes), `test_update1119.py` (updates wait for idle; atomic SW precache; previous code kept one release; image-cache LRU), `test_syncsafety77.py`.

The published site never contains `tests/` (see `PUBLISHING.md`).
