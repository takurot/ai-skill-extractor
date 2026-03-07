from typing import Any, Dict, Optional

import httpx


class GithubClient:
    def __init__(self, token: str, base_url: str = "https://api.github.com"):
        self.token = token
        self.base_url = base_url
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            self._client = httpx.Client(base_url=self.base_url, headers=headers)
        return self._client

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> httpx.Response:
        client = self._get_client()
        response = client.get(endpoint, params=params)
        self._handle_rate_limit(response)
        response.raise_for_status()
        return response

    def _handle_rate_limit(self, response: httpx.Response) -> None:
        """
        Handle GitHub API rate limits.

        This is a placeholder for more robust token bucket and
        Retry-After handling to be implemented in the Collector.
        """
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining and int(remaining) < 10:
            # TODO: Add logging or sleep logic based on X-RateLimit-Reset
            pass

        if response.status_code == 403 and "Retry-After" in response.headers:
            # TODO: Handle secondary rate limits
            pass

    def close(self) -> None:
        if self._client:
            self._client.close()
