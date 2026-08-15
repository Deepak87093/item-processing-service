from decimal import Decimal

from app.models.item import ItemStatus, Item
from app.schema.item import ItemCreate
from app.services.item_processor import create_item


def test_create_item(db_session):
    item_data = ItemCreate(
        name="Laptop",
        amount=Decimal("85000.00"),
    )

    item = create_item(db_session, item_data)

    assert item.id is not None
    assert item.name == "Laptop"
    assert item.amount == Decimal("85000.00")
    assert item.status == ItemStatus.PENDING


def test_database_is_isolated(db_session):
    items = db_session.query(Item).all()

    assert items == []