# Record numbering by clock for wardrobe-sync

David, 22 Nov 2026: "Yes to server". This closes the weakness written up at
the end of `../sync-speed/README.md`.

**Status: deployed 22 Nov 2026 09:22:34 UTC with David's yes.** Live version
id starts `b0458e49`; the version before it is `091f0389` (the sync speed
change). A full download of the account (305 records, 32.1 MB) was saved
just before the upload; it matched the local copy record for record.

Checked on the live service after the upload:

- Settings: KV binding `SYNC_KV` and both secrets still bound; `/register`
  without the secret answers 403.
- A read with the old bookmark 928 returned a clock bookmark on a whole
  minute, 237 s behind the clock, and the stored counter moved up to it.
- Three harmless saves (one record re-saved unchanged) were stored with
  numbers within half a second of the clock. A device on the new bookmark
  and one still on 928 both received the record.
- One save, a few seconds after the upload, was still answered by the
  previous version (Cloudflare was still rolling the new one out). It took
  the number just above the stored counter, as planned for that case, and
  both devices received it.
- The live app run against the live service, read-only (its uploads held
  back): full download of 305 records in 8 s, "Restored from the cloud",
  then "Synced", the bookmark stored as a clock value, no page errors.

## The fault

Every stored record carries a number (`seq`), and each device keeps a
bookmark: the highest number it has been told about. A sync returns the
records numbered above the bookmark. The numbers came from a counter kept in
KV (`seq/<account>`), read, increased and written back by each request.

KV may serve a value up to about a minute old in a location that read it
recently. So two devices saving close together could be handed the same
number, and a device whose bookmark had already passed that number never
received the other device's record. Seen on the live service on 22 Nov:
number 898 went to a record from David's phone and to a save made 28 s later
from elsewhere. An older pair shares number 351.

The same loss happens without any duplicate: a record written in one place
is not visible everywhere at once, so a device that syncs in between gets a
bookmark above a record it has not been shown.

## The change

- **Numbers are the server's clock in milliseconds.** A stale counter read
  can no longer lower a number.
- **The bookmark handed back trails the clock by three minutes**
  (`SEQ_MARGIN_MS`), rounded down to a whole minute (`SEQ_STEP_MS`). Anything
  written, or still spreading through KV, inside that window is sent again on
  the next sync.
- **A repeat is harmless.** The app replaces a record only when the incoming
  `updatedAt` is newer than the one it holds (`syApplyDownload56` in
  `src/app.html`), so a record it already has is skipped.
- **The whole-minute step** is there for the app's paged download loop, which
  stops when the bookmark comes back unchanged.
- **Devices move over on their own.** A device holding an old small-number
  bookmark is served by the same rule (numbers above it), and gets a clock
  bookmark back. The app treats the bookmark as an opaque number.
- **The stored counter is kept** at or above every number and bookmark
  handed out, so the previous worker version, if rolled back to, continues
  above them. Its two writes can no longer fail a sync.
- The receipt inbox and the price-drop feed number their records the same
  way.

Not changed: authorization, the mass-delete guard, how records are compared
and written, snapshots.

## What it costs

- A device gets its own last upload back once on its next sync (it is
  skipped on arrival). A photo added on the phone is downloaded once more.
- A record written less than about three minutes before a device's previous
  sync is sent to that device again. In the simulation, devices syncing
  every 20 s see a record version 2.8 times on average; at a calmer pace
  (minutes between syncs) 1.1 times.

## What it does not fix

Two devices rewriting the **same** record within about a minute of each
other: the server compares the incoming `updatedAt` with a copy of the
record that may be stale, so the later arrival can win over a newer edit.
This is older than this change and untouched by it.

## Files

- `apply.py`: applies the change to a downloaded copy of the live module
  (which must already have the snapshot fix and the sync speed change):
  `python3 apply.py live.js patched.js`. Six replacements; it stops if any
  is not found the expected number of times.
- `test.mjs`: simulation, no network:
  `node --max-old-space-size=2048 test.mjs /abs/live.mjs /abs/patched.mjs`.
  The KV in it caches per location for 60 s and delays visibility of a write
  in other locations; time is virtual. 18 checks:
  - the 22 Nov collision reproduces on the live code and is gone;
  - three devices in three locations, two simulated hours of edits and
    syncs, twelve runs: the live code leaves records undelivered in every
    run (about 87 device/record pairs in all), the new code in none, also
    when writes take up to 100 s to show elsewhere;
  - a device with an old bookmark receives exactly the newer records;
  - the app's paged download loop stops within three pages;
  - roll-back to the previous version stays safe;
  - 220 single-device requests: the device holds the same data as with the
    live code after every answer, with the same refusals, the same stored
    data apart from the numbers, and the same number of snapshots;
  - a receipt pushed by the server reaches the device.
  It also runs against `../worker.ts` before and after the change
  (`node --experimental-strip-types`).
- The suites in `../snapshot-fix` and `../sync-speed` compare against the
  code that was live before their own change and use the old small numbers,
  so some of their checks no longer apply to code that has this change.

## Roll-back

Redeploy the previous version. The stored counter is normally already above
every bookmark; to be certain, set `seq/<account>` to the current time in
milliseconds first (one KV write), so the old code's next number is above
anything a device holds.
