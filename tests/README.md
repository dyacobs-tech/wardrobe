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

Run it locally:

    pip install playwright && python -m playwright install chromium
    python -m http.server 8000 &          # from the repo root
    python tests/smoke.py                  # or: python tests/smoke.py https://dyacobs-tech.github.io/wardrobe/

`tests/smoke_baseline.json` lists issues known on 17 Nov 2026. They report `KNOWN` instead of failing. When one starts passing the run prints `FIXED?`; delete it from the baseline then. Any other failure fails the run.

The GitHub Action (`.github/workflows/smoke.yml`) runs on every push to `main`, on pull requests, daily against the live site, and on demand.

**For the publisher (MUSE):** the publish step must keep the `.github/` and `tests/` folders. If it replaces the whole tree, add them to what it preserves.
