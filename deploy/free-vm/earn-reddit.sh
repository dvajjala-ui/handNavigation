#!/usr/bin/env bash
# Earn Reddit content topics on the VM using the user's own saved sign-in.
# One batch per subreddit; only a VERIFIED batch is imported, and the import tool
# refuses a result whose page is not that topic's configured Reddit URL, so a
# topic cannot become collectable on the strength of a lookalike page.
# A sign-in wall or network block is reported and left unimported: nothing here
# types a credential, answers a challenge or substitutes another source.
set -u
cd "$HOME/handnavigate" || exit 1
PY=windows-agent/.venv/bin/python
DATA=/home/ubuntu/handnavigate-data
COUNT=${COUNT:-20}

# The persistent worker owns the saved browser profile while a task runs.
systemctl --user stop handnavigate-browser.service
sleep 3

while IFS='|' read -r key sub url; do
  [ -z "$key" ] && continue
  out="/home/ubuntu/reddit-results/earn-$key-$(date +%Y%m%d-%H%M)"
  rm -rf "$out"
  echo "=== COLLECT $key -> $out"
  HANDNAVIGATE_REMOTE_RUNNER=1 $PY windows-agent/tools/collect_reddit.py \
    --channel "" --profile-data "$DATA" --page-url "$url" \
    --count "$COUNT" --output "$out" 2>&1 | tail -14
  echo "=== IMPORT $key"
  if grep -q '"status": "VERIFIED"' "$out/result.json"; then
    HANDNAVIGATE_REMOTE_RUNNER=1 $PY windows-agent/tools/import_collection.py \
      --source reddit --result "$out/result.json" --topic "$key" 2>&1 | tail -2
  else
    echo "Not imported. Batch status: $(grep -m1 '"status"' "$out/result.json" 2>/dev/null || echo 'no manifest')"
  fi
done <<'TOPICS'
animals|aww|https://www.reddit.com/r/aww/top/?t=month
architecture|ArchitecturePorn|https://www.reddit.com/r/ArchitecturePorn/top/?t=month
art|Art|https://www.reddit.com/r/Art/top/?t=month
food|FoodPorn|https://www.reddit.com/r/FoodPorn/top/?t=month
nature|EarthPorn|https://www.reddit.com/r/EarthPorn/top/?t=month
travel|travel|https://www.reddit.com/r/travel/top/?t=month
TOPICS

systemctl --user start handnavigate-browser.service
sleep 4
echo "=== SERVICE AFTER BATCH: $(systemctl --user is-active handnavigate-browser.service)"
FINAL=/tmp/earn-reddit-final.py
printf '%s\n' \
 "import sys; sys.path[:0]=['windows-agent','.']" \
 "from core.collections import CollectionDB" \
 "db=CollectionDB()" \
 "with db.connect() as c:" \
 "    for r in c.execute('select key, pinterest_verified, reddit_verified, reddit_url from public.collection_topics order by key'):" \
 "        print('topic', r['key'], 'pinterest=', r['pinterest_verified'], 'reddit=', r['reddit_verified'], r['reddit_url'])" \
 "    print('images', c.execute('select count(*) n from public.collected_images').fetchone()['n'])" \
 "    for r in c.execute('select source, topic_key, count(*) n from public.collected_images group by 1,2 order by 1,2'):" \
 "        print('library', r['source'], r['topic_key'], r['n'])" \
 "    for r in c.execute('select name, source, enabled, daily_time, image_count, random_topic from public.collection_jobs'):" \
 "        print('job', dict(r))" \
 > "$FINAL"
$PY "$FINAL"
