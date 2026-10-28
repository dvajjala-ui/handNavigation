# Add a website to image collections

Desktop 0.8 connects a verified image workflow to the collection worker. Built-in Pinterest, Reddit and Imgflip recipes remain available. This does not guarantee access to every website or twenty new results from a narrow topic.

1. Create an **image download** workflow. Use `{{topic}}` in its search URL or taught search input. This is the only supported changing variable for collection recipes.
2. Choose the image group, image hosts and pagination. If the site needs search actions, teach them and add a visible result check.
3. Review, approve and complete a successful download run. Editing its executable settings requires a new approval and successful run.
4. In **Review**, choose **Use for image collections**. The worker must be idle; a running worker restarts using the same data folder. Its own Chrome/Edge profile may need a first sign-in because the teaching browser has a separate session.
5. Open **Image collections**, select the new source and enter different topics/counts. Downloads use the shared daily budget, validation, duplicate history and storage verification.

The worker stores recipes in its private `source-recipes.json`, with an integrity checksum and backups. No cookies or credentials are copied from the teaching browser. A corrupt registry is preserved and reported instead of silently discarded. Removing a source keeps existing files, browser profiles and collection history. Local jobs retain their exact source recipe so retrying after an update/removal uses the original definition.

When connected to StickerDock, the worker advertises only source ID, name and revision. Admin lists those sources after the worker connects. Server-side compatibility checks require one configured worker to support every source in a job; older workers cannot claim unfamiliar jobs. Recipes, URLs, taught actions, profiles and passwords are not sent in the capability advertisement.

A source added on your desktop is installed on that worker only. A separate Railway/VM worker needs the reviewed recipe installed in its own data folder and its own actual-host acceptance before it can run that source. The existing `HANDNAVIGATE_SOURCES_FILE` configuration remains supported. Guest blocks and human checks stop collection normally; there is no bypass or automatic rights approval.

Qualification covers real owned HTTP images: form-search preparation, visible checks, changed topics, durable source storage, immutable retry recipes, removal/history retention and malformed-registry rejection. These tests are distinct from the earlier live Pinterest/Reddit/Imgflip acceptance records.
