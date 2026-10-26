# Actual Pinterest download trial

The user signed in through the in-app browser and explicitly asked to use that session. The separate Playwright profile did not contain that login. The attempted standalone download correctly stopped with AUTH_REQUIRED and saved no gated Pinterest previews.

The live trial then used the existing signed-in in-app Pinterest tab. It searched for `nature landscape`, read the actual Pin links and image elements from the rendered DOM, and downloaded 20 distinct image assets through the supported browser `downloadMedia` interface. Lazy-loaded results were observed between batches. No authentication cookies were copied or exported, and no Pin was saved to a board or uploaded elsewhere.

The exact 20 browser-returned files were decoded using the project's image validator, checked for unique SHA-256 hashes, and organized under `C:\Users\dvajj\Downloads\Pinterest-nature-landscape`. All 20 files passed validation. Total bytes: 783185. Minimum width: 360 pixels; minimum height: 157 pixels. These are the served image versions downloaded by the browser, not a claim about original source resolution.

Evidence: `evidence/pinterest-download/live-result.json` and the same manifest in the Downloads folder. Each entry records its actual local filename, Pin URL, image URL, decoded format, dimensions, byte count and hash.

This qualifies this assisted, signed-in in-app browser download. It does not qualify standalone Chromium authentication, unattended Pinterest scheduling, arbitrary topics/sites or an original-resolution Pinterest download adapter. The local download tests and live-browser regression separately passed 47 cases. The regular CLI still needs its own dedicated browser login for a fresh fetch; the in-app login is a separate session.
