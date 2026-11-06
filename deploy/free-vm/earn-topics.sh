#!/usr/bin/env bash
# Earn the not-yet-verified Pinterest topics on the VM: one signed-in 20-image
# batch per topic, imported only if that batch verifies. The import tool refuses
# a result whose URL is not the topic's configured source, so this cannot mark a
# topic collectable on the strength of a lookalike page.
set -u
cd "$HOME/handnavigate" || exit 1
PY=windows-agent/.venv/bin/python
DATA=/home/ubuntu/handnavigate-data

# Topics still to earn come from the database (enabled, Pinterest not yet verified), so a topic added by a
# migration (e.g. 003_sticker_topics.sql) needs no edit here. Optional arguments limit the run to those keys:
#   deploy/free-vm/earn-topics.sh memes indian_memes
TOPICS=$(HANDNAVIGATE_REMOTE_RUNNER=1 $PY - <<'PY'
import sys; sys.path[:0] = ['windows-agent', '.']
from core.collections import CollectionDB
with CollectionDB().connect() as c:
    for r in c.execute("select key, label, pinterest_url from public.collection_topics "
                       "where enabled and not pinterest_verified order by key"):
        print(r['key'] + '|' + r['label'] + '|' + r['pinterest_url'])
PY
)
if [ -z "$TOPICS" ]; then echo "=== every enabled topic is already verified on Pinterest"; exit 0; fi

# The persistent worker owns the saved browser profile while a task runs.
systemctl --user stop handnavigate-browser.service
sleep 3

while IFS='|' read -r key label url; do
  [ -z "$key" ] && continue
  if [ "$#" -gt 0 ] && ! printf '%s\n' "$@" | grep -qx "$key"; then continue; fi
  out="/home/ubuntu/pinterest-results/earn-$key-$(date +%Y%m%d-%H%M)"
  rm -rf "$out"
  echo "=== COLLECT $key -> $out"
  HANDNAVIGATE_REMOTE_RUNNER=1 $PY windows-agent/tools/collect_pinterest.py \
    --channel "" --profile-data "$DATA" --topic "$label" --page-url "$url" \
    --count 20 --output "$out" 2>&1 | tail -3
  echo "=== IMPORT $key"
  HANDNAVIGATE_REMOTE_RUNNER=1 $PY windows-agent/tools/import_collection.py \
    --source pinterest --result "$out/result.json" --topic "$key" 2>&1 | tail -2
done <<< "$TOPICS"

systemctl --user start handnavigate-browser.service
sleep 4
echo "=== SERVICE AFTER BATCH: $(systemctl --user is-active handnavigate-browser.service)"
FINAL=/tmp/earn-topics-final.py
printf '%s\n' \
 "import sys; sys.path[:0]=['windows-agent','.']" \
 "from core.collections import CollectionDB" \
 "db=CollectionDB()" \
 "with db.connect() as c:" \
 "    for r in c.execute('select key, pinterest_verified from public.collection_topics order by key'):" \
 "        print('topic', r['key'], 'verified=', r['pinterest_verified'])" \
 "    print('images', c.execute('select count(*) n from public.collected_images').fetchone()['n'])" \
 "    for r in c.execute('select topic_key, count(*) n, sum(byte_count) b from public.collected_images group by 1 order by 1'):" \
 "        print('library', r['topic_key'], r['n'], r['b'])" \
 "    print('job', dict(c.execute('select name, enabled, daily_time, image_count from public.collection_jobs').fetchone()))" \
 > "$FINAL"
$PY "$FINAL"
