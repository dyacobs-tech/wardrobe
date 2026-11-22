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

## 3. Receipts by email

David, 21 Nov 2026 (after seeing Indyx ask "Do your online shopping receipts
go to a Gmail address?"): ask for the email his receipts go to, so purchases
are tracked from order emails.

**What already exists (build .41):**

- Shop › Receipts: a review page. Each purchase found in an order email
  shows as a card; one tap files it into the Closet and into Purchased.
  Nothing is filed without a tap.
- The sync worker's `/receipt-inbox`: takes parsed order lines and delivers
  them to the app. It only adds; a dismissed or confirmed line never comes
  back.

**What is missing:** the part that reads the order emails. It was a script
run on a computer, outside the app. Nothing reads them today as far as we
can tell from the repo.

**Ways to feed it, simplest first:**

1. A scheduled Claude task reads the Gmail inbox for new order emails and
   sends the purchases to the inbox above. No new app code. Needs David's OK
   to read his mail, and the inbox's secret entered once in a secure form.
2. A forwarding address: he forwards receipts (or sets a Gmail filter) to a
   DONNA address, and the worker reads only what is forwarded. Needs a domain
   that can receive email. This is the privacy-friendly choice for clients.
3. "Connect Gmail" inside the app, as Indyx appears to do. Google treats
   reading Gmail as a restricted permission; a public app has to pass
   Google's verification first. Check Google's current rules before
   planning this.

**In the app:** Profile gets "Where do your receipts go?" with the email, so
the reader knows which inbox to watch.

## 4. Other parked items

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
  - sync efficiency: the read side was fixed on 22 Nov 2026
    (worker/sync-speed). Still open: the record counter can hand the same
    number to two devices that save within about a minute of each other
    (see that folder's README), and a full download is built in memory,
    which will stop working somewhere above the current 31 MB closet (the
    Worker limit is 128 MB; the exact ceiling is not measured).
