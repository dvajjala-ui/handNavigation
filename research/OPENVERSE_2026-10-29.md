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

This is source and local-live evidence. It is not yet a Railway deployment or a
natural scheduled-run acceptance. The existing Flickr plan stays authoritative
until the compatible hosted worker is deployed and Openverse storage read-back
is checked in StickerDock.
