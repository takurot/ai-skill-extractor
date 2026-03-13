from __future__ import annotations

import time
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class GithubApiResponse:
    data: Any | None
    etag: str | None
    next_url: str | None
    not_modified: bool = False


class GithubClient:
    def __init__(
        self,
        token: str,
        base_url: str = "https://api.github.com",
        *,
        timeout: float = 30.0,
        max_retries: int = 3,
        sleep_fn: Callable[[float], None] | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        self.token = token
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.sleep_fn = sleep_fn or time.sleep
        self.transport = transport
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            self._client = httpx.Client(
                base_url=self.base_url,
                headers=headers,
                timeout=self.timeout,
                transport=self.transport,
            )
        return self._client

    def build_cache_key(self, endpoint: str, params: Mapping[str, Any] | None = None) -> str:
        base_url = httpx.URL(self.base_url)
        url = httpx.URL(endpoint) if endpoint.startswith("http") else base_url.join(endpoint)
        if not params:
            return str(url)

        query_params: list[tuple[str, str | int | float | bool | None]] = []
        for key, value in sorted(params.items(), key=lambda item: item[0]):
            if isinstance(value, list):
                for item in value:
                    query_params.append((key, str(item)))
            else:
                query_params.append((key, str(value)))
        return str(url.copy_merge_params(query_params))

    def get_json(
        self,
        endpoint: str,
        *,
        params: Mapping[str, Any] | None = None,
        etag: str | None = None,
    ) -> GithubApiResponse:
        request_headers = {"If-None-Match": etag} if etag else None
        response = self._request(
            endpoint,
            params=params,
            headers=request_headers,
            allow_not_modified=True,
        )
        if response.status_code == 304:
            return GithubApiResponse(
                data=None,
                etag=etag,
                next_url=None,
                not_modified=True,
            )

        next_url = response.links.get("next", {}).get("url")
        return GithubApiResponse(
            data=response.json(),
            etag=response.headers.get("ETag"),
            next_url=next_url,
        )

    def paginate_json(
        self,
        endpoint: str,
        *,
        params: Mapping[str, Any] | None = None,
        etag: str | None = None,
    ) -> Iterator[GithubApiResponse]:
        current_endpoint = endpoint
        current_params = params
        current_etag = etag

        while True:
            page = self.get_json(
                current_endpoint,
                params=current_params,
                etag=current_etag,
            )
            yield page
            if page.not_modified or not page.next_url:
                return
            current_endpoint = page.next_url
            current_params = None
            current_etag = None

    def _request(
        self,
        endpoint: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        allow_not_modified: bool = False,
    ) -> httpx.Response:
        client = self._get_client()

        for attempt in range(self.max_retries + 1):
            response = client.get(endpoint, params=params, headers=headers)
            if response.is_success:
                return response
            if allow_not_modified and response.status_code == 304:
                return response

            retry_after = self._calculate_retry_delay(response, attempt)
            if retry_after is not None and attempt < self.max_retries:
                self.sleep_fn(retry_after)
                continue

            response.raise_for_status()

        raise RuntimeError("GitHub request failed after exhausting retries.")

    def _calculate_retry_delay(self, response: httpx.Response, attempt: int) -> float | None:
        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return float(retry_after)
            except ValueError:
                return None

        remaining = response.headers.get("X-RateLimit-Remaining")
        reset = response.headers.get("X-RateLimit-Reset")
        if remaining == "0" and reset:
            try:
                wait_seconds = float(reset) - time.time()
            except ValueError:
                wait_seconds = 0.0
            return max(wait_seconds, 0.0)

        if response.status_code in {403, 429, 500, 502, 503, 504}:
            return float(2**attempt)

        return None

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
