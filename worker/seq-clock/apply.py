"""Apply the record-numbering change to a copy of the live wardrobe-sync module.

usage: python3 apply.py <live worker.js> <patched worker.js>

<live worker.js> is the module downloaded read-only from Cloudflare. It must
already carry the snapshot fix and the sync speed change. Each old text must
be found the stated number of times or the script stops without writing.
"""
import sys
src, dst = sys.argv[1], sys.argv[2]
js = open(src).read()
assert "SCAN_BATCH" in js, "the sync speed change must be in the file first"
assert "SEQ_MARGIN_MS" not in js, "this file already has the numbering change"
EDITS = [
 # 1. helpers
 ('''const SCAN_BATCH = 16;
''', '''// Record numbers ("seq") are the server's clock in milliseconds, not a
// counter. A counter kept in KV can be read stale (KV may serve a value up
// to about a minute old), so two devices saving close together were given
// the same number, and a device whose bookmark had passed that number never
// received the other device's record. With clock numbers a stale read
// cannot lower a number, and the bookmark handed back to a device
// deliberately trails the clock by SEQ_MARGIN_MS: anything written, or
// still spreading through KV, in that window is sent again on the next
// sync. The app ignores a record it already holds (same updatedAt), so a
// repeat costs a little download and nothing else.
// The bookmark moves in whole steps of SEQ_STEP_MS so that the app's paged
// download loop sees an unchanged bookmark and stops.
// The stored counter (seq/<acct>) is kept at or above every number and
// every bookmark handed out, so the previous version of this worker, if it
// is ever rolled back to, continues above them.
const SEQ_MARGIN_MS = 180 * 1e3;
const SEQ_STEP_MS = 60 * 1e3;
const nextSeq = (last) => Math.max(Date.now(), last + 1);
const bookmarkFor = (t) => Math.floor((t - SEQ_MARGIN_MS) / SEQ_STEP_MS) * SEQ_STEP_MS;
const SCAN_BATCH = 16;
''', 1),
 # 2. /sync: numbers come from the clock
 ('''  const allocSeq = () => {
    seqAllocated = true;
    return ++seqCounter;
  };
''', '''  const allocSeq = () => {
    seqAllocated = true;
    seqCounter = nextSeq(seqCounter);
    return seqCounter;
  };
''', 1),
 # 3. /sync: the counter write can no longer fail the request; the scan's start time is noted
 ('''  if (seqAllocated) await kv.put(seqKey, String(seqCounter));
  // Record heads are read SCAN_BATCH at a time.''', '''  if (seqAllocated) {
    try {
      await kv.put(seqKey, String(seqCounter));
    } catch (_) {
    }
  }
  const scanStart = Date.now();
  // Record heads are read SCAN_BATCH at a time.''', 1),
 # 4. /sync: the bookmark trails the clock
 ('''  const now = seqCounter;
  if (dirty) await snapshotAfterSync(kv, acct, ctx, outChars >= SNAP_DEFER_MAX_CHARS);
''', '''  const mark = bookmarkFor(scanStart);
  const now = Math.max(since, mark);
  if (mark > seqCounter) {
    try {
      await kv.put(seqKey, String(mark));
    } catch (_) {
    }
  }
  if (dirty) await snapshotAfterSync(kv, acct, ctx, outChars >= SNAP_DEFER_MAX_CHARS);
''', 1),
 # 5. the receipt inbox and the price-drop feed number their records the same way
 ('''    const seq = ++seqCounter;
''', '''    const seq = seqCounter = nextSeq(seqCounter);
''', 2),
]
out = js
for old, new, n in EDITS:
    assert out.count(old) == n, "expected %d match(es) for:\n%s" % (n, old[:160])
    out = out.replace(old, new)
assert "++seqCounter" not in out
open(dst, "w").write(out)
print("patched:", dst, "| %d -> %d characters; %d places changed" % (len(js), len(out), sum(e[2] for e in EDITS)))
