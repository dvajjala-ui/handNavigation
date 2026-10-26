# HandNavigate Desktop: measured test report

Date: 27 October 2026. This report describes the local Windows build at version 0.5.0 and the tests present in this repository. It does not certify a particular third-party website or claim that the product is free of all bugs.

## Result

The app now has a working local Electron browser and runner. Against owned HTTP test pages it saved 20 valid images, repeated the same approved task with a second value and saved 20 different images, replayed a taught form task, and uploaded files through a real browser file input. The transfer was marked verified only after the app fetched and compared the images persisted by the receiving site. A repeated transfer did not submit duplicate uploads.

The daily queue was enabled through the app after both configured values had a verified run. A test clock advanced to a later scheduled occurrence, and the queue then invoked the actual embedded-browser downloader and chose a new image. This is evidence for one scheduled execution, not an overnight or multi-day endurance test.

## Commands and evidence

| Check | Command or artifact | Measured result |
| --- | --- | --- |
| Core tests | `npm test` | 16 passed, 0 failed; [console log](../analysis/desktop-unit-final-console.txt) |
| Desktop acceptance | `npm run test:desktop` | 16 passed, 0 failed; [results](../desktop/evidence/e2e-results.json) and [console log](../analysis/desktop-e2e-final-console.txt) |
| Portable Windows build | `npm run dist` | Produced `dist/HandNavigate-0.5.0-Windows.exe` (116,423,427 bytes); SHA-256 `31A2A3DE43A237A5A5942326485DE97228C02F10AEC3DA549618DF5CB05F4D19`; [build log](../analysis/desktop-package-console.txt) |
| Exact portable executable smoke | `node desktop/test/packaged.cjs dist/HandNavigate-0.5.0-Windows.exe` | The one-file EXE started, ran its embedded browser, saved 3 images, and all 3 independently decoded with matching SHA-256; [result](../desktop/evidence/packaged-results.json) |
| Production dependency audit | `npm audit --omit=dev --json` | 0 reported vulnerabilities at the time of the audit; [report](../analysis/desktop-production-audit.json) |

The acceptance test launches Electron, uses the visible app controls for the 20-image download and teaching path, and visits its own local HTTP fixture in the embedded browser. Downloaded bytes are decoded and checked for hashes after the run. The transfer and several fault scenarios create tasks through a test-only main-process hook, then use the same production runner and browser. Those scenarios establish runner behavior but do not prove that every transfer setup control has been exercised end to end. A separate smoke test starts the final portable EXE itself with isolated app data and completes a three-image download through its public UI bridge.

The test suite also demonstrated persistent app session reuse across a restart; a shortfall of eligible source images reporting `PARTIAL` with valid files retained; invalid placeholders being skipped when a valid image remains; an image on an unreviewed host being blocked; and a false upload confirmation becoming `NEEDS_REVIEW` with automatic retry blocked. It then explicitly confirmed that the missing upload was absent, retried once, and verified the original without creating duplicates. The core tests cover approval invalidation, interrupted-run review, integrity-checked database backup recovery, uncertain-upload resolution, rehearsal of every scheduled value, daily occurrence deduplication, and daylight-saving transitions.

## What is still unqualified

- The new desktop executable has not yet completed a live Pinterest or other external-site run in this report. An earlier assisted download of 20 Pinterest images used the Codex in-app browser, not this packaged app. That earlier result cannot be counted as a desktop-app pass.
- Arbitrary websites vary in selectors, authentication, image delivery, uploads, and verification. The supported generic path is a user-taught main-frame workflow with reviewed site/image hosts and a concrete result check. Canvas-only interfaces, cross-origin iframe controls, drag-and-drop-only uploaders, and galleries that expose only recompressed thumbnails require site-specific support.
- The daily queue runs while this local app remains open and the computer is awake. The test advanced a clock; it did not leave the computer running overnight.
- The receiving site test exposed the original uploaded bytes. A receiving service that changes image bytes needs a different explicit verification rule before a transfer can be called verified.
- Sign-in, MFA, and CAPTCHA still require the user. Cookies have the website's usual lifetime; session-only cookies may not persist after the app closes.
- This executable is a local unsigned Windows build. The tests establish source-app behavior and one exact-package smoke run; they do not establish an installer, code signing, store review, long-running stability, or compatibility with every Windows configuration.

For the user workflow and setup sequence, see [Desktop start guide](../DESKTOP_START_HERE.md).
