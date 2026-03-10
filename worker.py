from __future__ import annotations

import asyncio
import logging

from app.core.logging import configure_logging
from app.core.jobs import (
    pop_next_job_id,
    mark_failed,
    mark_running,
    mark_succeeded,
    get_job,
)
from app.db.session import SessionLocal
from app.services.stores_tokens import get_store_access_token
from app.services.import_products import seed_products
from app.core.cache import invalidate_store

configure_logging()
logger = logging.getLogger("app.worker")


async def handle_job(job_id: str) -> None:
    job = get_job(job_id)
    if not job:
        return

    job_type = job.get("type")
    payload = job.get("payload") or {}

    mark_running(job_id)

    try:
        if job_type == "seed_products":
            store_id = str(payload.get("store_id") or "")
            if not store_id:
                raise RuntimeError("Missing store_id in job payload")

            db = SessionLocal()
            try:
                token = get_store_access_token(db, store_id)
                if not token:
                    raise RuntimeError(f"Missing access token for store_id={store_id}")

                imported = await seed_products(
                    db=db, store_id=store_id, access_token=token
                )
                invalidate_store(store_id)
            finally:
                db.close()

            mark_succeeded(job_id, {"imported": imported, "store_id": store_id})
            return

        raise RuntimeError(f"Unknown job type: {job_type}")

    except Exception as e:
        logger.exception("job_failed", extra={"job_id": job_id})
        mark_failed(job_id, str(e))


async def main() -> None:
    logger.info("worker_started")
    while True:
        job_id = pop_next_job_id(block_seconds=5)
        if not job_id:
            await asyncio.sleep(0.2)
            continue
        await handle_job(job_id)


if __name__ == "__main__":
    asyncio.run(main())
