import argparse
import sys

from plan_b.config import Config
from plan_b.logging_config import setup_logging


def _build_fetcher(save_html: str | None, from_html: str | None):
    """Build the HTTP fetcher for the requested debug mode.

    --from-html replays saved pages (offline); --save-html captures live pages
    to disk; otherwise a plain live fetcher is used.
    """
    from plan_b.fetch import FixtureFetcher, LiveFetcher, SavingFetcher

    if from_html:
        return FixtureFetcher(from_html)
    if save_html:
        return SavingFetcher(LiveFetcher(), save_html)
    return None  # Orchestrator/scraper will default to LiveFetcher


def main():
    parser = argparse.ArgumentParser(
        prog="plan_b",
        description="Scrape 1LIVE Plan B songs and create Tidal/Spotify playlists",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 'run' command
    run_parser = subparsers.add_parser("run", help="Run the full pipeline once")
    run_parser.add_argument(
        "--no-tidal",
        action="store_true",
        help="Disable Tidal playlist update",
    )
    run_parser.add_argument(
        "--spotify",
        action="store_true",
        help="Also update Spotify playlist",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape and match but do not modify any playlist",
    )
    run_parser.add_argument(
        "--save-html",
        metavar="DIR",
        help="Save fetched pages to DIR (for building fixtures / debugging)",
    )
    run_parser.add_argument(
        "--from-html",
        metavar="DIR",
        help="Replay pages from DIR instead of the network (offline)",
    )

    # 'scrape' command - scrapers only, no credentials needed
    scrape_parser = subparsers.add_parser(
        "scrape", help="Scrape and print songs only (no matching, no credentials)"
    )
    scrape_parser.add_argument(
        "--save-html",
        metavar="DIR",
        help="Save fetched pages to DIR (for building fixtures / debugging)",
    )
    scrape_parser.add_argument(
        "--from-html",
        metavar="DIR",
        help="Replay pages from DIR instead of the network (offline)",
    )

    # 'login' command - one-time interactive Tidal auth
    subparsers.add_parser(
        "login", help="Authenticate with Tidal once and save the session file"
    )

    # 'schedule' command
    sched_parser = subparsers.add_parser("schedule", help="Run on a daily schedule")
    sched_parser.add_argument(
        "--time",
        default=Config.SCHEDULE_TIME,
        help=f"Time to run in HH:MM format (default: {Config.SCHEDULE_TIME})",
    )
    sched_parser.add_argument(
        "--days",
        nargs="+",
        default=["tuesday", "wednesday", "thursday", "friday"],
        metavar="DAY",
        help="Weekdays to run on (default: tuesday wednesday thursday friday)",
    )
    sched_parser.add_argument(
        "--no-tidal",
        action="store_true",
        help="Disable Tidal playlist update",
    )
    sched_parser.add_argument(
        "--spotify",
        action="store_true",
        help="Also update Spotify playlist",
    )
    sched_parser.add_argument(
        "--run-now",
        action="store_true",
        help="Also run once immediately on startup (default: wait for schedule)",
    )

    args = parser.parse_args()
    setup_logging()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    enable_tidal = not getattr(args, "no_tidal", False)
    enable_spotify = getattr(args, "spotify", False)

    # Validate Spotify config if enabled
    if enable_spotify:
        errors = Config.validate_spotify()
        if errors:
            print("Spotify configuration errors:")
            for err in errors:
                print(f"  - {err}")
            print("\nSee .env.example for setup instructions.")
            sys.exit(1)

    if args.command == "scrape":
        from plan_b.orchestrator import Orchestrator

        fetcher = _build_fetcher(args.save_html, args.from_html)
        orchestrator = Orchestrator(
            enable_tidal=False, enable_spotify=False, fetcher=fetcher
        )
        _, unique = orchestrator.collect_songs()
        print(f"\n{len(unique)} unique songs scraped:")
        for song in unique:
            played = song.played_at.strftime("%a %H:%M") if song.played_at else "??"
            print(f"  [{played}] {song.artist} - {song.title}  ({song.source})")

    elif args.command == "login":
        from plan_b.services.tidal import TidalService

        print("Starting Tidal login...")
        TidalService()  # triggers interactive OAuth and saves the session file
        print(f"\nTidal session saved to {Config.TIDAL_SESSION_FILE}")

    elif args.command == "run":
        from plan_b.orchestrator import Orchestrator

        fetcher = _build_fetcher(args.save_html, args.from_html)
        orchestrator = Orchestrator(
            enable_tidal=enable_tidal,
            enable_spotify=enable_spotify,
            dry_run=args.dry_run,
            fetcher=fetcher,
        )
        summary = orchestrator.run()

        print("\nDone!" + (" (dry run)" if args.dry_run else ""))
        print(f"  Songs found:   {summary['songs_scraped']} (scraped), {summary['songs_unique']} unique")
        if enable_tidal:
            print(
                f"  Tidal:         {summary['tidal_matched']} matched, "
                f"{summary['tidal_unmatched']} not found"
            )
        if enable_spotify:
            print(
                f"  Spotify:       {summary['spotify_matched']} matched, "
                f"{summary['spotify_unmatched']} not found"
            )
        if summary["unmatched_songs"]:
            print("\n  Songs not found on streaming services:")
            for s in summary["unmatched_songs"]:
                print(f"    - {s}")

    elif args.command == "schedule":
        from plan_b.scheduler import run_scheduler

        run_scheduler(
            time_str=args.time,
            days=args.days,
            enable_tidal=enable_tidal,
            enable_spotify=enable_spotify,
            run_on_start=args.run_now,
        )


if __name__ == "__main__":
    main()
