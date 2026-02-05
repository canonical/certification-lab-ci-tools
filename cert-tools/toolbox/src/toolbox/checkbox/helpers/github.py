"""Helper for working with Checkbox versions from the GitHub repository."""

import logging
import os

from typing import Iterable

from github import Github, Auth
from packaging.version import Version

GH_TOKEN_ENV_VAR = "GITHUB_TOKEN"

logger = logging.getLogger(__name__)


class CheckboxVersionHelper:
    """Helper for resolving Checkbox versions to specific GitHub commits.
    Authentication:
        Set GITHUB_TOKEN environment variable to authenticate with GitHub API
        and avoid rate limits (60 requests/hour without auth, 5000 with auth).
    """

    def __init__(self):
        gh_token = os.environ.get(GH_TOKEN_ENV_VAR)

        if gh_token:
            auth = Auth.Token(gh_token)
            self.repo = Github(auth=auth).get_repo("canonical/checkbox")
        else:
            logger.warning(
                f"{GH_TOKEN_ENV_VAR} not set. This may result in rate limit exhaustion."
            )
            self.repo = Github().get_repo("canonical/checkbox")

    @staticmethod
    def get_release_and_offset(version: str) -> tuple[Version, int]:
        """Extract release version and dev offset from a version string."""
        version = Version(version)
        return Version(".".join(map(str, version.release))), version.dev or 0

    def get_tags(self) -> Iterable[Version]:
        """Get all version tags from the repository, sorted newest first."""
        return sorted(
            (
                Version(tag.name)
                for tag in self.repo.get_tags()
                if tag.name.startswith("v")
            ),
            reverse=True,
        )

    @staticmethod
    def get_previous_tag(tags: Iterable[str], version: Version) -> Version | None:
        """Find the most recent tag before the given version."""
        return next((tag for tag in tags if tag < version), None)

    def get_commit_for_version(self, version: str):
        """Resolve a Checkbox version to its corresponding commit SHA."""
        release, offset = self.get_release_and_offset(version)
        tags = self.get_tags()
        previous = self.get_previous_tag(tags, release)
        if not previous:
            raise ValueError(
                f"Unable to locate a previous tag for the version: {release}"
            )
        comparison = self.repo.compare(f"v{previous}~1", "main")
        return comparison.commits[offset].sha
