"""Read-only check of the Supabase image library: tables, bucket privacy and stored objects."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT.parent)]

from core.collections import BUCKET, CollectionDB  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", help="Write a sanitized machine-readable report to this path.")
    args = parser.parse_args()
    report = {"checked_at": datetime.now(timezone.utc).isoformat()}

    db = CollectionDB()
    with db.connect() as conn:
        tables = {}
        for name in ("collection_topics", "collection_jobs", "collection_runs", "collected_images"):
            tables[name] = conn.execute(f"select count(*) as n from public.{name}").fetchone()["n"]
        print("rows:", json.dumps(tables))
        report["row_counts"] = tables

        images = conn.execute(
            "select source, topic_key, rendition, count(*) as n, sum(byte_count) as bytes "
            "from public.collected_images group by 1,2,3 order by 1,2"
        ).fetchall()
        print("library:")
        for row in images:
            print(f"  {row['source']}/{row['topic_key']} [{row['rendition']}] "
                  f"{row['n']} images, {row['bytes']} bytes")
        report["library"] = [{k: str(v) for k, v in row.items()} for row in images]

        runs = conn.execute(
            "select source, topic_key, status, requested, downloaded, stored, scheduled_date, "
            "to_char(started_at, 'YYYY-MM-DD HH24:MI') as started, left(coalesce(error,''), 90) as error "
            "from public.collection_runs order by started_at desc limit 10"
        ).fetchall()
        print("runs:")
        for row in runs:
            print(f"  {row['started']}  {row['source']}/{row['topic_key']}  {row['status']}  "
                  f"{row['stored']}/{row['requested']} stored{(' | ' + row['error']) if row['error'] else ''}")
        report["runs"] = [{k: str(v) if v is not None else None for k, v in row.items()} for row in runs]

        jobs = conn.execute(
            "select name, source, coalesce(topic_key,'<random>') as topic, random_topic, image_count, "
            "to_char(daily_time,'HH24:MI') as at, timezone, enabled from public.collection_jobs order by created_at desc"
        ).fetchall()
        print("jobs:")
        for row in jobs:
            print(f"  [{row['source']}/{row['topic']}] {row['name']} - {row['image_count']} daily at "
                  f"{row['at']} {row['timezone']} enabled={row['enabled']}")
        report["jobs"] = [{k: str(v) for k, v in row.items()} for row in jobs]

        topics = conn.execute(
            "select key, label, pinterest_verified, enabled from public.collection_topics order by key"
        ).fetchall()
        print("topics:", ", ".join(f"{t['key']}=verified:{t['pinterest_verified']}/on:{t['enabled']}" for t in topics))
        report["topics"] = [{k: str(v) for k, v in row.items()} for row in topics]

        secured = conn.execute(
            "select relname, relrowsecurity from pg_class where relname in "
            "('collection_topics','collection_jobs','collection_runs','collected_images')"
        ).fetchall()
        print("row-level security:", json.dumps({r["relname"]: r["relrowsecurity"] for r in secured}))
        grants = conn.execute(
            "select privilege_type, grantee from information_schema.role_table_grants "
            "where table_schema='public' and table_name='collected_images' and grantee in ('anon','authenticated')"
        ).fetchall()
        print("anon/authenticated grants on collected_images:", grants or "none")
        report["row_level_security"] = {r["relname"]: r["relrowsecurity"] for r in secured}
        report["anon_or_authenticated_grants"] = [dict(g) for g in grants]

    _, bucket = db.storage("GET", "bucket/" + BUCKET)
    meta = json.loads(bucket)
    print(f"bucket: {meta['id']} public={meta.get('public')} limit={meta.get('file_size_limit')} "
          f"mime={meta.get('allowed_mime_types')}")
    report["bucket"] = {"id": meta["id"], "public": meta.get("public"),
                        "file_size_limit": meta.get("file_size_limit"),
                        "allowed_mime_types": meta.get("allowed_mime_types")}

    _, listed = db.storage("POST", f"object/list/{BUCKET}", json.dumps({"prefix": "", "limit": 1000}).encode(),
                           "application/json")
    objects = json.loads(listed)
    print("storage top-level entries:", json.dumps([o.get("name") for o in objects]))
    report["storage_top_level"] = [o.get("name") for o in objects]

    print("\nfull read-back (every stored row, sha-256 verified):")
    with db.connect() as conn:
        rows = conn.execute("select id, byte_count from public.collected_images order by collected_at").fetchall()
    verified = 0
    for row in rows:
        data, _mime = db.image_bytes(str(row["id"]))
        if len(data) != row["byte_count"]:
            raise SystemExit(f"length mismatch for {row['id']}: bucket={len(data)} db={row['byte_count']}")
        verified += 1
    print(f"  {verified}/{len(rows)} objects downloaded from the private bucket and matched "
          "their recorded hash and size")
    report["read_back_verified"] = verified
    report["read_back_expected"] = len(rows)

    if args.json:
        target = Path(args.json)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        print(f"wrote {target}")


if __name__ == "__main__":
    main()
