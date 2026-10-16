"""Where to send the user after a Google OAuth callback.

Native clients pass a custom URL scheme (`trackit://...`); the web client
passes a `return_url` on an allowlisted origin. Tokens go in the URL
fragment for web so they never reach a server's access logs.
"""

from urllib.parse import urlencode, urlsplit

from app.core.config import settings


def validate_web_return_url(return_url: str) -> str:
    """Return `return_url` if its origin is allowlisted, else raise ValueError."""
    parts = urlsplit(return_url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError("return_url must be an absolute http(s) URL")
    origin = f"{parts.scheme}://{parts.netloc}"
    if origin not in settings.web_return_origin_list:
        raise ValueError(f"return_url origin {origin} is not allowed")
    return return_url


def build_return_redirect(claims: dict, path: str, params: dict[str, str]) -> str:
    """Build the post-OAuth redirect from the state token claims.

    `path` is the native deep-link host (`auth`, `gmail-connected`); for web
    it travels as `kind` in the fragment so one page can handle both flows.
    """
    return_url = claims.get("return_url")
    if return_url:
        # Re-check: the allowlist may have changed during the 10-min state TTL.
        base = validate_web_return_url(return_url).split("#", 1)[0]
        return f"{base}#{urlencode({'kind': path, **params})}"
    scheme = claims.get("return_scheme") or settings.mobile_return_scheme
    return f"{scheme}://{path}?{urlencode(params)}"
