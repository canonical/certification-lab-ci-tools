from typing import Iterable

from github import Github
from packaging.version import Version


class CheckboxVersionHelper:
    def __init__(self):
        self.repo = Github().get_repo("canonical/checkbox")

    @staticmethod
    def get_release_and_offset(version: str) -> tuple[str, int]:
        version = Version(version)
        return Version(".".join(map(str, version.release))), version.dev or 0

    def get_tags(self) -> Iterable[str]:
        return sorted(
            (
                Version(tag.name)
                for tag in self.repo.get_tags()
                if tag.name.startswith("v")
            ),
            reverse=True,
        )

    @staticmethod
    def get_previous_tag(tags: Iterable[str], version: Version):
        return next((tag for tag in tags if tag < version), None)

    def get_commit_for_version(self, version: str):
        release, offset = self.get_release_and_offset(version)
        tags = self.get_tags()
        previous = self.get_previous_tag(tags, release)
        if not previous:
            raise ValueError(
                f"Unable to locate a previous tag for the version: {release}"
            )
        comparison = self.repo.compare(f"v{previous}~1", "main")
        return comparison.commits[offset].sha
