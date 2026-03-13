from datetime import date

from pydantic import BaseModel, Field


class RepoFilter(BaseModel):
    merged_only: bool = True
    since: date = date(2023, 1, 1)
    until: date | None = None
    min_review_comments: int = 2
    include_issue_comments: bool = True
    include_review_summaries: bool = True
    include_followup_commits: bool = True
    labels_include: list[str] = Field(default_factory=list)
    labels_exclude: list[str] = Field(default_factory=list)
    file_extensions: list[str] = Field(default_factory=lambda: [".py", ".ts", ".tsx", ".cpp", ".h"])


class RepoLimits(BaseModel):
    max_prs_per_repo: int = 5000
    max_comments_per_pr: int = 500
    max_files_per_pr: int = 200
    max_parallel_repos: int = 1


class ReposConfig(BaseModel):
    repos: list[str]
    filters: RepoFilter = Field(default_factory=RepoFilter)
    limits: RepoLimits = Field(default_factory=RepoLimits)
