import threading

from app.models import Item, ItemStatus
from app.services.item_processor import process_item


def test_concurrent_processing(
    test_engine,
    session_factory,
):
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

    results = []
    errors = []

    def worker():
        session = session_factory()

        try:
            result = process_item(session, item_id)
            results.append(result.status)
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

    assert not errors
    assert len(results) == 2