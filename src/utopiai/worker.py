from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from utopiai.config import Settings
from utopiai.db import session_factory
from utopiai.dreaming import DreamWorker
from utopiai.logging import configure_logging
from utopiai.media import MediaGateway
from utopiai.media_worker import MediaWorker


async def run() -> None:
    settings = Settings.load()
    configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)
    sessions = session_factory(settings.database_url)
    dream_worker = DreamWorker(settings, sessions)
    media_gateway = MediaGateway(settings.image_profile, settings.data_dir)
    media_worker = MediaWorker(settings, sessions, media_gateway)
    audited_date = None
    while True:
        try:
            did_work = await dream_worker.run_one_due()
            did_work |= await media_worker.run_one_pending()
            local = datetime.now(ZoneInfo(settings.timezone))
            if local.hour == 3 and audited_date != local.date():
                recovered = await dream_worker.recover_stale()
                logger.info("dream_audit recovered=%s", recovered)
                audited_date = local.date()
            if not did_work:
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("worker_error")
            await asyncio.sleep(15)


def main() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run())


if __name__ == "__main__":
    main()
