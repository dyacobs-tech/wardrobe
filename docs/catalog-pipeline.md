# The Edit catalog pipeline

A reusable, append-only pipeline for The Edit (the shoppable catalog in
the Donna wardrobe app). It is designed so today's Shopify pulls and
tomorrow's affiliate-network feeds (Rakuten, CJ, Impact, Awin,
Partnerize, plus generic CSV/XML and ShopStyle/Skimlinks stubs) share
one schema, one ingest path, and one nightly refresh.

Shopify ingest is the source that ships inventory now. Affiliate
adapters are implemented and tested against fixtures, but they are
**disabled by default** and do not run — and do not apply to any
programme or create any accounts — until a human enables them and
provides credentials via environment variables.

## What stays sacred

- Every SKU already in `assets/edit-catalog.json` is **locked**. Ingest
  never deletes a row and never overwrites a field on an existing row.
- New rows are appended only after a dedupe against:
  1. canonical product URL (`url`)
  2. `brand + name` (case-insensitive)
- Sold-out items are dropped from an *incoming* batch. An item that was
  already in the catalog and later goes out of stock is marked
  `status: "inactive"` by the nightly refresh — it is not removed.
- Seed rows (the original verified catalog) do not have
  `pipeline: true`. Refresh leaves them untouched, including price.

## Layout

```
scripts/feeds/
  brands.yml            curated stores + affiliate source flags
  schema.py             normalized product + category / colour / tier
  shopify_pull.py       public products.json puller (rate-limited)
  cutout.py             rembg / IS-Net cut-out on #F6F2EA, webp 640px
  ingest.py             append-only merge into assets/edit-catalog.json
  refresh.py            nightly price/stock; mark inactive, never delete
  run.py                orchestrator
  sources/
    base.py             skip-cleanly-if-disabled-or-no-creds interface
    shopify.py
    rakuten.py          Rakuten Advertising
    cj.py               CJ
    impact.py           Impact
    awin.py             Awin
    partnerize.py      Partnerize (Mr Porter, SSENSE, Farfetch)
    csv_xml.py          generic CSV / XML / JSON file feed
    aggregator.py       ShopStyle + Skimlinks stubs
docs/catalog-pipeline.md
tests/feeds/            fixtures-based unit tests (not part of the app shell)
```

The live GitHub Pages site is the app shell (`index.html`, `assets/`,
`sw.js`). `tests/` and `scripts/` are for development and CI
(`tests/smoke.py` already runs in Actions) and must not be linked from
the UI. Do not copy test fixtures into `assets/`.

## Normalized schema

Every adapter maps to the same row. Fields the live app already reads
(`window.editNormalizeCatalog`) come first; the rest are extras that
older clients ignore.

| Field | Required | Notes |
| --- | --- | --- |
| `url` | yes | **Canonical product page.** Dedupe key. Never a tracking link. |
| `affiliateUrl` | no | Network tracking / deep link, stored separately. Future click-through can prefer this when present; the app still uses `url` today. |
| `brand`, `name`, `price` | yes | `price` is a number. |
| `currency`, `priceDisplay` | no | `priceDisplay` is the formatted string (`$240`, `£390`). |
| `cat`, `subcat` | yes | See category map below. |
| `colour`, `hex` | no | Auto-tagged from the title / colour option. |
| `img`, `imgUrl` | yes (one) | `img` is the local webp after cut-out; `imgUrl` is the remote source. |
| `retailer`, `tier`, `st`, `sq`, `keys` | no | `tier` is the price band: `affordable` / `accessible` / `luxury` / `insensitive`. |
| `inStock`, `sizes` | no | `sizes`: `[{size, available, sku, price}]`. Incoming sold-out rows are dropped. |
| `source` | yes | `shopify:<store-id>`, `rakuten:<advertiser>`, `cj:<id>`, `impact:<campaign>`, `awin:<merchant>`, `partnerize:<campaign>`, `csvxml:<id>`, `aggregator:shopstyle` / `aggregator:skimlinks`. |
| `sourceId` | no | Platform product id / SKU. |
| `status` | no | `active` (default) or `inactive`. |
| `pipeline` | no | `true` for rows this pipeline manages. |
| `locked` | no | `true` means refresh must not touch the row. Seed rows are treated as locked even when the flag is absent. |
| `verified`, `retrievedAt` | no | ISO dates. |
| `occasion`, `gap`, `pairs` | no | Auto-tagged; `pairs` is filled at ingest against the closet, for *new* rows only. |

Category auto-tag (`cat` / `subcat`): trousers (incl. chinos), jeans,
shorts, swim, knitwear (incl. polo), shirt (incl. overshirt), blazer,
outerwear, shoes (loafer / sneaker / shoe), belt, sunglasses, bag, tie.
Women's / kids / loud graphic / underwear / gift-card rows are dropped.

## How to run (Shopify — the path that ships now)

```bash
# 1. See which sources will actually run
python3 scripts/feeds/run.py sources

# 2. Pull public products.json (polite delays, 429 backoff, robots.txt)
python3 scripts/feeds/shopify_pull.py --config scripts/feeds/brands.yml

#    or, reuse already-downloaded dumps
python3 scripts/feeds/shopify_pull.py --from-cache /path/to/raw/shopify

# 3. Normalize in-stock, in-taste rows
python3 scripts/feeds/run.py normalize --from-cache data/feeds/shopify \
    --out data/feeds/normalized.json

# 4. Cut images out onto #F6F2EA and rewrite `img` to assets/editimg/<hash>.webp
#    (batch helper lives with cutout.py; ingest expects img already local)

# 5. Append at most N new SKUs. Existing rows are preserved verbatim.
python3 scripts/feeds/ingest.py \
    --catalog assets/edit-catalog.json \
    --products data/feeds/normalized.json \
    --batch 250

# 6. After a catalog or first-paint change: bump WARDROBE_BUILD in
#    src/app.html and sw.js, then python3 scripts/build_shell.py
```

Probe a store without ingesting:

```bash
python3 scripts/feeds/shopify_pull.py --probe --include-disabled --store orlebar
```

Only stores with `enabled: true` and a successful `products.json`
verification are pulled for real. Brands on David's list that have not
yet served a product list stay in `brands.yml` as `enabled: false`.

Rate limits: default 3s between pages, 5s between stores, exponential
backoff on HTTP 429 (honours `Retry-After`). The puller is read-only
and does not authenticate.

## Nightly refresh

```bash
python3 scripts/feeds/refresh.py --catalog assets/edit-catalog.json
```

For each pipeline Shopify row the script re-fetches
`/products/<handle>.json`, updates price / sizes / `inStock`, and marks
missing or sold-out rows `inactive`. Seed rows are skipped. Nothing is
deleted. Safe to run from a scheduled job.

## Affiliate networks (implemented, not applied)

Do **not** apply to Rakuten Advertising, CJ, Impact, Awin, Partnerize,
ShopStyle, or Skimlinks, and do not create accounts, from this pipeline. The adapters
exist so a future commercial product can plug a feed in without another
ingest rewrite.

Each network adapter:

- is listed under `affiliates:` in `scripts/feeds/brands.yml` with
  `enabled: false`
- reads credentials **only** from environment variables
- returns a skip reason and zero items when disabled or when any
  required variable is unset (no error, no network call)
- maps the network's product fields onto the normalized schema
- stores the tracking URL in `affiliateUrl` and the merchant product
  page in `url`

### What to set when (later) enabling one

| Network | Env vars | Typical product API / feed | Canonical URL field | Tracking URL field |
| --- | --- | --- | --- | --- |
| Rakuten Advertising | `RAKUTEN_TOKEN` | Product Search API | `product_url` / `landing_page_url` | `buy_url` / `click_url` / `linkurl` |
| CJ | `CJ_API_KEY` | Product Search v2 | `product-url` / `manufacturer-page` | `buy-url` |
| Impact | `IMPACT_SID`, `IMPACT_TOKEN` | Catalogs API (HTTP Basic SID:token) | `LandingPageUrl` / `CanonicalUrl` | `TrackingUrl` / `TrackingLink` |
| Awin | `AWIN_API_KEY` (optional `AWIN_PUBLISHER_ID`) | Product datafeed / API v3 | `merchant_deep_link` | `aw_deep_link` |
| Partnerize | `PARTNERIZE_USER_KEY`, `PARTNERIZE_API_KEY` | Catalog / product feed (camref / prf.hn links) | `destination_url` / `product_url` | `tracking_url` / `click_url` / camref deep link |
| ShopStyle | `SHOPSTYLE_API_KEY` | ShopStyle API | `pageUrl` | `clickUrl` |
| Skimlinks | `SKIMLINKS_API_KEY`, `SKIMLINKS_PUBLISHER_ID` | Link-wrapping API + a product feed | `canonical_url` | wrapped `affiliate_url` |
| Generic CSV/XML | none | local path or https URL in `feed:` | `url` / `link` / `merchant_deep_link` | `affiliate_url` / `click_url` / `aw_deep_link` / `buy_url` |


### Which network for which retailer (research, Nov 2026)

This is a map for a future commercial hook-up. It does not change any
existing catalog row, and nothing is applied automatically.

- **Partnerize** — Mr Porter, SSENSE and Farfetch run their US publisher
  programmes here. Together they account for roughly half of the current
  Edit's retailer links (the original verified batch has 14 SSENSE +
  6 Mr Porter SKUs; Farfetch was not used as a live source because it
  blocked the first fetch). Use the Partnerize adapter, not Rakuten/CJ/
  Impact/Awin, when those three are enabled later.
- **Impact** — Nordstrom and END.
- **Rakuten Advertising** — Todd Snyder moved from CJ to Rakuten around
  November 2026; use the Rakuten adapter for that brand going forward.
- Brand-direct Shopify pulls (Kiton, Sunspel, Drake's, and the other
  curated `brands.yml` stores) do not go through an affiliate network.

To enable later (not now):

1. Put the token in the environment (or a secret store). Never commit it.
2. Flip `enabled: true` on that block in `brands.yml`.
3. Run `python3 scripts/feeds/run.py sources` and confirm the skip
   reason is gone.
4. Normalize and ingest through the same append-only path.

### How links and commissions flow

```
product card  →  affiliateUrl (if set)  →  network  →  merchant PDP
                 else url (canonical PDP)
```

The catalog always keeps the canonical PDP so we can verify the page
still loads, refresh price/stock, and dedupe. The network's deep link
is what would later carry the publisher id / click token and is how a
commission would be attributed. This pipeline does not wrap links, does
not register clicks, and does not settle commissions. Enabling a
network later should not rewrite existing `url` values.

## Cut-outs and image rules

- Background is always off-white `#F6F2EA`. No grey studio backdrops.
- `cutout.py` prefers rembg (`isnet-general-use`) and falls back to
  the same IS-Net model via onnxruntime.
- Output is webp, max 640px, quality 80, named
  `assets/editimg/<sha16>.webp` so the service worker and lazy loader
  stay unchanged.
- Images on seed rows are not replaced.

## Tests

```bash
python3 -m pytest tests/feeds -q
```

Tests are fixture-based and make no network calls and no live
applications. They must stay out of the deployed app shell.

## Shipping batches

Push only through a fresh clone, rebase onto `origin/main` immediately
before each push, fast-forward only, never force-push, never revert
other workers' commits. After appending a batch, bump `WARDROBE_BUILD`
in `src/app.html` and `sw.js` and run `python3 scripts/build_shell.py`
if the shell changed. No sync writes.
