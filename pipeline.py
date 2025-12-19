"""
Pipeline module for processing GitHub PRs and storing them in Supabase.

Similar to jira-history/pipeline.py:
1. Fetch data from GitHub API
2. Parse into Pydantic models
3. Upsert to Supabase tables
"""

import os

from loguru import logger
from supabase import Client, create_client

from github_api import (
    fetch_issue_comments,
    fetch_pr_details,
    fetch_pr_review_comments,
    fetch_pr_reviews,
    fetch_pull_requests,
    fetch_commits,
)
from model import GithubCommit, GithubPrComment, GithubPrReview, GithubPullRequest


def get_supabase_client() -> Client:
    """Initialize and return a Supabase client."""
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

    if not url or not key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables must be set"
        )

    return create_client(url, key)


def parse_pull_requests(
    prs: list[dict], owner: str, repo: str, repo_id: str
) -> list[GithubPullRequest]:
    """
    Parse GitHub PR data into GithubPullRequest models.

    Similar to parse_issues() in Jira pipeline.

    For each PR:
    1. Fetch detailed PR info (additions, deletions, etc.)
    2. Fetch reviews (like Jira changelog)
    3. Fetch comments (review comments + issue comments)

    Args:
        prs: List of PR dictionaries from GitHub API
        owner: Repository owner
        repo: Repository name
        repo_id: Repository ID string

    Returns:
        List of parsed GithubPullRequest objects with nested reviews/comments
    """
    parsed_prs = []
    repo_full_name = f"{owner}/{repo}"

    for pr in prs:
        pr_number = pr["number"]
        logger.debug(f"Parsing PR #{pr_number}")

        # Fetch detailed PR info (similar to fetch_issues_details in Jira)
        pr_details = fetch_pr_details(owner, repo, pr_number)

        # Fetch reviews (similar to changelog in Jira)
        reviews_data = fetch_pr_reviews(owner, repo, pr_number)
        reviews = []
        for review in reviews_data:
            # Skip pending reviews (not yet submitted)
            if review.get("state") == "PENDING":
                continue

            review_obj = GithubPrReview(
                github_review_id=review["id"],
                repository_id=repo_id,
                state=review["state"],
                body=review.get("body"),
                reviewer_github_id=str(review["user"]["id"]),
                github_submitted_at=review.get("submitted_at"),
            )
            reviews.append(review_obj)

        # Fetch review comments (comments on code lines)
        review_comments_data = fetch_pr_review_comments(owner, repo, pr_number)
        comments = []
        for comment in review_comments_data:
            comment_obj = GithubPrComment(
                github_comment_id=comment["id"],
                repository_id=repo_id,
                comment_type="review_comment",
                body=comment["body"],
                author_github_id=str(comment["user"]["id"]),
                is_bot=comment["user"].get("type") == "Bot",
                review_id=comment.get("pull_request_review_id"),
                github_created_at=comment.get("created_at"),
            )
            comments.append(comment_obj)

        # Fetch issue comments (general discussion)
        issue_comments_data = fetch_issue_comments(owner, repo, pr_number)
        for comment in issue_comments_data:
            comment_obj = GithubPrComment(
                github_comment_id=comment["id"],
                repository_id=repo_id,
                comment_type="issue_comment",
                body=comment["body"],
                author_github_id=str(comment["user"]["id"]),
                is_bot=comment["user"].get("type") == "Bot",
                review_id=None,  # Issue comments don't have a review
                github_created_at=comment.get("created_at"),
            )
            comments.append(comment_obj)

        # Parse assignees and reviewers
        assignees = [str(a["id"]) for a in pr_details.get("assignees", [])]
        requested_reviewers = [
            str(r["id"]) for r in pr_details.get("requested_reviewers", [])
        ]

        # Create PR object with nested reviews and comments
        pr_obj = GithubPullRequest(
            github_pr_id=pr_details["id"],
            repository_id=repo_id,
            repository_full_name=repo_full_name,
            pr_number=pr_number,
            title=pr_details["title"],
            body=pr_details.get("body"),
            state=pr_details["state"],
            author_github_id=str(pr_details["user"]["id"]),
            commits_count=pr_details.get("commits"),
            additions=pr_details.get("additions"),
            deletions=pr_details.get("deletions"),
            changed_files=pr_details.get("changed_files"),
            github_created_at=pr_details.get("created_at"),
            github_updated_at=pr_details.get("updated_at"),
            merged_at=pr_details.get("merged_at"),
            closed_at=pr_details.get("closed_at"),
            assignees=assignees if assignees else None,
            requested_reviewers=requested_reviewers if requested_reviewers else None,
            reviews=reviews,
            comments=comments,
        )

        parsed_prs.append(pr_obj)

    return parsed_prs


def parse_commits(commits_data: list[dict], repo_id: str, repo_full_name: str) -> list[GithubCommit]:
    """
    Parse GitHub commit data into GithubCommit models.

    Args:
        commits_data: List of commit dictionaries from GitHub API
        repo_id: Repository ID string
        repo_full_name: Full repository name (owner/repo)

    Returns:
        List of parsed GithubCommit objects
    """
    commits = []

    for commit in commits_data:
        # Author might be None if the commit email doesn't match a GitHub user
        author_id = None
        if commit.get("author"):
            author_id = str(commit["author"]["id"])

        commit_obj = GithubCommit(
            sha=commit["sha"],
            repository_id=repo_id,
            repository_full_name=repo_full_name,
            message=commit["commit"]["message"],
            author_github_id=author_id,
            github_timestamp=commit["commit"]["author"]["date"],
        )
        commits.append(commit_obj)

    return commits


def write_prs_and_related_to_db(
    prs: list[GithubPullRequest], supabase: Client
) -> None:
    """
    Write parsed PRs, reviews, and comments to Supabase database.

    Similar to write_issues_and_changelogs_to_db() in Jira pipeline:
    1. Upsert PRs first
    2. Get back the inserted IDs
    3. Link reviews/comments to those IDs
    4. Upsert reviews and comments
    """
    if not prs:
        logger.info("No PRs to write")
        return

    # Step 1: Write PRs (exclude nested reviews/comments)
    serialized_prs = [
        pr.model_dump(exclude={"reviews", "comments"})
        for pr in prs
    ]

    response = (
        supabase.table("github_pull_requests")
        .upsert(serialized_prs, on_conflict="github_pr_id")
        .execute()
    )

    # Create mapping: github_pr_id -> internal id
    pr_id_map = {item["github_pr_id"]: item["id"] for item in response.data}
    logger.info(f"Upserted {len(pr_id_map)} PRs")

    # Step 2: Write reviews (link to PR internal ID)
    review_entries = []
    for pr in prs:
        internal_pr_id = pr_id_map.get(pr.github_pr_id)
        if not internal_pr_id:
            continue

        for review in pr.reviews:
            review.pull_request_id = internal_pr_id
            review_entries.append(review.model_dump())

    if review_entries:
        response = (
            supabase.table("github_pr_reviews")
            .upsert(review_entries, on_conflict="github_review_id")
            .execute()
        )
        logger.info(f"Upserted {len(review_entries)} reviews")
    else:
        logger.debug("No reviews to insert")

    # Step 3: Write comments (link to PR internal ID)
    comment_entries = []
    for pr in prs:
        internal_pr_id = pr_id_map.get(pr.github_pr_id)
        if not internal_pr_id:
            continue

        for comment in pr.comments:
            comment.pull_request_id = internal_pr_id
            comment_entries.append(comment.model_dump())

    if comment_entries:
        response = (
            supabase.table("github_pr_comments")
            .upsert(comment_entries, on_conflict="github_comment_id")
            .execute()
        )
        logger.info(f"Upserted {len(comment_entries)} comments")
    else:
        logger.debug("No comments to insert")


def write_commits_to_db(commits: list[GithubCommit], supabase: Client) -> None:
    """
    Write commits to Supabase database.
    """
    if not commits:
        logger.info("No commits to write")
        return

    serialized_commits = [commit.model_dump() for commit in commits]

    response = (
        supabase.table("github_commits")
        .upsert(serialized_commits, on_conflict="sha")
        .execute()
    )
    logger.info(f"Upserted {len(response.data)} commits")


def run_pipeline(owner: str, repo: str, include_commits: bool = True) -> None:
    """
    Execute the full pipeline: fetch PRs, parse them, and store in database.

    Similar to run_pipeline() in Jira.

    Args:
        owner: Repository owner (user or org)
        repo: Repository name
        include_commits: Whether to also fetch and store commits
    """
    logger.info(f"Starting pipeline for {owner}/{repo}")

    # Initialize Supabase client
    supabase = get_supabase_client()
    logger.info("Connected to Supabase")

    # Use owner/repo as repository_id (consistent with webhook handler)
    repo_id = f"{owner}/{repo}"
    repo_full_name = f"{owner}/{repo}"

    # Fetch PRs from GitHub
    logger.info(f"Fetching PRs from GitHub repo {owner}/{repo}")
    prs = fetch_pull_requests(owner, repo)
    logger.info(f"Fetched {len(prs)} PRs")

    if prs:
        # Parse PRs (also fetches reviews and comments for each)
        logger.info("Parsing PRs with reviews and comments")
        parsed_prs = parse_pull_requests(prs, owner, repo, repo_id)
        logger.info(f"Parsed {len(parsed_prs)} PRs")

        # Write to database
        logger.info("Writing PRs, reviews, and comments to database")
        write_prs_and_related_to_db(parsed_prs, supabase)

    # Optionally fetch and store commits
    if include_commits:
        logger.info("Fetching commits from GitHub")
        commits_data = fetch_commits(owner, repo)
        logger.info(f"Fetched {len(commits_data)} commits")

        if commits_data:
            logger.info("Parsing commits")
            parsed_commits = parse_commits(commits_data, repo_id, repo_full_name)

            logger.info("Writing commits to database")
            write_commits_to_db(parsed_commits, supabase)

    logger.info("Pipeline completed successfully")
