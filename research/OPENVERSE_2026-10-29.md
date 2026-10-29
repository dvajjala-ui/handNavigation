# Openverse source qualification — 2026-10-29

## Outcome

HandNavigate source now includes `openverse`, a keyless read-only adapter for
Openverse image search. It is designed for the hosted daily collector and does
not require a browser profile, AI key or paid API.

Openverse candidates remain private and unreviewed when delivered to
StickerDock. A reported CC0 or public-domain label is carried as a review hint;
it does not approve generation or publish a pack. The owner must verify the
original work and record rights evidence in StickerDock Admin.

## Safety and product contract

- Search is fixed to `https://api.openverse.org/v1/images/`.
- Anonymous requests use the documented 20-result page bound.
- Queries request `cc0,pdm`, commercial/modification-compatible and non-mature
  candidates.
- Pixels are fetched only from Openverse's fixed-origin thumbnail proxy. An
  arbitrary result host is retained as provenance but never fetched by the
  worker.
- Result IDs, dimensions, license URL, landing URL, title, creator and bounded
  review tags are validated before the shared image runner sees a candidate.
- The shared runner still enforces the 25 MB/40 MP image bounds, decoded
  JPEG/PNG/WebP validation, exact/perceptual duplicate checks and journaled
  delivery.
- Transient Openverse 429/5xx responses receive two bounded retries. Other
  failures stop honestly.
- Repeated topics now search up to five documented result pages (20 results
  each), skipping previously collected source URLs. The adapter stops after
  enough fresh candidates are found and respects the returned page count.
  This is a bounded search, not a guarantee of 20 usable new images on every
  day; pixel validation and near-duplicate checks can still reduce the yield.

## Evidence in this change

- `npm test`: 37/37 desktop/core tests passed.
- `npm run test:service`: 36/36 service/worker tests passed.
- Live keyless local check: two requested images returned
  `VERIFIED_LOCAL`, both decoded at 600 px, one reported `CC0` and one reported
  `PUBLIC_DOMAIN`.
- Tests cover fixed-origin downloads, unsafe provenance hosts, result bounds,
  mature/unsupported-license rejection, duplicate suppression, metadata
  delivery and transient retry bounds.

The initial qualification was source and local-live evidence. Railway
deployment `345e7ebe-239e-4d1d-8287-4f4e71363d79` now reports success at
0.9.2 source `27dccb4`, with the 10:00 Asia/Kolkata schedule and persistent
volume retained. It has not yet performed an Openverse-to-Supabase read-back
or a natural daily acceptance. The existing Flickr plan stays authoritative
until that live source is verified in StickerDock.

## 0.9.2 repeated-topic paging

The [Openverse API](https://api.openverse.org/v1/) documents bounded anonymous
pagination. Version 0.9.2 requests up to five 20-result pages, stops when it
has enough fresh candidates, and does not follow arbitrary next-page URLs.
The worker retains its source and pixel duplicate checks. A focused test covers
a complete first page of previously collected sources followed by fresh page
two results. Source-bound CI passed [37 core](https://github.com/dvajjala-ui/handNavigation/actions/runs/40927080401),
[37 worker](https://github.com/dvajjala-ui/handNavigation/actions/runs/40927079344),
and [bounded container](https://github.com/dvajjala-ui/handNavigation/actions/runs/40927079288)
checks. Hosted Openverse storage read-back remains pending.

## 0.9.3 strict license keys

Only explicit `cc0` and `pdm` keys are accepted. A forged `constructor`
license without a URL no longer inherits a JavaScript object property and
enters the candidate queue. The focused regression test and 37 worker tests
pass. Railway deployment `48bb09af-d854-4c0f-92a0-17d7de7299af` reports
success at source `0189803`; hosted Openverse read-back is still pending.
