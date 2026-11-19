"""Build .74 follow-ups (WebKit standalone 390x844, local server, workers.dev blocked,
open-meteo answered by a stub so no network is used):
  * Home (Wardrobe mode): the outfit title is shown, light on the dark caption,
    and Home still fits one screen
  * no "Can't find variable: syFetch" at boot with a location set; weather loads
  * Ideas / Closet / Shop sub-tab bars are centred (equal left/right inset) with the
    back chevron on and off; no label is clipped; the first label clears the chevron
  * the closet feed's Shuffle is centred

    PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=1 /tmp/pwvenv/bin/python tests/test_fix74.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_composer73 import BLOCK, BUILD, FIXTURE, FIXTURE_PHOTO, STANDALONE_INIT, start_server  # noqa: E402

LOC = {"name": "Palm Beach, Florida", "lat": 26.70306, "lon": -80.03661, "admin": "Florida", "country": "United States"}
WEATHER = {"current": {"time": "2026-11-18T12:00", "temperature_2m": 78.0, "apparent_temperature": 80.0, "weather_code": 1},
           "daily": {"time": ["2026-11-18"], "temperature_2m_max": [81.0], "temperature_2m_min": [70.0],
                     "precipitation_probability_max": [10], "weather_code": [1]}}

BAR_JS = """(id) => {
  const g = document.getElementById(id), r = g.getBoundingClientRect();
  const cells = [...g.children].filter(c => getComputedStyle(c).display !== 'none');
  const first = cells[0], rg = document.createRange(); rg.selectNodeContents(first);
  const tr = [...rg.getClientRects()].filter(x => x.width > 0)[0];
  const fab = document.getElementById('view-back');
  return { left: Math.round(r.left), right: Math.round(innerWidth - r.right),
           widths: cells.map(c => Math.round(c.getBoundingClientRect().width)),
           clipped: cells.filter(c => c.scrollWidth > c.clientWidth + 1).map(c => c.innerText.trim()),
           back: document.body.classList.contains('view-back-on'),
           fabRight: fab.hidden ? null : fab.getBoundingClientRect().right, firstText: tr ? tr.left : null,
           docW: document.documentElement.scrollWidth };
}"""


def lum(rgb):
    v = [int(x) for x in rgb[rgb.index("(") + 1:rgb.index(")")].split(",")[:3]]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]


def main() -> int:
    os.environ.setdefault("PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS", "1")
    results = []

    def check(name, ok, detail=""):
        results.append(bool(ok))
        print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail != "" else ""))

    httpd, url = start_server()
    try:
        with sync_playwright() as p:
            browser = p.webkit.launch()
            ctx = browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2,
                                      is_mobile=True, has_touch=True, service_workers="block")
            ctx.add_init_script(STANDALONE_INIT)
            seed = {"items": [dict(i, addedISO="2026-11-17", photo=FIXTURE_PHOTO) for i in FIXTURE], "todaySource": "wardrobe", "formality": 4,
                    "homeLocation": LOC, "currentLocation": LOC}
            ctx.add_init_script("(() => { if (localStorage.getItem('wardrobe.items')) return; const S = %s;"
                                " for (const k in S) localStorage.setItem('wardrobe.' + k, JSON.stringify(S[k])); })();" % json.dumps(seed))
            ctx.route(BLOCK, lambda r: r.abort())
            ctx.route("**/api.open-meteo.com/**", lambda r: r.fulfill(status=200, content_type="application/json",
                                                                       headers={"access-control-allow-origin": "*"},
                                                                       body=json.dumps(WEATHER)))
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(url, wait_until="load")
            page.wait_for_timeout(1800)
            check("build is .74", page.evaluate("window.WARDROBE_BUILD") == BUILD == "2026-11-19.79.3")
            check("no syFetch error at boot", not [e for e in errors if "syFetch" in e], errors[:3])
            check("weather loads at boot", page.evaluate("!!(window.currentWeather || (typeof currentWeather !== 'undefined' && currentWeather)) && currentWeather.temp === 78"))

            t = page.evaluate("""() => { const n = document.getElementById('today-name'), r = n.getBoundingClientRect();
                return { text: n.textContent.trim(), want: todayLook && (displayTitleForLook(todayLook) || todayLook.title),
                  composer: !!(todayLook && todayLook.composer), color: getComputedStyle(n).color, h: r.height, vis: getComputedStyle(n).visibility,
                  fits: (document.scrollingElement || document.documentElement).scrollHeight <= innerHeight + 1, bottom: r.bottom }; }""")
            check("Home deals a composed look", t["composer"])
            check("Home title shows the composed look's name", t["text"] and t["text"] == t["want"] and t["h"] > 0 and t["vis"] == "visible", t["text"])
            check("Home title is light on the dark caption", lum(t["color"]) > 200, t["color"])
            check("Home still fits one screen", t["fits"] and t["bottom"] < 844)
            page.evaluate("dealAnotherToday()"); page.wait_for_timeout(300)
            t2 = page.evaluate("document.getElementById('today-name').textContent.trim()")
            check("Home title updates on a new deal", bool(t2), t2)

            # Closet subnav (2 tabs) stays centred; Outfits and Shop have no subnav.
            page.locator("#section-closet").click(); page.wait_for_timeout(350)
            for state in ("back", "noback"):
                if state == "noback":
                    page.evaluate("document.body.classList.remove('view-back-on')"); page.wait_for_timeout(100)
                b = page.evaluate(BAR_JS, "subnav-closet")
                check(f"subnav-closet ({state}) centred", abs(b["left"] - b["right"]) <= 1, f'{b["left"]}/{b["right"]}')
                check(f"subnav-closet ({state}) equal columns, none clipped", max(b["widths"]) - min(b["widths"]) <= 1 and not b["clipped"] and b["docW"] == 390, b)
                if state == "back" and b["back"]:
                    page.evaluate("window.scrollTo(0, 900)"); page.wait_for_timeout(250)
                    b2 = page.evaluate(BAR_JS, "subnav-closet")
                    check("subnav-closet first label clears the back chevron when stuck", b2["fabRight"] is None or b2["firstText"] >= b2["fabRight"], b2)
                    page.evaluate("window.scrollTo(0, 0)"); page.wait_for_timeout(200)
            page.evaluate("syncViewBack()")
            page.locator("#section-ideas").click(); page.wait_for_timeout(500)
            hidden_ideas = page.evaluate("document.getElementById('subnav-ideas').hidden || document.getElementById('subnav').hidden")
            check("Outfits has no section subnav", hidden_ideas)
            feed = page.evaluate("""() => {
              const f = document.getElementById('closet-feed');
              const b = document.getElementById('cf-shuffle');
              if (!f || f.hidden || !b) return null;
              const br = b.getBoundingClientRect(), h = document.querySelector('#closet-feed .cf-head').getBoundingClientRect();
              return Math.abs((br.left + br.right) / 2 - (h.left + h.right) / 2);
            }""")
            if feed is not None:
                check("closet feed Shuffle is centred", feed <= 2, feed)
            page.locator("#tab-find").click(); page.wait_for_timeout(300)
            hidden_shop = page.evaluate("document.getElementById('subnav-find').hidden || document.getElementById('subnav').hidden")
            check("The Edit has no section subnav", hidden_shop)
            check("no JS errors", not errors, errors[:3])
            ctx.close(); browser.close()
    finally:
        httpd.shutdown()
    print(f"{sum(results)}/{len(results)} passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
