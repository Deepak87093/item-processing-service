from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schema.item import ItemCreate, ItemResponse, ItemProcessResponse
from app.services.item_processor import create_item, get_item, process_item
from app.services.idempotency import IdempotencyConflictError
from fastapi import Header


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
    idempotency_key: str | None = Header(
        default=None,
        alias="Idempotency-Key",
    ),
    db: Session = Depends(get_db),
):
    try:
        item = process_item(
            db,
            item_id,
            idempotency_key,
        )

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found",
        )

    except IdempotencyConflictError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Idempotency key was already used "
                "for a different request"
            ),
        )

    return ItemProcessResponse(
        item_id=item.id,
        status=item.status,
        message="Item processed successfully",
    )