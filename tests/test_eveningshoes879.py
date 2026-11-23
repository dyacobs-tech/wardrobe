"""Evening Sharp takes nearly any shoe except slides, Vans, TOMS and athletic sneakers (.86.79).

David, 23 Nov 2026: "Evening sharp can be nearly any shoes besides slides / Or vans or athletic sneakers /
No slides vans toms or athletic sneakers / Can be all Giorgio, boudain, loro Belgian Edward green stubbs",
and of the Baudoin & Lange maple suede espadrilles: "Maple I wear these a lot!!!!" and
"Baudoin maple are everything BUT casual!!!!!". Then: "Casual shoes are SNEAKERS and slip ons ONLY /
Baudoin are evening sharp evening dressy formal / Espadrilles stop at evening sharp", and of the
other Baudoins: "Others can go through formal". Then: "Evening sharp can also have sneakers!!!!! / But casual
should NOT have any loafers or velvets or anything / NO - baudoin espadrilles can be casual daytime or evening
sharp as top category. / Other baudoins are evening sharp to formal."
Also: "appears my velasca slippers in every picture '!!!!! Where are my other shoes??????"
"""
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"

YES = [
    "Giorgio Armani Navy Suede Whipstitch Slip-On Loafers",
    "Giorgio Armani Taupe Leather Whipstitch Slip-On Loafers",
    "Baudoin & Lange Tan Suede Penny Espadrilles",
    "Baudoin & Lange Rust Suede Tassel Loafers",
    "Loro Piana Dark Brown Suede Summer Walk Loafers",
    "Belgian Shoes Olive Suede Loafers",
    "Edward Green Dark Brown Suede Penny Loafers",
    "Stubbs & Wootton Blue Camo Needlepoint Slippers",
    "Velasca Brown Suede Venetian Slippers",
    "Vibi Venezia Navy Stripe Furlane Slippers",
    "Common Projects White Leather Achilles Low Sneakers",
    "Brunello Cucinelli Light Grey Suede Runner Sneakers",
]
NO = [
    "Frescobol Carioca White and Navy Leather Pool Slides",
    "Brunello Cucinelli Navy Pool Slides",
    "Vans Tan Suede Authentic Sneakers",
    "Vans Black and White Checkerboard Slip-On Sneakers",
    "TOMS Cream Canvas Slip-Ons",
]

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    ctx = browser.new_context(service_workers="block")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(URL) else r.abort())
    page = ctx.new_page()
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_function("() => typeof eveningSharpShoe879 === 'function' && window.WardrobeComposer")
    got = page.evaluate("""([yes, no]) => {
      const C = window.WardrobeComposer;
      const ok = n => eveningSharpShoe879(C.profile({ id: 'x', name: n, category: 'Shoes' }));
      return { yes: yes.filter(n => !ok(n)), no: no.filter(n => ok(n)) };
    }""", [YES, NO])
    assert not got["yes"], ("shoes he allows at Evening Sharp were refused", got["yes"])
    assert not got["no"], ("slides, Vans or TOMS were allowed at Evening Sharp", got["no"])
    # "Baudoin are evening sharp evening dressy formal" (maples included); "Espadrilles stop at evening sharp";
    # "Casual shoes are SNEAKERS and slip ons ONLY"
    r = page.evaluate("""() => { const P = n => WardrobeComposer.profile({ id: n, name: n, category: 'Shoes' });
      const casual = n => shoeIsCasual866(P(n));
      return {
        maple: P('Baudoin & Lange Tan Suede Penny Espadrilles'), tassel: P('Baudoin & Lange Rust Suede Tassel Loafers'),
        lpEsp: P('Loro Piana Light Blue Knit Espadrilles'),
        casualYes: ['Vans Tan Suede Authentic Sneakers', 'TOMS Cream Canvas Slip-Ons', 'Bottega Veneta Black and White Intrecciato Slip-On Sneakers', 'D.A.T.E. Cream and Navy Retro Runner Sneakers'].filter(n => !casual(n)),
        casualNo: ['Giorgio Armani Navy Suede Whipstitch Slip-On Loafers', 'Baudoin & Lange Tan Suede Penny Espadrilles', 'Prada Dark Brown Suede Boat Shoes', 'Loro Piana Dark Brown Suede Summer Walk Loafers', 'Loro Piana Light Blue Knit Espadrilles'].filter(n => casual(n)) }; }""")
    assert r["maple"]["lo"] == 2 and r["maple"]["hi"] == 4, r["maple"]
    assert r["tassel"]["lo"] == 4 and r["tassel"]["hi"] == 6, r["tassel"]
    # no loafers, slippers or velvets below Evening Sharp
    low = page.evaluate("""() => ['Giorgio Armani Navy Suede Whipstitch Slip-On Loafers', 'Velasca Brown Suede Venetian Slippers',
      'Belgian Shoes Black Velvet Loafers', 'Edward Green Dark Brown Suede Penny Loafers', 'Vibi Venezia Navy Stripe Furlane Slippers',
      'Loro Piana Dark Brown Suede Summer Walk Loafers'].map(n => [n, WardrobeComposer.profile({ id: n, name: n, category: 'Shoes' }).lo]).filter(x => x[1] < 4)""")
    assert not low, ("loafers or slippers allowed at a casual level", low)
    assert r["lpEsp"]["hi"] == 4, r["lpEsp"]
    assert not r["casualYes"], ("sneakers or slip-ons not counted as casual", r["casualYes"])
    assert not r["casualNo"], ("non-sneaker shoes counted as casual", r["casualNo"])
    # the blazer check follows the same rule at Evening Sharp
    blazer = page.evaluate("""() => formalShoesOk866({ t: {}, l: { kind: 'blazer' }, s: { name: 'Giorgio Armani Navy Suede Whipstitch Slip-On Loafers', category: 'Shoes' } }, { level: 4 })""")
    assert blazer is True, blazer
    browser.close()
print("Confirmed his shoe levels: casual levels without loafers or slippers, Evening Sharp with sneakers, Baudoin espadrilles to Evening Sharp, other Baudoins to Formal")
