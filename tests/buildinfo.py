"""The build under test, read from sw.js — tests never hard-code a build number."""
import re
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
CURRENT_BUILD = re.search(r"const WARDROBE_BUILD = '([^']+)'", (_ROOT / "sw.js").read_text()).group(1)
