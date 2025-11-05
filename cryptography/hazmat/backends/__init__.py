"""Backends stubs."""

from .openssl import backend as openssl_backend


def default_backend():
    return openssl_backend
