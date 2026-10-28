#!/bin/sh
set -eu
umask 077
# Railway mounts a new persistent volume as root. Only the data root needs
# ownership preparation; the browser and collector run as the unprivileged user.
install -d -m 0700 -o pwuser -g pwuser /data
exec runuser -u pwuser -- timeout --signal=TERM --kill-after=30s 28m xvfb-run -a -s '-screen 0 1360x900x24 -nolisten tcp' node /app/service/batch.cjs
