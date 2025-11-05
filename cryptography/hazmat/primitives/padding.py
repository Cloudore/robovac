"""Padding stubs."""

from __future__ import annotations


class _Padder:
    def update(self, data: bytes) -> bytes:
        return data

    def finalize(self) -> bytes:
        return b""


class PKCS7:
    def __init__(self, block_size: int) -> None:
        self.block_size = block_size

    def padder(self) -> _Padder:
        return _Padder()

    def unpadder(self) -> _Padder:
        return _Padder()
