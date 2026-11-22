"""Apply the snapshot fix to a copy of the live wardrobe-sync module.

usage: python3 apply.py <live worker.js> <patched worker.js>

<live worker.js> is the module downloaded read-only from Cloudflare (GET
/accounts/<id>/workers/scripts/wardrobe-sync returns it as one multipart
part named "worker.js"). Only the writeSnapshot function is replaced, with
the text in writeSnapshot.patched.js; the script stops if the live file
does not have exactly one writeSnapshot followed by another function.
"""
import os, sys
src, dst = sys.argv[1], sys.argv[2]
js = open(src).read()
assert js.count("async function writeSnapshot(") == 1, "expected exactly one writeSnapshot"
a = js.index("async function writeSnapshot(")
e = js.index("async function", a + 10)
new = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "writeSnapshot.patched.js")).read()
assert "SNAP_PART" not in js, "this file already has the fix"
open(dst, "w").write(js[:a] + new + js[e:])
print("patched:", dst, "| writeSnapshot %d -> %d characters; nothing else changed" % (e - a, len(new)))
