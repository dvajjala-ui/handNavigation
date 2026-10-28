# Persistent worker with an interactive browser

Target: one Ubuntu 24.04 x86-64 VM, initially 2 vCPU / 4 GB RAM, at least 40 GB
persistent disk. Sizing is an initial engineering estimate. Account/billing,
server creation and source access still require qualification on the chosen host.

The VM polls StickerDock outbound, so no public application, VNC or browser-debug
port is needed. Docker preserves profiles, originals, retry state and duplicate
history in a named volume. Processes restart automatically after failure/reboot.
This adds a private visual console for genuine human sign-in/checks, not challenge
bypass. Anonymous browsing remains the first attempt.

1. Install Docker Engine and the Compose plugin on the new VM following Docker's
   official Ubuntu instructions. Clone this repository at the reviewed revision.
2. Copy `worker.env.example` to `worker.env` in this directory and set its existing
   server-only ingest credential locally on the VM. Use `chmod 600 worker.env`.
   Do not send the credential in chat, commit it or place it in browser JavaScript.
3. Start `docker compose -f deploy/vm/compose.yaml up -d --build` from the repository.
4. Keep ports 47832, 5900 and 6080 closed in the cloud firewall. The compose file
   binds its published endpoints only to host loopback. Use SSH-key access.
5. Open a private console tunnel from your computer:

   `ssh -N -L 6080:127.0.0.1:6080 USER@SERVER`

   Then visit `http://127.0.0.1:6080/vnc.html`. The console has no separate password
   because it is accessible only through the authenticated SSH tunnel. Never
   change its host binding to a public address. Provider web consoles usually
   supply terminals; they are not a substitute for this graphical browser.
6. Collect two real images per source, inspect per-source status and Supabase
   read-back, then verify restart/resume and a normal daily run. A free signed-in
   browser session may help only where the source permits it. A new VM/network
   cannot guarantee guest access, and restrictions must not be bypassed.
7. Retire the old active worker only after the new host is qualified. If the VM
   becomes the worker, change StickerDock's daily action back to enqueue-only so
   the GitHub worker and VM do not unexpectedly split jobs across different site
   access contexts. They share expiring exclusive cloud leases.

Do not run `docker compose down -v`: that would remove the persistent library and
profiles. Normal upgrades use `up -d --build`, retain the volume, and wait for an
active collection to finish before stopping it.
