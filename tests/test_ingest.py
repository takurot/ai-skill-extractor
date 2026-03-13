from collections.abc import Generator
from datetime import date
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.ingest.collector import Collector
from src.ingest.github_client import GithubClient
from src.models.db import (
    Base,
    RawIssueComment,
    RawPullRequest,
    RawReview,
    RawReviewComment,
    RepoSyncState,
    RequestCacheEntry,
)
from src.models.repos import RepoFilter, RepoLimits


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


@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_github_client_retries_retry_after() -> None:
    request_count = 0
    sleep_calls: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        if request_count == 1:
            return httpx.Response(
                403,
                headers={"Retry-After": "0"},
                request=request,
            )
        return httpx.Response(200, json={"ok": True}, request=request)

    client = GithubClient(
        token="fake_token",
        transport=httpx.MockTransport(handler),
        sleep_fn=sleep_calls.append,
    )

    response = client.get_json("/rate-limited")

    assert response.data == {"ok": True}
    assert request_count == 2
    assert sleep_calls == [0.0]


def test_github_client_paginates_results() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("page") == "2":
            return httpx.Response(200, json=[{"id": 2}], request=request)
        return httpx.Response(
            200,
            json=[{"id": 1}],
            headers={"Link": '<https://api.github.com/items?page=2>; rel="next"'},
            request=request,
        )

    client = GithubClient(token="fake_token", transport=httpx.MockTransport(handler))

    pages = list(client.paginate_json("/items"))

    assert [page.data for page in pages] == [[{"id": 1}], [{"id": 2}]]


def test_collector_collects_filtered_data_and_updates_sync_state(session: Session) -> None:
    request_counts: dict[str, int] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        request_counts[path] = request_counts.get(path, 0) + 1

        if path == "/repos/example/project/pulls":
            return httpx.Response(
                200,
                json=[
                    {"number": 10, "updated_at": "2026-03-11T10:00:00Z"},
                    {"number": 11, "updated_at": "2026-03-10T08:00:00Z"},
                ],
                headers={"ETag": '"prs-v1"'},
                request=request,
            )

        if path == "/repos/example/project/pulls/10":
            return httpx.Response(
                200,
                json={
                    "id": 1010,
                    "number": 10,
                    "state": "closed",
                    "merged_at": "2026-03-11T09:30:00Z",
                    "updated_at": "2026-03-11T10:00:00Z",
                    "labels": [{"name": "bug"}],
                    "changed_files": 2,
                },
                headers={"ETag": '"pr-10"'},
                request=request,
            )

        if path == "/repos/example/project/pulls/10/files":
            return httpx.Response(
                200,
                json=[{"filename": "src/main.py"}, {"filename": "README.md"}],
                headers={"ETag": '"pr-10-files"'},
                request=request,
            )

        if path == "/repos/example/project/pulls/10/comments":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 201,
                        "path": "src/main.py",
                        "diff_hunk": "@@ -1 +1 @@\n-old\n+new",
                        "body": "Please add a test.",
                        "created_at": "2026-03-11T10:05:00Z",
                        "user": {"login": "reviewer1"},
                    },
                    {
                        "id": 202,
                        "path": "src/main.py",
                        "diff_hunk": "@@ -5 +5 @@\n-old\n+new",
                        "body": "Handle the error path too.",
                        "created_at": "2026-03-11T10:06:00Z",
                        "user": {"login": "reviewer2"},
                    },
                ],
                headers={"ETag": '"pr-10-comments"'},
                request=request,
            )

        if path == "/repos/example/project/pulls/10/reviews":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 301,
                        "state": "COMMENTED",
                        "body": "Looks mostly good.",
                        "submitted_at": "2026-03-11T10:07:00Z",
                        "user": {"login": "reviewer1"},
                    }
                ],
                headers={"ETag": '"pr-10-reviews"'},
                request=request,
            )

        if path == "/repos/example/project/issues/10/comments":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 401,
                        "body": "Added context in the PR thread.",
                        "created_at": "2026-03-11T10:08:00Z",
                        "user": {"login": "reviewer3"},
                    }
                ],
                headers={"ETag": '"pr-10-issue-comments"'},
                request=request,
            )

        if path == "/repos/example/project/pulls/11":
            return httpx.Response(
                200,
                json={
                    "id": 1011,
                    "number": 11,
                    "state": "closed",
                    "merged_at": "2026-03-10T07:30:00Z",
                    "updated_at": "2026-03-10T08:00:00Z",
                    "labels": [{"name": "bug"}],
                    "changed_files": 1,
                },
                headers={"ETag": '"pr-11"'},
                request=request,
            )

        if path == "/repos/example/project/pulls/11/files":
            return httpx.Response(
                200,
                json=[{"filename": "src/secondary.py"}],
                headers={"ETag": '"pr-11-files"'},
                request=request,
            )

        if path == "/repos/example/project/pulls/11/comments":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 211,
                        "path": "src/secondary.py",
                        "diff_hunk": "@@ -1 +1 @@\n-old\n+new",
                        "body": "One comment is not enough for the filter.",
                        "created_at": "2026-03-10T08:05:00Z",
                        "user": {"login": "reviewer1"},
                    }
                ],
                headers={"ETag": '"pr-11-comments"'},
                request=request,
            )

        if path == "/repos/example/project/pulls/11/reviews":
            return httpx.Response(
                200,
                json=[],
                headers={"ETag": '"pr-11-reviews"'},
                request=request,
            )

        if path == "/repos/example/project/issues/11/comments":
            return httpx.Response(
                200,
                json=[],
                headers={"ETag": '"pr-11-issue-comments"'},
                request=request,
            )

        raise AssertionError(f"Unexpected request path: {path}")

    collector = Collector(
        client=GithubClient(token="fake_token", transport=httpx.MockTransport(handler)),
        filters=RepoFilter(
            since=date(2026, 3, 1),
            merged_only=True,
            min_review_comments=2,
            labels_include=["bug"],
            file_extensions=[".py"],
        ),
        limits=RepoLimits(max_prs_per_repo=10, max_comments_per_pr=10, max_files_per_pr=10),
    )

    stats = collector.collect_repository(session, "example/project")
    session.commit()

    assert stats.pull_requests == 1
    assert stats.reviews == 1
    assert stats.review_comments == 2
    assert stats.issue_comments == 1
    assert session.query(RawPullRequest).count() == 1
    assert session.query(RawReviewComment).count() == 2
    assert session.query(RawReview).count() == 1
    assert session.query(RawIssueComment).count() == 1
    assert session.query(RequestCacheEntry).count() >= 5

    saved_pr = session.query(RawPullRequest).filter_by(pr_number=10).one()
    assert saved_pr.changed_files_count == 2
    sync_state = session.get(RepoSyncState, "example/project")
    assert sync_state is not None
    assert sync_state.latest_pr_updated_at is not None
    assert sync_state.latest_pr_updated_at.isoformat().startswith("2026-03-11T10:00:00")
    assert request_counts["/repos/example/project/pulls/10/comments"] == 1
    assert request_counts["/repos/example/project/pulls/11/comments"] == 1


def test_collector_uses_conditional_requests_for_unchanged_repo(session: Session) -> None:
    request_counts: dict[str, int] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        request_counts[path] = request_counts.get(path, 0) + 1

        if path == "/repos/example/project/pulls":
            if request.headers.get("If-None-Match") == '"prs-v1"':
                return httpx.Response(304, headers={"ETag": '"prs-v1"'}, request=request)
            return httpx.Response(
                200,
                json=[{"number": 10, "updated_at": "2026-03-11T10:00:00Z"}],
                headers={"ETag": '"prs-v1"'},
                request=request,
            )

        if path == "/repos/example/project/pulls/10":
            return httpx.Response(
                200,
                json={
                    "id": 1010,
                    "number": 10,
                    "state": "closed",
                    "merged_at": "2026-03-11T09:30:00Z",
                    "updated_at": "2026-03-11T10:00:00Z",
                    "labels": [{"name": "bug"}],
                    "changed_files": 1,
                },
                headers={"ETag": '"pr-10"'},
                request=request,
            )

        if path == "/repos/example/project/pulls/10/files":
            return httpx.Response(
                200,
                json=[{"filename": "src/main.py"}],
                headers={"ETag": '"pr-10-files"'},
                request=request,
            )

        if path == "/repos/example/project/pulls/10/comments":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 201,
                        "path": "src/main.py",
                        "diff_hunk": "@@ -1 +1 @@\n-old\n+new",
                        "body": "Please add a test.",
                        "created_at": "2026-03-11T10:05:00Z",
                        "user": {"login": "reviewer1"},
                    },
                    {
                        "id": 202,
                        "path": "src/main.py",
                        "diff_hunk": "@@ -5 +5 @@\n-old\n+new",
                        "body": "Handle the error path too.",
                        "created_at": "2026-03-11T10:06:00Z",
                        "user": {"login": "reviewer2"},
                    },
                ],
                headers={"ETag": '"pr-10-comments"'},
                request=request,
            )

        if path == "/repos/example/project/pulls/10/reviews":
            return httpx.Response(
                200,
                json=[],
                headers={"ETag": '"pr-10-reviews"'},
                request=request,
            )

        if path == "/repos/example/project/issues/10/comments":
            return httpx.Response(
                200,
                json=[],
                headers={"ETag": '"pr-10-issue-comments"'},
                request=request,
            )

        raise AssertionError(f"Unexpected request path: {path}")

    collector = Collector(
        client=GithubClient(token="fake_token", transport=httpx.MockTransport(handler)),
        filters=RepoFilter(since=date(2026, 3, 1), min_review_comments=2, file_extensions=[".py"]),
        limits=RepoLimits(max_prs_per_repo=10, max_comments_per_pr=10, max_files_per_pr=10),
    )

    first_stats = collector.collect_repository(session, "example/project")
    session.commit()
    first_detail_calls = request_counts.get("/repos/example/project/pulls/10", 0)

    second_stats = collector.collect_repository(session, "example/project")
    session.commit()

    assert first_stats.pull_requests == 1
    assert second_stats.pull_requests == 0
    assert request_counts["/repos/example/project/pulls"] == 2
    assert request_counts["/repos/example/project/pulls/10"] == first_detail_calls


def test_collector_max_prs_per_repo_counts_persisted_matches(session: Session) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path

        if path == "/repos/example/project/pulls":
            return httpx.Response(
                200,
                json=[
                    {"number": 10, "updated_at": "2026-03-12T10:00:00Z"},
                    {"number": 11, "updated_at": "2026-03-11T10:00:00Z"},
                ],
                request=request,
            )
        if path == "/repos/example/project/pulls/10":
            return httpx.Response(
                200,
                json={
                    "id": 1010,
                    "number": 10,
                    "state": "closed",
                    "merged_at": "2026-03-12T09:00:00Z",
                    "updated_at": "2026-03-12T10:00:00Z",
                    "labels": [{"name": "docs"}],
                    "changed_files": 1,
                },
                request=request,
            )
        if path == "/repos/example/project/pulls/11":
            return httpx.Response(
                200,
                json={
                    "id": 1011,
                    "number": 11,
                    "state": "closed",
                    "merged_at": "2026-03-11T09:00:00Z",
                    "updated_at": "2026-03-11T10:00:00Z",
                    "labels": [{"name": "bug"}],
                    "changed_files": 1,
                },
                request=request,
            )
        if path == "/repos/example/project/pulls/11/files":
            return httpx.Response(
                200,
                json=[{"filename": "src/main.py"}],
                request=request,
            )
        if path == "/repos/example/project/pulls/11/comments":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 211,
                        "path": "src/main.py",
                        "diff_hunk": "@@ -1 +1 @@\n-old\n+new",
                        "body": "Please add a test.",
                        "created_at": "2026-03-11T10:05:00Z",
                    },
                    {
                        "id": 212,
                        "path": "src/main.py",
                        "diff_hunk": "@@ -5 +5 @@\n-old\n+new",
                        "body": "Handle the error path too.",
                        "created_at": "2026-03-11T10:06:00Z",
                    },
                ],
                request=request,
            )

        raise AssertionError(f"Unexpected request path: {path}")

    collector = Collector(
        client=GithubClient(token="fake_token", transport=httpx.MockTransport(handler)),
        filters=RepoFilter(
            since=date(2026, 3, 1),
            merged_only=True,
            min_review_comments=2,
            include_issue_comments=False,
            include_review_summaries=False,
            labels_include=["bug"],
            file_extensions=[".py"],
        ),
        limits=RepoLimits(max_prs_per_repo=1, max_comments_per_pr=10, max_files_per_pr=10),
    )

    stats = collector.collect_repository(session, "example/project")
    session.commit()

    assert stats.pull_requests == 1
    saved_pr = session.query(RawPullRequest).one()
    assert saved_pr.pr_number == 11


def test_collector_file_extension_filter_scans_beyond_persist_limit(session: Session) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path

        if path == "/repos/example/project/pulls":
            return httpx.Response(
                200,
                json=[{"number": 10, "updated_at": "2026-03-12T10:00:00Z"}],
                request=request,
            )
        if path == "/repos/example/project/pulls/10":
            return httpx.Response(
                200,
                json={
                    "id": 1010,
                    "number": 10,
                    "state": "closed",
                    "merged_at": "2026-03-12T09:00:00Z",
                    "updated_at": "2026-03-12T10:00:00Z",
                    "labels": [{"name": "bug"}],
                    "changed_files": 2,
                },
                request=request,
            )
        if path == "/repos/example/project/pulls/10/files":
            return httpx.Response(
                200,
                json=[
                    {"filename": "README.md"},
                    {"filename": "src/main.py"},
                ],
                request=request,
            )
        if path == "/repos/example/project/pulls/10/comments":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 201,
                        "path": "src/main.py",
                        "diff_hunk": "@@ -1 +1 @@\n-old\n+new",
                        "body": "Please add a test.",
                        "created_at": "2026-03-12T10:05:00Z",
                    },
                    {
                        "id": 202,
                        "path": "src/main.py",
                        "diff_hunk": "@@ -5 +5 @@\n-old\n+new",
                        "body": "Handle the error path too.",
                        "created_at": "2026-03-12T10:06:00Z",
                    },
                ],
                request=request,
            )

        raise AssertionError(f"Unexpected request path: {path}")

    collector = Collector(
        client=GithubClient(token="fake_token", transport=httpx.MockTransport(handler)),
        filters=RepoFilter(
            since=date(2026, 3, 1),
            merged_only=True,
            min_review_comments=2,
            include_issue_comments=False,
            include_review_summaries=False,
            labels_include=["bug"],
            file_extensions=[".py"],
        ),
        limits=RepoLimits(max_prs_per_repo=10, max_comments_per_pr=10, max_files_per_pr=1),
    )

    stats = collector.collect_repository(session, "example/project")
    session.commit()

    assert stats.pull_requests == 1
    saved_pr = session.query(RawPullRequest).one()
    assert saved_pr.changed_files_count == 2
    assert saved_pr.raw_data["files"] == [{"filename": "README.md"}]
