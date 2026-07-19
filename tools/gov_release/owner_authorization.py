from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SHA = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
RELEASE_ID = re.compile(r"^[A-Za-z0-9._-]+$")


class OwnerAuthorizationError(ValueError):
    pass


def need(ok: bool, code: str) -> None:
    if not ok:
        raise OwnerAuthorizationError(code)


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def optional_digest(value: str | None) -> str | None:
    if value in {None, "", "null"}:
        return None
    need(DIGEST.fullmatch(value) is not None, "optional-digest")
    return value


def expected_command(
    *,
    release_id: str,
    sequence: int,
    previous_release_digest: str | None,
    supersedes_release_digest: str | None,
    engine_sha: str,
    accepted_decision_digest: str,
) -> dict[str, Any]:
    need(RELEASE_ID.fullmatch(release_id) is not None, "release-id")
    need(isinstance(sequence, int) and sequence >= 0, "sequence")
    need(SHA.fullmatch(engine_sha) is not None, "engine-sha")
    need(DIGEST.fullmatch(accepted_decision_digest) is not None, "accepted-decision-digest")
    previous = optional_digest(previous_release_digest)
    supersedes = optional_digest(supersedes_release_digest)
    return {
        "kind": "govReleaseOwnerAuthorization.v1",
        "status": "approved",
        "releaseId": release_id,
        "sequence": sequence,
        "previousReleaseDigest": previous,
        "supersedesReleaseDigest": supersedes,
        "engineSha": engine_sha,
        "acceptedDecisionDigest": accepted_decision_digest,
        "effectAuthorization": True,
        "meaningAuthority": False,
        "adoptionRecord": False,
        "allRepositoriesEnforced": False,
        "businessOutcomeAchieved": False,
    }


def validate_comment(comment: dict[str, Any], *, owner: str, expected: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    need(isinstance(comment, dict), "comment-object")
    user = comment.get("user")
    need(isinstance(user, dict) and user.get("login") == owner, "comment-owner")
    comment_id = comment.get("id")
    need(isinstance(comment_id, int) and comment_id > 0, "comment-id")
    body = comment.get("body")
    need(isinstance(body, str), "comment-body")
    try:
        command = json.loads(body)
    except json.JSONDecodeError as exc:
        raise OwnerAuthorizationError("comment-json") from exc
    need(isinstance(command, dict), "command-object")
    need(command == expected, "command-mismatch")
    need(body == canonical(command).decode(), "command-not-canonical")
    return comment_id, command


def make_transport(
    *,
    mode: str,
    owner: str,
    actor: str,
    repository: str,
    command: dict[str, Any],
    comment_id: int | None,
) -> dict[str, Any]:
    need(mode in {"direct-owner", "owner-comment"}, "mode")
    need(bool(owner) and bool(actor) and bool(repository), "transport-identity")
    need(actor == owner if mode == "direct-owner" else actor == "github-actions[bot]", "trigger-actor")
    need(comment_id is None if mode == "direct-owner" else isinstance(comment_id, int) and comment_id > 0, "transport-comment-id")
    return {
        "kind": "govReleaseOwnerAuthorizationTransport.v1",
        "status": "pass",
        "mode": mode,
        "owner": owner,
        "triggerActor": actor,
        "repository": repository,
        "commentId": comment_id,
        "command": command,
        "commandDigest": digest(command),
        "ownerAuthorized": True,
        "meaningAuthority": False,
        "adoptionRecord": False,
        "authority": False,
    }


def direct_transport(*, owner: str, actor: str, repository: str, expected: dict[str, Any]) -> dict[str, Any]:
    need(actor == owner, "direct-owner")
    return make_transport(mode="direct-owner", owner=owner, actor=actor, repository=repository, command=expected, comment_id=None)


def comment_transport(
    *,
    comment: dict[str, Any],
    owner: str,
    actor: str,
    repository: str,
    expected: dict[str, Any],
) -> dict[str, Any]:
    need(actor == "github-actions[bot]", "comment-trigger-actor")
    comment_id, command = validate_comment(comment, owner=owner, expected=expected)
    return make_transport(mode="owner-comment", owner=owner, actor=actor, repository=repository, command=command, comment_id=comment_id)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["direct", "comment"])
    parser.add_argument("--owner", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--sequence", required=True, type=int)
    parser.add_argument("--previous-release-digest", required=True)
    parser.add_argument("--supersedes-release-digest", required=True)
    parser.add_argument("--engine-sha", required=True)
    parser.add_argument("--accepted-decision-digest", required=True)
    parser.add_argument("--comment-json", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    expected = expected_command(
        release_id=args.release_id,
        sequence=args.sequence,
        previous_release_digest=args.previous_release_digest,
        supersedes_release_digest=args.supersedes_release_digest,
        engine_sha=args.engine_sha,
        accepted_decision_digest=args.accepted_decision_digest,
    )
    if args.mode == "direct":
        report = direct_transport(owner=args.owner, actor=args.actor, repository=args.repository, expected=expected)
    else:
        need(args.comment_json is not None and args.comment_json.is_file(), "comment-file")
        report = comment_transport(
            comment=json.loads(args.comment_json.read_text(encoding="utf-8")),
            owner=args.owner,
            actor=args.actor,
            repository=args.repository,
            expected=expected,
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(canonical(report).decode() + "\n", encoding="utf-8")
    print(canonical(report).decode())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
