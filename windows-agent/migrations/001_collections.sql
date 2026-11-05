-- HandNavigate private image library. Apply with the configured Postgres connection.
begin;

create table if not exists public.collection_topics (
  key text primary key check (key ~ '^[a-z][a-z0-9_]{1,39}$'),
  label text not null,
  pinterest_url text not null,
  reddit_subreddit text not null,
  pinterest_verified boolean not null default false,
  enabled boolean not null default true
);

-- Sources start unverified. A topic becomes collectable only after
-- tools/import_collection.py accepts a real signed-in run for that source's exact URL.
insert into public.collection_topics (key,label,pinterest_url,reddit_subreddit) values
 ('travel','Travel','https://in.pinterest.com/lonelyplanet/mountain-travel-best-places-to-visit/','travel'),
 ('nature','Nature','https://in.pinterest.com/search/pins/?q=nature%20landscape','EarthPorn'),
 ('animals','Animals','https://in.pinterest.com/search/pins/?q=wildlife%20photography','aww'),
 ('art','Art','https://in.pinterest.com/search/pins/?q=digital%20art','Art'),
 ('food','Food','https://in.pinterest.com/search/pins/?q=food%20photography','FoodPorn'),
 ('architecture','Architecture','https://in.pinterest.com/search/pins/?q=architecture%20photography','ArchitecturePorn')
on conflict (key) do nothing;

create table if not exists public.collection_jobs (
  id uuid primary key default gen_random_uuid(),
  name text not null check (length(name) between 1 and 120),
  source text not null check (source in ('pinterest','reddit')),
  topic_key text references public.collection_topics(key),
  random_topic boolean not null default false,
  image_count integer not null check (image_count between 1 and 20),
  daily_time time without time zone not null,
  timezone text not null default 'Asia/Kolkata',
  enabled boolean not null default false,
  created_at timestamptz not null default now(),
  check ((random_topic and topic_key is null) or (not random_topic and topic_key is not null))
);

create table if not exists public.collection_runs (
  id uuid primary key default gen_random_uuid(),
  job_id uuid references public.collection_jobs(id),
  scheduled_date date,
  source text not null check (source in ('pinterest','reddit')),
  topic_key text not null references public.collection_topics(key),
  requested integer not null check (requested between 1 and 20),
  downloaded integer not null default 0,
  stored integer not null default 0,
  status text not null check (status in ('RUNNING','VERIFIED','PARTIAL','HALTED','NEEDS_REVIEW')),
  error text,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  unique(job_id,scheduled_date)
);

create table if not exists public.collected_images (
  id uuid primary key default gen_random_uuid(),
  run_id uuid references public.collection_runs(id),
  source text not null check (source in ('pinterest','reddit')),
  topic_key text not null references public.collection_topics(key),
  source_page_url text not null,
  source_image_url text not null,
  source_post_id text,
  storage_bucket text not null default 'handnavigate-images' check (storage_bucket='handnavigate-images'),
  storage_path text not null unique,
  sha256 text not null unique check (sha256 ~ '^[0-9a-f]{64}$'),
  mime_type text not null check (mime_type in ('image/jpeg','image/png','image/webp')),
  width integer not null check (width >= 128),
  height integer not null check (height >= 128),
  byte_count integer not null check (byte_count between 1 and 26214400),
  rendition text not null default 'preview' check (rendition in ('preview','original')),
  rights_status text not null default 'reference_only' check (rights_status in ('reference_only','licensed','owned')),
  collected_at timestamptz not null default now()
);

create index if not exists collected_images_filter_idx on public.collected_images(topic_key,source,collected_at desc);
create index if not exists collection_runs_started_idx on public.collection_runs(started_at desc);

alter table public.collection_topics enable row level security;
alter table public.collection_jobs enable row level security;
alter table public.collection_runs enable row level security;
alter table public.collected_images enable row level security;
revoke all on public.collection_topics, public.collection_jobs, public.collection_runs, public.collected_images from anon, authenticated;
-- The loopback worker uses Postgres credentials; no browser or anonymous write policy.
commit;
