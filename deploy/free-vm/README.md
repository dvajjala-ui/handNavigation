# Remote Pinterest runner — 5 November 2026

Current target: twenty decoded Pinterest images in a folder on a remote host. After guest access failed, the user allowed a one-time manual Pinterest login and a browser-only 1 GB VM trial. Instagram and uploads are excluded. No Pinterest task runs on the user's laptop.

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

## Actual remote result

The Windows-hosted [search trial](https://github.com/dvajjala-ui/handNavigation/actions/runs/42010439198) and [public travel-board trial](https://github.com/dvajjala-ui/handNavigation/actions/runs/42011610291) both returned `ACCESS_REQUIRED`, **0/20 images**, with a visible login form and gated image placeholders. No Pinterest task ran on the user's laptop. No login gate was removed. A different host may behave differently, but this does not establish working guest Pinterest access.

The [x64 and Arm Docker checks](https://github.com/dvajjala-ui/handNavigation/actions/runs/42009765486) successfully built the image and started its browser as an unprivileged user. These are container/browser startup checks, not a deployed Oracle VM or successful Pinterest collection. The remote [machine-readable diagnosis](../../windows-agent/evidence/remote-pinterest.json) records the exact board URL and observed outcome.

## Run on a provisioned Linux VM

This Docker deployment is a remote browser worker; Windows remains the desktop-app target. Run from the repository root on the remote VM:

```sh
docker build -f deploy/free-vm/Dockerfile -t handnavigate-pinterest .
mkdir -p "$HOME/handnavigate-results"
# Match the remote host user's UID/GID for the new bind-mounted result folder.
docker run --rm --user "$(id -u):$(id -g)" --shm-size=1g -v "$HOME/handnavigate-results:/data" handnavigate-pinterest \
  --topic "nature landscape" --count 20 --output /data/pinterest-2026-11-05
```

To test an exact public board instead of search, add `--page-url "https://www.pinterest.com/lonelyplanet/mountain-travel-best-places-to-visit/"`. This is the board that returned the login gate above. The collector admits only exact Pinterest HTTPS hosts for this option; it excludes hidden and gated image elements.

The command runs as the remote host user's UID/GID so its newly created data folder stays writable without opening permissions to everyone. The image's default user is unprivileged UID 10001 when no override is supplied. Each run needs a new empty output directory. The result folder contains `pictures/`, `result.json` and a public-page diagnostic screenshot. Browser runtime data is separate and should not be shared. The repository's `.dockerignore` excludes local models, browser sessions, credentials, build output and dependencies from the Docker build context.

Daily cron/systemd operation should be enabled only after that host returns `VERIFIED` with 20/20 images. A repeated identical source can exhaust fresh results; the current acceptance is one batch and does not establish multi-day fresh-image delivery. A date-stamped output path prevents overwriting earlier batches.

## Current Oracle deployment

The signed-in Free Tier tenancy was inspected in Mumbai. The root compartment had no instances, boot volumes or block volumes. A 2 OCPU / 12 GB A1 request failed with `Out of capacity`. After the user explicitly selected the smaller trial, an Always Free `VM.Standard.E2.1.Micro` with Ubuntu 24.04 Minimal and a default 46.6 GB boot disk was created and reached `Running`. SSH access was verified using a new key stored outside the repository. Its existing network permits SSH from the deployment workstation's exact IPv4 address only; the outbound internet route and rules were already present.

This VM is for the Pinterest browser trial. Its 952 MiB usable RAM is insufficient for the recommended 4B Ollama model. No model is installed there. [bootstrap-browser.sh](bootstrap-browser.sh) installs the browser dependencies and a 2 GiB swap file inside the free boot disk. It does not activate recurring tasks.

**Actual signed-in result: VERIFIED, 20/20 images in 103.19 seconds.** All twenty files were independently reopened and decoded on the VM, matched to the manifest and checked for distinct SHA-256 hashes. The folder is `/home/ubuntu/pinterest-results/2026-11-05-manual-01/pictures`. Total size: 593,886 bytes. They are advertised board previews, 236 pixels wide, not original-resolution downloads. [Sanitized evidence](../../windows-agent/evidence/oracle-pinterest.json). Images, the signed-in page screenshot, cookies and browser profile stayed on the VM.

The application is running as the persistent user service `handnavigate-browser.service`, with linger enabled so it survives SSH disconnect. Its setup and saved browser session are on the VM. The UI listens only on `127.0.0.1:47841`; reach it through an SSH tunnel, not an open public app port. No real recurring task is enabled, and the local-model planning button needs a larger host with Ollama. Structured plans and browser tasks remain available.

## One-time manual sign-in on the VM

Run on the selected Ubuntu VM, from the repository root:

```sh
systemctl --user stop handnavigate-browser.service
HANDNAVIGATE_REMOTE_RUNNER=1 windows-agent/.venv/bin/python windows-agent/tools/remote_login.py \
  --data /home/ubuntu/handnavigate-data
```

The helper starts a temporary display, VNC and noVNC bound only to remote loopback. From your own machine, forward the port over SSH:

```sh
ssh -N -i /path/to/private-key -L 127.0.0.1:6080:127.0.0.1:6080 ubuntu@VM_IP
```

Open `http://127.0.0.1:6080/vnc.html` and sign in yourself. The helper stores the session only in the VM's dedicated browser profile; it does not record passwords or send credentials to a model. Stop the helper cleanly after sign-in (SIGTERM), or let its 20-minute deadline expire. Then collect using that saved profile:

```sh
HANDNAVIGATE_REMOTE_RUNNER=1 windows-agent/.venv/bin/python windows-agent/tools/collect_pinterest.py \
  --channel "" --profile-data /home/ubuntu/handnavigate-data \
  --page-url "https://www.pinterest.com/lonelyplanet/mountain-travel-best-places-to-visit/" \
  --count 20 --output /home/ubuntu/pinterest-results/first-signed-in-run
```

The profile lock prevents a sign-in browser and collector from owning the session together. The output folder must be new and empty. One displayed image contributes one candidate URL, so srcset resolutions cannot inflate the requested count. The final manifest independently decodes files and verifies hashes and the exact count. Gated/hidden images remain excluded, even with a saved profile.

After manual sign-in/collection, restart the persistent worker with `systemctl --user start handnavigate-browser.service`. The [service unit](handnavigate-browser.service) uses the same data folder and unprivileged account. For the application UI, forward `127.0.0.1:47841:127.0.0.1:47841` with SSH and open `http://127.0.0.1:47841` locally. The tunnel needs a connected client only while using the UI; the remote service itself continues independently.

To install that service on a newly prepared VM, run from the repository root:

```sh
mkdir -p "$HOME/.config/systemd/user"
cp deploy/free-vm/handnavigate-browser.service "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now handnavigate-browser.service
sudo loginctl enable-linger "$USER"
```

Never commit or upload the VM's `handnavigate-data`, SSH private keys, browser profiles or cookies. The daily schedule remains disabled until the actual source passes. Windows-only always-on hosting is not claimed to be perpetually free.
