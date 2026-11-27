"""Redrawn pictures: belts that failed, untucked Evening Casual shirts, and hidden pictures with cut-off arms (.87.05).

David, 24 Nov 2026, quoting the outstanding list: "6 Evening Casual pictures drawn with a tucked shirt, to redraw
untucked ... 18 hidden pictures with unfixable arms ... 36 pictures whose belt edit failed and are still beltless.
Fix these". Of the 36 beltless pictures, 10 have a polo or sweater worn out over the trousers, where no belt shows,
so they stay as they are; the other 26 were redrawn and reviewed by eye twice, independently. 10 passed both reviews. 16
stay beltless: in 8 the edit shortened or tucked a sweater that is worn out over the trousers, and the other 8 had a
smudged, see-through or kinked belt, the wrong belt, a damaged button, a pale mark at the belt end, or no belt at all. Of the 6 untucked shirts, 4 were already drawn worn out and
only needed the app to use them (test_untucked8705); 2 were redrawn. Of the 18 hidden pictures, the arms were redrawn
past the cut, reviewed, and the good ones are shown again (2 could not be extended and stay hidden).
Checks: every redrawn picture is listed under its new name with every file it needs and the old name is gone; the
pictures shown again are off every hidden list (test_pictures8704 then checks their arms and head size like every
other picture); the 2 that could not be fixed are still hidden.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
P = json.loads((ROOT / "tests/pictures8705.json").read_text())
from picture_names import current
from oldpics import is_redrawn
src = (ROOT / "src/app.html").read_text()
seed = json.loads(re.search(r"var ONBODY_SEED = (\{.*?\});\n", src).group(1))
files = {e["f"] for e in seed["r"]}
feet = json.loads((ROOT / "assets/onbody-cut/feet.json").read_text())["feet"]
lq = json.loads((ROOT / "assets/onbody-cut/lq.json").read_text())["lq"]
cman = json.loads((ROOT / "assets/onbody-cut/manifest.json").read_text())["map"]
hidden = set(re.findall(r'"([0-9a-f]{16})\.webp"', "".join(re.findall(r"var ONBODY_(?:TUCK_EXCLUDE|REJECTED859|TEELONG879|AUDIT883) = \{.*?\};", src))))
kinds = list(P["kind"].values())
assert kinds.count("belt") == 10 and kinds.count("untuck") == 2, (kinds.count("belt"), kinds.count("untuck"))
assert kinds.count("arms") == len(P["unhidden"]) and len(P["unhidden"]) >= 12, len(P["unhidden"])
for old, new in P["renamed"].items():
    new = current(new)
    assert old + ".webp" not in files and new + ".webp" in files, ("redrawn picture not listed", old, new)
    gone = is_redrawn(new)   # .87.27: since redrawn in high-res, so its old files were removed
    for d in ("assets/onbody/", "assets/onbody-cut/", "assets/onbody-cut-hq/"):
        assert gone or (ROOT / d / (new + ".webp")).exists(), ("missing file", d, new)
        assert not (ROOT / d / (old + ".webp")).exists(), ("old file left behind", d, old)
    if gone:
        continue
    assert new in feet and new in lq and cman.get(new + ".webp"), ("redrawn picture missing from feet/lq/cut manifest", new)
for old, new in P["renamed"].items():
    if P["kind"][new] == "arms":
        assert old not in hidden and current(new) not in hidden, ("a repaired picture is still hidden", old, new)
        assert '"%s.webp"' % old not in src, ("the old name of a repaired picture is still in the app", old)
for still in ("0a0c65c69b2bb757", "0bee885cef807469"):
    assert current(still) in hidden, ("a picture whose arms could not be fixed is shown", still)
print("Confirmed %d belts, %d untucked shirts and %d pictures with whole arms are in; 2 unfixable pictures stay hidden"
      % (kinds.count("belt"), kinds.count("untuck"), kinds.count("arms")))
