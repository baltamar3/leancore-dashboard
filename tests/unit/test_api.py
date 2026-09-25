import fakeredis
import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError as RedisConnectionError

from src.api.app import app, get_redis, settings


class BrokenRedis:
    def pipeline(self, *args, **kwargs):
        raise RedisConnectionError("redis down")


@pytest.fixture
def fake_redis():
    return fakeredis.FakeAsyncRedis()


@pytest.fixture
def client(fake_redis):
    app.dependency_overrides[get_redis] = lambda: fake_redis
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_metrics_endpoint_returns_requested_window(client):
    response = client.get("/metrics/payments?minutes=5")

    assert response.status_code == 200
    body = response.json()
    assert body["minutes"] == 5
    assert len(body["buckets"]) == 5
    assert all(bucket["processed"] == 0 and bucket["failed"] == 0 for bucket in body["buckets"])


def test_metrics_endpoint_uses_default_when_minutes_omitted(client):
    response = client.get("/metrics/payments")

    assert response.status_code == 200
    assert response.json()["minutes"] == settings.default_metrics_minutes


@pytest.mark.parametrize("minutes", ["0", "-1", "not-a-number", "999999"])
def test_metrics_endpoint_rejects_invalid_minutes(client, minutes):
    response = client.get(f"/metrics/payments?minutes={minutes}")

    assert response.status_code == 422


def test_metrics_endpoint_returns_503_when_storage_unavailable():
    app.dependency_overrides[get_redis] = lambda: BrokenRedis()
    try:
        with TestClient(app) as client:
            response = client.get("/metrics/payments")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503


def test_dashboard_page_loads(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "/metrics/payments" in response.text


def test_dashboard_page_has_time_window_selector_and_both_views(client):
    response = client.get("/")

    body = response.text
    assert 'data-minutes="5"' in body
    assert 'data-minutes="15"' in body
    assert 'data-minutes="30"' in body
    assert 'data-minutes="60"' in body
    assert 'id="custom-minutes"' in body
    assert f'max="{settings.max_metrics_minutes}"' in body

    assert 'id="view-timeseries"' in body
    assert 'id="view-aggregate"' in body
    assert 'data-view="timeseries"' in body
    assert 'data-view="aggregate"' in body
