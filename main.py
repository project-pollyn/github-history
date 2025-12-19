#!/usr/bin/env python3
"""
Main entry point for the GitHub history pipeline.

Usage:
    python main.py <owner> <repo>

Example:
    python main.py project-pollyn scrumble-honey-bot
"""

import sys

from dotenv import load_dotenv
from loguru import logger

from pipeline import run_pipeline

load_dotenv()


def main():
    """Main entry point."""
    if len(sys.argv) != 3:
        logger.error("Usage: python main.py <owner> <repo>")
        logger.error("Example: python main.py project-pollyn scrumble-honey-bot")
        sys.exit(1)

    owner = sys.argv[1]
    repo = sys.argv[2]

    try:
        run_pipeline(owner, repo)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        raise


if __name__ == "__main__":
    main()
