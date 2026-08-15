from sqlalchemy.orm import Session
import json
from app.models.item import Item, ItemStatus
from app.models import ProcessingRecord
from app.schema.item import ItemCreate
from app.models.idempotency import IdempotencyRecord
from app.services.idempotency import (
    IdempotencyConflictError,
    generate_request_hash
)
import time



def create_item(
    db: Session,
    item_data: ItemCreate,
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

def process_item(
    db: Session,
    item_id: int,
    idempotency_key: str | None = None,
) -> Item:
    request_hash = None

    # ---------------------------------------------------------
    # 1. Check idempotency key
    # ---------------------------------------------------------
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
            if existing_record.request_hash != request_hash:
                raise IdempotencyConflictError(
                    "Idempotency key was already used "
                    "for a different request"
                )

            return get_item(db, existing_record.item_id)

    # ---------------------------------------------------------
    # 2. Lock the item
    # ---------------------------------------------------------
    item = get_item_for_update(db, item_id)

    if item is None:
        raise ValueError("Item not found")

    # ---------------------------------------------------------
    # 3. Check whether already completed
    # ---------------------------------------------------------
    if item.status == ItemStatus.COMPLETED:
        return item

    item.status = ItemStatus.PROCESSING

    # ---------------------------------------------------------
    # 4. Store idempotency record
    # ---------------------------------------------------------
    if idempotency_key:
        idempotency_record = IdempotencyRecord(
            idempotency_key=idempotency_key,
            item_id=item.id,
            request_hash=request_hash,
            status="PROCESSING",
        )

        db.add(idempotency_record)

    # ---------------------------------------------------------
    # 5. Record business processing
    # ---------------------------------------------------------
    processing_record = ProcessingRecord(
        item_id=item.id,
        status="STARTED",
    )

    db.add(processing_record)

    # ---------------------------------------------------------
    # 6. Simulate business operation
    # ---------------------------------------------------------
    time.sleep(2)

    # ---------------------------------------------------------
    # 7. Complete processing
    # ---------------------------------------------------------
    processing_record.status = "SUCCESS"

    item.status = ItemStatus.COMPLETED

    if idempotency_key:
        idempotency_record.status = "COMPLETED"
        idempotency_record.response = json.dumps(
            {
                "item_id": item.id,
                "status": item.status.value,
                "message": "Item processed successfully",
            }
        )

    db.commit()
    db.refresh(item)

    return item

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