from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.item import ItemStatus


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=0)


class ItemResponse(BaseModel):
    id: int
    name: str
    amount: Decimal
    status: ItemStatus

    model_config = {
        "from_attributes": True,
    }


class ItemProcessResponse(BaseModel):
    item_id: int
    status: ItemStatus
    message: str