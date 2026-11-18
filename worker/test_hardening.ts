// In-memory unit tests for wardrobe-sync delete hardening.
// No network, no wrangler, no production KV.
// Usage: deno run --allow-env test_hardening.ts
import { handler, liveIdManifest, type Env } from "./worker.ts";

let pass = 0, fail = 0;
function check(name: string, cond: boolean, extra = "") {
  if (cond) { pass++; console.log("  ok  " + name); }
  else { fail++; console.log("  FAIL " + name + (extra ? " — " + extra : "")); }
}

class MemoryKV {
  store = new Map<string, string>();
  get(key: string): Promise<string | null> {
    return Promise.resolve(this.store.has(key) ? this.store.get(key)! : null);
  }
  put(key: string, value: string): Promise<void> {
    this.store.set(key, value);
    return Promise.resolve();
  }
  delete(key: string): Promise<void> {
    this.store.delete(key);
    return Promise.resolve();
  }
  list(options?: { prefix?: string; cursor?: string; limit?: number }) {
    const prefix = options?.prefix ?? "";
    const all = [...this.store.keys()].filter((k) => k.startsWith(prefix)).sort();
    const start = options?.cursor ? Number(options.cursor) || 0 : 0;
    const limit = options?.limit ?? 1000;
    const slice = all.slice(start, start + limit);
    const list_complete = start + slice.length >= all.length;
    return Promise.resolve({
      keys: slice.map((name) => ({ name })),
      list_complete,
      cursor: list_complete ? undefined : String(start + slice.length),
    });
  }
}

function env(): Env {
  return {
    SYNC_KV: new MemoryKV() as unknown as Env["SYNC_KV"],
    REGISTER_SECRET: "test-register-secret",
    RENDER_WATCHER_SECRET: "test-watcher-secret",
  };
}

const BASE = "http://wardrobe-sync.test";

async function call(
  e: Env,
  path: string,
  opts: { method?: string; body?: unknown; headers?: Record<string, string> } = {},
) {
  const headers: Record<string, string> = { ...(opts.headers || {}) };
  let body: string | undefined;
  if (opts.body !== undefined) {
    headers["content-type"] = headers["content-type"] || "application/json";
    body = typeof opts.body === "string" ? opts.body : JSON.stringify(opts.body);
  }
  const res = await handler(
    new Request(BASE + path, { method: opts.method || "GET", headers, body }),
    e,
  );
  return { status: res.status, j: await res.json().catch(() => null) };
}

async function register(e: Env) {
  const r = await call(e, "/register", {
    method: "POST",
    headers: { "x-register-secret": "test-register-secret" },
  });
  if (r.status !== 200 || !r.j?.key) throw new Error("register failed: " + JSON.stringify(r));
  return r.j as { key: string; acct: string };
}

async function sync(e: Env, key: string, body: unknown) {
  return call(e, "/sync", {
    method: "POST",
    headers: { authorization: "Bearer " + key },
    body,
  });
}

function live(recs: { data?: unknown; deleted?: boolean }[] | undefined) {
  return (recs || []).filter((x) => x.data && !x.deleted);
}

const T = 1_700_000_000_000;

async function seedItems(e: Env, key: string, n: number, at = T) {
  const changes = [];
  const ids: string[] = [];
  for (let i = 0; i < n; i++) {
    const id = "item-" + i;
    ids.push(id);
    changes.push({ coll: "items", id, updatedAt: at + i, data: { id, name: id } });
  }
  const r = await sync(e, key, { since: 0, changes, meta: null });
  if (r.status !== 200) throw new Error("seed failed: " + JSON.stringify(r));
  return { ids, now: r.j.now as number };
}

function tombs(ids: string[], at: number, extra: Record<string, unknown> = {}) {
  return ids.map((id, i) => ({
    coll: "items",
    id,
    updatedAt: at + i,
    deleted: true,
    ...extra,
  }));
}

// 1. Service identity + a fresh account
{
  const e = env();
  const root = await call(e, "/");
  check("GET / identifies the service", root.status === 200 && root.j?.ok === true && root.j?.service === "wardrobe-sync");
}

// 2. Ordinary single delete from an old client (no baseline, no baseUpdatedAt) still applies
{
  const e = env();
  const { key } = await register(e);
  const seeded = await seedItems(e, key, 3);
  const r = await sync(e, key, {
    since: seeded.now,
    changes: tombs(["item-0"], T + 1000),
    meta: null,
  });
  check("old-client single delete is accepted", r.status === 200, JSON.stringify(r.j));
  const down = await sync(e, key, { since: 0, changes: [], meta: null });
  const gone = (down.j?.recs || []).find((x: { id: string }) => x.id === "item-0");
  check("old-client single delete becomes a tombstone", gone?.deleted === true);
  check("other records stay live", live(down.j?.recs).length === 2);
}

// 3. Server-truth: matching baseUpdatedAt deletes; mismatch cancels and heals
{
  const e = env();
  const { key } = await register(e);
  const seeded = await seedItems(e, key, 2);
  const ok = await sync(e, key, {
    since: seeded.now,
    changes: [{
      coll: "items",
      id: "item-0",
      updatedAt: T + 2000,
      deleted: true,
      baseUpdatedAt: T + 0, // seed used T+i
    }],
    meta: null,
  });
  check("matching baseUpdatedAt delete is accepted", ok.status === 200 && (ok.j?.cancelled || []).length === 0);

  const bad = await sync(e, key, {
    since: 0,
    changes: [{
      coll: "items",
      id: "item-1",
      updatedAt: T + 3000,
      deleted: true,
      baseUpdatedAt: 1, // not the live updatedAt
    }],
    meta: null,
  });
  check("mismatched baseUpdatedAt is cancelled, not 409",
    bad.status === 200 && bad.j?.cancelled?.[0]?.reason === "server_truth",
    JSON.stringify(bad.j?.cancelled));
  const healed = (bad.j?.recs || []).find((x: { id: string }) => x.id === "item-1");
  check("cancelled delete returns the live record so the client can heal",
    healed && !healed.deleted && healed.data?.id === "item-1",
    JSON.stringify(healed));
  const down = await sync(e, key, { since: 0, changes: [], meta: null });
  const still = (down.j?.recs || []).find((x: { id: string }) => x.id === "item-1");
  check("mismatched delete did not tombstone the live record", still && !still.deleted);
}

// 4. Legacy circuit breaker (no baseline): 8 of 10 is 409; nothing is written
{
  const e = env();
  const { key } = await register(e);
  await seedItems(e, key, 10);
  const blocked = await sync(e, key, {
    since: 0,
    changes: tombs(["item-0","item-1","item-2","item-3","item-4","item-5","item-6","item-7"], T + 4000),
    meta: null,
  });
  check("deleting 8 of 10 without confirmation -> 409 mass_delete",
    blocked.status === 409 && blocked.j?.error === "mass_delete" &&
    blocked.j?.deletions === 8 && blocked.j?.live === 10,
    JSON.stringify(blocked.j));
  const peek = await sync(e, key, { since: 0, changes: [], meta: null });
  check("blocked pass deleted nothing", (peek.j?.recs || []).filter((x: { deleted?: boolean }) => x.deleted).length === 0);
}

// 5. confirmMassDelete alone cannot wipe live records (the Nov 18 hole)
{
  const e = env();
  const { key } = await register(e);
  await seedItems(e, key, 10);
  const ids = ["item-0","item-1","item-2","item-3","item-4","item-5","item-6","item-7"];
  const r = await sync(e, key, {
    since: 0,
    changes: tombs(ids, T + 5000),
    meta: null,
    confirmMassDelete: true,
  });
  check("confirm without baseline/baseUpdatedAt returns 200", r.status === 200, JSON.stringify(r.j));
  check("all 8 live deletes are cancelled with server_truth",
    (r.j?.cancelled || []).length === 8 &&
    (r.j?.cancelled || []).every((c: { reason: string }) => c.reason === "server_truth"),
    JSON.stringify(r.j?.cancelled));
  const down = await sync(e, key, { since: 0, changes: [], meta: null });
  check("confirm without proof left all 10 records live", live(down.j?.recs).length === 10, "live=" + live(down.j?.recs).length);
}

// 6. Wrong baseline + confirm still cancels (confirm cannot bypass the gate)
{
  const e = env();
  const { key } = await register(e);
  await seedItems(e, key, 10);
  const ids = ["item-0","item-1","item-2","item-3","item-4","item-5","item-6","item-7"];
  const r = await sync(e, key, {
    since: 0,
    changes: tombs(ids, T + 6000),
    meta: null,
    confirmMassDelete: true,
    baseline: { items: { n: 10, h: "0".repeat(64) } },
  });
  check("mismatched baseline does not 409", r.status === 200, JSON.stringify(r.j));
  check("mismatched baseline cancels with baseline_mismatch",
    (r.j?.cancelled || []).length === 8 &&
    (r.j?.cancelled || []).every((c: { reason: string }) => c.reason === "baseline_mismatch"),
    JSON.stringify(r.j?.cancelled));
  const down = await sync(e, key, { since: 0, changes: [], meta: null });
  check("mismatched baseline left all 10 live", live(down.j?.recs).length === 10);
}

// 7. Matching baseline + confirm applies the mass delete
{
  const e = env();
  const { key } = await register(e);
  const { ids } = await seedItems(e, key, 10);
  const man = await liveIdManifest(ids);
  const drop = ids.slice(0, 8);
  const r = await sync(e, key, {
    since: 0,
    changes: tombs(drop, T + 7000),
    meta: null,
    confirmMassDelete: true,
    baseline: { items: man },
  });
  check("matching baseline + confirm accepts the mass delete",
    r.status === 200 && (r.j?.cancelled || []).length === 0, JSON.stringify(r.j));
  const down = await sync(e, key, { since: 0, changes: [], meta: null });
  check("verified confirmed pass leaves the other 2 records",
    live(down.j?.recs).length === 2, "live=" + live(down.j?.recs).length);
}

// 8. Matching baseline without confirm still trips the tight breaker
{
  const e = env();
  const { key } = await register(e);
  const { ids } = await seedItems(e, key, 10);
  const man = await liveIdManifest(ids);
  const four = await sync(e, key, {
    since: 0,
    changes: tombs(ids.slice(0, 4), T + 8000),
    meta: null,
    baseline: { items: man },
  });
  check("4 of 10 with matching baseline and no confirm -> 409 (tight breaker)",
    four.status === 409 && four.j?.error === "mass_delete" && four.j?.deletions === 4,
    JSON.stringify(four.j));
  const two = await sync(e, key, {
    since: 0,
    changes: tombs(ids.slice(0, 2), T + 8100, { baseUpdatedAt: T }), // baseUpdatedAt overridden per item below
    meta: null,
    baseline: { items: man },
  });
  // 2 of 10 is >10% of live, so the tight breaker should also 409
  check("2 of 10 with matching baseline and no confirm -> 409 (>10%)",
    two.status === 409 && two.j?.error === "mass_delete" && two.j?.deletions === 2,
    JSON.stringify(two.j));
  const one = await sync(e, key, {
    since: 0,
    changes: [{
      coll: "items",
      id: "item-0",
      updatedAt: T + 8200,
      deleted: true,
      baseUpdatedAt: T + 0,
    }],
    meta: null,
    baseline: { items: man },
  });
  check("1 of 10 with matching baseline needs no confirmation", one.status === 200, JSON.stringify(one.j));
}

// 9. Stale write still cannot regress a live record
{
  const e = env();
  const { key } = await register(e);
  await seedItems(e, key, 1);
  await sync(e, key, {
    since: 0,
    changes: [{ coll: "items", id: "item-0", updatedAt: T + 50, data: { id: "item-0", name: "newer" } }],
    meta: null,
  });
  const staleDel = await sync(e, key, {
    since: 0,
    changes: [{
      coll: "items",
      id: "item-0",
      updatedAt: T + 1,
      deleted: true,
      baseUpdatedAt: T,
    }],
    meta: null,
  });
  check("stale tomb (older updatedAt) is ignored", staleDel.status === 200 && (staleDel.j?.cancelled || []).length === 0);
  const down = await sync(e, key, { since: 0, changes: [], meta: null });
  const rec = (down.j?.recs || []).find((x: { id: string }) => x.id === "item-0");
  check("stale tomb left the newer live record in place", rec && !rec.deleted && rec.data?.name === "newer");
}

console.log("");
console.log(pass + " passed, " + fail + " failed");
if (fail) Deno.exit(1);
