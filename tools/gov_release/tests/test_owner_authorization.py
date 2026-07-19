from __future__ import annotations

import copy
import json
import unittest

from tools.gov_release.owner_authorization import (
    OwnerAuthorizationError,
    canonical,
    comment_transport,
    direct_transport,
    expected_command,
)


class OwnerAuthorizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.owner = "roccho-dev"
        self.repository = "roccho-dev/governance"
        self.command = expected_command(
            release_id="company-operating-contract-v0.2.0",
            sequence=0,
            previous_release_digest="null",
            supersedes_release_digest="null",
            engine_sha="a" * 40,
            accepted_decision_digest="sha256:" + "b" * 64,
        )
        self.comment = {
            "id": 123,
            "user": {"login": self.owner},
            "body": canonical(self.command).decode(),
        }

    def test_direct_owner_and_comment_transport(self) -> None:
        direct = direct_transport(owner=self.owner, actor=self.owner, repository=self.repository, expected=self.command)
        comment = comment_transport(
            comment=self.comment,
            owner=self.owner,
            actor="github-actions[bot]",
            repository=self.repository,
            expected=self.command,
        )
        self.assertEqual(direct["mode"], "direct-owner")
        self.assertEqual(comment["mode"], "owner-comment")
        self.assertEqual(comment["commentId"], 123)
        self.assertEqual(direct["commandDigest"], comment["commandDigest"])
        self.assertTrue(comment["ownerAuthorized"])
        self.assertFalse(comment["meaningAuthority"])
        self.assertFalse(comment["adoptionRecord"])

    def assert_rejected(self, mutate) -> None:
        comment = copy.deepcopy(self.comment)
        expected = copy.deepcopy(self.command)
        mutate(comment, expected)
        with self.assertRaises(OwnerAuthorizationError):
            comment_transport(
                comment=comment,
                owner=self.owner,
                actor="github-actions[bot]",
                repository=self.repository,
                expected=expected,
            )

    def test_wrong_owner_rejected(self) -> None:
        self.assert_rejected(lambda comment, expected: comment["user"].update(login="other"))

    def test_wrong_engine_rejected(self) -> None:
        self.assert_rejected(lambda comment, expected: expected.update(engineSha="c" * 40))

    def test_wrong_decision_rejected(self) -> None:
        self.assert_rejected(lambda comment, expected: expected.update(acceptedDecisionDigest="sha256:" + "d" * 64))

    def test_extra_field_rejected(self) -> None:
        def mutate(comment, expected):
            command = json.loads(comment["body"])
            command["extra"] = True
            comment["body"] = canonical(command).decode()
        self.assert_rejected(mutate)

    def test_unapproved_rejected(self) -> None:
        def mutate(comment, expected):
            command = json.loads(comment["body"])
            command["status"] = "pending"
            comment["body"] = canonical(command).decode()
        self.assert_rejected(mutate)

    def test_noncanonical_body_rejected(self) -> None:
        self.assert_rejected(lambda comment, expected: comment.update(body=json.dumps(self.command, indent=2)))

    def test_non_bot_comment_transport_rejected(self) -> None:
        with self.assertRaises(OwnerAuthorizationError):
            comment_transport(
                comment=self.comment,
                owner=self.owner,
                actor=self.owner,
                repository=self.repository,
                expected=self.command,
            )

    def test_non_owner_direct_transport_rejected(self) -> None:
        with self.assertRaises(OwnerAuthorizationError):
            direct_transport(owner=self.owner, actor="github-actions[bot]", repository=self.repository, expected=self.command)


if __name__ == "__main__":
    unittest.main()
