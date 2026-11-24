# DONNA (repo: `wardrobe`)

David's personal menswear wardrobe app: a single-page PWA on GitHub Pages,
with Cloudflare Workers for sync and try-on. David is the owner and the only
person who approves changes. This file is the short version; the linked files
are the authority, and where they disagree with this one, say so to David.

**Start here after 24 Nov 2026:** `docs/grok-handover.md` is the current
state, the design handover to Grok (who owns design work from now on), and the
list of docs that are out of date (including lines of this file). Then
`docs/queue.md` for what is queued. `docs/handover.md` (22 Nov) is older.

## Standing rules

- **Publishing: David has given a standing OK** (22 Nov 2026, asked "say
  'always' and I'll publish every fix as soon as its tests pass": "Always").
  Publish each finished fix once the full test suite passes: push to
  `preview`, wait for its CI run to go green, then run "Promote preview to
  live", and tell him afterwards what went live. Still never push to `main`
  directly and never force-push.
- **Preview data is real data.** The preview build shares browser storage and
  the sync account with the live app on the same device.
- **Never delete synced data.** A dislike never deletes a piece. Sync deletes
  are tombstones guarded server-side; read `worker/README.md` before touching
  anything in that path.
- **Do not deploy or write to the workers** (`wardrobe-sync`, `wardrobe-tryon`)
  without David's yes. `workers/tryon/` is a read-only copy of the deployed
  script; take a backup of the live script before any approved deploy.
- **Menswear only.** Never recommend women's items.
- **No owner personal data in the shipped page.** `tests/smoke.py` checks it.
- **FASHN credits can be spent without asking first** (David, 22 Nov 2026:
  "Use credits I don't care", after "Yes spend whatever you need for FASHN").
  Renders cost about 2 credits each and photo edits 1 (verify before
  quoting). Tell him afterwards how many were used and what is left. Any
  other spend, such as a new paid service, still needs a cost and his yes
  first.
- **Affiliate sources stay off** until a human enables them and supplies
  credentials. Do not apply to programmes or create accounts.
- **The Edit catalog is append-only.** Existing SKUs are locked; ingest never
  deletes a row or overwrites a field. See `docs/catalog-pipeline.md`.
- **`docs/eventual.md` is parked work.** Nothing there is in progress. Each
  item starts with a plan and mockups for David.

## Making a change to the app

1. Edit **`src/app.html`** (the whole app, about 3.9 MB). Never edit
   `index.html` or `app/*`: they are generated. Search the file with Grep;
   do not read it whole.
2. Run `python3 scripts/build_shell.py`. After a change to Home's first
   paint, also run `python3 scripts/critical_css.py`.
3. Bump the build string (`YYYY-MM-DD.86.NN`) everywhere it appears: once in
   `sw.js` (`WARDROBE_BUILD`) and three times in `src/app.html` (meta tag,
   build stamp, `var WARDROBE_BUILD`). Grep for the current number to find
   them. Check `preview` for the latest number first; another session may
   have taken the next one.
4. Add or update a test in `tests/` for the behaviour, quoting David's
   request in the docstring as existing tests do.
5. Run `python3 tests/run_all.py` (or `--only <name> ...`). Tests read the
   build from `sw.js`; never hard-code a build number. Tests block the real
   workers and use local mocks; keep it that way.

## Commits and branches

- One finished change per commit. CI rejects subjects starting with `WIP`
  and cache-bump-only commits.
- Subject: lowercase scope prefix, then what David will see, in plain words,
  then the build in brackets. Example from the log:
  `nav: the bar is bigger and sits clear of the home indicator (.86.42)`.
  Docs- and tests-only commits carry no build number.
- Work is meant to land on **`preview`** (published at `/wardrobe/preview/`).
  A cloud session that was assigned its own `claude/...` branch pushes there
  instead and tells David, who decides what reaches `preview`.
- `PUBLISHING.md` has the full flow. Two lines in it are out of date: the
  daily 04:00 promotion was removed on 21 Nov 2026 (manual only, see
  `.github/workflows/promote.yml`), and it names a `Grok Bot` commit author
  that no commit in the history uses.
- Almost every app change touches `src/app.html`, `index.html`, `sw.js` and
  the build number, so two sessions changing the app at once will conflict.
  Fetch `preview` before starting and again before pushing.

## Where things are

| Path | What |
|---|---|
| `src/app.html` | The app source. The only app file to edit. |
| `index.html`, `app/`, `sw.js` | Generated shell, code chunks, service worker. |
| `assets/` | Photos, on-body renders, cut-outs, catalog JSON. |
| `scripts/` | Build (`build_shell.py`, `critical_css.py`, `assemble_site.py`) and the catalog pipeline (`feeds/`). |
| `tests/` | Playwright tests, fixtures, `quarantine.json`, `smoke_baseline.json`. See `tests/README.md`. |
| `worker/` | Sync worker source and notes. The live worker differs from this copy; the README says how. |
| `workers/tryon/` | Read-only copy of the deployed try-on worker. |
| `docs/` | `catalog-pipeline.md`, `eventual.md`, `handover.md`. |
| `tools/chat-2026-11-22/` | Helper scripts from the 21–22 Nov chat. Not part of the app. |
| `.github/workflows/` | `smoke.yml` (CI), `pages.yml` (deploy), `promote.yml` (preview to live, manual). |

## David's style rules

The rules live in code and tests, not here. Find the current version before
changing behaviour near them:

- Dress levels: Daytime, Nighttime Casual, Nighttime Dressy, Formal.
- Belts follow rules (matched to shoes, plain leather with a blazer and up,
  never dealt at random); sunglasses by day only. Grep `belt` in
  `src/app.html` and see `tests/test_composer73.py`, `tests/test_gotos843.py`.
- When David states a new rule, put it in a test with the date and the quote.

## Talking to David

- Plain language, what changed on screen, no code unless asked.
- State uncertainty. Do not present a guess as a fact, and do not invent
  API names, sources or numbers; verify in the repo or the current docs.
- Report test results as they are, including failures and quarantined tests.
