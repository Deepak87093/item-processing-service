import threading

from sqlalchemy import select

from app.models import (
    IdempotencyRecord,
    Item,
    ItemStatus,
    ProcessingRecord,
)
from app.services.item_processor import process_item


def test_concurrent_same_idempotency_key(
    session_factory,
):
    # ---------------------------------------------------------
    # 1. Create test item
    # ---------------------------------------------------------
    setup_session = session_factory()

    item = Item(
        name="Concurrent Idempotency Item",
        amount=100,
        status=ItemStatus.PENDING,
    )

    setup_session.add(item)
    setup_session.commit()
    setup_session.refresh(item)

    item_id = item.id

    setup_session.close()

    # Both requests use exactly the same key.
    idempotency_key = "concurrent-key-001"

    results = []
    errors = []

    # ---------------------------------------------------------
    # 2. Worker
    # ---------------------------------------------------------
    def worker():
        session = session_factory()

        try:
            result = process_item(
                session,
                item_id,
                idempotency_key,
            )

            results.append(result)

        except Exception as exc:
            errors.append(exc)

        finally:
            session.close()

    # ---------------------------------------------------------
    # 3. Start two concurrent requests
    # ---------------------------------------------------------
    thread_1 = threading.Thread(target=worker)
    thread_2 = threading.Thread(target=worker)

    thread_1.start()
    thread_2.start()

    thread_1.join()
    thread_2.join()

    # ---------------------------------------------------------
    # 4. Verify
    # ---------------------------------------------------------
    verification_session = session_factory()

    try:
        records = verification_session.execute(
            select(ProcessingRecord).where(
                ProcessingRecord.item_id == item_id
            )
        ).scalars().all()

        idempotency_records = verification_session.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.idempotency_key
                == idempotency_key
            )
        ).scalars().all()

        final_item = verification_session.get(
            Item,
            item_id,
        )

        assert len(results) == 2

        assert len(errors) == 0

        assert len(records) == 1

        assert len(idempotency_records) == 1

        assert final_item is not None
        assert final_item.status == ItemStatus.COMPLETED

    finally:
        verification_session.close()