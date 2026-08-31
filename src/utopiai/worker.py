from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from utopiai.config import Settings
from utopiai.db import session_factory
from utopiai.dreaming import DreamWorker
from utopiai.logging import configure_logging


async def run() -> None:
    settings = Settings.load()
    configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)
    worker = DreamWorker(settings, session_factory(settings.database_url))
    audited_date = None
    while True:
        try:
            processed = await worker.run_one_due()
            local = datetime.now(ZoneInfo(settings.timezone))
            if local.hour == 3 and audited_date != local.date():
                recovered = await worker.recover_stale()
                logger.info("dream_audit recovered=%s", recovered)
                audited_date = local.date()
            if not processed:
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("dream_worker_error")
            await asyncio.sleep(15)


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
