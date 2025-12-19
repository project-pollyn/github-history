# GitHub History Integration

This project provides a Python-based pipeline to fetch and process GitHub pull request history data.
It allows to pull all PRs along with their reviews and comments for a given repository and populate the `github_pull_requests`, `github_pr_reviews`, `github_pr_comments`, and `github_commits` tables.

> _Note_: The `github_events` table can not be populated from historical data, leading to a difference to the live recorded data.

## Setup

### Auth token

Create a Personal Access Token (classic) with `repo` scope:
https://github.com/settings/tokens

### Env file

Create a `.env` file with the following variables:

```
# github env
GITHUB_TOKEN=<github_personal_access_token>

# supabase env
SUPABASE_URL=<url>
SUPABASE_SERVICE_ROLE_KEY=<key>
```

### Create venv

We recommend to use `uv`

```sh
uv venv --python 3.12
source .venv/bin/activate
uv sync # install dependencies to be in sync with pyproject.toml
```

### DB

The pipeline uses upserts with the following unique constraints (these should already exist):

```sql
-- github_pull_requests table
UNIQUE (github_pr_id)

-- github_pr_reviews table
UNIQUE (github_review_id)

-- github_pr_comments table
UNIQUE (github_comment_id)

-- github_commits table
UNIQUE (sha)
```

The pipeline also requires `project_id` to be nullable on these tables. This was added via migration:
`20251219165954_make_github_project_id_nullable.sql`

## Run pipeline

Automatically pull all PRs, reviews, comments, and commits from the GitHub API and push them to the configured database:

```shell
python main.py <owner> <repo>
```

Example:
```shell
python main.py project-pollyn scrumble-honey-bot
```

## What gets fetched

For each repository, the pipeline:

1. **Fetches all PRs** (open + closed + merged)
2. **For each PR:**
   - Fetches detailed info (additions, deletions, changed files)
   - Fetches all reviews (approvals, change requests)
   - Fetches review comments (comments on specific code lines)
   - Fetches issue comments (general discussion)
3. **Fetches all commits** for the repository

## Limitations

- Currently the pipeline does not match and insert the proper pollyn `project_id` for each PR (since this would require a project integration etc.)
- The pipeline makes multiple API calls per PR (1 for details + 1 for reviews + 2 for comments), which can be slow for repos with many PRs
- GitHub API has rate limits: 5,000 requests/hour for authenticated users. For large repos, you may hit this limit.
- The pipeline fetches all commits from the repo, not just those associated with PRs
