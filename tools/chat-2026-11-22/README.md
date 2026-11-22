# Helper scripts from the chat of 21–22 Nov 2026

These are the working scripts from that chat's temporary folder, copied here
so the next chat does not have to rewrite them. They are **not part of the
app** and nothing in the build uses them. `docs/handover.md` says what each
was for.

Before running one:

- Every script has a hard-coded folder path at the top (a variable called `S`
  or an absolute `/tmp/claude-0/...` path). That folder no longer exists.
  Point it at your own working folder.
- `SYNC_ACCOUNT_ID` stands in for the sync account number. The real value
  appears in `workers/tryon/worker.js` and in the app's own sync settings; do
  not copy it into more files.
- Calls to FASHN, Cloudflare and the sync worker carry a dummy
  `Authorization` header. In the cloud environment named `wardrobe` the
  network proxy swaps in the real key. No script contains a key.
- Scripts that read `sync/latest-dl.json` expect a full copy of the closet:
  `POST https://wardrobe-sync.dyacobs.workers.dev/sync` with body
  `{"since":0,"changes":[]}` (about 32 MB). Keep that file out of the repo:
  it holds David's closet and pictures.

| Folder | What is in it |
|---|---|
| `renders/` | On-avatar outfit pictures. `swap.py` (one FASHN try-on on an existing render, head restored), `drive.py` (batch runner), `integrate.py` (writes `assets/onbody*`, manifests, `feet.json`, `lq.json`), `frame.py` and `qa.py` (catch zoomed or cropped results), `fixfeet2.py` and `fixfeet5.py` (repair a cut-out that lost a shoe), `plan/` (pick outfits with the app's own dealer and validate them), `outfits-shot.js` (screenshot the Outfits tab). |
| `closet-pictures/` | Closet pictures in the look of the earlier ones. `edit-batch.py` (FASHN `edit` on an earlier picture of the same kind of garment), `tee-finish.py` (fit to the card and shift to the measured cloth colour), `tee-prints.py` (put a print back), `fin2.py` (fit any cut-out onto the 900×1200 cream card). |
| `phone-sim/` | The live app in a phone-sized browser with David's data. `shots.js`, `loro.js`, `jacket.js` serve the closet from the local copy (nothing is written). `real.js` talks to the real sync server read-only: uploads are held back. |
| `open-speed/` | The flicker work. `launch.js` (records every frame of an open), `mut.js` (lists every change to the Home screen with its time), `prof.js` + `an.py` (processor profile of an open). |
| `drive/` | `fetch.sh <fileId> <out>`: download a Drive file that is shared as "Anyone with the link". Exit 3 means it is still private. |
| `tests/` | `chromerun.py` (run one repo test with Chromium standing in for WebKit), `fullrun2.sh` (run the suite to a log), `livecheck845.js` (quick check of the live site after a publish). |
