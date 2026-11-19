# Publishing (from Nov 19 2026)

**Live** = `main` → https://dyacobs-tech.github.io/wardrobe/
**Preview** = `preview` → https://dyacobs-tech.github.io/wardrobe/preview/

1. Agents and humans push work to **`preview`**, never straight to `main`.
   Edit `src/app.html`, run `python3 scripts/build_shell.py` (and
   `scripts/critical_css.py` after first-paint changes), bump the build in
   `sw.js` / `src/app.html`, commit with a scope prefix
   (`safety:`, `speed:`, `design:`, `edit:` …) as `Grok Bot <bot@grokbot>`.
   One finished change per commit: no `WIP`, no cache-bump-only commits.
2. Every push runs CI (`smoke` + `tests`: every file in `tests/` via
   `tests/run_all.py`; quarantined tests are listed with reasons in
   `tests/quarantine.json`).
3. **Promotion**: `.github/workflows/promote.yml` fast-forwards `main` to
   `preview` daily at 04:00 ET, or on demand (Actions → "Promote preview to
   live" → Run). It refuses when preview's head has no green CI or when
   `main` has commits `preview` lacks. Never force-push.
4. Deploys: `.github/workflows/pages.yml` assembles only the app files
   (`scripts/assemble_site.py`) — `tests/`, fixtures, `src/`, `scripts/` and
   worker sources are never published.

The preview build shares the browser storage (and therefore the sync account)
of the live app on the same device, so treat it as real data. Its service
worker and caches are separate (`preview-…`), and it reads the live `assets/`.
