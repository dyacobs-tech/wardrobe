"""A level-specific closet search must return the same outfits as the full deck."""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/"
    items = json.loads(Path(__file__).with_name("fixture_closet83.json").read_text())
    for name, category, colour in [
        ("Black patent Oxford shoes", "Shoes", "Black"),
        ("Black leather oxford dress shoes", "Shoes", "Black"),
        ("Tuxedo trousers", "Trousers", "Black"),
        ("White tuxedo dress shirt", "Shirts", "White"),
        ("Black shawl collar dinner jacket", "Suits", "Black"),
        ("Navy suit jacket", "Suits", "Navy"),
        ("Grey wool dress trousers", "Trousers", "Grey"),
        ("Olive tailored shorts", "Shorts", "Olive"),
    ]:
        items.append(dict(id=name, name=name, category=category, colourName=colour))

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(service_workers="block")
        context.route("**/*", lambda r: r.continue_() if r.request.method == "GET"
                      and r.request.url.startswith(url) else r.abort())
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded")
        page.wait_for_function("() => window.WardrobeRules && window.WardrobeComposer")
        page.evaluate("""items => {
          const rules = window.WardrobeRules;
          function record(c) {
            return [c.key, c.t.id, c.b.id, c.s.id, c.l?.id, c.mask, c.score, c.tuck, c.tuckPrompt];
          }
          function deal(deck, level) {
            let seed = 3;
            const rng = () => ((seed = (214013 * seed + 2531011) >>> 0) / 4294967296);
            return deck.deal(12, {level, temp: 74, rng}).map(o => [o.key, o.tuck, o.acc?.id]);
          }
          for (const active of [rules.seedRules(), [...rules.seedRules(), rules.makeRule('Never wear red.')]]) {
            rules.setActive(active);
            const full = WardrobeComposer.build(items);
            for (let level = 1; level <= 7; level++) {
              const narrow = WardrobeComposer.build(items, null, level);
              const expected = full.forLevel(level).map(record);
              if (!expected.length || JSON.stringify(narrow.combos.map(record)) !== JSON.stringify(expected))
                throw Error('Different eligible combinations at level ' + level);
              if (JSON.stringify(deal(narrow, level)) !== JSON.stringify(deal(full, level)))
                throw Error('Different outfit selection at level ' + level);
            }
          }
        }""", items)
        browser.close()
    print("Matched outfit eligibility, order, scores and seeded deals at all seven dress levels.")


if __name__ == "__main__":
    main()
