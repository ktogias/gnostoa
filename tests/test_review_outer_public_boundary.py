"""The public boundary L1 and the merge-admission guard use (#389 F1).

`tools.review_outer` keeps one implementation behind each public name: the public
function calls its private one at call time, so a test that patches the private name
still reaches every caller of the public one. L1 likewise exposes `open_pulls` over its
one open-population enumeration. These tests hold the delegation, its late binding
and each refusal unchanged.
"""

from __future__ import annotations

import unittest
from unittest import mock

from ci import review_github_current_state as l1
from tools import review_outer
from tools.review_protected import ProtectedMainDocument

HEAD = "a" * 40
OTHER = "b" * 40


class ReviewOuterPublicBoundaryTests(unittest.TestCase):
    """Each public name delegates to its private implementation at call time."""

    def test_decode_outer_result_reaches_a_patched_implementation(self) -> None:
        decoded = {"outcome": "PASS"}
        with mock.patch.object(
            review_outer, "_decode_outer_result", return_value=decoded
        ) as private:
            self.assertIs(decoded, review_outer.decode_outer_result(2, b"{}"))
        private.assert_called_once_with(2, b"{}")

    def test_decode_outer_result_refuses_an_oversized_result(self) -> None:
        # The bound is read at call time: patched small, five bytes exceed it.
        with mock.patch.object(review_outer, "_MAX_RESULT_BYTES", 4):
            with self.assertRaisesRegex(
                review_outer.PriorEffectiveOuterUnavailable, "exceeds the bounded size"
            ):
                review_outer.decode_outer_result(2, b"12345")

    def test_transport_refusal_is_the_private_one(self) -> None:
        # The refusal is the private implementation's own, read at call time.
        with mock.patch.object(review_outer, "_TRANSPORT_UNAVAILABLE", "refused here"):
            with self.assertRaises(
                review_outer.PriorEffectiveOuterUnavailable
            ) as raised:
                review_outer.require_transport_compatible_consumer(
                    {"identity": "other"}
                )
        self.assertEqual("refused here", str(raised.exception))

    def test_transport_check_reaches_a_patched_implementation(self) -> None:
        consumer = {"identity": "pinned"}
        with mock.patch.object(
            review_outer, "_require_transport_compatible_consumer"
        ) as private:
            review_outer.require_transport_compatible_consumer(consumer)
        private.assert_called_once_with(consumer)

    def test_the_pinned_consumer_reaches_the_private_runner_unchanged(self) -> None:
        def acquire() -> ProtectedMainDocument:
            raise AssertionError("the patched runner never acquires")

        document = {"input": True}
        with mock.patch.object(
            review_outer,
            "_run_prior_effective_current_advisory_with_acquisition",
            return_value=(0, b"{}"),
        ) as private:
            self.assertEqual(
                (0, b"{}"),
                review_outer.run_prior_effective_current_advisory_with_acquisition(
                    document, acquire_consumer=acquire
                ),
            )
        private.assert_called_once_with(document, acquire_consumer=acquire)
        self.assertIs(acquire, private.call_args.kwargs["acquire_consumer"])


class OpenPullsPublicBoundaryTests(unittest.TestCase):
    """L1's public open population is its one private enumeration."""

    def test_open_pulls_reaches_a_patched_enumeration(self) -> None:
        listed = [{"number": 7, "head_sha": HEAD}]
        reader = mock.Mock(spec=l1.GitHubRestClient)
        with mock.patch.object(l1, "_open_pulls", return_value=listed) as private:
            self.assertIs(listed, l1.open_pulls(reader, "ktogias/gnostoa"))
        private.assert_called_once_with(reader, "ktogias/gnostoa")

    def test_open_pulls_refuses_a_number_at_two_heads(self) -> None:
        listing = [{"number": 7, "head_sha": HEAD}, {"number": 7, "head_sha": OTHER}]
        reader = mock.Mock(spec=l1.GitHubRestClient)
        with mock.patch.object(l1, "_open_pull_listing", return_value=listing):
            with self.assertRaisesRegex(l1.ProviderReadError, "at two heads"):
                l1.open_pulls(reader, "ktogias/gnostoa")

    def test_open_pulls_keeps_one_listed_twice_at_one_head_once(self) -> None:
        listing = [
            {"number": 7, "head_sha": HEAD},
            {"number": 7, "head_sha": HEAD},
            {"number": 3, "head_sha": OTHER},
        ]
        with mock.patch.object(l1, "_open_pull_listing", return_value=listing):
            self.assertEqual(
                [{"number": 3, "head_sha": OTHER}, {"number": 7, "head_sha": HEAD}],
                l1.open_pulls(mock.Mock(spec=l1.GitHubRestClient), "ktogias/gnostoa"),
            )


if __name__ == "__main__":
    unittest.main()
