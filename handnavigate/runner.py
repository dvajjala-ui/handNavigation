"""Deterministic, local-only browser execution with checked file effects.

This is an engineering experiment, not a sandbox for arbitrary websites.
No model provider, generated code, external URL, or remote write is supported.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import struct
import threading
import time
from typing import Any
from urllib.parse import urlencode, urlsplit
from uuid import uuid4
import zlib

from playwright.sync_api import Browser, Error as BrowserError, TimeoutError as BrowserTimeout, sync_playwright

from .contracts import ContractError, digest, validate_parameters, validate_recipe
from .fixture import CASES, load_memory_fixture

MAX_BYTES = 524288
MAX_CANDIDATES = 40


class Halt(RuntimeError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def chromium_options() -> dict:
    explicit = os.environ.get("HANDNAVIGATE_CHROMIUM")
    if explicit:
        if not Path(explicit).is_file():
            raise ContractError("HANDNAVIGATE_CHROMIUM does not point to a browser executable")
        return {"executable_path": explicit}
    # Prefer the Playwright-managed browser. Use a system Chromium only if needed.
    return {}


def launch_browser(playwright, *, headless: bool = True):
    options = chromium_options()
    try:
        return playwright.chromium.launch(headless=headless, **options)
    except BrowserError:
        if options:
            raise
        executable = shutil.which("chromium") or shutil.which("chromium-browser")
        if not executable:
            raise
        return playwright.chromium.launch(headless=headless, executable_path=executable)


def verify_png(data: bytes, expected_hash: str) -> dict:
    """Verify the fixture's bounded 8-bit RGB PNG contract, not general image semantics."""
    if not 64 <= len(data) <= MAX_BYTES:
        raise Halt("FILE_SIZE", f"Downloaded file is outside the 64-{MAX_BYTES} byte budget")
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise Halt("FILE_FORMAT", "The downloaded bytes are not a PNG")
    pos, ihdr, image_data, ended = 8, None, bytearray(), False
    while pos < len(data):
        if pos + 12 > len(data):
            raise Halt("FILE_FORMAT", "The PNG is truncated")
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        if pos + length + 12 > len(data):
            raise Halt("FILE_FORMAT", "A PNG chunk is incomplete")
        kind = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        crc = struct.unpack(">I", data[pos + 8 + length:pos + 12 + length])[0]
        if zlib.crc32(kind + payload) & 0xffffffff != crc:
            raise Halt("FILE_FORMAT", "PNG chunk checksum mismatch")
        if ihdr is None and kind != b"IHDR":
            raise Halt("FILE_FORMAT", "PNG header is missing")
        if kind == b"IHDR":
            if ihdr is not None or length != 13:
                raise Halt("FILE_FORMAT", "Invalid PNG header")
            ihdr = struct.unpack(">IIBBBBB", payload)
        elif kind == b"IDAT":
            image_data.extend(payload)
        elif kind == b"IEND":
            if length != 0 or pos + 12 != len(data):
                raise Halt("FILE_FORMAT", "Unexpected bytes after the PNG end marker")
            ended = True
        else:
            raise Halt("FILE_FORMAT", "This lab only accepts its minimal PNG fixture format")
        pos += length + 12
    if not ended or ihdr is None or not image_data:
        raise Halt("FILE_FORMAT", "Incomplete PNG")
    width, height, depth, color, compression, filtering, interlace = ihdr
    if not (1 <= width <= 512 and 1 <= height <= 512 and
            (depth, color, compression, filtering, interlace) == (8, 2, 0, 0, 0)):
        raise Halt("FILE_FORMAT", "PNG is outside the lab's supported image profile")
    expected_raw = height * (1 + width * 3)
    try:
        decompressor = zlib.decompressobj()
        raw = decompressor.decompress(bytes(image_data), expected_raw + 1)
        if len(raw) != expected_raw or not decompressor.eof or decompressor.unused_data:
            raise Halt("FILE_FORMAT", "Unexpected decompressed image size")
        if any(raw[y * (1 + width * 3)] != 0 for y in range(height)):
            raise Halt("FILE_FORMAT", "Unsupported PNG row filter in this lab")
    except zlib.error as exc:
        raise Halt("FILE_FORMAT", "Cannot decode PNG image data") from exc
    actual = sha256(data).hexdigest()
    if actual != expected_hash:
        raise Halt("HASH_MISMATCH", "The image does not match the item's declared SHA-256")
    return {"sha256": actual, "bytes": len(data), "width": width, "height": height}


@contextmanager
def exclusive_lock(root: Path):
    """One local runner at a time. Stale locks require deliberate operator recovery."""
    path = root / ".execution.lock"
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise Halt("RUNNER_BUSY", "The runner is busy or a stale lock needs manual review") from exc
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(json.dumps({"pid": os.getpid(), "created_at": now()}))
        yield
    finally:
        path.unlink(missing_ok=True)


class Runner:
    def __init__(self, output: Path | str, *, headless: bool = True,
                 cancel_event: threading.Event | None = None, timeout_ms: int = 1800):
        self.output = Path(output).resolve()
        self.output.mkdir(parents=True, exist_ok=True)
        self.headless = headless
        self.cancel_event = cancel_event or threading.Event()
        self.timeout_ms = timeout_ms

    def run(self, recipe: dict, approval: dict, *, origin: str, topic: str,
            limit: int = 10, case: str = "normal", job_key: str | None = None,
            browser: Browser | None = None, pause_after: int | None = None,
            fixture_transport: str = "http") -> dict:
        validate_recipe(recipe)
        validate_parameters(topic, limit)
        if approval.get("recipe_sha256") != digest(recipe):
            raise ContractError("This exact workflow version has not been reviewed")
        parsed = urlsplit(origin)
        if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port or
                parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password):
            raise ContractError("The lab only runs against an explicit http://127.0.0.1:PORT origin")
        if fixture_transport not in ("http", "memory"):
            raise ContractError("Choose http or memory fixture transport explicitly")
        if case not in CASES:
            raise ContractError("Unknown test scenario")
        if fixture_transport == "memory" and case == "redirect":
            raise ContractError("HTTP redirects cannot be represented by the offline Blob fixture")
        if pause_after is not None and (type(pause_after) is not int or pause_after < 1):
            raise ContractError("pause_after must be a positive integer")
        key = job_key or str(uuid4())
        if not isinstance(key, str) or not 1 <= len(key) <= 120:
            raise ContractError("Invalid job key")
        report: dict[str, Any] = {
            "run_id": str(uuid4()), "job_key": key, "workflow": recipe["id"],
            "recipe_sha256": digest(recipe), "scenario": case, "fixture_transport": fixture_transport,
            "parameters": {"topic": topic, "limit": limit},
            "status": "RUNNING", "started_at": now(), "model_calls": 0,
            "model_call_basis": "No model client or provider code exists in this runner.",
            "verified_files": [], "skipped": [], "events": [], "blocked_requests": [],
            "resumed_files": 0, "new_downloads": 0, "error": None,
        }
        started = time.monotonic()
        context = None
        own_browser = None
        playwright_manager = None
        conn = None
        try:
            with exclusive_lock(self.output):
                conn = sqlite3.connect(self.output / "journal.db")
                conn.executescript('''
                  PRAGMA journal_mode=WAL;
                  CREATE TABLE IF NOT EXISTS jobs (
                    job_key TEXT PRIMARY KEY, contract_hash TEXT NOT NULL, created_at TEXT NOT NULL);
                  CREATE TABLE IF NOT EXISTS items (
                    job_key TEXT NOT NULL, item_id TEXT NOT NULL, sha256 TEXT NOT NULL,
                    path TEXT NOT NULL, bytes INTEGER NOT NULL,
                    PRIMARY KEY(job_key, item_id));
                ''')
                identity = digest({"recipe": recipe, "topic": topic, "limit": limit, "case": case, "transport": fixture_transport})
                existing = conn.execute("SELECT contract_hash FROM jobs WHERE job_key=?", (key,)).fetchone()
                if existing and existing[0] != identity:
                    raise Halt("JOB_CONTRACT_CHANGED", "Resume key is bound to different inputs or a different workflow")
                if not existing:
                    with conn:
                        conn.execute("INSERT INTO jobs VALUES (?,?,?)", (key, identity, now()))
                folder = self.output / "artifacts" / sha256(key.encode()).hexdigest()[:20]
                folder.mkdir(parents=True, exist_ok=True)
                for item_id, expected_hash, relpath, size in conn.execute(
                        "SELECT item_id,sha256,path,bytes FROM items WHERE job_key=? ORDER BY rowid", (key,)):
                    path = (self.output / relpath).resolve()
                    if not path.is_relative_to(folder.resolve()) or not path.is_file():
                        raise Halt("CHECKPOINT_MISSING", "A previously verified file is missing or has an unsafe path")
                    try:
                        meta = verify_png(path.read_bytes(), expected_hash)
                    except Halt as exc:
                        raise Halt("CHECKPOINT_TAMPERED", "A previously verified file no longer passes validation") from exc
                    report["verified_files"].append({"item_id": item_id, "path": relpath, **meta, "reused": True})
                    report["resumed_files"] += 1
                self._check(report, started)
                if browser is None:
                    playwright_manager = sync_playwright().start()
                    own_browser = launch_browser(playwright_manager, headless=self.headless)
                    browser = own_browser
                context = browser.new_context(accept_downloads=True, service_workers="block",
                                              viewport={"width": 1280, "height": 850})
                context.set_default_timeout(self.timeout_ms)
                context.route("**/*", lambda route: self._route(route, origin, report))
                context.route_web_socket("**/*", lambda socket: self._block_socket(socket, report))
                page = context.new_page()
                context.on("page", lambda popup: self._block_popup(popup, report))
                page.on("dialog", lambda dialog: self._block_dialog(dialog, report))
                url = origin + "/library?" + urlencode({"case": case, "transport": fixture_transport})
                if fixture_transport == "memory":
                    load_memory_fixture(page, case)
                else:
                    page.goto(url, wait_until="domcontentloaded")
                self._check(report, started)
                if page.get_by_test_id("login-required").count():
                    raise Halt("AUTH_REQUIRED", "Session expired; human sign-in is required")
                for step in recipe["steps"]:
                    self._check(report, started)
                    target = self._resolve(page, step["target"], report, started)
                    if step["op"] == "fill":
                        target.fill(topic)
                    elif step["op"] == "click":
                        target.click()
                    elif step["op"] == "wait":
                        target.wait_for(state="visible")
                    elif step["op"] == "collect":
                        self._collect(page, target, step, report, started, conn, folder, key,
                                      limit=limit, pause_after=pause_after)
                    self._check(report, started)
                    report["events"].append({"step": step["id"], "outcome": "checked"})
                has_collection = any(x["op"] == "collect" for x in recipe["steps"])
                if not has_collection:
                    report["status"] = "REPLAYED"
                    report["completion_note"] = "Recorded steps replayed; no file-effect contract was supplied."
                else:
                    report["status"] = "VERIFIED" if len(report["verified_files"]) == limit else "PARTIAL"
                    report["completion_note"] = "Verified local file count, format, bounded decode, and declared hash."
        except Halt as exc:
            report["status"] = {"CANCELLED": "CANCELLED", "CONTROLLED_PAUSE": "PAUSED"}.get(exc.code, "HALTED")
            report["error"] = {"code": exc.code, "message": str(exc)}
        except BrowserTimeout as exc:
            report["status"] = "HALTED"
            report["error"] = {"code": "TIMEOUT", "message": "An expected control, state, or download did not arrive in time."}
        except Exception as exc:
            report["status"] = "HALTED"
            report["error"] = {"code": "RUNTIME_ERROR", "message": f"{type(exc).__name__}: {str(exc)[:250]}"}
        finally:
            if context is not None:
                try:
                    if report["status"] not in ("VERIFIED", "REPLAYED") and context.pages:
                        screenshot = self.output / f"failure-{report['run_id']}.png"
                        context.pages[0].screenshot(path=str(screenshot), full_page=True, timeout=1500)
                        report["failure_screenshot"] = screenshot.name
                except BrowserError:
                    pass
                context.close()
            if own_browser is not None:
                own_browser.close()
            if playwright_manager is not None:
                playwright_manager.stop()
            if conn is not None:
                conn.close()
            report["finished_at"] = now()
            report["elapsed_seconds"] = round(time.monotonic() - started, 3)
            report["verified_count"] = len(report["verified_files"])
            self._write_report(report)
        return report

    def _write_report(self, report: dict) -> None:
        directory = self.output / "reports"
        directory.mkdir(exist_ok=True)
        path = directory / f"{report['run_id']}.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, indent=2))
        os.replace(temporary, path)
        report["report_path"] = str(path)

    def _check(self, report: dict, started: float) -> None:
        if self.cancel_event.is_set():
            raise Halt("CANCELLED", "The operator stopped the run")
        if report["blocked_requests"]:
            raise Halt("NETWORK_POLICY", "A request outside the local GET-only fixture policy was blocked")
        if report.get("unexpected_surface"):
            raise Halt("UNEXPECTED_SURFACE", "An unapproved popup or dialog was encountered")
        if time.monotonic() - started > 45:
            raise Halt("TIME_BUDGET", "Run exceeded the bounded lab execution budget")

    def _route(self, route, origin: str, report: dict) -> None:
        request = route.request
        url = urlsplit(request.url)
        allowed = (f"{url.scheme}://{url.netloc}" == origin and request.method == "GET" and
                   url.path in ("/library", "/api/search", "/preview", "/download", "/favicon.ico"))
        if allowed:
            response = route.fetch(max_redirects=0, timeout=self.timeout_ms)
            if 300 <= response.status < 400:
                report["blocked_requests"].append({"method": "REDIRECT", "destination": "unapproved redirect"})
                route.abort("blockedbyclient")
            else:
                route.fulfill(response=response)
        else:
            report["blocked_requests"].append({"method": request.method, "destination": f"{url.scheme}://{url.netloc}{url.path}"})
            route.abort("blockedbyclient")

    def _block_socket(self, socket, report: dict) -> None:
        report["blocked_requests"].append({"method": "WEBSOCKET", "destination": "blocked"})
        socket.close()

    def _block_popup(self, popup, report: dict) -> None:
        report["unexpected_surface"] = "popup"
        popup.close()

    def _block_dialog(self, dialog, report: dict) -> None:
        report["unexpected_surface"] = "dialog"
        dialog.dismiss()

    def _resolve(self, scope, strategies: list[dict], report: dict, started: float):
        deadline = time.monotonic() + self.timeout_ms / 1000
        while True:
            self._check(report, started)
            for index, strategy in enumerate(strategies):
                if strategy["by"] == "role":
                    candidate = scope.get_by_role(strategy["role"], name=strategy["name"], exact=True)
                elif strategy["by"] == "label":
                    candidate = scope.get_by_label(strategy["value"], exact=True)
                else:
                    candidate = scope.get_by_test_id(strategy["value"])
                count = candidate.count()
                if count > 20:
                    raise Halt("AMBIGUOUS_TARGET", "Too many matching controls; refusing to choose")
                visible = [candidate.nth(i) for i in range(count) if candidate.nth(i).is_visible()]
                if len(visible) > 1:
                    raise Halt("AMBIGUOUS_TARGET", "More than one visible control matches the approved target")
                if len(visible) == 1:
                    if index:
                        report["events"].append({"outcome": "approved_alternative", "strategy": strategy})
                    return visible[0]
            if time.monotonic() >= deadline:
                raise Halt("TARGET_NOT_FOUND", "No uniquely identified control matches an approved strategy")
            if hasattr(scope, "wait_for_timeout"):
                scope.wait_for_timeout(40)
            else:
                scope.page.wait_for_timeout(40)

    def _collect(self, page, container, step, report, started, conn, folder, job_key,
                 *, limit: int, pause_after: int | None) -> None:
        # Snapshot identity, not screen positions. This deliberately excludes dynamic/infinite lists.
        candidates = container.locator("article[data-asset-id]").evaluate_all('''nodes => nodes.map(n => ({
          id: n.dataset.assetId, sha256: n.dataset.sha256,
          links: [...n.querySelectorAll('a')].map(a => a.getAttribute('href'))
        }))''')
        if len(candidates) > MAX_CANDIDATES:
            raise Halt("CANDIDATE_BUDGET", "Too many candidates for the approved bounded loop")
        identities: dict[str, dict] = {}
        for item in candidates:
            if not re.fullmatch(r"[a-z0-9-]{1,64}", item.get("id") or "") or not re.fullmatch(r"[0-9a-f]{64}", item.get("sha256") or ""):
                raise Halt("ITEM_IDENTITY", "A result lacks a valid stable ID or declared content hash")
            if item["id"] in identities:
                if item != identities[item["id"]]:
                    raise Halt("ITEM_IDENTITY", "Duplicate item IDs disagree about content or download destination")
                report["skipped"].append({"item_id": item["id"], "reason": "duplicate_id"})
            else:
                identities[item["id"]] = item
        done_ids = {item["item_id"] for item in report["verified_files"]}
        done_hashes = {item["sha256"] for item in report["verified_files"]}
        for item_id, item in identities.items():
            self._check(report, started)
            if len(report["verified_files"]) >= limit:
                break
            if item_id in done_ids:
                continue
            if item["sha256"] in done_hashes:
                report["skipped"].append({"item_id": item_id, "reason": "duplicate_content"})
                continue
            if not item["links"]:
                report["skipped"].append({"item_id": item_id, "reason": "download_unavailable"})
                continue
            if len(item["links"]) != 1:
                raise Halt("AMBIGUOUS_TARGET", "A result has more than one download destination")
            # Identical duplicate IDs were checked above and intentionally deduplicated.
            row = container.locator(f'article[data-asset-id="{item_id}"]').first
            if row.get_attribute("data-sha256") != item["sha256"]:
                raise Halt("ITEM_CHANGED", "The result identity changed after selection")
            link = self._resolve(row, step["download_target"], report, started)
            if link.get_attribute("href") != item["links"][0]:
                raise Halt("ITEM_CHANGED", "The download target changed after selection")
            self._check(report, started)
            temporary = folder / f"{item_id}.part"
            try:
                with page.expect_download(timeout=self.timeout_ms) as waiting:
                    link.click()
                download = waiting.value
                self._check(report, started)
                failure = download.failure()
                if failure:
                    raise Halt("DOWNLOAD_FAILED", "Browser reported an incomplete or blocked download")
                download.save_as(str(temporary))
                size = temporary.stat().st_size
                if size > MAX_BYTES:
                    raise Halt("FILE_SIZE", "Download exceeded the allowed byte budget")
                meta = verify_png(temporary.read_bytes(), item["sha256"])
                filename = f"{item_id}-{meta['sha256'][:12]}.png"
                destination = folder / filename
                os.replace(temporary, destination)
                relative = destination.relative_to(self.output).as_posix()
                with conn:
                    conn.execute("INSERT INTO items VALUES (?,?,?,?,?)", (job_key, item_id, meta["sha256"], relative, meta["bytes"]))
                report["verified_files"].append({"item_id": item_id, "path": relative, **meta, "reused": False})
                report["new_downloads"] += 1
                done_hashes.add(meta["sha256"])
                done_ids.add(item_id)
                # Bound action rate on our owned fixture; do not flood the browser download queue.
                page.wait_for_timeout(140)
                report["events"].append({"item_id": item_id, "outcome": "file_verified"})
                if pause_after is not None and report["new_downloads"] >= pause_after:
                    raise Halt("CONTROLLED_PAUSE", "Deliberate interruption after a verified checkpoint")
            finally:
                temporary.unlink(missing_ok=True)
