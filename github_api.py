"""
GitHub API client for fetching historical data.

Similar to jira_api.py - handles all API calls to GitHub.

GitHub API uses:
- Base URL: https://api.github.com
- Auth: Personal Access Token as Bearer token
- Pagination: Link header or per_page/page params
"""

from os import environ
from typing import Generator

import requests
from loguru import logger

BASE_URL = "https://api.github.com"


def _get_headers() -> dict:
    """Get headers with authentication."""
    token = environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN environment variable must be set")

    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _paginate(url: str, params: dict = None) -> Generator[dict, None, None]:
    """
    Handle GitHub API pagination.

    GitHub uses Link headers for pagination. This generator yields
    all items across all pages.
    """
    headers = _get_headers()
    params = params or {}
    params["per_page"] = 100  # Max allowed

    while url:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()

        items = response.json()
        for item in items:
            yield item

        # Check for next page in Link header
        url = None
        params = {}  # Clear params for subsequent requests (they're in the URL)
        if "Link" in response.headers:
            links = response.headers["Link"].split(", ")
            for link in links:
                if 'rel="next"' in link:
                    url = link.split(";")[0].strip("<>")
                    break


def fetch_pull_requests(owner: str, repo: str) -> list[dict]:
    """
    Fetch all pull requests for a repository (open and closed).

    Similar to fetch_issues_for_project() in Jira.

    Args:
        owner: Repository owner (user or org)
        repo: Repository name

    Returns:
        List of PR dictionaries from GitHub API
    """
    if not owner or not repo:
        raise ValueError("owner and repo cannot be empty")

    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls"
    params = {"state": "all"}  # Get open, closed, and merged

    logger.debug(f"Fetching PRs from {owner}/{repo}")
    prs = list(_paginate(url, params))
    logger.debug(f"Fetched {len(prs)} PRs")

    return prs


def fetch_pr_details(owner: str, repo: str, pr_number: int) -> dict:
    """
    Fetch detailed information for a specific PR.

    Similar to fetch_issues_details() in Jira.
    Gets additional fields like additions, deletions, commits count.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number

    Returns:
        PR details dictionary
    """
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = _get_headers()

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    return response.json()


def fetch_pr_reviews(owner: str, repo: str, pr_number: int) -> list[dict]:
    """
    Fetch all reviews for a PR.

    This is like fetching the changelog in Jira - gives us the review history.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number

    Returns:
        List of review dictionaries
    """
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/reviews"

    logger.debug(f"Fetching reviews for PR #{pr_number}")
    reviews = list(_paginate(url))
    logger.debug(f"Fetched {len(reviews)} reviews for PR #{pr_number}")

    return reviews


def fetch_pr_review_comments(owner: str, repo: str, pr_number: int) -> list[dict]:
    """
    Fetch review comments (comments on specific code lines) for a PR.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number

    Returns:
        List of review comment dictionaries
    """
    url = f"{BASE_URL}/repos/{owner}/{repo}/pulls/{pr_number}/comments"

    logger.debug(f"Fetching review comments for PR #{pr_number}")
    comments = list(_paginate(url))
    logger.debug(f"Fetched {len(comments)} review comments for PR #{pr_number}")

    return comments


def fetch_issue_comments(owner: str, repo: str, pr_number: int) -> list[dict]:
    """
    Fetch issue comments (general discussion) for a PR.

    PRs are also issues in GitHub, so general comments use the issues endpoint.

    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: PR number (same as issue number)

    Returns:
        List of issue comment dictionaries
    """
    url = f"{BASE_URL}/repos/{owner}/{repo}/issues/{pr_number}/comments"

    logger.debug(f"Fetching issue comments for PR #{pr_number}")
    comments = list(_paginate(url))
    logger.debug(f"Fetched {len(comments)} issue comments for PR #{pr_number}")

    return comments


def fetch_repository_info(owner: str, repo: str) -> dict:
    """
    Fetch repository information including the numeric ID.

    Args:
        owner: Repository owner
        repo: Repository name

    Returns:
        Repository info dictionary with 'id', 'full_name', etc.
    """
    url = f"{BASE_URL}/repos/{owner}/{repo}"
    headers = _get_headers()

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    return response.json()


def fetch_commits(owner: str, repo: str, since: str = None) -> list[dict]:
    """
    Fetch commits for a repository.

    Args:
        owner: Repository owner
        repo: Repository name
        since: Optional ISO 8601 date to fetch commits after

    Returns:
        List of commit dictionaries
    """
    url = f"{BASE_URL}/repos/{owner}/{repo}/commits"
    params = {}
    if since:
        params["since"] = since

    logger.debug(f"Fetching commits from {owner}/{repo}")
    commits = list(_paginate(url, params))
    logger.debug(f"Fetched {len(commits)} commits")

    return commits
