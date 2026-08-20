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

from typing import Any, Dict

import primp

# Desktop Chrome, the handshake MDL sees most. chrome_130, firefox_133 and
# safari_18 were tested and pass too — this is a preference, not a dependency.
IMPERSONATE = "chrome_131"

DEFAULT_TIMEOUT = 25


def client(timeout: int = DEFAULT_TIMEOUT) -> primp.Client:
    return primp.Client(impersonate=IMPERSONATE, timeout=timeout)


def as_params(values: Dict[str, Any]) -> Dict[str, str]:
    """Query values as strings, which primp requires and requests did not.

    Passing an int raises `'int' object cannot be converted to 'PyString'`, so
    every caller that builds a params dict from route arguments has to come
    through here. Nones are dropped rather than sent as the string "None".
    """
    return {k: str(v) for k, v in values.items() if v is not None}
