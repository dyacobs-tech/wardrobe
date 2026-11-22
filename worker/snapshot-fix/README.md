# Snapshot fix for wardrobe-sync (deployed 22 Nov 2026)

**Status: deployed 22 Nov 2026 00:44 UTC with David's yes ("Yes make server
change but make sure everything backed up").** Live version id starts
`ff2c0a19`; the version before it, `9b905cc1` (20 Nov), is the rollback.

Checked after the upload:

- Settings: KV binding `SYNC_KV` and both secrets still bound; `/register`
  without the secret answers 403 (it would be 503 if the secret were gone).
- A real write (two records) returned HTTP 200 in 32 s. Before the fix every
  write ended in 503 after 60 to 85 s.
- The KV listing shows a new complete snapshot (meta `{at, chunks: 5, v: 2}`),
  30.2 MB in 5 parts. Read back through the KV API it holds all 285 live
  records and the profile data, each identical to a fresh full download.
- The ring is still 10 complete snapshots. Orphan parts went from 1,395 to
  1,276 on the first run (the sweep is capped at 120 deletes a run).
- Compared with the full backup taken just before the upload: only the two
  records of that write changed, none missing.

## The fault

Since the closet passed 25 MiB (21 Nov 2026, about 21:24 UTC) every
state-changing `/sync` has ended in HTTP 503, Cloudflare error 1102, after
60 to 85 seconds. The records are stored each time; what dies is the hourly
safety snapshot written at the end of the request:

- The old `writeSnapshot` builds the whole closet in memory three times
  (parsed objects, the JSON text, and the same text wrapped again), then,
  because that text no longer fits one KV value, writes it as about 500
  parts of 60,000 characters.
- Read from the KV listing on 21 Nov: the last complete snapshot is from
  20:19 UTC. Each of the 8 attempts after it wrote 164 to 192 parts and
  never its meta key. 1,395 orphan parts are left behind.

Effect for David: every save from his phone shows "Couldn't sync" although
the data is saved, and no safety copy has been made since 20:19 UTC.

## The change

Only `writeSnapshot` changes (see `../worker.ts`). The snapshot keeps its
JSON shape but is streamed: each record's stored text is appended as it is
and flushed in parts of about 6 MB (6 parts for a 32 MB closet). The ring
trim deletes old snapshots from the listing instead of reading them back,
and parts left by dead writes are swept (at most 120 deletes a run, and only
when older than two hours). Nothing else in the worker is touched.

## Files

The live code is not kept in this repo (it is downloaded read-only from
Cloudflare when needed; version 13, uploaded through the API on 20 Nov
2026, is what these files were tested against).

- `writeSnapshot.patched.js`: the new function, as plain JavaScript.
- `apply.py`: replaces only `writeSnapshot` in a downloaded copy of the
  live module: `python3 apply.py live.js patched.js`.
- `test.mjs`: in-memory tests, no network:
  `node --max-old-space-size=2048 test.mjs /abs/live.mjs /abs/patched.mjs`.
  The same request sequence goes to both files; every response and every
  non-snapshot key must be identical. Then the new layout, the ring trim,
  the orphan sweep and a 32 MB closet are checked. 21 checks pass.

## How it was deployed (repeat only with David's yes)

1. Take a full `since: 0` backup of his account.
2. Download the live module, run `apply.py`, run `test.mjs`, then upload the
   patched file as module `worker.js` with the same settings as
   version 13: `compatibility_date` 2025-06-01, KV binding `SYNC_KV`, and
   `keep_bindings: ["secret_text"]` so both secrets stay (seen working on
   22 Nov: both secrets were still bound after the upload).
3. Check: `GET /` answers, a no-op sync is 200, a small write returns 200
   (not 503), the KV listing shows a new snapshot with a meta key and about
   6 parts, the parts join into JSON holding every live record, and a full
   download still works.
4. If anything is off, upload the downloaded live file the same way.

## Still open after this fix

- A full download builds the whole closet in memory before answering. It
  works at 30 MB (checked 21 Nov). It will need streaming as the closet
  grows; where that limit is has not been measured.
- Every sync reads one KV key per record to find what changed.
