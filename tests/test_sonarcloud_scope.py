from __future__ import annotations

import unittest

from tools import sonarcloud_scope


class DetailsScopeTests(unittest.TestCase):
    """The PAO's Q-a on #424 (6123049205): one pure helper tells which SonarCloud
    analysis a check run's details URL names, for the readback's adapter and the
    merge-evidence gate alike."""

    def test_the_scope_of_a_details_url(self) -> None:
        dashboard = "https://sonarcloud.io/dashboard"
        for name, details, scope in (
            (
                "this pull request",
                f"{dashboard}?id=ktogias_gnostoa&pullRequest=312",
                "ours",
            ),
            (
                "the same, keys reordered",
                f"{dashboard}?pullRequest=312&id=ktogias_gnostoa",
                "ours",
            ),
            (
                "another pull request",
                f"{dashboard}?id=ktogias_gnostoa&pullRequest=311",
                "foreign",
            ),
            (
                "another project",
                f"{dashboard}?id=ktogias_other&pullRequest=312",
                "foreign",
            ),
            ("a branch", f"{dashboard}?id=ktogias_gnostoa&branch=main", "foreign"),
            ("no subject", f"{dashboard}?id=ktogias_gnostoa", "malformed"),
            (
                "two pull requests",
                f"{dashboard}?id=ktogias_gnostoa&pullRequest=312&pullRequest=313",
                "malformed",
            ),
            (
                "another page",
                "https://sonarcloud.io/project/overview?id=ktogias_gnostoa&pullRequest=312",
                "malformed",
            ),
            (
                "another host",
                "https://sonarcloud.io.example/dashboard?id=ktogias_gnostoa&pullRequest=312",
                "malformed",
            ),
            (
                "plain http",
                "http://sonarcloud.io/dashboard?id=ktogias_gnostoa&pullRequest=312",
                "malformed",
            ),
            (
                "an unparsable host",
                "https://[sonarcloud.io/dashboard?id=ktogias_gnostoa&pullRequest=312",
                "malformed",
            ),
            ("not a URL", "pull request 312", "malformed"),
            ("none", None, "malformed"),
            ("not text", 312, "malformed"),
        ):
            with self.subTest(name):
                self.assertEqual(
                    scope,
                    sonarcloud_scope.details_scope(
                        details, project="ktogias_gnostoa", pull="312"
                    ),
                )

    def test_the_project_key_is_owner_and_name(self) -> None:
        self.assertEqual(
            "ktogias_gnostoa", sonarcloud_scope.project_key("ktogias/gnostoa")
        )

    def test_the_check_identity(self) -> None:
        self.assertEqual(12526, sonarcloud_scope.CHECK_APP_ID)
        self.assertEqual("SonarCloud Code Analysis", sonarcloud_scope.CHECK_NAME)


if __name__ == "__main__":
    unittest.main()
