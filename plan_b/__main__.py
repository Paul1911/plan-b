import argparse
import sys

from plan_b.config import Config
from plan_b.logging_config import setup_logging


def main():
    parser = argparse.ArgumentParser(
        prog="plan_b",
        description="Scrape 1LIVE Plan B songs and create Tidal/Spotify playlists",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 'run' command
    run_parser = subparsers.add_parser("run", help="Run the full pipeline once")
    run_parser.add_argument(
        "--tidal",
        action="store_true",
        default=True,
        help="Update Tidal playlist (default: on)",
    )
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
        "--tidal",
        action="store_true",
        default=True,
        help="Update Tidal playlist (default: on)",
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

    if args.command == "run":
        from plan_b.orchestrator import Orchestrator

        orchestrator = Orchestrator(enable_tidal=enable_tidal, enable_spotify=enable_spotify)
        summary = orchestrator.run()

        print(f"\nDone!")
        print(f"  Songs found:   {summary['songs_scraped']} (scraped), {summary['songs_unique']} unique")
        if enable_tidal:
            print(
                f"  Tidal:         {summary['tidal_matched']} added to playlist, "
                f"{summary['tidal_unmatched']} not found"
            )
        if enable_spotify:
            print(
                f"  Spotify:       {summary['spotify_matched']} added to playlist, "
                f"{summary['spotify_unmatched']} not found"
            )
        if summary["unmatched_songs"]:
            print(f"\n  Songs not found on streaming services:")
            for s in summary["unmatched_songs"]:
                print(f"    - {s}")

    elif args.command == "schedule":
        from plan_b.scheduler import run_scheduler

        run_scheduler(
            time_str=args.time,
            days=args.days,
            enable_tidal=enable_tidal,
            enable_spotify=enable_spotify,
        )


if __name__ == "__main__":
    main()
