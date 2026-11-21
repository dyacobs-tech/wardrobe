# DONNA: the eventual list

Ideas David has approved for later. None of these is in progress. Each one
starts with a plan and mockups for David, and nothing goes live without his OK.

## Standing rules for every item here

- Send David a plan and mockups first.
- Make no live changes without his OK.
- Never recommend women's items.

## 1. ShopMy as an affiliate source

Brief from David, 21 Nov 2026:

- Add ShopMy as another affiliate source alongside Rakuten, CJ, Impact and
  Awin. Keep it **off until ShopMy approves the account**.
- Make every Inspo and icon look shoppable.
- Route each piece to the best store for it.
- Compare what ShopMy pays after its cut (David's figure: 18%) with the
  direct networks, and use whichever earns more for the same item.
- If ShopMy approves us, look at its auto-link script:
  guide.shopmy.us/en/articles/17359610.
- **Do not build:** an influencer marketplace, link-in-bio pages, physical
  gifting, or anything that hides other brands' links.

Open questions for the plan:

- Does ShopMy's link format work from a home-screen PWA?
- Does its auto-link script run on a page we host? Read the guide above
  before assuming it does.

## 2. Vintage and resale: eBay and The RealReal

**eBay.** eBay has an official Buy › Browse API whose `item_summary/search`
method searches listings by keyword, category or image. The eBay Partner
Network is its affiliate programme. An affiliate campaign id sent in the
`X-EBAY-C-ENDUSERCTX` request header should return an `itemAffiliateWebUrl`
on each item. Developers on eBay's forum report getting it working only
after some trouble. To check before building:

- The exact header syntax: eBay's Buying Integration Guide has it.
- Whether a personal app needs extra approval or scopes for the affiliate
  fields.
- The API needs an app key, so the calls would run through our worker and
  never from the page.

**The RealReal.** It has an official affiliate page
(therealreal.com/affiliates); third-party sites say it runs on Impact.
Commission and cookie terms differ from one aggregator to the next, so take
them from the programme itself. There is no public product API that we know
of. Choices, best first:

- Check whether Impact offers a RealReal product feed.
- Link out to a RealReal search per piece, with no product photos in the
  app.
- Scrape, which is not recommended (terms of service).

How it could look in the app: a "Vintage" option on Dress me's New picker
and on Shop. Resale listings are one of a kind and sell out fast, so we
would fetch them live and never bake them into the renders.

## 3. Other parked items

- Colour palette, folded into AI creation and Inspo.
- Share a link to DONNA → a store inbox.
- AI "describe a look".
- Many more on-body renders, as a batch plan with a cost first (each FASHN
  render costs about 2 credits).
- Bring a go-to back on Home now and then.
- A wardrobe-cataloguing service (research only).
- Engineering:
  - a photo cache in the service worker
  - the IndexedDB gap in preview
  - silent account creation
  - sync efficiency
