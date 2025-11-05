"""Hash primitive stubs."""

from __future__ import annotations


class MD5:
    def __init__(self) -> None:
        pass


class Hash:
    def __init__(self, algorithm: MD5, backend: object | None = None) -> None:
        self.algorithm = algorithm
        self._data = bytearray()

    def update(self, data: bytes) -> None:
        self._data.extend(data)

    def finalize(self) -> bytes:
        return bytes(self._data)
