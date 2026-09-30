"""One HTTP client for everything that leaves for MyDramaList.

MDL sits behind Cloudflare, which scores a caller on two things at once: the
reputation of the address it comes from, and the TLS fingerprint of the client
making the call. Those two combine rather than being checked in turn, which is
why the same code can work from one machine and not another.

cloudscraper's fingerprint was good enough to pass from a residential address
and not from a datacenter one. Measured against the same three slugs in the
same minute: 9 successes out of 9 from a home connection, 4 out of 9 from a
Hetzner server. Plain curl was refused from both, so the address alone was
never the whole story either.

primp impersonates a real browser's handshake, and the same Hetzner box then
answered 12 out of 12. That is what makes self-hosting the scraper possible.

Everything goes through here so the profile is decided once.
"""

import os
from typing import Any, Dict

import primp

# The newest Safari this primp knows. primp 2 names profiles generically
# ("chrome", "safari", "firefox", "edge") for its latest of each, so keeping up
# with browsers is a dependency bump rather than a code change.
#
# Not Chrome. On 2026-09-30 Cloudflare began challenging primp 0.15's
# chrome_131 and chrome_133 from a residential address — MDL's /v1 JSON API
# first (threads, tag search), then its pages. primp 2's Chromium profiles fare
# no better: over the same 20 requests, "chrome" drew 403s on 2 to 6 and "edge"
# on 11, while "safari" and "firefox" drew none. If Safari starts drawing them,
# Firefox is the next name to try.
IMPERSONATE = "safari"

DEFAULT_TIMEOUT = 25

# Which client leaves for MDL: "primp" or "cloudscraper". On 2026-09-29 MDL
# refused primp from both Hetzner and Vercel (403 on every slug) while
# cloudscraper still passed from a home connection, so Vercel — which sets
# VERCEL=1 — falls back to the client it used before primp. MDL_CLIENT
# overrides either way.
CLIENT = os.environ.get("MDL_CLIENT") or ("cloudscraper" if os.environ.get("VERCEL") else "primp")

# Cloudflare went on to refuse every datacenter address, Vercel's included, and
# let only residential ones through. MDL_PROXY sends the calls out through one —
# e.g. "http://100.x.y.z:8888", a proxy on a home machine reached over Tailscale.
# Unset, calls leave directly.
PROXY = os.environ.get("MDL_PROXY") or None


class _CloudscraperClient:
    """cloudscraper behind primp's call shape: a timeout set once, not per call."""

    def __init__(self, timeout: int) -> None:
        import cloudscraper  # type: ignore[import-untyped,import-not-found,unused-ignore]

        self._session = cloudscraper.create_scraper()
        if PROXY:
            self._session.proxies = {"http": PROXY, "https": PROXY}
        self._timeout = timeout

    def get(self, url: str, **kwargs: Any) -> Any:
        return self._session.get(url, timeout=self._timeout, **kwargs)

    def post(self, url: str, **kwargs: Any) -> Any:
        return self._session.post(url, timeout=self._timeout, **kwargs)


def client(timeout: int = DEFAULT_TIMEOUT) -> Any:
    if CLIENT == "cloudscraper":
        return _CloudscraperClient(timeout)
    return primp.Client(impersonate=IMPERSONATE, timeout=timeout, proxy=PROXY)


def as_params(values: Dict[str, Any]) -> Dict[str, str]:
    """Query values as strings, which primp requires and requests did not.

    Passing an int raises `'int' object cannot be converted to 'PyString'`, so
    every caller that builds a params dict from route arguments has to come
    through here. Nones are dropped rather than sent as the string "None".
    """
    return {k: str(v) for k, v in values.items() if v is not None}
