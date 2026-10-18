"""Byte acquisition for existing JSONL and contract consumers.

Pins and the consumer are supplied by the trusted caller, independently of the
input producer. A digest, Git OID, or supplied source descriptor authenticates
neither an owner nor admission. This module never selects executable input code,
admits meaning, writes a record, or acquires a network resource.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path, PurePosixPath
import re
from typing import Any, Callable

from tools.package_contract_port_cold import ColdInputError, GitReader
from tools.package_contract_port_common import STATUS_EXIT


class InputBoundaryError(ValueError):
    def __init__(self, reason: str, status: str = "UNKNOWN"):
        super().__init__(reason)
        self.status, self.exit_code = status, STATUS_EXIT[status]


def require(condition: bool, reason: str, status: str = "UNKNOWN") -> None:
    if not condition:
        raise InputBoundaryError(reason, status)


@dataclass(frozen=True)
class SourcePin:
    """Existing source-reference fields; configuration, not an input assertion."""
    repository: str
    revision: str
    path: str
    digest: str

    def __post_init__(self):
        require(isinstance(self.repository, str) and bool(self.repository)
                and not any(c.isspace() or ord(c) < 32 for c in self.repository), "source-repository", "INVALID")
        require(isinstance(self.revision, str) and bool(re.fullmatch(r"[0-9a-f]{40}", self.revision)),
                "source-exact-revision", "INVALID")
        require(isinstance(self.path, str), "source-path", "INVALID")
        p = PurePosixPath(self.path)
        require(bool(self.path) and str(p) == self.path and not p.is_absolute()
                and ".." not in p.parts and "\\" not in self.path and ":" not in self.path
                and not any(ord(c) < 32 for c in self.path),
                "source-canonical-path", "INVALID")
        require(isinstance(self.digest, str) and bool(re.fullmatch(r"sha256:[0-9a-f]{64}", self.digest)),
                "source-exact-digest", "INVALID")

    def descriptor(self) -> dict[str, str]:
        return dict(repository=self.repository, revision=self.revision,
                    path=self.path, digest=self.digest)


@dataclass(frozen=True)
class SuppliedBody:
    raw: bytes
    source: SourcePin | None
    complete: bool


@dataclass(frozen=True)
class Readback:
    raw: bytes
    source: SourcePin
    acquisition: str
    retained: bool
    native: dict[str, str] | None = None


class BytesReader:
    """Adapt a caller's existing byte receiver; make no native-retention claim."""
    def __init__(self, receive: Callable[[SourcePin], SuppliedBody]):
        self.receive = receive

    def read(self, pin: SourcePin) -> Readback:
        try:
            value = self.receive(pin)
        except (FileNotFoundError, KeyError) as error:
            raise InputBoundaryError("input-bytes-missing") from error
        except OSError as error:
            raise InputBoundaryError("input-bytes-unreadable:" + type(error).__name__) from error
        require(isinstance(value, SuppliedBody), "input-receiver-shape", "INVALID")
        require(value.source is not None, "input-origin-unknown")
        require(value.source == pin, "input-source-mismatch")
        require(value.complete is True, "input-acquisition-incomplete")
        _verify_bytes(value.raw, pin)
        return Readback(value.raw, pin, "supplied-bytes", False)


def _verify_bytes(raw: bytes, pin: SourcePin) -> None:
    require(isinstance(raw, bytes), "input-raw-bytes-required", "INVALID")
    require("sha256:" + hashlib.sha256(raw).hexdigest() == pin.digest, "input-digest-mismatch")


class GitObjectReader:
    """Resolve one holding ref once; every file is read at the fixed commit.

    The trusted caller owns the root-to-repository binding. Native object
    integrity and retention do not establish that binding or meaning admission.
    """
    def __init__(self, root: Path, git: str, *, repository: str, holding_ref: str,
                 revision: str, tree: str):
        self.repository = repository
        self.reader = GitReader(root, git)
        try:
            self.snapshot = self.reader.held(holding_ref, revision)
        except ColdInputError as error:
            raise InputBoundaryError("git:" + str(error), error.status) from error
        require(self.snapshot["tree"] == tree, "input-tree-mismatch")

    def read(self, pin: SourcePin) -> Readback:
        require(pin.repository == self.repository, "input-repository-mismatch")
        require(pin.revision == self.snapshot["revision"], "input-revision-mismatch")
        try:
            raw, blob, mode = self.reader.file(self.snapshot["revision"], pin.path)
        except ColdInputError as error:
            raise InputBoundaryError("git:" + str(error), error.status) from error
        _verify_bytes(raw, pin)
        native = {**self.snapshot, "gitBlob": blob, "mode": mode}
        return Readback(raw, pin, "native-git-objects", True, native)


def _read(reader: Any, pin: SourcePin) -> Readback:
    # New acquisition surfaces use BytesReader's callback. They cannot supply a
    # native-retention assertion instead of the native reader's actual check.
    require(isinstance(reader, (BytesReader, GitObjectReader)), "input-reader-boundary", "INVALID")
    body = reader.read(pin)
    require(body.source == pin, "input-source-mismatch")
    _verify_bytes(body.raw, pin)
    return body


def read_json(reader: Any, pin: SourcePin, consumer: Any) -> tuple[Any, Readback]:
    """Use the trusted existing consumer's strict JSON parser, not data code."""
    body = _read(reader, pin)
    try:
        value = consumer.load_json(body.raw.decode("utf-8"))
    except UnicodeError as error:
        raise InputBoundaryError("input-utf8", "INVALID") from error
    except consumer.InputError as error:
        raise InputBoundaryError("input-json:" + str(error), error.status) from error
    return value, body


def select_jsonl_record(reader: Any, pin: SourcePin, record_id: str,
                        consumer: Any) -> tuple[dict, Readback]:
    """Select an immutable original; selection confers no admission."""
    require(isinstance(record_id, str) and bool(record_id)
            and not any(ord(c) < 32 for c in record_id), "jsonl-record-id", "INVALID")
    body = _read(reader, pin)
    try:
        values = [consumer.load_json(line) for line in body.raw.decode("utf-8").splitlines()
                  if line.strip()]
    except UnicodeError as error:
        raise InputBoundaryError("input-utf8", "INVALID") from error
    except consumer.InputError as error:
        raise InputBoundaryError("input-json:" + str(error), error.status) from error
    require(all(isinstance(row, dict) for row in values), "jsonl-object-required", "INVALID")
    matches = [row for row in values if row.get("raw_id", row.get("id")) == record_id]
    require(bool(matches), "jsonl-record-missing")
    require(len(matches) == 1, "jsonl-record-duplicate-or-conflict", "INVALID")
    return matches[0], body


def compare_inputs(*, packet_reader: Any, packet_pin: SourcePin,
                   admission_reader: Any, admission_pin: SourcePin,
                   consumer: Any) -> tuple[dict, dict[str, Readback]]:
    """Delegate unchanged to one existing pure comparator.

    Admission has a separate reader and independently supplied pin. The producer
    cannot select either this trusted configuration or the executable consumer.
    Empty admission is passed unchanged: the existing comparator returns UNKNOWN.
    """
    packet, packet_readback = read_json(packet_reader, packet_pin, consumer)
    admission, admission_readback = read_json(admission_reader, admission_pin, consumer)
    result = consumer.compare(packet, admission)
    return result, {"packet": packet_readback, "admission": admission_readback}
