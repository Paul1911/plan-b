import logging
import time

import schedule

logger = logging.getLogger(__name__)


def run_scheduler(
    time_str: str = "09:00",
    enable_tidal: bool = True,
    enable_spotify: bool = False,
):
    """Run the pipeline on a daily schedule."""
    from plan_b.orchestrator import Orchestrator

    orchestrator = Orchestrator(enable_tidal=enable_tidal, enable_spotify=enable_spotify)

    def job():
        logger.info("Scheduled run starting...")
        try:
            summary = orchestrator.run()
            logger.info(f"Scheduled run complete: {summary['songs_unique']} songs processed")
        except Exception as e:
            logger.error(f"Scheduled run failed: {e}", exc_info=True)

    schedule.every().day.at(time_str).do(job)
    logger.info(f"Scheduler started. Daily run at {time_str}. Press Ctrl+C to stop.")

    # Run once immediately on start
    job()

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user.")
