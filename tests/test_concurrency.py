import threading

from sqlalchemy import select

from app.models import Item, ItemStatus, ProcessingRecord
from app.services.item_processor import process_item


def test_concurrent_processing(
    session_factory,
):
    # ---------------------------------------------------------
    # 1. Create the item that both threads will try to process
    # ---------------------------------------------------------
    setup_session = session_factory()

    item = Item(
        name="Concurrent Item",
        amount=100,
        status=ItemStatus.PENDING,
    )

    setup_session.add(item)
    setup_session.commit()
    setup_session.refresh(item)

    item_id = item.id

    setup_session.close()

    # ---------------------------------------------------------
    # 2. Run two concurrent processing requests
    # ---------------------------------------------------------
    # Both requests use exactly the same key.
    idempotency_key = "concurrent-key-001"
    barrier = threading.Barrier(2)

    results = []
    errors = []


    def worker():
        session = session_factory()

        try:
            barrier.wait()

            result = process_item(
                session,
                item_id,
                #idempotency_key,
            )

            results.append(result.item.status)

        except Exception as exc:
            errors.append(exc)

        finally:
            session.close()

    thread_1 = threading.Thread(target=worker)
    thread_2 = threading.Thread(target=worker)

    thread_1.start()
    thread_2.start()

    thread_1.join()
    thread_2.join()

    # ---------------------------------------------------------
    # 3. Both requests should complete successfully
    # ---------------------------------------------------------
    assert not errors
    assert len(results) == 2

    # ---------------------------------------------------------
    # 4. Verify the database state
    # ---------------------------------------------------------
    verification_session = session_factory()

    try:
        records = verification_session.execute(
            select(ProcessingRecord).where(
                ProcessingRecord.item_id == item_id
            )
        ).scalars().all()

        final_item = verification_session.get(
            Item,
            item_id,
        )

        # Only ONE actual processing operation should happen.
        assert len(records) == 1

        # That processing operation must succeed.
        assert records[0].status == "SUCCESS"

        # The item must finally be COMPLETED.
        assert final_item is not None
        assert final_item.status == ItemStatus.COMPLETED

    finally:
        verification_session.close()