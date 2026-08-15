from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schema.item import ItemCreate, ItemResponse, ItemProcessResponse
from app.services.item_processor import create_item, get_item, process_item


router = APIRouter(
    prefix="/items",
    tags=["Items"],
)


@router.post(
    "",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_item_endpoint(
    item_data: ItemCreate,
    db: Session = Depends(get_db),
):
    return create_item(db, item_data)


@router.get(
    "/{item_id}",
    response_model=ItemResponse,
)
def get_item_endpoint(
    item_id: int,
    db: Session = Depends(get_db),
):
    item = get_item(db, item_id)

    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    return item


@router.post(
    "/{item_id}/process",
    response_model=ItemProcessResponse,
)
def process_item_endpoint(
    item_id: int,
    db: Session = Depends(get_db),
):
    try:
        item = process_item(db, item_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    return ItemProcessResponse(
        item_id=item.id,
        status=item.status,
        message="Item processed successfully",
    )