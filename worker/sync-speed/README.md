# Sync speed change for wardrobe-sync (deployed 22 Nov 2026)

**Status: deployed 22 Nov 2026 01:59:50 UTC with David's yes ("Yes fix server
sync", "Yes do that for cloudflare").** Live version id starts `091f0389`.
Rollback is the version before it, `ff2c0a19` (the snapshot fix, 22 Nov
00:44 UTC); `9b905cc1` (20 Nov) is the one before that.

A full download of the account (301 records, 31.3 MB) was saved just before
the upload and compared record by record with the local copy: identical.

## What was slow

Every `/sync`, even one with nothing to send or fetch, read the head of every
record one after another: 301 round trips to KV. Measured on the live
service on 22 Nov, from a location that had not just read the same keys:
25.8 s for a read-only sync, 32 to 43 s for a save. A phone that is put down
during that time drops the connection, and Cloudflare may then cancel the
request ("When the client disconnects ... outstanding work may be canceled
unless it is passed to ctx.waitUntil()", Workers limits page, read 22 Nov
2026).

## The change

All in `handleSync` and three lines of `writeSnapshot` (see `../worker.ts`):

1. **Record heads are read 16 at a time** (`SCAN_BATCH`). The same keys are
   read and the answer is the same, in the same order.
2. **The record counter is stored as soon as the writes are done**, before
   the scan (it used to be stored after it). A request cut off while
   scanning no longer leaves records numbered above the stored counter.
3. **The hourly safety snapshot no longer holds the answer back.** It is
   handed to `ctx.waitUntil` (30 seconds allowed after the answer).
   `writeSnapshot` sets a flag key, `snapflag/<account>`, when it starts
   writing and deletes it when the snapshot is complete:
   - no flag: start the snapshot and answer at once;
   - a flag younger than 90 s: one is being written right now, do nothing;
   - an older flag: the last attempt did not finish, so this sync waits for
     its snapshot before answering, as every sync did before.

   The sync also waits when the answer itself is over 16 million characters,
   so a full download and a snapshot are not in memory together.

Not changed: authorization, the mass-delete guard, how records are written,
the snapshot's content, the hourly throttle, the ring of 10 snapshots.

## Measured after the upload (same place, 22 Nov 2026)

- Read-only sync: 1.6 to 1.8 s (was 25.8 s cold, 4.6 to 8.3 s warm).
- A save: 2.6 s (was 32 to 43 s).
- Settings: KV binding `SYNC_KV` and both secrets still bound; `/register`
  without the secret answers 403.
- First background snapshot, 02:53 UTC (the previous complete one was
  01:51:50, so none was due before 02:51:50): a save sent at 02:53:05
  answered in 4.5 s; at 02:53:10 the flag key was present and no new
  snapshot yet; at 02:53:31 a new complete snapshot (stamp 02:53:10, 5
  parts, `v: 2`) and no flag key. Read back through the KV API: 31.3 MB,
  291 records, each identical to the live data, profile data identical.
  The ring still holds 10; orphan parts went from 1,157 to 1,038.
  So the snapshot took about 21 s of the 30 s allowed after the answer.
  When a closet grows enough to pass 30 s, the flag key makes the next
  sync wait for its snapshot (see 3 above); a scheduled (cron) snapshot
  would be the cleaner answer then.

## Files

- `apply.py`: applies the change to a downloaded copy of the live module
  (which must already have the snapshot fix): `python3 apply.py live.js
  patched.js`. Nine exact replacements; it stops if any is not found once.
- `test.mjs`: in-memory tests, no network:
  `node --max-old-space-size=2048 test.mjs /abs/live.mjs /abs/patched.mjs`.
  29 checks. The same requests go to both files (a fixed sequence, then 400
  random ones with stale writes, ties, deletes, profile data and mass-delete
  refusals); every answer and every stored key must be identical. Then the
  background snapshot, the in-flight and never-finished cases, the
  large-answer case, the reads of a read-only sync, and the counter.
  It also runs against `worker.ts` before and after the change
  (`node --experimental-strip-types`), same result.
- `../snapshot-fix/test.mjs` still passes against the new code (its harness
  now waits for work handed to `waitUntil`; one count allows for the flag
  key's delete).

## Known weakness this does not fix

The record counter (`seq/<account>`) lives in KV, which may serve a value up
to about a minute old in a location that read it recently. Two devices that
save within that minute can be given the same number, and a device whose
cursor has already passed that number does not receive the other's record.
Seen once on 22 Nov: number 898 was given to a record from David's phone and
to a test re-save made 28 s later from elsewhere (identical data, so nothing
was lost). An older pair shares number 351. A proper fix needs a counter
that is consistent everywhere (a Durable Object) or a cursor that overlaps.
Until then: do not save from a script within about 70 s of calling `/sync`
from the same place.
