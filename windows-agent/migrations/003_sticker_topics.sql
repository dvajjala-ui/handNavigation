-- Sticker-worthy topics for StickerDock v2, which reads this library from the same Supabase project.
-- Apply after 002. Idempotent, because CollectionDB.migrate() re-runs every file.
-- Like every topic, these start unverified: a source becomes collectable for a topic only after a real signed-in run
-- on exactly this URL is imported (deploy/free-vm/earn-topics.sh, earn-reddit.sh).
begin;

insert into public.collection_topics (key,label,pinterest_url,reddit_subreddit,reddit_url) values
 ('memes','Memes','https://in.pinterest.com/search/pins/?q=funny%20memes','memes',
  'https://www.reddit.com/r/memes/top/?t=month'),
 ('indian_memes','Indian memes','https://in.pinterest.com/search/pins/?q=indian%20memes','IndianMeyMeys',
  'https://www.reddit.com/r/IndianMeyMeys/top/?t=month'),
 ('hinglish_memes','Hinglish memes','https://in.pinterest.com/search/pins/?q=hinglish%20memes','dankinindia',
  'https://www.reddit.com/r/dankinindia/top/?t=month'),
 ('reaction_memes','Reaction memes','https://in.pinterest.com/search/pins/?q=reaction%20memes','reactionpics',
  'https://www.reddit.com/r/reactionpics/top/?t=month'),
 ('bollywood_memes','Bollywood memes','https://in.pinterest.com/search/pins/?q=bollywood%20memes','BollywoodMemes',
  'https://www.reddit.com/r/BollywoodMemes/top/?t=month'),
 ('funny_animals','Funny animals','https://in.pinterest.com/search/pins/?q=funny%20animals','AnimalsBeingDerps',
  'https://www.reddit.com/r/AnimalsBeingDerps/top/?t=month')
on conflict (key) do nothing;

commit;
