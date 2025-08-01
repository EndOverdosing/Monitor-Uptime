import pytest
from unittest.mock import AsyncMock, patch
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from models import Base, URL
from main import app
from crud import get_all_urls, get_logs_for_url

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

client = TestClient(app)

@pytest.fixture
def db_session():
    """Create a new database session for a test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()

@pytest.mark.asyncio
@patch('main.check_single_url', new_callable=AsyncMock)
async def test_run_all_checks(mock_check_single_url, db_session):
    """
    Tests if run_all_checks function calls check_single_url for each URL in the database.
    """
    from main import run_all_checks

    db_session.add(URL(url="https://testsite1.com", submitted_by_ip="1.1.1.1"))
    db_session.add(URL(url="https://testsite2.com", submitted_by_ip="2.2.2.2"))
    db_session.commit()

    await run_all_checks(db_session)

    assert mock_check_single_url.call_count == 2
    print("\n✅ test_run_all_checks: Passed")

@pytest.mark.asyncio
async def test_check_single_url_success(db_session):
    """
    Tests the check_single_url function for a successful HTTP response.
    """
    from main import check_single_url

    test_url = URL(url="https://successfulsite.com", submitted_by_ip="1.2.3.4")
    db_session.add(test_url)
    db_session.commit()
    db_session.refresh(test_url)

    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value.status_code = 200
        mock_get.return_value.raise_for_status = lambda: None 

        await check_single_url(db_session, test_url)

    logs = get_logs_for_url(db_session, url_id=test_url.id)
    assert len(logs) == 1
    assert logs[0].is_up is True
    assert logs[0].status_code == 200
    print("✅ test_check_single_url_success: Passed")

@pytest.mark.asyncio
async def test_check_single_url_http_error(db_session):
    """
    Tests the check_single_url function for a failed (404) HTTP response.
    """
    from main import check_single_url

    test_url = URL(url="https://failedsite.com", submitted_by_ip="5.6.7.8")
    db_session.add(test_url)
    db_session.commit()
    db_session.refresh(test_url)

    with patch('httpx.AsyncClient.get', new_callable=AsyncMock) as mock_get:
        mock_response = httpx.Response(status_code=404, request=httpx.Request('GET', 'https://failedsite.com'))
        mock_get.side_effect = httpx.HTTPStatusError(message="Not Found", request=mock_response.request, response=mock_response)

        await check_single_url(db_session, test_url)

    logs = get_logs_for_url(db_session, url_id=test_url.id)
    assert len(logs) == 1
    assert logs[0].is_up is False
    assert logs[0].status_code == 404
    assert "HTTP Error: 404" in logs[0].error_message
    print("✅ test_check_single_url_http_error: Passed")