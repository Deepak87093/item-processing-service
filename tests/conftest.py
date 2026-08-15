import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session, sessionmaker

from app.config import TEST_DATABASE_URL
from app.database import Base
from app.models import Item, ProcessingRecord


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True,
    )

    Base.metadata.create_all(bind=engine)

    yield engine

    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="session")
def session_factory(test_engine):
    return sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


def clean_database(session: Session) -> None:
    """
    Clean test data in the correct foreign-key order.

    processing_records references items, so the child table
    must be deleted before the parent table.
    """

    session.execute(delete(ProcessingRecord))
    session.execute(delete(Item))
    session.commit()


@pytest.fixture(autouse=True)
def clean_test_database(test_engine):
    """
    Automatically clean the test database before and after
    every test.
    """

    session = Session(test_engine)

    try:
        clean_database(session)
    finally:
        session.close()

    yield

    session = Session(test_engine)

    try:
        clean_database(session)
    finally:
        session.close()


@pytest.fixture
def db_session(test_engine):
    """
    Database session for normal tests.
    """

    session = Session(test_engine)

    try:
        yield session
    finally:
        session.rollback()
        session.close()