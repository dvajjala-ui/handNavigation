# Remote Pinterest runner — 5 November 2026

Current target: guest Pinterest, twenty decoded images in a folder on a remote host. Instagram and uploads are excluded from this acceptance target. No local-computer Pinterest collection is required.

## Free hosting findings

| Option | Fit | Boundaries |
| --- | --- | --- |
| GitHub standard hosted Windows runner, public repository | Already available for a bounded software acceptance test | Free compute for public standard runners; a temporary test VM, not an always-on personal automation server. This repo's workflow is an acceptance test, not a perpetual image service. |
| Oracle Always Free A1 | Best candidate for a persistent free browser/model worker | Currently 2 Arm OCPUs, 12 GB RAM and 200 GB shared boot/block storage within the free limits. Linux, not Windows; home-region capacity/account eligibility and idle reclamation matter. A tenancy must be available before deployment. |
| Google Compute Engine free e2-micro | Small persistent Linux jobs | Resource allowance is too small for the proposed browser plus 4B model combination; Windows/image/network charges must not be assumed covered. |
| Hugging Face Spaces | Demonstrations | Current documentation requires a paid plan to create compute Spaces and free hardware sleeps. It does not meet a dependable free unattended daily-run requirement. |

Sources checked on 5 November:

- [GitHub runner billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions), [Actions permitted use](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features#actions).
- [Oracle Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm): capacity, 2 OCPU/12 GB, storage and idle reclamation.
- [Google free tier](https://cloud.google.com/free/docs/free-cloud-features).
- [Spaces resources and lifecycle](https://huggingface.co/docs/hub/spaces-overview).

No free provider guarantees access to every website. Cloud-IP blocks, sign-in requirements and human checks must be tested on the chosen host. The collector stops and reports incomplete results; it does not bypass those gates or replace Pinterest with another image source.

## Run on a provisioned Linux VM

This Docker deployment is a remote browser worker; Windows remains the desktop-app target. Run from the repository root on the remote VM:

```sh
docker build -f deploy/free-vm/Dockerfile -t handnavigate-pinterest .
mkdir -p "$HOME/handnavigate-results"
# Match the remote host user's UID/GID for the new bind-mounted result folder.
docker run --rm --user "$(id -u):$(id -g)" --shm-size=1g -v "$HOME/handnavigate-results:/data" handnavigate-pinterest \
  --topic "nature landscape" --count 20 --output /data/pinterest-2026-11-05
```

The command runs as the remote host user's UID/GID so its newly created data folder stays writable without opening permissions to everyone. The image's default user is unprivileged UID 10001 when no override is supplied. Each run needs a new empty output directory. The result folder contains `pictures/`, `result.json` and a public-page diagnostic screenshot. Browser runtime data is separate and should not be shared. The repository's `.dockerignore` excludes local models, browser sessions, credentials, build output and dependencies from the Docker build context.

Daily cron/systemd operation should be enabled only after that host returns `VERIFIED` with 20/20 images. A repeated identical source can exhaust fresh results; the current acceptance is one batch and does not establish multi-day fresh-image delivery. A date-stamped output path prevents overwriting earlier batches.

An Oracle account/tenancy, region and SSH access are required to provision or deploy there. No account, paid upgrade, VM purchase or public remote-control endpoint was created by this preparation. Windows-only always-on hosting is not claimed to be perpetually free.
