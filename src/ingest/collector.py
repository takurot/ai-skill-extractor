from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.ingest.github_client import GithubClient
from src.models.db import (
    RawIssueComment,
    RawPullRequest,
    RawReview,
    RawReviewComment,
    RepoSyncState,
    RequestCacheEntry,
)
from src.models.repos import RepoFilter, RepoLimits
from src.storage.database import upsert


@dataclass
class CollectionStats:
    pull_requests: int = 0
    reviews: int = 0
    review_comments: int = 0
    issue_comments: int = 0


@dataclass
class PullRequestPayload:
    detail: dict[str, Any]
    files: list[dict[str, Any]]
    review_comments: list[dict[str, Any]]
    reviews: list[dict[str, Any]]
    issue_comments: list[dict[str, Any]]


class Collector:
    def __init__(self, client: GithubClient, filters: RepoFilter, limits: RepoLimits):
        self.client = client
        self.filters = filters
        self.limits = limits

    def collect_repository(self, session: Session, repo: str) -> CollectionStats:
        """Fetch a repository's PR data and persist raw GitHub resources."""
        stats = CollectionStats()
        existing_state = session.get(RepoSyncState, repo)
        sync_cursor = self._normalize_datetime(
            existing_state.latest_pr_updated_at if existing_state else None
        )
        latest_seen_updated_at = sync_cursor

        list_endpoint = f"/repos/{repo}/pulls"
        list_params = {
            "state": "closed" if self.filters.merged_only else "all",
            "sort": "updated",
            "direction": "desc",
            "per_page": 100,
        }
        list_cache_key = self.client.build_cache_key(list_endpoint, list_params)
        list_etag = self._get_cached_etag(session, list_cache_key)

        first_page = True
        processed_prs = 0
        stop_iteration = False

        for page in self.client.paginate_json(list_endpoint, params=list_params, etag=list_etag):
            if first_page and page.not_modified:
                self._update_sync_state(session, repo, latest_seen_updated_at)
                return stats

            if first_page and page.etag:
                self._store_etag(session, list_cache_key, page.etag)
            first_page = False

            for summary in self._coerce_list(page.data):
                updated_at = self._parse_datetime(summary.get("updated_at"))
                if updated_at is None:
                    continue

                latest_seen_updated_at = self._max_datetime(latest_seen_updated_at, updated_at)

                if self.filters.until and updated_at.date() > self.filters.until:
                    continue

                if updated_at.date() < self.filters.since:
                    stop_iteration = True
                    break

                if sync_cursor and updated_at <= sync_cursor:
                    stop_iteration = True
                    break

                if processed_prs >= self.limits.max_prs_per_repo:
                    stop_iteration = True
                    break
                processed_prs += 1

                pr_number = int(summary["number"])
                payload = self._fetch_pull_request_payload(session, repo, pr_number)
                if payload is None:
                    continue

                self._persist_pull_request_payload(session, repo, payload)
                stats.pull_requests += 1
                stats.review_comments += len(payload.review_comments)
                stats.reviews += len(payload.reviews)
                stats.issue_comments += len(payload.issue_comments)

            if stop_iteration:
                break

        self._update_sync_state(session, repo, latest_seen_updated_at)
        return stats

    def _fetch_pull_request_payload(
        self,
        session: Session,
        repo: str,
        pr_number: int,
    ) -> PullRequestPayload | None:
        detail = self._fetch_single_resource(
            session,
            f"/repos/{repo}/pulls/{pr_number}",
            fallback_loader=lambda: self._load_saved_pr_detail(session, repo, pr_number),
        )
        if not detail:
            return None

        merged_at = self._parse_datetime(detail.get("merged_at"))
        if self.filters.merged_only and merged_at is None:
            return None

        reference_date = (
            merged_at
            if self.filters.merged_only
            else self._parse_datetime(detail.get("updated_at"))
            or self._parse_datetime(detail.get("created_at"))
        )
        if reference_date is None or not self._matches_date_filters(reference_date):
            return None

        if not self._matches_label_filters(detail):
            return None

        files = self._fetch_collection_resource(
            session,
            f"/repos/{repo}/pulls/{pr_number}/files",
            params={"per_page": 100},
            fallback_loader=lambda: self._load_saved_files(session, repo, pr_number),
            limit=self.limits.max_files_per_pr,
        )
        if not self._matches_file_filters(files):
            return None

        review_comments = self._fetch_collection_resource(
            session,
            f"/repos/{repo}/pulls/{pr_number}/comments",
            params={"per_page": 100},
            fallback_loader=lambda: self._load_saved_review_comments(session, repo, pr_number),
            limit=self.limits.max_comments_per_pr,
        )
        if len(review_comments) < self.filters.min_review_comments:
            return None

        reviews = []
        if self.filters.include_review_summaries:
            reviews = self._fetch_collection_resource(
                session,
                f"/repos/{repo}/pulls/{pr_number}/reviews",
                params={"per_page": 100},
                fallback_loader=lambda: self._load_saved_reviews(session, repo, pr_number),
                limit=self.limits.max_comments_per_pr,
            )

        issue_comments = []
        if self.filters.include_issue_comments:
            issue_comments = self._fetch_collection_resource(
                session,
                f"/repos/{repo}/issues/{pr_number}/comments",
                params={"per_page": 100},
                fallback_loader=lambda: self._load_saved_issue_comments(session, repo, pr_number),
                limit=self.limits.max_comments_per_pr,
            )

        detail_with_files = dict(detail)
        detail_with_files["files"] = files
        return PullRequestPayload(
            detail=detail_with_files,
            files=files,
            review_comments=review_comments,
            reviews=reviews,
            issue_comments=issue_comments,
        )

    def _fetch_single_resource(
        self,
        session: Session,
        endpoint: str,
        *,
        fallback_loader: Callable[[], dict[str, Any] | None],
        use_cache: bool = True,
    ) -> dict[str, Any] | None:
        cache_key = self.client.build_cache_key(endpoint)
        etag = self._get_cached_etag(session, cache_key) if use_cache else None
        response = self.client.get_json(endpoint, etag=etag)

        if response.not_modified:
            cached_resource = fallback_loader()
            if cached_resource is not None:
                return cached_resource
            return self._fetch_single_resource(
                session,
                endpoint,
                fallback_loader=fallback_loader,
                use_cache=False,
            )

        if response.etag:
            self._store_etag(session, cache_key, response.etag)
        return self._coerce_dict(response.data)

    def _fetch_collection_resource(
        self,
        session: Session,
        endpoint: str,
        *,
        params: dict[str, Any],
        fallback_loader: Callable[[], list[dict[str, Any]] | None],
        limit: int,
        use_cache: bool = True,
    ) -> list[dict[str, Any]]:
        cache_key = self.client.build_cache_key(endpoint, params)
        etag = self._get_cached_etag(session, cache_key) if use_cache else None

        items: list[dict[str, Any]] = []
        first_page = True
        for page in self.client.paginate_json(endpoint, params=params, etag=etag):
            if first_page and page.not_modified:
                cached_items = fallback_loader()
                if cached_items is not None:
                    return cached_items[:limit]
                return self._fetch_collection_resource(
                    session,
                    endpoint,
                    params=params,
                    fallback_loader=fallback_loader,
                    limit=limit,
                    use_cache=False,
                )

            if first_page and page.etag:
                self._store_etag(session, cache_key, page.etag)
            first_page = False

            items.extend(self._coerce_list(page.data))
            if len(items) >= limit:
                return items[:limit]

        return items

    def _persist_pull_request_payload(
        self,
        session: Session,
        repo: str,
        payload: PullRequestPayload,
    ) -> None:
        now = self._utcnow()
        detail = payload.detail
        merged_at = self._parse_datetime(detail.get("merged_at"))
        updated_at = self._parse_datetime(detail.get("updated_at")) or now

        upsert(
            session,
            RawPullRequest,
            {
                "id": str(detail["id"]),
                "repo": repo,
                "pr_number": int(detail["number"]),
                "state": str(detail.get("state", "closed")),
                "merged_at": merged_at,
                "changed_files_count": int(detail.get("changed_files", len(payload.files))),
                "raw_data": detail,
                "created_at": now,
                "updated_at": updated_at,
            },
        )

        for comment in payload.review_comments:
            upsert(
                session,
                RawReviewComment,
                {
                    "id": str(comment["id"]),
                    "repo": repo,
                    "pr_number": int(detail["number"]),
                    "comment_id": str(comment["id"]),
                    "path": str(comment.get("path", "")),
                    "diff_hunk": str(comment.get("diff_hunk", "")),
                    "body": str(comment.get("body", "")),
                    "raw_data": comment,
                    "created_at": self._parse_datetime(comment.get("created_at")) or now,
                },
            )

        for review in payload.reviews:
            upsert(
                session,
                RawReview,
                {
                    "id": str(review["id"]),
                    "repo": repo,
                    "pr_number": int(detail["number"]),
                    "review_id": str(review["id"]),
                    "state": str(review.get("state", "COMMENTED")),
                    "body": str(review.get("body", "")),
                    "raw_data": review,
                    "submitted_at": self._parse_datetime(review.get("submitted_at")) or now,
                },
            )

        for issue_comment in payload.issue_comments:
            upsert(
                session,
                RawIssueComment,
                {
                    "id": str(issue_comment["id"]),
                    "repo": repo,
                    "pr_number": int(detail["number"]),
                    "comment_id": str(issue_comment["id"]),
                    "body": str(issue_comment.get("body", "")),
                    "raw_data": issue_comment,
                    "created_at": self._parse_datetime(issue_comment.get("created_at")) or now,
                },
            )

    def _matches_date_filters(self, timestamp: datetime) -> bool:
        target_date = timestamp.date()
        if target_date < self.filters.since:
            return False
        if self.filters.until and target_date > self.filters.until:
            return False
        return True

    def _matches_label_filters(self, detail: dict[str, Any]) -> bool:
        labels = {
            str(label.get("name", "")).lower()
            for label in self._coerce_list(detail.get("labels", []))
            if isinstance(label, dict)
        }
        include = {label.lower() for label in self.filters.labels_include}
        exclude = {label.lower() for label in self.filters.labels_exclude}

        if include and not (labels & include):
            return False
        if exclude and labels & exclude:
            return False
        return True

    def _matches_file_filters(self, files: list[dict[str, Any]]) -> bool:
        extensions = tuple(self.filters.file_extensions)
        if not extensions:
            return True
        return any(str(file_info.get("filename", "")).endswith(extensions) for file_info in files)

    def _load_saved_pr_detail(
        self, session: Session, repo: str, pr_number: int
    ) -> dict[str, Any] | None:
        row = (
            session.query(RawPullRequest)
            .filter(
                RawPullRequest.repo == repo,
                RawPullRequest.pr_number == pr_number,
            )
            .one_or_none()
        )
        return row.raw_data if row else None

    def _load_saved_files(
        self, session: Session, repo: str, pr_number: int
    ) -> list[dict[str, Any]] | None:
        detail = self._load_saved_pr_detail(session, repo, pr_number)
        if detail is None:
            return None
        raw_files = detail.get("files") or []
        return [file_info for file_info in raw_files if isinstance(file_info, dict)]

    def _load_saved_review_comments(
        self, session: Session, repo: str, pr_number: int
    ) -> list[dict[str, Any]] | None:
        if self._load_saved_pr_detail(session, repo, pr_number) is None:
            return None
        rows = (
            session.query(RawReviewComment)
            .filter(
                RawReviewComment.repo == repo,
                RawReviewComment.pr_number == pr_number,
            )
            .all()
        )
        return [row.raw_data for row in rows]

    def _load_saved_reviews(
        self, session: Session, repo: str, pr_number: int
    ) -> list[dict[str, Any]] | None:
        if self._load_saved_pr_detail(session, repo, pr_number) is None:
            return None
        rows = (
            session.query(RawReview)
            .filter(
                RawReview.repo == repo,
                RawReview.pr_number == pr_number,
            )
            .all()
        )
        return [row.raw_data for row in rows]

    def _load_saved_issue_comments(
        self, session: Session, repo: str, pr_number: int
    ) -> list[dict[str, Any]] | None:
        if self._load_saved_pr_detail(session, repo, pr_number) is None:
            return None
        rows = (
            session.query(RawIssueComment)
            .filter(
                RawIssueComment.repo == repo,
                RawIssueComment.pr_number == pr_number,
            )
            .all()
        )
        return [row.raw_data for row in rows]

    def _get_cached_etag(self, session: Session, key: str) -> str | None:
        cache_entry = session.get(RequestCacheEntry, key)
        return cache_entry.etag if cache_entry else None

    def _store_etag(self, session: Session, key: str, etag: str) -> None:
        now = self._utcnow()
        existing = session.get(RequestCacheEntry, key)
        upsert(
            session,
            RequestCacheEntry,
            {
                "key": key,
                "etag": etag,
                "created_at": existing.created_at if existing else now,
                "updated_at": now,
            },
        )

    def _update_sync_state(
        self,
        session: Session,
        repo: str,
        latest_pr_updated_at: datetime | None,
    ) -> None:
        now = self._utcnow()
        existing = session.get(RepoSyncState, repo)
        upsert(
            session,
            RepoSyncState,
            {
                "repo": repo,
                "last_synced_at": now,
                "latest_pr_updated_at": latest_pr_updated_at
                or (existing.latest_pr_updated_at if existing else None),
                "created_at": existing.created_at if existing else now,
                "updated_at": now,
            },
        )

    def _coerce_list(self, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    def _coerce_dict(self, value: Any) -> dict[str, Any] | None:
        return value if isinstance(value, dict) else None

    def _parse_datetime(self, value: Any) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return self._normalize_datetime(parsed)

    def _normalize_datetime(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _max_datetime(
        self,
        current: datetime | None,
        candidate: datetime | None,
    ) -> datetime | None:
        if candidate is None:
            return current
        if current is None or candidate > current:
            return candidate
        return current

    def _utcnow(self) -> datetime:
        return datetime.now(timezone.utc)
