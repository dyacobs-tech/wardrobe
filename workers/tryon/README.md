# wardrobe-tryon (deployed source, read-only copy)

The Cloudflare Worker behind Ask, photo identify and try-on
(`https://wardrobe-tryon.dyacobs.workers.dev`). Until Nov 19 2026 its source
lived only on Cloudflare; this folder is a verbatim copy of the deployed
script, fetched read-only through the Cloudflare API.

- Deployed etag: `939ddd1c01f8b91dd899dd867fd51a3a1a6fb01fb1a7e98b165a815189514089`
- Last modified on Cloudflare: 2026-11-19 03:20 ET (08:20 UTC)
- Compatibility date: 2025-06-01, module worker, `fetch` handler only

Bindings (names only; no values are stored here):

| Binding | Type |
|---|---|
| `AI` | Workers AI |
| `SYNC_KV`, `TRYON_KV` | KV namespaces |
| `ASK_CAP_PER_DAY`, `IDENTIFY_CAP_PER_DAY`, `TRYON_CAP_PER_DAY`, `FASHN_MODE`, `FASHN_RESOLUTION` | plain-text vars |

The FASHN API key is read at runtime from `env.FASHN_API_KEY` or, failing
that, from `TRYON_KV` (see `fashnKey()`); it is not in this repo.

Deploy only through the Cloudflare MCP `execute` tool, with a backup of the
current script first (standing rule). This copy is not wired to any deploy
command. If the deployed script changes, refresh this copy and its etag.
