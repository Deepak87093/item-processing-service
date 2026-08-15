from sqlalchemy.orm import Session

from app.models.item import Item, ItemStatus
from app.models import ProcessingRecord
from app.schema.item import ItemCreate
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
) -> Item:
    item = get_item_for_update(db, item_id)

    if item is None:
        raise ValueError("Item not found")

    if item.status == ItemStatus.COMPLETED:
        return item

    item.status = ItemStatus.PROCESSING

    processing_record = ProcessingRecord(
        item_id=item.id,
        status="STARTED",
    )

    db.add(processing_record)

    # Simulate expensive business processing.
    time.sleep(2)

    processing_record.status = "SUCCESS"
    item.status = ItemStatus.COMPLETED

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