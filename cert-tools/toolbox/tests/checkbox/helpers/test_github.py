"""Tests for CheckboxVersionHelper."""

from typing import NamedTuple

import pytest
from packaging.version import Version

from toolbox.checkbox.helpers.github import CheckboxVersionHelper


class Tag(NamedTuple):
    """Simple tag object for testing."""

    name: str


class Commit(NamedTuple):
    """Simple commit object for testing."""

    sha: str


class TestCheckboxVersionHelper:
    """Tests for CheckboxVersionHelper."""

    @pytest.mark.parametrize(
        "version_string,expected_release,expected_offset",
        [
            ("4.0.0", Version("4.0.0"), 0),
            ("4.0.0.dev42", Version("4.0.0"), 42),
            ("3.5.2", Version("3.5.2"), 0),
            ("3.5.2.dev100", Version("3.5.2"), 100),
        ],
    )
    def test_get_release_and_offset(
        self, version_string, expected_release, expected_offset
    ):
        """Test extracting release version and dev offset from version strings."""
        release, offset = CheckboxVersionHelper.get_release_and_offset(version_string)
        assert release == expected_release
        assert offset == expected_offset

    @pytest.mark.parametrize(
        "tags,version,expected_previous",
        [
            # Previous tag found
            (
                [
                    Version("4.0.0"),
                    Version("3.5.0"),
                    Version("3.0.0"),
                    Version("2.0.0"),
                ],
                Version("3.2.0"),
                Version("3.0.0"),
            ),
            # Multiple options - returns closest
            (
                [
                    Version("4.0.0"),
                    Version("3.5.0"),
                    Version("3.2.0"),
                    Version("3.0.0"),
                ],
                Version("3.3.0"),
                Version("3.2.0"),
            ),
            # No previous tag exists
            (
                [Version("4.0.0"), Version("3.5.0"), Version("3.0.0")],
                Version("2.0.0"),
                None,
            ),
            # Empty tag list
            ([], Version("3.0.0"), None),
        ],
    )
    def test_get_previous_tag(self, tags, version, expected_previous):
        """Test finding previous tag for a given version."""
        result = CheckboxVersionHelper.get_previous_tag(tags, version)
        assert result == expected_previous

    def test_get_tags_filters_and_sorts(self, mocker):
        """Test that get_tags filters version tags and sorts them."""
        tags = [
            Tag("v3.5.0"),
            Tag("random-tag"),
            Tag("v4.0.0"),
            Tag("v3.0.0"),
        ]

        mock_repo = mocker.Mock()
        mock_repo.get_tags.return_value = tags

        helper = CheckboxVersionHelper()
        helper.repo = mock_repo

        result = helper.get_tags()

        # Should filter out non-version tags and sort in descending order
        assert result == [Version("4.0.0"), Version("3.5.0"), Version("3.0.0")]

    def test_get_tags_empty_repository(self, mocker):
        """Test get_tags with no tags in repository."""
        mock_repo = mocker.Mock()
        mock_repo.get_tags.return_value = []

        helper = CheckboxVersionHelper()
        helper.repo = mock_repo

        tags = helper.get_tags()

        assert tags == []

    def test_get_tags_only_non_version_tags(self, mocker):
        """Test get_tags with only non-version tags."""
        tags = [Tag("latest"), Tag("stable")]

        mock_repo = mocker.Mock()
        mock_repo.get_tags.return_value = tags

        helper = CheckboxVersionHelper()
        helper.repo = mock_repo

        result = helper.get_tags()

        assert result == []

    def test_get_commit_for_version_success(self, mocker):
        """Test successfully getting commit for a version."""
        tags = [Tag("v4.0.0"), Tag("v3.5.0")]
        commits = [Commit("abc123"), Commit("def456"), Commit("ghi789")]

        mock_comparison = mocker.Mock()
        mock_comparison.commits = commits

        mock_repo = mocker.Mock()
        mock_repo.get_tags.return_value = tags
        mock_repo.compare.return_value = mock_comparison

        helper = CheckboxVersionHelper()
        helper.repo = mock_repo

        # Test version 3.6.0.dev2 (should use tag v3.5.0 and offset 2)
        commit = helper.get_commit_for_version("3.6.0.dev2")

        assert commit == "ghi789"
        mock_repo.compare.assert_called_once_with("v3.5.0~1", "main")

    def test_get_commit_for_version_no_offset(self, mocker):
        """Test getting commit with no dev offset."""
        tags = [Tag("v4.0.0"), Tag("v3.5.0")]
        commits = [Commit("abc123")]

        mock_comparison = mocker.Mock()
        mock_comparison.commits = commits

        mock_repo = mocker.Mock()
        mock_repo.get_tags.return_value = tags
        mock_repo.compare.return_value = mock_comparison

        helper = CheckboxVersionHelper()
        helper.repo = mock_repo

        commit = helper.get_commit_for_version("3.6.0")

        assert commit == "abc123"
        mock_repo.compare.assert_called_once_with("v3.5.0~1", "main")

    def test_get_commit_for_version_no_previous_tag(self, mocker):
        """Test getting commit when no previous tag exists."""
        tags = [Tag("v4.0.0")]

        mock_repo = mocker.Mock()
        mock_repo.get_tags.return_value = tags

        helper = CheckboxVersionHelper()
        helper.repo = mock_repo

        with pytest.raises(ValueError, match="Unable to locate a previous tag"):
            helper.get_commit_for_version("3.0.0")

    def test_init_creates_repo(self, mocker):
        """Test that __init__ creates a GitHub repo object."""
        mock_github = mocker.Mock()
        mock_repo = mocker.Mock()
        mock_github.get_repo.return_value = mock_repo
        mocker.patch("toolbox.checkbox.helpers.github.Github", return_value=mock_github)

        helper = CheckboxVersionHelper()

        assert helper.repo is mock_repo
        mock_github.get_repo.assert_called_once_with("canonical/checkbox")
