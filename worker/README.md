# wardrobe-sync

Cloud sync service for the Wardrobe app (https://dyacobs-tech.github.io/wardrobe/).
Cloudflare Worker + Workers KV (`SYNC_KV`). The HTTP contract matches Padel Log
sync, so the app client cannot tell which host serves it.

**This copy is ready to review and to test locally. It is not deployed.**
Do not run `wrangler deploy`, and do not write to
`wardrobe-sync.dyacobs.workers.dev`, unless David has explicitly said yes
and a Cloudflare login or API token is available. `npm run deploy` is
wired to refuse.

| File | What |
|---|---|
| `worker.ts` | The service — Cloudflare Workers + Workers KV. The deploy target, once approved. |
| `wrangler.toml` | Workers config (KV binding `SYNC_KV`). Namespace ids are placeholders only. |
| `test_hardening.ts` | In-memory unit tests for delete hardening (no network, no wrangler). |
| `test.ts` | Broader HTTP round-trip checks, run against `wrangler dev`. |
| `main.ts` | Legacy Deno Deploy version (Deno KV). Reference only — do not deploy. |

Secrets (`REGISTER_SECRET`, `RENDER_WATCHER_SECRET`) are set with
`wrangler secret put` on the Worker and are never stored in this folder.

## How sync treats deletes today (and what this patch changes)

Every record is last-writer-wins on the client-supplied `updatedAt`.
A delete is not an erasure: it is stored as a tombstone
`{ coll, id, updatedAt, deleted: true }`. Payload chunks are removed after
the tombstone meta is written. Clients page new records with `since` / `now`.

The original server also had a mass-delete guard: a pass that would
tombstone ≥ 6 records and more than 20% of a collection was refused with
`409 { error: "mass_delete" }` unless the client retried with
`confirmMassDelete: true`. That guard is what stopped the Nov 18, 2026
incident (54 tombs from a short local list versus a still-intact server
snapshot). The remaining hole was that a confirmed pass still followed
plain LWW, and a tomb stamped with “now” is newer than the live server
`updatedAt`, so it would have been applied.

This patch adds three server-side layers. Old clients that send neither
`baseline` nor `baseUpdatedAt` keep working for ordinary small deletes.

1. **Baseline-manifest gate.** The client may send
   `baseline: { [coll]: { n, h } }` where `h` is the sha256 of the sorted
   live ids joined by a newline. If that manifest does not match the
   server’s live id-set, every delete for that collection is *cancelled*
   (HTTP 200, not 409). The live records are returned so the client can
   heal. `confirmMassDelete` cannot override a mismatch. If `baseline` is
   omitted, this gate is skipped.
2. **Circuit breaker.** A pass that would tombstone too much of a
   collection is refused 409 unless confirmed. Old clients keep the
   original floor-6 / 20% rule. Clients that sent a *matching* baseline
   get a tighter rule: more than 3 records, or more than 10% of live.
   `confirmMassDelete` loosens the breaker only.
3. **Server-truth.** A delete of a currently-live record is applied only
   if the client proves it saw that version: `baseUpdatedAt` equals the
   live `updatedAt`, or the client sent a matching baseline for that
   collection. `confirmMassDelete` alone is not proof. Cancelled deletes
   are listed in a `cancelled` array (`reason` is `server_truth` or
   `baseline_mismatch`); old clients can ignore the field. The live
   record is included in `recs` so a local tomb can be overwritten.

A future app build should start sending `baseline` and per-delete
`baseUpdatedAt`, and should treat a `409 mass_delete` the same way it
already treats the client-side “Confirm deletes” prompt.

## Local tests

The default test is a self-contained Deno harness with an in-memory KV.
It does not touch the network or production:

```
cd worker
deno run --allow-env test_hardening.ts
# or: npm test
```

The broader HTTP suite still runs against a local `wrangler dev` (use
only a fresh local persist directory, never production KV):

```
npx wrangler dev --var REGISTER_SECRET:test-register-secret \
  --var RENDER_WATCHER_SECRET:test-watcher-secret \
  --var RENDER_CAP_PER_DAY:3 --persist-to /tmp/wardrobe-sync-test
# in another shell:
deno run --allow-net --allow-env test.ts http://localhost:8787
```

## Deploying (needs David’s yes — do not do this yet)

A real deploy needs all of the following:

- David’s explicit approval to publish this worker over production.
- A Cloudflare login, or an API token with permission to edit the
  `wardrobe-sync` Worker and its `SYNC_KV` namespace.
- The production KV namespace id put into `wrangler.toml` locally
  (do not commit that id). The placeholder values here will not
  bind to the live namespace.
- The existing Worker secrets already set on production
  (`REGISTER_SECRET`, `RENDER_WATCHER_SECRET`). Do not rotate or
  overwrite them unless David asks.

The live endpoint is `https://wardrobe-sync.dyacobs.workers.dev`.
