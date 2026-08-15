from fastapi import FastAPI
from sqlalchemy import text

from app.api.items import router as items_router
from app.database import engine


app = FastAPI(
    title="Item Processing Service",
    version="1.0.0",
)


app.include_router(items_router)


@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }


@app.get("/health/db")
def database_health_check():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))

    return {
        "database": result.scalar_one()
    }