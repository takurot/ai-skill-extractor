from typing import List, Optional

from pydantic import BaseModel, Field


class RepoFilter(BaseModel):
    merged_only: bool = True
    since: str = "2023-01-01"
    until: Optional[str] = None
    min_review_comments: int = 2
    include_issue_comments: bool = True
    include_review_summaries: bool = True
    include_followup_commits: bool = True
    labels_include: List[str] = Field(default_factory=list)
    labels_exclude: List[str] = Field(default_factory=list)
    file_extensions: List[str] = Field(default_factory=lambda: [".py", ".ts", ".tsx", ".cpp", ".h"])


class RepoLimits(BaseModel):
    max_prs_per_repo: int = 5000
    max_comments_per_pr: int = 500
    max_files_per_pr: int = 200


class ReposConfig(BaseModel):
    repos: List[str]
    filters: RepoFilter = Field(default_factory=RepoFilter)
    limits: RepoLimits = Field(default_factory=RepoLimits)
