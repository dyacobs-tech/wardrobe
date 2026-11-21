"""Wardrobe smoke test — boots a build in a headless iPhone-sized browser and
checks the things that have broken before.

Usage:
    python tests/smoke.py                      # http://localhost:8000/ (CI serves the checkout)
    python tests/smoke.py https://dyacobs-tech.github.io/wardrobe/

Safety: every request to the sync / render worker (*.workers.dev) is blocked,
so a run never registers a sync account, uploads data or queues a render.
Each run uses a fresh, empty browser profile.

Known issues live in tests/smoke_baseline.json. A check listed there reports
KNOWN instead of failing; when it starts passing the run says so, so the
entry can be deleted. Any NEW failure fails the run (exit 1).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from wardrobe_fixture import photographed_closet

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/"
HERE = Path(__file__).resolve().parent
BASELINE = json.loads((HERE / "smoke_baseline.json").read_text(encoding="utf-8"))
KNOWN_CHECKS = set(BASELINE.get("known_failing_checks", []))
KNOWN_DEAD_IDS = set(BASELINE.get("known_dead_ids", []))

results: list[tuple[str, str, str]] = []  # (status, check, detail)


def check(name: str, ok: bool, detail: str = "") -> None:
    if ok:
        status = "FIXED?" if name in KNOWN_CHECKS else "PASS"
    else:
        status = "KNOWN" if name in KNOWN_CHECKS else "FAIL"
    results.append((status, name, detail))


def main() -> int:
    errors: list[str] = []
    bad_responses: list[str] = []
    blocked: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(
            viewport={"width": 375, "height": 812},
            device_scale_factor=2,
            is_mobile=True,
            has_touch=True,
            service_workers="block",  # test the network build, not a cached shell
        )

        def block_worker(route):
            blocked.append(route.request.url)
            route.abort()

        ctx.route(re.compile(r"https?://[^/]*workers\.dev/.*"), block_worker)
        # Exercise the asynchronous weather update on both opens with the same forecast.
        ctx.route("**/v1/forecast?**", lambda r: r.fulfill(json={
            "current": {"temperature_2m": 70, "weather_code": 0}, "daily": {"time": []}
        }))
        # A named Home outfit needs a photograph keyed to these closet IDs.
        ctx.add_init_script(
            "(() => { if (localStorage.getItem('wardrobe.items')) return;"
            " localStorage.setItem('wardrobe.items', JSON.stringify(%s));"
            " localStorage.setItem('wardrobe.todaySource', JSON.stringify('wardrobe'));"
            " })();" % json.dumps(photographed_closet())
        )
        page = ctx.new_page()
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}")
                if m.type == "error" and "workers.dev" not in m.text
                and "ERR_FAILED" not in m.text
                # Resource-load failures are judged by the own-origin
                # 4xx/5xx check below; third-party images (retailer CDNs)
                # can refuse cross-origin loads and are not app bugs.
                and not m.text.startswith("Failed to load resource") else None)
        origin = re.match(r"https?://[^/]+", URL).group(0)

        def on_response(r):
            if r.url.startswith(origin) and r.status >= 400:
                bad_responses.append(f"{r.status} {r.url}")

        page.on("response", on_response)

        # ---- boot -------------------------------------------------------
        page.goto(URL, wait_until="load")
        page.wait_for_timeout(2500)
        build = page.evaluate(
            "document.querySelector('meta[name=wardrobe-build]')?.content || ''")
        check("build meta present", bool(build), build)
        title1 = page.evaluate("document.querySelector('#today-name')?.innerText?.trim() || ''")
        check("Today hero has a title", bool(title1), title1)
        img_ok = page.evaluate(
            """() => {
              const collage = document.getElementById('today-collage');
              const cells = collage && !collage.hidden ? collage.querySelectorAll('img, .fl-cell').length : 0;
              const i = document.getElementById('today-img');
              const photo = !!(i && !i.hidden && i.complete && i.naturalWidth > 0 && i.offsetParent);
              return photo || cells >= 3;
            }""")
        check("Today hero photo loaded", img_ok)

        # ---- manifest + icons ------------------------------------------
        man = page.evaluate(
            "fetch('manifest.webmanifest').then(r => r.ok ? r.json() : null).catch(() => null)")
        check("manifest loads", man is not None)
        if man:
            for ic in man.get("icons", []):
                st = page.evaluate(f"fetch({json.dumps(ic['src'])}).then(r => r.status).catch(() => 0)")
                check(f"manifest icon {ic['src']}", st == 200, str(st))
            check("manifest start_url relative", man.get("start_url") in ("./", "."), str(man.get("start_url")))

        # ---- the five sections (build .39: Calendar is its own tab) -------
        for sel, panel in [("#section-closet", "panel-wardrobe"), ("#section-ideas", "panel-looks"),
                           ("#tab-find", "panel-find"), ("#tab-today", "panel-today"),
                           ("#section-calendar", "panel-calendar")]:
            try:
                page.click(sel, timeout=5000)
                page.wait_for_timeout(700)
                vis = page.evaluate(
                    f"(() => {{ const p = document.getElementById('{panel}');"
                    " return !!p && !p.hidden && p.offsetParent !== null; })()")
                check(f"tab {sel} shows #{panel}", vis)
                # .80.6: no page may be wider than the screen (a nowrap chip
                # row once made a page 1,500px wide and pushed the nav off)
                over = page.evaluate("document.documentElement.scrollWidth - innerWidth")
                check(f"tab {sel} fits the screen width", over <= 1, f"{over}px wider")
            except Exception as e:  # noqa: BLE001
                check(f"tab {sel} shows #{panel}", False, str(e)[:120])
        # the sub-pages too (only those this build has)
        for sel in ("#section-ideas", "#outfits-mine", "#outfits-inspo", "[data-inspo-view=onyou]", "#section-palettes",
                    "#section-icons", "#section-watches", "#tab-find", "#edit-tab-build", "#section-profile", "#tab-profile"):
            try:
                if not page.locator(sel).count() or not page.locator(sel).first.is_visible():
                    continue
                page.locator(sel).first.click(timeout=3000)
                page.wait_for_timeout(500)
                over = page.evaluate("document.documentElement.scrollWidth - innerWidth")
                check(f"page {sel} fits the screen width", over <= 1, f"{over}px wider")
            except Exception as e:  # noqa: BLE001
                check(f"page {sel} fits the screen width", False, str(e)[:120])

        # ---- closet: Mark worn was removed in .75 ---------------------------
        page.click("#section-closet")
        page.wait_for_timeout(600)
        wore = page.evaluate("""() => ({
          btn: !!document.querySelector("[data-item-wore]"),
          text: /\\bMark [Ww]orn\\b/.test(document.body.innerText || "")
        })""")
        check("Mark worn is removed", not wore.get("btn") and not wore.get("text"), str(wore))

        # ---- outfit of the day is stable for the day -----------------------
        page.click("#tab-today")
        page.wait_for_timeout(2500)
        t_a = page.evaluate("document.querySelector('#today-name')?.innerText?.trim() || ''")
        # A "fresh open" = a new tab (new sessionStorage, same localStorage),
        # which is what reopening the installed app does. A plain reload
        # keeps the session and would hide a re-deal.
        page2 = ctx.new_page()
        page2.on("pageerror", lambda e: errors.append(f"pageerror (2nd open): {e}"))
        page2.goto(URL, wait_until="load")
        page2.wait_for_timeout(2500)
        t_b = page2.evaluate("document.querySelector('#today-name')?.innerText?.trim() || ''")
        page2.close()
        check("Outfit of the day stable across app opens", t_a == t_b, f"{t_a!r} -> {t_b!r}")

        # ---- no personal data shipped in the page --------------------------
        # The rendered page AND every script/style file it loaded are checked.
        # Intended public strings (the site's own URL, the sync / try-on
        # worker hosts, the Home location line David asked for) are listed
        # explicitly in smoke_baseline.json "pii_allow" and removed first;
        # anything else matching a marker fails the run.
        html = page.content()
        code = page.evaluate("""async () => { const urls = [...document.querySelectorAll('script[src],link[rel=stylesheet]')].map(e => e.src || e.href).filter(u => u && u.indexOf(location.origin) === 0);
          const out = []; for (const u of urls) { try { out.push(await (await fetch(u)).text()); } catch (e) {} } return out.join('\\n'); }""")
        # The same public host is also embedded in a JS regex inside the bundle.
        hay = re.sub(r"\\+\.", ".", html + "\n" + code)
        for allowed in BASELINE.get("pii_allow", []):
            hay = hay.replace(allowed, "")
        low = hay.lower()
        pii = [w for w in BASELINE.get("pii_markers", []) if w.lower() in low]
        check("No owner PII in the page", not pii, ", ".join(pii))

        # ---- dead element ids --------------------------------------------
        src = page.evaluate("[...document.scripts].map(s => s.textContent).join('\\n')")
        ids = sorted(set(re.findall(r"getElementById\(\s*[\"']([A-Za-z0-9_\-]+)[\"']\s*\)", src)))
        missing = page.evaluate("ids => ids.filter(i => !document.getElementById(i))", ids)
        new_dead = sorted(set(missing) - KNOWN_DEAD_IDS)
        gone = sorted(KNOWN_DEAD_IDS - set(missing))
        check("No NEW dead element ids", not new_dead, ", ".join(new_dead))
        if gone:
            results.append(("FIXED?", "Dead ids now resolved or removed (trim baseline)", ", ".join(gone)))

        # ---- errors -------------------------------------------------------
        check("No JS errors", not errors, " | ".join(errors[:5]))
        # the cut-out manifest is optional until the cut-outs land (.78.5b)
        bad_responses = [r for r in bad_responses if "onbody-cut/manifest.json" not in r]
        check("No 4xx/5xx from own origin", not bad_responses, " | ".join(bad_responses[:5]))
        results.append(("INFO", "Worker calls blocked", str(len(blocked))))
        browser.close()

    width = max(len(r[1]) for r in results)
    for status, name, detail in results:
        print(f"{status:7} {name:<{width}}  {detail}")
    fails = [r for r in results if r[0] == "FAIL"]
    if os.environ.get("GITHUB_ACTIONS"):
        # Annotations show on the run page and through the public API.
        for status, name, detail in results:
            if status in ("FAIL", "FIXED?"):
                lvl = "error" if status == "FAIL" else "notice"
                msg = f"{status} {name}: {detail}".replace("%", "%25").replace("\r", "").replace("\n", " ")
                print(f"::{lvl} title=Smoke test::{msg[:900]}")
    print(f"\n{len(fails)} new failure(s); "
          f"{sum(r[0] == 'KNOWN' for r in results)} known issue(s); "
          f"{sum(r[0] == 'FIXED?' for r in results)} known issue(s) now passing.")
    return 1 if fails else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 — surface crashes as an annotation
        import traceback
        tb = traceback.format_exc()
        print(tb)
        if os.environ.get("GITHUB_ACTIONS"):
            print("::error title=Smoke test crashed::" + tb.replace("%", "%25").replace("\n", "%0A")[-1800:])
        sys.exit(2)
