import logging
import time

import schedule

logger = logging.getLogger(__name__)

# Map day names to schedule library attributes
_DAY_MAP = {
    "monday": schedule.every().monday,
    "tuesday": schedule.every().tuesday,
    "wednesday": schedule.every().wednesday,
    "thursday": schedule.every().thursday,
    "friday": schedule.every().friday,
    "saturday": schedule.every().saturday,
    "sunday": schedule.every().sunday,
}


def run_scheduler(
    time_str: str = "04:00",
    days: list[str] | None = None,
    enable_tidal: bool = True,
    enable_spotify: bool = False,
):
    """Run the pipeline on a schedule.

    Args:
        time_str: Time of day in HH:MM format.
        days: List of weekday names to run on, e.g. ["tuesday", "friday"].
              If None or empty, runs every day.
        enable_tidal: Update Tidal playlist.
        enable_spotify: Update Spotify playlist.
    """
    from plan_b.orchestrator import Orchestrator

    orchestrator = Orchestrator(enable_tidal=enable_tidal, enable_spotify=enable_spotify)

    def job():
        logger.info("Scheduled run starting...")
        try:
            summary = orchestrator.run()
            logger.info(f"Scheduled run complete: {summary['songs_unique']} songs processed")
        except Exception as e:
            logger.error(f"Scheduled run failed: {e}", exc_info=True)

    if days:
        for day in days:
            day_lower = day.lower().strip()
            if day_lower not in _DAY_MAP:
                logger.warning(f"Unknown day '{day}', skipping")
                continue
            _DAY_MAP[day_lower].at(time_str).do(job)
        day_str = ", ".join(days)
        logger.info(f"Scheduler started. Runs every {day_str} at {time_str}.")
    else:
        schedule.every().day.at(time_str).do(job)
        logger.info(f"Scheduler started. Daily run at {time_str}.")

    logger.info("Press Ctrl+C to stop.")

    # Run once immediately on start
    job()

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user.")
