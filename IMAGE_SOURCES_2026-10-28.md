# Source qualification — 28 October 2026

| Source | Delivered behavior | Qualification |
| --- | --- | --- |
| Pinterest | Topic search, bounded pagination, own saved browser session, static image downloads | 20 images fetched back from production Supabase |
| Reddit | Media search, source-post provenance, saved session, documented image hosts | Four images fetched back from production Supabase |
| Imgflip | Read-only popular meme-template catalog, name filtering and shared Runner validation/dedup | Two distinct templates fetched back from production Supabase |

Imgflip's [official API](https://imgflip.com/api) documents a free `GET /get_memes` catalog and separate paid full-catalog search/generation operations. The live catalog returned100 entries at qualification time. HandNavigate locally filters names, reads only advertised static URLs on `i.imgflip.com`, records template provenance and never calls paid endpoints. The catalog is finite: a narrow topic can yield few or no unused matches, so select another source too when a larger daily count is needed. An initial two-Drake-template test correctly saved only one because similarity filtering recognized the near duplicate; a two-topic check (`Distracted`, `Cat`) saved two distinct images. [Local proof](service/evidence/imgflip-local-20261028.json), [production proof](service/evidence/cloud-live-0795c1cf-b839-4d91-8f2f-1928694bbc51.json).

Bluesky's [official API routing documentation](https://bsky.network/docs/api-directory/) supports public AppView reads, but its search endpoint returned HTTP403 HTML from this host on qualification. It is **not enabled** or claimed to work here. No challenge or access restriction was bypassed.

Commons, news/blog pictures and Openverse are not fallback sources for this collection workflow. Existing Pinterest OAuth remains reference-only. Access to public media and successful technical download tests do not themselves establish reuse permissions; candidates stay outside generation until separately reviewed/admitted.

To add a future source, provide a reviewed recipe/adapter, allowed hosts, stable provenance, count/pagination behavior and actual download tests. Arbitrary URLs or scripts from a model are not accepted as worker source IDs.
