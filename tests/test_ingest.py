from typing import Any
from unittest.mock import patch

from src.ingest.github_client import GithubClient


def test_github_client_init() -> None:
    client = GithubClient(token="fake_token")
    assert client.token == "fake_token"
    assert client.base_url == "https://api.github.com"


@patch("src.ingest.github_client.httpx.Client")
def test_github_client_headers(mock_client: Any) -> None:
    client = GithubClient(token="fake_token")
    client._get_client()  # initialize client
    mock_client.assert_called_once()
    call_kwargs = mock_client.call_args.kwargs
    assert "Authorization" in call_kwargs.get("headers", {})
    assert call_kwargs["headers"]["Authorization"] == "Bearer fake_token"
    assert call_kwargs["headers"]["Accept"] == "application/vnd.github+json"
