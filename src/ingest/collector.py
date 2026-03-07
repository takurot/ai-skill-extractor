from typing import Any, Dict, Generator

from src.ingest.github_client import GithubClient
from src.models.repos import RepoFilter, RepoLimits


class Collector:
    def __init__(self, client: GithubClient, filters: RepoFilter, limits: RepoLimits):
        self.client = client
        self.filters = filters
        self.limits = limits

    def fetch_prs(self, repo: str) -> Generator[Dict[str, Any], None, None]:
        """Fetch PRs based on configuration filters."""
        # TODO: Implement actual GitHub API call with pagination and filtering
        # Example endpoint: f"/repos/{repo}/pulls?state=all&sort=updated&direction=desc"
        # This is a stub returning empty generator for now
        yield from []

    def fetch_comments(self, repo: str, pr_number: int) -> Generator[Dict[str, Any], None, None]:
        """Fetch review comments for a specific PR."""
        # TODO: Implement actual GitHub API call with pagination
        # Example endpoint: f"/repos/{repo}/pulls/{pr_number}/comments"
        yield from []
