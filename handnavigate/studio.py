"""Loopback-only local development studio with a durable, single-worker queue."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import sqlite3
import threading
from urllib.parse import parse_qs, urlsplit

from .contracts import ContractError, digest, load_default, validate_parameters, validate_recipe
from .controller import Controller
from .connectors import ConnectionRegistry, demo_profile
from .vault import SessionVault
from .teaching_service import TeachingService
from .teaching import ADAPTER
from .teaching_runner import ASSETS
from .fixture import CASES
from .recorder import compile_recording
from .scheduling import preview, validate_schedule

ROOT = Path(__file__).resolve().parent.parent



def teaching_html(csrf):
    html = (ROOT / 'ui' / 'teach.html').read_text()
    for marker, value in {
        '__CSRF_TOKEN__': csrf,
        '__PRACTICE_FORM__': (ASSETS / 'owned_form.html').read_text(),
        '__PRACTICE_SCRIPT__': (ASSETS / 'owned_form.js').read_text(),
        '__RECORDER_SCRIPT__': (ASSETS / 'teaching_recorder.js').read_text(),
        '__TEACHING_APP__': (ROOT / 'ui' / 'teach.js').read_text(),
    }.items():
        html = html.replace(marker, value)
    return html.replace("__CSRF_TOKEN__", csrf)


def fields(args, allowed, required=()):
    if not isinstance(args, dict) or set(args) - set(allowed) or set(required) - set(args):
        raise ContractError("Unknown or missing request fields")
    if "id" in args and (not isinstance(args["id"], str) or not re.fullmatch(r"[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}", args["id"])):
        raise ContractError("Invalid resource ID")


class StudioServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, origin: str, output: Path, *, port: int = 4177, transport: str = "memory"):
        if transport not in ("memory", "http"):
            raise ContractError("Unknown fixture transport")
        super().__init__(("127.0.0.1", port), StudioHandler)
        self.fixture_origin, self.output, self.transport = origin, output.resolve(), transport
        self.csrf = secrets.token_urlsafe(32)
        self.state_lock = threading.RLock()
        try:
            self.controller = Controller(self.output, origin)
            self.store = self.controller.store
            self.connections = ConnectionRegistry(self.output)
            self.vault = SessionVault(self.output / "sessions")
            self.teaching = TeachingService(self.store, self.output, self.controller.execution_lock)
        except BaseException:
            if hasattr(self, "controller"):
                self.controller.close()
            self.server_close()
            raise

    @property
    def origin(self):
        return f"http://127.0.0.1:{self.server_port}"

    @property
    def recipe(self):
        return self.store.recipe()

    @property
    def busy(self):
        return self.store.busy()

    @property
    def history(self):
        # Preserve the old public property order; API remains newest-first.
        return self.store.history()[::-1]

    @property
    def cancel_event(self):
        return self.controller.cancel_event

    def snapshot(self):
        recipe = self.recipe
        attempts = self.store.attempts()
        connections = self.connections.list()
        for connection in connections:
            path = self.vault.path(connection['profile'])
            connection['session'] = {'encrypted_file_present': path.is_file() and not path.is_symlink(),
                                     'validity': 'NOT_CHECKED'}
        qualification = None
        try:
            report_path = self.output / 'qualification.json'
            if report_path.is_file() and report_path.stat().st_size <= 524288:
                qualification = json.loads(report_path.read_text())
        except (OSError, ValueError):
            qualification = {'status': 'UNREADABLE', 'checks': []}
        return {"busy": self.busy, "history": self.store.history(), "recipe": recipe,
                "recipe_sha256": digest(recipe), "fixture_transport": self.transport,
                "fixture_origin": self.fixture_origin, "cases": CASES,
                "schedules": self.store.schedules(), "drafts": self.store.drafts(),
                "connections": connections, "connection_example": demo_profile(), "qualification": qualification,
                "guided_teaching": self.teaching.snapshot(),
                "attempts": attempts, "audit": self.store.audit(35),
                "needs_review": [a for a in attempts if a["state"] == "NEEDS_REVIEW"],
                "scheduler": {"running": bool(self.controller.worker and self.controller.worker.is_alive()),
                              "error": self.controller.error, "last_tick_at": self.controller.last_tick_at,
                              "scope": "Runs only while this local studio process is open and the computer is awake"},
                "notice": "Owned synthetic fixture only. Local daily scheduling, no external websites, cloud or AI model."}

    def validated_run(self, args):
        fields(args, {"topic", "limit", "case", "job_key", "pause_after", "reviewed_sha256"},
               {"topic", "limit", "reviewed_sha256"})
        validate_parameters(args["topic"], args["limit"])
        recipe = self.recipe
        if args["reviewed_sha256"] != digest(recipe):
            raise ContractError("Review the current recipe before running")
        case = args.get("case", "normal")
        if not isinstance(case, str) or case not in CASES or (case == "redirect" and self.transport == "memory"):
            raise ContractError("Scenario is unavailable for this fixture transport")
        pause = args.get("pause_after")
        if pause is not None and (type(pause) is not int or not 1 <= pause <= 20):
            raise ContractError("Invalid pause checkpoint")
        key = args.get("job_key")
        if key is not None and (not isinstance(key, str) or not 1 <= len(key) <= 120):
            raise ContractError("Invalid job key")
        request = {"topic": args["topic"], "limit": args["limit"], "case": case,
                   "fixture_transport": self.transport, "pause_after": pause}
        if key:
            request["job_key"] = key
        return recipe, request

    def start_run(self, args):
        if self.controller.error:
            raise ContractError("Worker is stopped. Restart the studio and review interrupted work")
        recipe, request = self.validated_run(args)
        key = self.store.submit_manual(recipe, request, self.controller.clock())
        self.controller.notify()
        return key

    def draft_from_recording(self, args):
        fields(args, {"events", "example_topic", "ready_test_id", "append_collection"}, {"events", "example_topic", "append_collection"})
        if type(args["append_collection"]) is not bool:
            raise ContractError("Collection template selection must be an explicit boolean")
        recipe = compile_recording(args["events"], example_topic=args["example_topic"],
                                   ready_test_id=args.get("ready_test_id"))
        source = "Imported events; explicit topic binding; no intent inference"
        if args["append_collection"]:
            if args.get("ready_test_id") != "results-ready":
                raise ContractError("The authored local collection template requires results-ready")
            recipe["steps"].append(deepcopy(load_default()["steps"][-1]))
            recipe["name"] = "Taught search with explicitly selected local collection contract"
            source += "; collection loop and PNG verifier explicitly selected, not learned"
        recipe["revision"] = self.recipe["revision"] + 1
        return self.store.create_draft(recipe, source, self.controller.clock())


class StudioHandler(BaseHTTPRequestHandler):
    server: StudioServer

    def log_message(self, *_args):
        pass

    def respond(self, body: bytes | dict, status=200, content_type="application/json"):
        if isinstance(body, dict):
            body = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def valid_host(self):
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_port}"

    def do_GET(self):
        if not self.valid_host():
            return self.respond({"error": "Invalid host"}, 403)
        path = urlsplit(self.path).path
        if path == "/":
            html = (ROOT / "ui" / "index.html").read_text().replace("__CSRF_TOKEN__", self.server.csrf)
            return self.respond(html.encode(), content_type="text/html; charset=utf-8")
        if path == "/teach":
            html = teaching_html(self.server.csrf)
            return self.respond(html.encode(), content_type="text/html; charset=utf-8")
        if path == "/api/teaching":
            return self.respond({**self.server.teaching.snapshot(), "adapter": ADAPTER})
        if path == "/api/teaching/artifact":
            query = parse_qs(urlsplit(self.path).query)
            try:
                content = self.server.teaching.artifact(query['run'][0], query['row'][0])
                return self.respond(content)
            except (KeyError, IndexError, ContractError, OSError):
                return self.respond({"error": "Verified teaching artifact is unavailable or changed"}, 409)
        if path == "/api/status":
            return self.respond(self.server.snapshot())
        if path == "/api/evidence":
            target = ROOT / "evidence" / "test-results.json"
            return self.respond(json.loads(target.read_text()) if target.exists() else {"notice": "Run tests first"})
        if path == "/api/artifact":
            query = parse_qs(urlsplit(self.path).query)
            try:
                report = self.server.store.report(query["run"][0])
                index = int(query["index"][0])
                if index < 0 or report is None:
                    raise ValueError()
                artifact = report["verified_files"][index]
                target = (self.server.output / artifact["path"]).resolve()
                if not target.is_relative_to((self.server.output / "artifacts").resolve()):
                    raise ValueError()
                if target.stat().st_size > 524288:
                    return self.respond({"error": "Artifact exceeded the verified size budget"}, 409)
                content = target.read_bytes()
                if sha256(content).hexdigest() != artifact["sha256"]:
                    return self.respond({"error": "Artifact changed after verification"}, 409)
                return self.respond(content, content_type="image/png")
            except (KeyError, IndexError, ValueError, OSError):
                return self.respond({"error": "Artifact not found"}, 404)
        return self.respond({"error": "Not found"}, 404)

    def do_POST(self):
        if (not self.valid_host() or self.headers.get("Origin") != self.server.origin or
                not secrets.compare_digest(self.headers.get("X-HandNavigate-Token", ""), self.server.csrf)):
            return self.respond({"error": "Local origin and session token required"}, 403)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 65536 or self.headers.get("Content-Type") != "application/json":
                raise ContractError("Expected a JSON request no larger than 64 KiB")
            self.connection.settimeout(10)
            def reject_constant(_):
                raise ContractError("Non-finite JSON values are not supported")
            args = json.loads(self.rfile.read(length), parse_constant=reject_constant)
            if not isinstance(args, dict):
                raise ContractError("Request must be an object")
            path = urlsplit(self.path).path
            at = self.server.controller.clock()
            if path == "/api/teaching/compile":
                allowed = {'events', 'bindings', 'name', 'verification_contract', 'max_rows'}
                fields(args, allowed, allowed)
                return self.respond(self.server.teaching.compile(args), 201)
            if path == "/api/teaching/import":
                fields(args, {'recipe'}, {'recipe'})
                return self.respond(self.server.teaching.create(args['recipe']), 201)
            if path == "/api/teaching/approve":
                fields(args, {'lesson_id', 'reviewed_sha256', 'acknowledgement'},
                       {'lesson_id', 'reviewed_sha256', 'acknowledgement'})
                return self.respond(self.server.teaching.approve(args['lesson_id'], args['reviewed_sha256'], args['acknowledgement']))
            if path == "/api/teaching/revoke":
                fields(args, {'lesson_id'}, {'lesson_id'})
                return self.respond(self.server.teaching.revoke(args['lesson_id']))
            if path == "/api/teaching/plan":
                fields(args, {'lesson_id', 'rows'}, {'lesson_id', 'rows'})
                return self.respond(self.server.teaching.plan(args['lesson_id'], args['rows']))
            if path == "/api/teaching/run":
                allowed = {'lesson_id', 'rows', 'reviewed_plan_sha256', 'request_id'}
                fields(args, allowed, allowed)
                return self.respond(self.server.teaching.start(args['lesson_id'], args['rows'], args['reviewed_plan_sha256'], args['request_id']), 202)
            if path == "/api/teaching/stop":
                fields(args, {'run_id'}, {'run_id'})
                return self.respond(self.server.teaching.stop(args['run_id']))
            if path == "/api/teaching/acknowledge":
                fields(args, {'run_id', 'acknowledgement'}, {'run_id', 'acknowledgement'})
                return self.respond(self.server.teaching.acknowledge(args['run_id'], args['acknowledgement']))
            if path == "/api/connections":
                fields(args, {'profile', 'base_sha256'}, {'profile'})
                return self.respond(self.server.connections.put(args['profile'], args.get('base_sha256')), 201)
            if path == "/api/connections/approve":
                fields(args, {'connection_id', 'reviewed_sha256', 'permission_confirmed'},
                       {'connection_id', 'reviewed_sha256', 'permission_confirmed'})
                return self.respond(self.server.connections.approve(args['connection_id'], args['reviewed_sha256'], args['permission_confirmed']))
            if path == "/api/connections/forget":
                fields(args, {'connection_id'}, {'connection_id'})
                connection = self.server.connections.revoke(args['connection_id'])
                return self.respond(self.server.vault.forget(connection['profile']))
            if path == "/api/run":
                key = self.server.start_run(args)
                return self.respond({"started": True, "attempt_id": key}, 202)
            if path == "/api/stop":
                fields(args, set())
                self.server.controller.stop_active()
                return self.respond({"stop_requested": True})
            if path == "/api/schedules/preview":
                validate_schedule(args)
                return self.respond({"occurrences": preview(args, at), "dst_policy": "skip nonexistent time; first occurrence only when repeated"})
            if path == "/api/schedules":
                fields(args, {"spec", "run"}, {"spec", "run"})
                recipe, request = self.server.validated_run(args["run"])
                key = self.server.store.create_schedule(args["spec"], recipe, request, at)
                self.server.controller.notify()
                return self.respond({"id": key}, 201)
            if path == "/api/schedules/toggle":
                fields(args, {"id", "enabled", "reviewed_sha256"}, {"id", "enabled"})
                self.server.store.toggle_schedule(args["id"], args["enabled"], args.get("reviewed_sha256"), at)
                return self.respond({"updated": True})
            if path == "/api/drafts/compile":
                return self.respond(self.server.draft_from_recording(args), 201)
            if path == "/api/drafts":
                fields(args, {"recipe", "base_sha256"}, {"recipe", "base_sha256"})
                current = self.server.recipe
                if args["base_sha256"] != digest(current):
                    raise ContractError("Active recipe changed; reload before editing")
                validate_recipe(args["recipe"])
                if args["recipe"]["revision"] != current["revision"] + 1:
                    raise ContractError("Draft revision must be the active revision plus one")
                return self.respond(self.server.store.create_draft(args["recipe"], "Explicit recipe editor; not model generated", at), 201)
            if path == "/api/drafts/approve":
                fields(args, {"id", "reviewed_sha256"}, {"id", "reviewed_sha256"})
                recipe = self.server.store.activate_draft(args["id"], args["reviewed_sha256"], at)
                return self.respond({"approved": True, "recipe_sha256": digest(recipe)})
            if path == "/api/reconcile":
                fields(args, {"id", "acknowledgement"}, {"id", "acknowledgement"})
                self.server.store.resolve_interrupted(args["id"], args["acknowledgement"], at)
                return self.respond({"resolved_without_retry": True, "schedules_remain_paused": True})
            return self.respond({"error": "Not found"}, 404)
        except (ContractError, ValueError, TypeError, KeyError) as exc:
            return self.respond({"error": str(exc)}, 400)
        except (OSError, sqlite3.Error):
            return self.respond({"error": "Local storage or request I/O failed; no automatic retry"}, 503)


@contextmanager
def running_studio(origin: str, output: Path, *, port=4177, transport="memory"):
    server = StudioServer(origin, output, port=port, transport=transport)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.teaching.close()
        server.controller.close()
        server.server_close()
        thread.join(timeout=3)
