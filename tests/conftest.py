import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session, sessionmaker

from app.config import TEST_DATABASE_URL
from app.database import Base
from app.models import Item


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
    )


@pytest.fixture
def db_session(test_engine):
    session = Session(test_engine)

    # Clean data left by previous test runs.
    session.execute(delete(Item))
    session.commit()

    try:
        yield session
    finally:
        session.rollback()

        # Clean up after the test as well.
        session.execute(delete(Item))
        session.commit()

        session.close()