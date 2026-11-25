"""Short Hamburg data service outages are retried; longer ones get a clear message."""

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterator, List
from unittest.mock import patch

import pytest
import requests
from fastapi.testclient import TestClient
from urllib3.util.retry import Retry

from src.api.ogc_api.services.http_requests import HamburgOGCAPI
from src.api.ogc_api.utils.user_messages import (
    DATA_SERVICE_UNAVAILABLE_MESSAGE,
    to_user_error,
)
from src.api.web_app import create_app

pytestmark = [pytest.mark.unit]


HANG = 0
HANG_SECONDS = 1.0


class _Server:
    """Local HTTP server answering with the given status codes, then 200.

    ``HANG`` accepts the request and sends nothing for ``HANG_SECONDS``.
    """

    def __init__(self, statuses: List[int]):
        self.statuses = list(statuses)
        self.requests = 0
        server = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                server.requests += 1
                status = server.statuses.pop(0) if server.statuses else 200
                if status == HANG:
                    time.sleep(HANG_SECONDS)
                    return
                body = json.dumps({"type": "FeatureCollection", "features": []}).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/items"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def no_backoff(monkeypatch) -> Iterator[None]:
    monkeypatch.setattr(Retry, "sleep", lambda self, response=None: None)
    yield


def test_short_outage_is_retried(no_backoff):
    server = _Server([503, 502])
    try:
        data = HamburgOGCAPI.fetch_data(server.url, {"f": "json"})
    finally:
        server.close()
    assert data["type"] == "FeatureCollection"
    assert server.requests == 3


def test_lasting_outage_gives_the_unavailable_message(no_backoff):
    server = _Server([503] * 10)
    try:
        with pytest.raises(requests.HTTPError) as excinfo:
            HamburgOGCAPI.fetch_data(server.url, {"f": "json"})
    finally:
        server.close()
    assert server.requests == 4
    assert str(to_user_error(excinfo.value)) == DATA_SERVICE_UNAVAILABLE_MESSAGE


@pytest.fixture
def short_timeout(monkeypatch) -> Iterator[None]:
    monkeypatch.setattr(HamburgOGCAPI, "TIMEOUT", (1, 0.3))
    yield


def test_short_hang_is_retried_once(no_backoff, short_timeout):
    server = _Server([HANG])
    try:
        data = HamburgOGCAPI.fetch_data(server.url, {"f": "json"})
    finally:
        server.close()
    assert data["type"] == "FeatureCollection"
    assert server.requests == 2


def test_lasting_hang_gives_the_unavailable_message(no_backoff, short_timeout):
    server = _Server([HANG, HANG, HANG])
    try:
        with pytest.raises(requests.ConnectionError) as excinfo:
            HamburgOGCAPI.fetch_data(server.url, {"f": "json"})
    finally:
        server.close()
    assert server.requests == 2
    assert str(to_user_error(excinfo.value)) == DATA_SERVICE_UNAVAILABLE_MESSAGE


def test_client_errors_are_not_retried(no_backoff):
    server = _Server([400])
    try:
        with pytest.raises(requests.HTTPError):
            HamburgOGCAPI.fetch_data(server.url, {"f": "json"})
    finally:
        server.close()
    assert server.requests == 1


def test_data_endpoint_answers_503_when_the_service_is_down():
    client = TestClient(create_app())
    with patch(
        "src.api.data_api.oaf_endpoints.DataFetcher.fetch_tree_data",
        side_effect=requests.ConnectionError("connection refused"),
    ):
        response = client.get(
            "/data/bimfabrikhh-datasets/oaf-trees",
            params={"min_x": 9.9861, "min_y": 53.4867, "max_x": 9.9872, "max_y": 53.4872},
        )
    assert response.status_code == 503
    assert response.json()["detail"] == DATA_SERVICE_UNAVAILABLE_MESSAGE


def test_biotope_endpoint_answers_503_when_the_service_is_down():
    client = TestClient(create_app())
    with patch(
        "src.api.data_api.oaf_endpoints.HamburgOGCAPI.fetch_data",
        side_effect=requests.ConnectionError("connection refused"),
    ):
        response = client.get(
            "/data/bimfabrikhh-datasets/oaf-biotopes",
            params={"min_x": 9.9861, "min_y": 53.4867, "max_x": 9.9872, "max_y": 53.4872},
        )
    assert response.status_code == 503
    assert response.json()["detail"] == DATA_SERVICE_UNAVAILABLE_MESSAGE
