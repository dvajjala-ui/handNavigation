-- More sticker topics for StickerDock v2 (6 November owner request): memes, adult humour, movies/series/songs,
-- girls/boys/bro-code/love memes, and GIF topics. Apply after 003. Idempotent (CollectionDB.migrate() re-runs it).
-- Like every topic these start unverified: a source becomes collectable only after a real signed-in run on exactly
-- this URL is imported (deploy/free-vm/earn-topics.sh). Subreddit names are checked by that first run; one that
-- does not exist simply never earns verification.
-- "(18+)" topics feed StickerDock's adult lane: adult humour on non-explicit images. StickerDock's worker rejects
-- sexually explicit images and anything involving minors, so no porn topics are seeded.
begin;

insert into public.collection_topics (key,label,pinterest_url,reddit_subreddit,reddit_url) values
 ('dank_memes','Dank memes','https://in.pinterest.com/search/pins/?q=dank%20memes','dankmemes',
  'https://www.reddit.com/r/dankmemes/top/?t=month'),
 ('dark_memes','Dark memes (18+)','https://in.pinterest.com/search/pins/?q=dark%20humor%20memes','DarkHumorAndMemes',
  'https://www.reddit.com/r/DarkHumorAndMemes/top/?t=month'),
 ('adult_humor','Adult humour (18+)','https://in.pinterest.com/search/pins/?q=adult%20humor%20memes','dirtymemes',
  'https://www.reddit.com/r/dirtymemes/top/?t=month'),
 ('dirty_jokes','Dirty jokes (18+)','https://in.pinterest.com/search/pins/?q=dirty%20jokes%20funny','DirtyJokes',
  'https://www.reddit.com/r/DirtyJokes/top/?t=month'),
 ('funny','Funny','https://in.pinterest.com/search/pins/?q=funny%20pictures','funny',
  'https://www.reddit.com/r/funny/top/?t=month'),
 ('series_memes','Web series and TV memes','https://in.pinterest.com/search/pins/?q=web%20series%20memes','DunderMifflin',
  'https://www.reddit.com/r/DunderMifflin/top/?t=month'),
 ('movie_memes','Movie memes','https://in.pinterest.com/search/pins/?q=movie%20memes%20funny','MovieMemes',
  'https://www.reddit.com/r/MovieMemes/top/?t=month'),
 ('old_movie_memes','Old movie memes','https://in.pinterest.com/search/pins/?q=old%20bollywood%20movie%20memes','classicfilms',
  'https://www.reddit.com/r/classicfilms/top/?t=month'),
 ('song_memes','Song memes','https://in.pinterest.com/search/pins/?q=song%20memes%20funny','musicmemes',
  'https://www.reddit.com/r/musicmemes/top/?t=month'),
 ('girls_memes','Memes for girls','https://in.pinterest.com/search/pins/?q=relatable%20memes%20for%20girls','TrollXChromosomes',
  'https://www.reddit.com/r/TrollXChromosomes/top/?t=month'),
 ('boys_memes','Memes for boys','https://in.pinterest.com/search/pins/?q=memes%20for%20boys%20funny','TrollYChromosome',
  'https://www.reddit.com/r/TrollYChromosome/top/?t=month'),
 ('bro_code','Bro code','https://in.pinterest.com/search/pins/?q=bro%20code%20memes','TrollYChromosome',
  'https://www.reddit.com/r/TrollYChromosome/top/?t=month'),
 ('love_memes','Love and relationship memes','https://in.pinterest.com/search/pins/?q=love%20memes%20funny','relationshipmemes',
  'https://www.reddit.com/r/relationshipmemes/top/?t=month'),
 ('reaction_gifs','Reaction GIFs','https://in.pinterest.com/search/pins/?q=reaction%20gif','reactiongifs',
  'https://www.reddit.com/r/reactiongifs/top/?t=month'),
 ('funny_gifs','Funny GIFs','https://in.pinterest.com/search/pins/?q=funny%20gif','gifs',
  'https://www.reddit.com/r/gifs/top/?t=month'),
 ('movie_gifs','Movie and Bollywood GIFs','https://in.pinterest.com/search/pins/?q=bollywood%20reaction%20gif','HighQualityGifs',
  'https://www.reddit.com/r/HighQualityGifs/top/?t=month')
on conflict (key) do nothing;

commit;
