#!/usr/bin/env bash
# Earn the remaining Pinterest content topics on the VM: one signed-in 20-image
# batch per topic, imported only if that batch verifies. The import tool refuses
# a result whose URL is not the topic's configured source, so this cannot mark a
# topic collectable on the strength of a lookalike page.
set -u
cd "$HOME/handnavigate" || exit 1
PY=windows-agent/.venv/bin/python
DATA=/home/ubuntu/handnavigate-data

# The persistent worker owns the saved browser profile while a task runs.
systemctl --user stop handnavigate-browser.service
sleep 3

while IFS='|' read -r key label url; do
  [ -z "$key" ] && continue
  out="/home/ubuntu/pinterest-results/earn-$key-$(date +%Y%m%d-%H%M)"
  rm -rf "$out"
  echo "=== COLLECT $key -> $out"
  HANDNAVIGATE_REMOTE_RUNNER=1 $PY windows-agent/tools/collect_pinterest.py \
    --channel "" --profile-data "$DATA" --topic "$label" --page-url "$url" \
    --count 20 --output "$out" 2>&1 | tail -3
  echo "=== IMPORT $key"
  HANDNAVIGATE_REMOTE_RUNNER=1 $PY windows-agent/tools/import_pinterest_collection.py \
    --result "$out/result.json" --topic "$key" 2>&1 | tail -2
done <<'TOPICS'
animals|wildlife photography|https://in.pinterest.com/search/pins/?q=wildlife%20photography
art|digital art|https://in.pinterest.com/search/pins/?q=digital%20art
food|food photography|https://in.pinterest.com/search/pins/?q=food%20photography
architecture|architecture photography|https://in.pinterest.com/search/pins/?q=architecture%20photography
TOPICS

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
