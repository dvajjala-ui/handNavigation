# Hosted collection hardening — October 28, 2026

The outbound claim advertises only installed source recipes, fixing compatibility
with StickerDock's Imgflip-aware queue. Docker Compose enables queue polling.

Chromium CDP request-stage interception checks every navigation redirect hop;
service workers are disabled. A regression verifies zero requests reach an
unapproved local target and that same-origin redirects continue to work.

Guest galleries can contain optional login UI without blocking available public
images. Real challenges and gated media remain blocked; access restrictions are
reported rather than bypassed. The worker does not require a Pinterest/Reddit API
account. A free account and an anonymous browser are different access contexts;
public availability from a user's PC does not guarantee datacenter-IP access.

StickerDock's scheduled GitHub Actions worker checks out an immutable revision,
restores a private dedup/retry journal, performs actual collections and verifies
storage. It excludes profiles/credentials from checkpoints. This deployment is
owned by StickerDock's handnavigate-intake workflow, not the desktop application.

Local verification: 36 desktop unit tests and 16 service tests pass. Worker CI
passes, as do Windows desktop/build/portable checks for browser revision b6bc66a.
The VM image/private console/headful Chromium check passes at
https://github.com/dvajjala-ui/handNavigation/actions/runs/40656090500.

Actual hosted collection stored two Imgflip images in Supabase. Pinterest and
Reddit reported guest restrictions; this does not prove their unattended use.
The visual console permits a real human check where the source allows one.
