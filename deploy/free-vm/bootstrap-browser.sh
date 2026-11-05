#!/usr/bin/env bash
# Run as the SSH user on the chosen Ubuntu VM. Browser-only: no model installation.
set -euo pipefail
if [ "${HANDNAVIGATE_REMOTE_RUNNER:-}" != 1 ]; then
  printf '%s\n' 'Set HANDNAVIGATE_REMOTE_RUNNER=1 on the chosen VM.' >&2
  exit 2
fi
sudo install -d -m 700 /var/swap
if [ ! -f /var/swap/handnavigate.swap ]; then
  sudo fallocate -l 2G /var/swap/handnavigate.swap
  sudo chmod 600 /var/swap/handnavigate.swap
  sudo mkswap /var/swap/handnavigate.swap
fi
if ! swapon --show=NAME --noheadings | grep -Fxq /var/swap/handnavigate.swap; then
  sudo swapon /var/swap/handnavigate.swap
fi
if ! grep -Fq '/var/swap/handnavigate.swap ' /etc/fstab; then
  printf '%s\n' '/var/swap/handnavigate.swap none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv git xvfb x11vnc novnc websockify xauth
if [ ! -d "$HOME/handnavigate/.git" ]; then
  git clone --depth 1 https://github.com/dvajjala-ui/handNavigation.git "$HOME/handnavigate"
fi
cd "$HOME/handnavigate"
python3 -m venv windows-agent/.venv
windows-agent/.venv/bin/python -m pip install -r windows-agent/requirements.txt
windows-agent/.venv/bin/python -m playwright install --with-deps chromium
printf '%s\n' 'Browser runtime ready. No model or recurring task was installed.'
