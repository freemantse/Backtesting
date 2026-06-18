"""Minimal stdlib HTTP GET so keyless sources work without `requests`.

TLS resolution order (handles corporate proxies with a custom root CA):
  1. ``SIXCYCLE_INSECURE_SSL=1``  -> disable verification (last resort, warns).
  2. ``SIXCYCLE_CA_BUNDLE`` / ``REQUESTS_CA_BUNDLE`` / ``SSL_CERT_FILE`` -> use it.
  3. ``certifi`` bundle if installed.
  4. system default.
Proxies are honoured automatically from ``HTTP_PROXY`` / ``HTTPS_PROXY``.
"""
from __future__ import annotations

import io
import os
import ssl
import urllib.request

_WARNED_INSECURE = False


def _ssl_context() -> ssl.SSLContext:
    global _WARNED_INSECURE
    if os.environ.get("SIXCYCLE_INSECURE_SSL") == "1":
        if not _WARNED_INSECURE:
            print("[http] WARNING: TLS verification disabled (SIXCYCLE_INSECURE_SSL=1).")
            _WARNED_INSECURE = True
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    for var in ("SIXCYCLE_CA_BUNDLE", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
        cafile = os.environ.get(var)
        if cafile and os.path.exists(cafile):
            return ssl.create_default_context(cafile=cafile)
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        return ssl.create_default_context()


def get_text(url: str, timeout: int = 60) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "sixcycle/0.1"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:  # noqa: S310
        return resp.read().decode("utf-8", errors="replace")


def get_csv_buffer(url: str, timeout: int = 60) -> io.StringIO:
    return io.StringIO(get_text(url, timeout=timeout))
