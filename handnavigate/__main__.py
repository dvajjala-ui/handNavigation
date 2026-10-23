from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

from playwright.sync_api import sync_playwright, Error as BrowserError
from .contracts import ContractError, approve, load_default
from .fixture import CASES, load_memory_fixture, running_fixture
from .recorder import Recorder, compile_recording
from .runner import Runner, launch_browser


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "live":
        from .live.cli import main as live_main
        return live_main(sys.argv[2:])
    parser = argparse.ArgumentParser(description="HandNavigate Lab - owned fixtures and explicitly reviewed experimental export contracts")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("live", help="Experimental real-URL browser core: inspect, record, agent, replay")
    run = commands.add_parser("run", help="Run the explicit local image-collection recipe")
    run.add_argument("--topic", default="architecture")
    run.add_argument("--limit", type=int, default=10)
    run.add_argument("--case", choices=CASES, default="normal")
    run.add_argument("--transport", choices=["memory", "http"], default="memory")
    run.add_argument("--output", type=Path, default=Path("runtime"))
    run.add_argument("--job-key")
    run.add_argument("--pause-after", type=int)
    run.add_argument("--headed", action="store_true")
    run.add_argument("--approve-local-demo", action="store_true", help="Explicitly approve the shipped owned-fixture recipe")
    studio = commands.add_parser("studio", help="Start the local development UI")
    studio.add_argument("--port", type=int, default=4177)
    studio.add_argument("--transport", choices=["memory", "http"], default="memory")
    studio.add_argument("--output", type=Path, default=Path("runtime"))
    record = commands.add_parser("record", help="Record fill/click actions on the owned fixture")
    record.add_argument("--example-topic", default="architecture")
    record.add_argument("--output", type=Path, default=Path("runtime/recording"))
    record.add_argument("--transport", choices=["memory", "http"], default="memory")
    record.add_argument("--automated-example", action="store_true", help="Drive an example instead of recording a human; labelled in output")
    approve_cmd = commands.add_parser("approve", help="Write a checksum review receipt for a recipe")
    approve_cmd.add_argument("recipe", type=Path)
    approve_cmd.add_argument("--reviewer", default="local operator")
    replay = commands.add_parser("replay", help="Replay a reviewed recorded recipe on the local fixture")
    replay.add_argument("recipe", type=Path)
    replay.add_argument("--topic", default="flowers")
    replay.add_argument("--transport", choices=["memory", "http"], default="memory")
    replay.add_argument("--output", type=Path, default=Path("runtime"))
    from .connection_cli import add_commands, COMMANDS, execute
    add_commands(commands)
    args = parser.parse_args()
    try:
        if args.command in COMMANDS:
            return execute(args)
        if args.command == "approve":
            recipe = json.loads(args.recipe.read_text())
            receipt = approve(recipe, args.reviewer)
            path = args.recipe.with_suffix(".approval.json")
            path.write_text(json.dumps(receipt, indent=2))
            print(path)
            return 0
        if args.command == "studio":
            from .studio import running_studio
            with running_fixture() as fixture, running_studio(fixture.origin, args.output, port=args.port, transport=args.transport) as server:
                print(f"HandNavigate local studio: {server.origin}", flush=True)
                print(f"Fixture transport: {args.transport}. No external websites or AI model.", flush=True)
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    return 0
        if args.command == "record":
            args.output.mkdir(parents=True, exist_ok=True)
            with running_fixture() as fixture, sync_playwright() as p:
                browser = launch_browser(p, headless=args.automated_example)
                page = browser.new_page()
                recorder = Recorder()
                if args.transport == "memory":
                    load_memory_fixture(page)
                    recorder.attach(page)
                else:
                    recorder.attach(page)
                    page.goto(fixture.origin + "/library")
                if args.automated_example:
                    page.get_by_label("Topic", exact=True).fill(args.example_topic)
                    page.get_by_role("button", name="Search", exact=True).click()
                    page.get_by_test_id("results-ready").wait_for()
                    page.wait_for_timeout(100)
                else:
                    print("In the opened browser: fill Topic, click Search, then CLOSE THE BROWSER TAB.")
                    print("Do not click Download: downloads require an explicitly authored verifier.")
                    while not page.is_closed():
                        try:
                            page.wait_for_timeout(150)
                        except Exception:
                            if not page.is_closed():
                                raise
                recorder.save(args.output / "events.json")
                recipe = compile_recording(recorder.events, example_topic=args.example_topic, ready_test_id="results-ready")
                (args.output / "recipe.json").write_text(json.dumps(recipe, indent=2))
                (args.output / "provenance.json").write_text(json.dumps({"automated_example": args.automated_example, "transport": args.transport}, indent=2))
                browser.close()
                print(f"Draft saved to {args.output}; review recipe.json before approving it.")
                return 0
        if args.command == "run":
            if not args.approve_local_demo:
                parser.error("Inspect recipes/collect-images.json and pass --approve-local-demo to authorize this local-only example")
            recipe = load_default()
            receipt = approve(recipe, "CLI operator approved local demo")
        else:
            recipe = json.loads(args.recipe.read_text())
            receipt = json.loads(args.recipe.with_suffix(".approval.json").read_text())
        with running_fixture() as fixture:
            result = Runner(args.output, headless=not getattr(args, "headed", False)).run(
                recipe, receipt, origin=fixture.origin, topic=args.topic,
                limit=getattr(args, "limit", 10), case=getattr(args, "case", "normal"),
                job_key=getattr(args, "job_key", None), pause_after=getattr(args, "pause_after", None),
                fixture_transport=args.transport)
        print(json.dumps(result, indent=2))
        return 0 if result["status"] in ("VERIFIED", "REPLAYED") else 2
    except BrowserError as exc:
        from .portal_runner import error_report
        print(json.dumps(error_report(exc)), file=sys.stderr)
        return 2
    except (ContractError, OSError, ValueError) as exc:
        print(f"Cannot start: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
