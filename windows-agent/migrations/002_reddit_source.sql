-- Add the Reddit source columns. Apply after 001_collections.sql.
begin;

alter table public.collection_topics add column if not exists reddit_url text;
alter table public.collection_topics add column if not exists reddit_verified boolean not null default false;

-- The seeded subreddits become exact, checkable start pages. A topic only becomes
-- collectable on Reddit after a signed-in run on this URL is imported.
update public.collection_topics
  set reddit_url='https://www.reddit.com/r/'||reddit_subreddit||'/top/?t=month'
  where reddit_url is null or reddit_url='';

alter table public.collection_topics alter column reddit_url set not null;

commit;
