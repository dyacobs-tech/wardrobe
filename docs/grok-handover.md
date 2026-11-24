# DONNA: design handover to Grok (24 Nov 2026)

David is moving **design work** (look and feel, layout, formatting) from Claude to Grok. This is the checklist for
that switch: what David decides first, the state of the code, setup, how a change ships, the rules that must not
break, a map of the design system, the open design work, and how work passes between Grok and Claude. `CLAUDE.md`
stays the authority for the rules; section 10 lists where it and other docs are out of date.

Line numbers drift with every build: find things by the selector, function or comment named here (grep `src/app.html`).

---

## 1. Decisions David makes before Grok starts

- [ ] **How Grok reaches the repo** (`dyacobs-tech/wardrobe`): which GitHub account or token, and which branch it
      pushes to. Nothing in the repo says how Grok connects.
- [ ] **Which commit author Grok uses.** `PUBLISHING.md` names a `Grok Bot` author (23 such commits exist on old side
      branches from 18–19 Nov; none on `main` or `preview`).
- [ ] **Do the standing OKs extend to Grok?** Both are in `CLAUDE.md` and name no assistant:
      publish every finished fix once the full test suite passes ("Always", 22 Nov), and spend FASHN credits without
      asking ("Use credits I don't care", 22 Nov).
- [ ] **One writer at a time.** Every app change touches `src/app.html`, `index.html`, `sw.js`, `app/*` and the build
      number, so two assistants changing the app at once conflict on every push. Recommended: Grok owns design
      changes, Claude keeps engineering and data work (section 9), and neither starts an app change while the other
      has one unpublished. Section 8 says how to hand over.
- [ ] **The approved but unreleased redesign `.86.93`** (commit `5d63a8c7` on `claude/keen-albattani-2m0tbq`): one
      tab-row style everywhere, 12 helper captions removed, all seven dress levels on Home and Curate. David approved
      each part ("Yes", "Yes", "All of them"). Either Claude lands it before handover, or Grok takes it as its first
      job (notes in section 7).
- [ ] **Test fixtures:** David decides what happens to `tests/fixture_closet_live.json` (Claude has told him why).
      Until then, never copy it into new fixtures or share screenshots made from it; use `photographed_closet()`.

## 2. State at handover

Check `sw.js` (`WARDROBE_BUILD`) on `main` and `preview` for the current builds.

| Where | Build at handover | What |
|---|---|---|
| Live: `main`, https://dyacobs-tech.github.io/wardrobe/ | .87.03 | Moves only through "Promote preview to live" |
| `preview` (`/wardrobe/preview/`) | .87.03 | Where every finished change lands first |
| `claude/keen-albattani-2m0tbq` | .86.93 | The unreleased redesign only. Do not start from it |
| Every other remote branch | — | Stale. `build-7x`, `cursor/*`, `ci-smoke-test` and `improve-mobile-polish` share no history with `main` (it restarted on 21 Nov) and cannot be merged |

- [ ] **Do not start until `preview` shows .87.03** (Claude publishes .87.00–.87.03 before handover). Then **start every
      change from `origin/preview`'s head**, never from a local `main` or an old branch.
- [ ] Shipped on 24 Nov: .86.97 (The Edit tap freeze fixed), .86.98 (lighter freeze recorder), .86.99 (The Edit at Pool
      / Beach shows only his own closet), .87.00 and .87.02 (Evening Casual is worn untucked), .87.01 (Ask DONNA opens
      a clean chat, with "Earlier chats"), .87.03 (113 tucked outfit pictures show their belt).
- [ ] **The next free build number is .87.04.** Builds use `2026-11-22.87.NN` (the date part has stayed fixed).

## 3. Setting up

- [ ] Read `CLAUDE.md`, then this file, then `tests/README.md` (partly stale, see section 10).
- [ ] Clone the whole repo, including the ~700 MB `assets/` tree: the tests serve the checkout.
- [ ] Python 3 with `playwright==1.60.0` (the version CI pins), `numpy`, `pillow`, `tinycss2` (`build_shell.py` needs
      it), and `ffmpeg` (one test decodes the cut-out webps). Install **both Chromium and WebKit** browsers.
      `tests/README.md` says Chromium only; that is not enough. Six files launch WebKit with no fallback.
- [ ] Run the full suite once before changing anything: `python3 tests/run_all.py` (about 30–35 minutes; it serves the
      checkout on a random port and blocks the real workers with local mocks). Everything should pass except files
      in `tests/quarantine.json`, which are reported but cannot fail the run. If one fails, re-run it alone
      (`--only <name>`) before deciding it is real: a few are timing-sensitive on a busy machine.
- [ ] You will not have the cloud keys (sync, try-on, FASHN) and do not need them for design work.

**Seeing the app with realistic data, without his private data or a sync key:**
`tests/wardrobe_fixture.py` (`photographed_closet()`) seeds a photographed closet (see the init script in
`tests/smoke.py`). `tests/audit78.py` `seed_script()` also seeds Shop. `tests/test_askfresh8701.py` shows Ask DONNA
with a chat history (seeds `wardrobe.ask.thread`, fakes sign-in, mocks POST `/ask`). The old screenshot tools
(`audit75–78.py`, `sweep64.py`) are stale: they click `#section-closet`, which no longer exists.

## 4. Making and shipping a change

1. Edit **`src/app.html` only** (the whole app, about 4 MB: grep it, never read it whole). Never edit `index.html` or
   `app/*`; they are generated.
2. `python3 scripts/build_shell.py`. After any change to Home's first paint: `build_shell.py`, then
   `python3 scripts/critical_css.py`, then `build_shell.py` again. The first-paint CSS is chosen by **exact selector
   text** from `src/critical-selectors.json` (last regenerated at .86.68): editing a Home rule's selector (for example
   adding `:not(#n893)`) silently drops it from first paint until that file is regenerated. `test_open850` requires
   Home to show within 3.4 s, so extra first-paint weight can fail it.
3. CSS moves to `app/` at build time, so a CSS `url()` must be written `url("assets/…")`, `url('assets/…')` or
   `url(assets/…)`; any other form 404s.
4. Bump the build string in four places: `sw.js` (`WARDROBE_BUILD`, once) and `src/app.html` (meta tag, build stamp,
   `var WARDROBE_BUILD`). Check `preview` for the latest number first.
5. **A font, icon or picture changed under the same file name never reaches the installed app** (and preview shows
   live's copy, see section 5). Fonts live in a hand-kept list in `sw.js` (`SHELL_FILES`) and are cached first:
   ship a changed font under a new file name and update both `SHELL_FILES` and the `@font-face` text in
   `addFonts806`. Redrawn pictures under the same name need `ONBODY_CACHE` in `sw.js` bumped.
6. Add or update a test for the behaviour, quoting David with the date in the docstring. Tests read the build from
   `sw.js`; never hard-code it.
7. Run the full suite. Report results as they are, including failures and quarantined tests.
8. One finished change per commit. Subject: lowercase scope, what David will see in plain words, build in brackets,
   e.g. `nav: the bar is bigger and sits clear of the home indicator (.86.42)`. Docs- or tests-only commits carry no
   build number. No `WIP`, no cache-bump-only commits.
9. Push to `preview` (fast-forward only: **never push `main`, never force-push**). CI ("Smoke test") runs on pushes to
   `main` and `preview` and on pull requests and takes about 25–36 minutes.
10. When it is green: Actions → "Promote preview to live" (manual; it refuses unless `preview`'s head has green `smoke`
    and `tests` checks). Deploy takes about 2–3 minutes. Then tell David what went live, in plain words, and how to
    get it (next point).

**How his iPhone gets a new build.** Only through the service worker: the app checks when it opens and when it comes
back to the foreground (at least 60 s after the last check). The new build installs in the background; the page
reloads into it, except while a sheet is open, a field has focus or he typed in the last 15 s (then an "Update ready."
bar shows). On a slow connection the first open still shows the old build. So after a promote, tell him: fully close
DONNA and reopen it; Profile → Advanced shows the build. (The page's own "newer build" check, `checkBuild`, reads only
the first 4 KB of `index.html` while the build tag sits further in, so it never fires: an engineering fix for Claude.)

## 5. Guardrails (never break these)

- [ ] **Preview is real data, and not a full sandbox.** `CLAUDE.md` says preview shares storage and the sync account
      with the live app. In the code (guard near the top of `src/app.html`, `/preview/`), preview **reads** the live
      data, its localStorage writes stay in memory and every write to the workers gets a fake 503, but **IndexedDB
      (the photo vault) is shared with the live app**; only the vault's clean-up sweep is skipped on preview. Ask
      DONNA, try-on and feedback do not work on preview.
- [ ] **Preview is not the installed app.** It deploys on every push to `preview` with no test gate (2–3 minutes); it
      runs in a Safari tab (no standalone mode, different heights than the home-screen app, which Home's geometry
      depends on); a fixed "PREVIEW" badge covers the centred wordmark; and its `assets/` are served from **live**
      (an asset changed under the same name shows live's copy, and a new asset goes live before promotion).
- [ ] **Never delete synced data.** A dislike never deletes a piece; earlier Ask chats are only hidden. Read
      `worker/README.md` before touching anything in the sync path.
- [ ] **Never deploy or write to the workers** (`wardrobe-sync`, `wardrobe-tryon`) without David's yes, and back up the
      live script first. `workers/tryon/` is a read-only copy.
- [ ] **Menswear only.** Never recommend or show women's items (`window.notMenswear853` filters the catalog).
- [ ] **No owner personal data in the shipped page.** `tests/smoke.py` checks the rendered page and every same-origin
      script and stylesheet it loads (not JSON data files or images). The repo is public: keep his photos and closet
      data out of it.
- [ ] **No camera photos of him in the app**; a logged look shows his avatar picture.
- [ ] **Affiliate sources stay off**; do not apply to programmes or create accounts. **The Edit catalog is append-only.**
      **`docs/eventual.md` is parked**: each item starts with a plan and mockups for David.
- [ ] **Any spend other than FASHN needs a cost and David's yes first.**
- [ ] **Removing markup:** smoke's dead-id check fails CI when an id looked up by inline or bundled code disappears
      (exceptions in `tests/smoke_baseline.json`), but lookups in the two big chunks (`app/01.*.js`, `app/02.*.js`)
      are **not** checked. Before deleting an element, grep `src/app.html` for its id and keep or retire each use.
- [ ] **Do not define `--sab`** in `:root`: it is a test hook that otherwise falls back to the real iPhone home-indicator
      inset (defining it puts the nav back on the home bar, a .86.42 complaint). Home geometry tokens (`--home-top`,
      `--home-room`, `--fig-h`, `--pv-fab-dy` …) are written by JavaScript; a stylesheet value fights the JS.
- [ ] **Words on screen:** "Looks", never "lookbook"; nothing is called "Vesper"; Shop never opens on Ask DONNA.
- [ ] When a safety check refuses something, do not route around it: tell David and let him decide.

## 6. Design system map

**Themes and colour.** `html[data-theme="light"|"dark"]`, light by default. The theme comes only from localStorage
`wardrobe-theme` or Profile → Info (`#theme-dark`); the phone's dark mode and Playwright's `color_scheme` are ignored.
Tokens in `:root` and the dark block: `--bg` #F6F2EA, `--surface` #FFFBF4, `--text` #1A1612, `--dim` #6E6456,
`--border` #E4D9C8, `--brass`, `--indigo`. Honey bottom nav: `--honey-nav` #C29E74 (dark #8A6A44), `--honey-ink*` at
4.5:1 contrast. Home has its own off-white set (`--ow-*`). About 300 hard-coded hex colours remain, and some tokens
are used but never defined (`--line`, `--muted`, `--card`, `--surface-2` …; but see `--sab` above).

**Dark mode is barely tested:** every layout guard runs in light; only `test_curate81` and `test_home864` really set
the dark theme (`test_audit883`'s "dark" check uses `color_scheme` and so runs in light). Check dark by hand after
any colour or token change.

**Type.** Inter (UI) and Fraunces (display), self-hosted variable fonts in `assets/fonts/`, added after first paint on
a first open (at once on later opens) with metric-matched fallbacks. Tokens: `--fs-label` 11px, `--fs-meta` 13,
`--fs-body` 15, `--fs-ctl` 12, `--fs-card-title` 16, `--fs-title` 20, `--fs-title-lg` 22. Headings and title classes
are forced to Fraunces 600 with `!important`. In practice there are 54 distinct font sizes.

**Sizing.** Pills: `--ctl-h` 34px, radius 999px, 12px/600, forced with `!important` (the .75 pill system). Cards:
`--radius` 16px. A 44px invisible touch strip sits in a `::before` on chips and buttons: do not draw icons in a
chip's `::before`. Bottom bar slot `--bb-h` = 68px + safe area; the visible `.nav-pill` is 52px.

**Breakpoints.** Phone layout below 900px (`max-width: 899px`: Home is `position: fixed`, sheets become bottom sheets,
card shadows off). From 900px the nav becomes a centred honey pill while content keeps the phone layout; from 1024px
content sits in a centred column. Also 760, 640 and 430px rules. Check 390–430, ~950 and ~1280px.

**Components.** Masthead `header.masthead` (wordmark per page). Bottom bar `#bottombar > .nav-pill > .navbtn` ×5.
Floating + `#pv-fab` (kept off card titles by JS). Back chevron `#view-back`. Cards: `.cf-card` (Looks), `.en-card`
(The Edit feeds), `.ask-card` (Ask DONNA), `.vp-card` (shared product card). Sheets: `.info-pop-backdrop >
.info-pop-card` (bottom sheets on phones), plus `#vp-sheet`, `#item-detail`, `#look-layer`.

**Tab rows: at least six styles live today** (the .86.93 redesign unifies them): Looks `.lk-seg841`, The Edit
`.ins-seg841`, `.ins-mini841`, Profile `#subnav-me .subnav-scroll`, Calendar `.cal-subtabs`, and Shop's three rows
(`.edit-section-tabs`, `.edit-shop-tabs`, Curate `.curate-subs`), which all also carry `.edit-tabs`:
`#panel-find .edit-tabs` is restyled in 7+ places.

**Page map.** Home `#tab-today` → `#panel-today`. Looks `#section-ideas` → `#panel-looks` (`html[data-lkm]` =
outfits / gotos / liked; Closet is `#panel-wardrobe`). The Edit `#section-inspo` renders inside `#panel-looks` with
`html[data-lkm="inspo"]` and `html[data-insv]` (Icons · Inspo · Dress me). Shop `#tab-find` → `#panel-find` (Shop ·
Curate · Ask DONNA). Calendar `#section-calendar`. Profile (masthead icon) → Info / Location / Rules / Advanced.

**How the CSS is layered (traps).** Blocks are appended by build ("Build .72 — one design system", ".78.9d honey nav",
".86.62 formatting audit" …) and later ones override earlier ones; beaten rules were left in place. About 1,500
`!important`s. Id boosters such as `:not(#_)` and `body:is(body, #lock782…)` are used to win; id-scoped rules
(`#subnav-me …`, `#panel-find …`) need an id in a new selector to be beaten, which is why .86.93 adds `:not(#n893)`.
48 inline `style=` attributes and about 100 JS style writes. Consolidating instead of appending another layer would
help every future change.

## 7. Open design work (suggested order)

1. **The .86.93 redesign** (if David hands it over). Rebase onto `preview`: only the three build-string lines conflict
   as text; for generated files take either side and rebuild. Then:
   - it forces `.ins-mini841 { display:flex !important }`, which beats the inline style that hides the empty pill at
     Pool / Beach since .86.99: keep that pill hidden, and add a check to `tests/test_poolcloset899.py`;
   - its Curate weight-group change (4 → 7 groups, `PARENT893`) is logic, not looks: have Claude review it;
   - add tests for the unified tab row and the removed captions; re-check `test_format862` and `test_layout888`;
   - it adds `:not(#n893)` to Home rules: regenerate the critical CSS (section 4, step 2).
2. **Rewrite the two quarantined design specs** to today's design, or retire them with David's OK: `test_design72`
   (the .72 pill spec) and `test_fix74` (old Home caption; today's rule: dark centred text on #F6F2EA with the "From
   your closet" title).
3. **`test_gotos843` (quarantined):** a Liked card's avatar is about 1px larger than its box. Unverified idea: the test
   measures with `getBoundingClientRect()`, which includes the CSS `scale` (0.9–1.1) used to even out his height.
4. **Picture proportions:** David said in chat that in some pictures he looks wider, taller or shorter. Get his
   screenshots first: if it is how pictures are sized on screen it is design; if the drawings are wrong it is picture
   work (section 9).
5. **Ask DONNA:** style the new "Earlier chats" button and divider (`.ask-earlier903`, `.ask-old903`, `.ask-new903`).
6. **Home stability** is his most repeated complaint: picture size, icons hidden under the nav, spacing, text that
   moves, flicker. Guarded by `test_homefit861`, `test_homevh852`, `test_home70`, `test_open850`, `test_height874` (all
   also in WebKit) and `test_hero1119` (Chromium only). Keep them green and check WebKit by hand.

**Tests that pin layout** (a redesign must keep these or change them on purpose). Both engines: `test_format862`
(Profile tabs ≥48px wide; Shop rows not cut; section labels exactly Shop / Curate / Ask DONNA) and the Home tests
above. Chromium only: `test_layout888` (pages end ≥8px clear of the bar; Profile tabs fit; the + never covers a card
title), `test_askpage882` (Ask answer 15–18px; cards ≤52% wide), `test_nav67`, `test_subnav64`, and `smoke.py` (no
page wider than the screen; no new dead ids). `test_nav62` is partly WebKit. There are no pixel baselines.
**Playwright cannot reproduce the iPhone's safe areas or the installed app**: `env(safe-area-inset-*)` is 0 there
(`test_nav62` fakes a 34px inset) and standalone mode is only faked. Status-bar and home-indicator spacing can only be
confirmed on David's phone or from his screenshots.

## 8. Handing work back and forth

- [ ] Keep one shared record: update **`docs/queue.md`** with what you changed, the build, and what is unfinished, in
      the same commit or right after. Claude reads it (and this file) before starting. Do not leave unpublished work in
      a local copy when handing over: publish it to `preview`, or say plainly what is unpublished and where.
- [ ] David's in-app feedback ("Send feedback", "Sent to Claude") is stored in synced data that only Claude can read
      (it needs the sync key). Ask David to send design notes to Grok directly, or ask Claude to pass them on.
- [ ] Before starting, fetch `preview` and check its build; before pushing, fetch again (another assistant may have
      taken the next build number).

## 9. Not design work (stays with Claude, or needs David's yes)

- The hardened sync worker: written, not deployed. David agreed in chat on 24 Nov ("Okay so this"); Claude deploys it
  after the app fixes are live, with a backup of the live script first (`worker/README.md`).
- Any worker change, e.g. Ask DONNA answering "Hi" with product picks (the try-on worker's prompt requires picks).
- The broken in-page "newer build" check (`checkBuild`, section 4).
- Outfit rules (belts, tucks, dress levels, swim, Formal, sweater-over-shirt): they live in code and tests, each with a
  test quoting David (`tests/test_composer73.py`, `test_eccasual8700.py`, `test_nosweater890.py`, `test_formal859.py`,
  `test_swim856.py` …).
- Pictures (FASHN renders and edits, cut-outs). 36 belt edits were rejected and those pictures stay beltless; pictures
  already drawn with a tucked shirt are kept out of Evening Casual until redrawn untucked.

## 10. Out-of-date docs (do not trust these lines)

- `CLAUDE.md`: lists four dress levels with old names (the app has seven: Pool / Beach, Daytime, Evening Casual,
  Evening Sharp, Evening Dressy, Formal, Black Tie); says builds are `.86.NN` (now `.87.NN`); says preview shares data
  (see section 5 for what it really does); cites `test_gotos843` for belts (belt checks are in `test_composer73`,
  `test_rules860`, `test_rules877`, `test_audit883`, `test_sharp865`); points new sessions to `docs/handover.md`.
- `PUBLISHING.md`: describes a daily 04:00 promotion (removed: manual only) and says every push runs CI (only
  `main`/`preview` pushes and pull requests do).
- `docs/handover.md` (last updated 22 Nov, around .86.66) and `docs/queue.md` (says live is .86.77) are stale.
- `tests/README.md`: old tab names; says install Chromium only; smoke also runs on `preview` pushes.
- `docs/catalog-pipeline.md`: says to push to `main` (never: push to `preview`).
- The seed Wardrobe Rules text in `src/app.html` still says dress tees are tucked and that the sweater rule applies
  only at 70°F+; the code and tests say otherwise.

## 11. Talking to David

- Plain language: what changed on screen. No code unless he asks. His iPhone is the test.
- State uncertainty; never present a guess as a fact or invent names, sources or numbers.
- Report test results as they are, including failures and quarantined tests.
- Do everything that needs no answer first, then ask once, briefly.
- When he states a new rule, put it in a test with the date and his words.
- `docs/queue.md` carries his request "I need more updates on what is in queue": end replies with a short version of
  what is queued.
