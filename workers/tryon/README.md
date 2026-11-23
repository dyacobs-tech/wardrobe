# wardrobe-tryon (deployed source, read-only copy)

The Cloudflare Worker behind Ask, photo identify and try-on
(`https://wardrobe-tryon.dyacobs.workers.dev`). Until Nov 19 2026 its source
lived only on Cloudflare; this folder is a verbatim copy of the deployed
script, fetched read-only through the Cloudflare API.

- Deployed 2026-11-23 ~15:10 UTC (David: "yes deploy the assistant"): Ask tries OpenAI first when a real
  OpenAI key (starts `sk-`) is saved as a secret; otherwise Workers AI as before. `GET /ask/ping` reports
  whether the key works and which model answered (no key values, 30 a day). Backup of the previous script
  (etag `939ddd1c…9089`) was taken before deploying; it is the previous version of this file in git.
- The Ask catalog in `TRYON_KV` (`catalog:v1`) was refreshed to the 1,987-product Edit catalog (was 250).
- Compatibility date: 2025-06-01, module worker, `fetch` handler only

Bindings (names only; no values are stored here):

| Binding | Type |
|---|---|
| `AI` | Workers AI |
| `SYNC_KV`, `TRYON_KV` | KV namespaces |
| `ASK_CAP_PER_DAY`, `IDENTIFY_CAP_PER_DAY`, `TRYON_CAP_PER_DAY`, `FASHN_MODE`, `FASHN_RESOLUTION` | plain-text vars |
| `key_BE3gX1OPxUqH6jDL` (secret), `apikey_01D4TB6uBd1x13y3rvuqqSez` (plain text) | added by David 23 Nov for the assistant; read by `openaiKey()` only if the value is an `sk-` key |

The FASHN API key is read at runtime from `env.FASHN_API_KEY` or, failing
that, from `TRYON_KV` (see `fashnKey()`); it is not in this repo.

Deploy only through the Cloudflare MCP `execute` tool, with a backup of the
current script first (standing rule). This copy is not wired to any deploy
command. If the deployed script changes, refresh this copy and its etag.
