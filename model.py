"""
Data models for GitHub history pipeline.
These models match the existing Pollyn database tables.
"""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class GithubPullRequest(BaseModel):
    """
    Matches the github_pull_requests table.

    Similar to JiraIssue - this is the main entity we fetch.
    """
    github_pr_id: int
    repository_id: str
    repository_full_name: Optional[str] = None
    pr_number: int
    title: str
    body: Optional[str] = None
    state: str  # open, closed, merged
    author_github_id: str
    commits_count: Optional[int] = None
    additions: Optional[int] = None
    deletions: Optional[int] = None
    changed_files: Optional[int] = None
    github_created_at: Optional[str] = None
    github_updated_at: Optional[str] = None
    merged_at: Optional[str] = None
    closed_at: Optional[str] = None
    assignees: Optional[list[str]] = None
    requested_reviewers: Optional[list[str]] = None
    project_id: Optional[UUID] = None  # NULL for historical import (same as Jira)

    # Nested data (not stored in PR table, but used for pipeline)
    reviews: list["GithubPrReview"] = []
    comments: list["GithubPrComment"] = []


class GithubPrReview(BaseModel):
    """
    Matches the github_pr_reviews table.

    Similar to JiraIssueChangelog - linked to the PR.
    """
    github_review_id: int
    repository_id: str
    state: str  # APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED, PENDING
    body: Optional[str] = None
    reviewer_github_id: str
    github_submitted_at: Optional[str] = None
    project_id: Optional[UUID] = None
    pull_request_id: Optional[int] = None  # Links to github_pull_requests.id after insert


class GithubPrComment(BaseModel):
    """
    Matches the github_pr_comments table.

    Includes both review comments (on code) and issue comments (general discussion).
    """
    github_comment_id: int
    repository_id: str
    comment_type: str  # "review_comment" or "issue_comment"
    body: str
    author_github_id: str
    is_bot: bool = False
    review_id: Optional[int] = None  # For review comments, links to the review
    github_created_at: Optional[str] = None
    project_id: Optional[UUID] = None
    pull_request_id: Optional[int] = None  # Links to github_pull_requests.id after insert


class GithubCommit(BaseModel):
    """
    Matches the github_commits table.
    """
    sha: str
    repository_id: str
    repository_full_name: Optional[str] = None
    message: str
    author_github_id: Optional[str] = None
    github_timestamp: Optional[str] = None
    project_id: Optional[UUID] = None
