import json
import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import (
    IdempotencyRecord,
    Item,
    ItemStatus,
    ProcessingRecord,
)
from app.services.idempotency import (
    IdempotencyConflictError,
    deserialize_response,
    generate_request_hash,
)


@dataclass
class ProcessResult:
    item: Item
    response: dict
    replayed: bool = False


def create_item(
    db: Session,
    item_data,
) -> Item:
    item = Item(
        name=item_data.name,
        amount=item_data.amount,
        status=ItemStatus.PENDING,
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    return item


def get_item(
    db: Session,
    item_id: int,
) -> Item | None:
    return (
        db.query(Item)
        .filter(Item.id == item_id)
        .first()
    )


def get_item_for_update(
    db: Session,
    item_id: int,
) -> Item | None:
    return (
        db.query(Item)
        .filter(Item.id == item_id)
        .with_for_update()
        .first()
    )


def process_item(
    db: Session,
    item_id: int,
    idempotency_key: str | None = None,
) -> ProcessResult:

    # =========================================================
    # 1. Check idempotency record
    # =========================================================

    request_hash = None

    if idempotency_key:
        request_hash = generate_request_hash(item_id)

        existing_record = (
            db.query(IdempotencyRecord)
            .filter(
                IdempotencyRecord.idempotency_key
                == idempotency_key
            )
            .first()
        )

        if existing_record:

            # Same key but different request
            if existing_record.request_hash != request_hash:
                raise IdempotencyConflictError(
                    "Idempotency key was already used "
                    "for a different request"
                )

            # Same key + same request = retry
            if existing_record.response:
                response = deserialize_response(
                    existing_record.response
                )

                item = get_item(
                    db,
                    existing_record.item_id,
                )

                if item is None:
                    raise ValueError("Item not found")

                return ProcessResult(
                    item=item,
                    response=response,
                    replayed=True,
                )

    # =========================================================
    # 2. Lock the item
    # =========================================================

    item = get_item_for_update(
        db,
        item_id,
    )

    if item is None:
        raise ValueError("Item not found")

    # =========================================================
    # 3. Check if already completed
    # =========================================================

    if item.status == ItemStatus.COMPLETED:

        response = {
            "item_id": item.id,
            "status": item.status.value,
            "message": "Item processed successfully",
        }

        return ProcessResult(
            item=item,
            response=response,
            replayed=False,
        )

    # =========================================================
    # 4. Mark item as processing
    # =========================================================

    item.status = ItemStatus.PROCESSING

    # =========================================================
    # 5. Create idempotency record
    # =========================================================

    idempotency_record = None

    if idempotency_key:

        idempotency_record = IdempotencyRecord(
            idempotency_key=idempotency_key,
            item_id=item.id,
            request_hash=request_hash,
            status="PROCESSING",
        )

        db.add(idempotency_record)

    # =========================================================
    # 6. Create business processing record
    # =========================================================

    processing_record = ProcessingRecord(
        item_id=item.id,
        status="STARTED",
    )

    db.add(processing_record)

    # =========================================================
    # 7. Simulate business processing
    # =========================================================

    time.sleep(2)

    # =========================================================
    # 8. Complete processing
    # =========================================================

    processing_record.status = "SUCCESS"

    item.status = ItemStatus.COMPLETED

    # =========================================================
    # 9. Build API response
    # =========================================================

    response = {
        "item_id": item.id,
        "status": item.status.value,
        "message": "Item processed successfully",
    }

    # =========================================================
    # 10. Store exact response for idempotent replay
    # =========================================================

    if idempotency_record:

        idempotency_record.status = "COMPLETED"

        idempotency_record.response = json.dumps(
            response
        )

    # =========================================================
    # 11. Commit everything atomically
    # =========================================================

    db.commit()
    db.refresh(item)

    return ProcessResult(
        item=item,
        response=response,
        replayed=False,
    )