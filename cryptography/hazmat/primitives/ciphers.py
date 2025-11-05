"""Cipher stubs."""

from __future__ import annotations


class AES:
    def __init__(self, key: bytes) -> None:
        self.key = key


class ECB:
    def __init__(self, iv: bytes | None = None) -> None:
        self.iv = iv


class algorithms:
    AES = AES


class modes:
    ECB = ECB


class Cipher:
    """Simple cipher shim that performs identity operations."""

    def __init__(self, algorithm: AES, mode: ECB, backend: object | None = None) -> None:
        self.algorithm = algorithm
        self.mode = mode

    def decryptor(self) -> "Cipher":
        return self

    def update(self, data: bytes) -> bytes:  # pragma: no cover - trivial
        return data

    def finalize(self) -> bytes:  # pragma: no cover - trivial
        return b""
