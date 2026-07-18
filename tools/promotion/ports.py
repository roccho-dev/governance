from __future__ import annotations

from typing import Any, Iterable, Protocol


class PromotionSourceReader(Protocol):
    def read_events(self) -> Iterable[dict[str, Any]]: ...


class GatePacketReader(Protocol):
    def read_gate_packet(self) -> dict[str, Any]: ...


class Signer(Protocol):
    def key_id(self) -> str: ...

    def sign(self, payload: bytes) -> bytes: ...


class PromotionWriter(Protocol):
    def append(
        self,
        event: dict[str, Any],
        signature: bytes,
        receipt: dict[str, Any],
    ) -> None: ...
