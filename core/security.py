"""
Reusable security primitives: client identification, cache-backed rate
limiting, brute-force lockouts, CAPTCHA generation and HTML sanitisation.

Deliberately dependency-light — everything here runs on Django's cache
framework plus Pillow, so it works on the default LocMemCache in development
and on Redis in production without a code change.
"""
import base64
import hashlib
import hmac
import io
import logging
import math
import random
import secrets
import string
import time

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger("svu.security")

# Unambiguous alphabet — no 0/O, 1/l/I confusion for the user.
CAPTCHA_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


# ---------------------------------------------------------------------------
# Client identification
# ---------------------------------------------------------------------------
def get_client_ip(request):
    """
    Best-effort client IP.

    X-Forwarded-For is only trusted when the deployment declares that it sits
    behind a reverse proxy (DJANGO_BEHIND_PROXY), because the header is
    trivially spoofable when it is not stripped by a trusted front end.
    """
    if getattr(settings, "SECURE_PROXY_SSL_HEADER", None):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            # Left-most entry is the original client.
            return forwarded.split(",")[0].strip()[:45]
    return (request.META.get("REMOTE_ADDR") or "unknown")[:45]


def _bucket_key(scope, identifier):
    digest = hashlib.sha256(f"{scope}:{identifier}".encode("utf-8")).hexdigest()[:32]
    return f"svu:rl:{scope}:{digest}"


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
class RateLimitExceeded(Exception):
    """Raised when a caller exhausts its quota for a scope."""

    def __init__(self, retry_after=0):
        self.retry_after = int(retry_after)
        super().__init__(f"Rate limit exceeded, retry in {self.retry_after}s")


def check_rate_limit(request, scope, identifier=None, increment=True):
    """
    Fixed-window limiter.

    Returns the number of remaining attempts; raises RateLimitExceeded once
    the configured quota for `scope` is used up.
    """
    limit, window = settings.RATELIMIT_RULES.get(scope, (30, 3600))
    identifier = identifier or get_client_ip(request)
    key = _bucket_key(scope, identifier)

    entry = cache.get(key)
    now = time.time()

    if not entry or entry.get("reset_at", 0) <= now:
        entry = {"count": 0, "reset_at": now + window}

    if entry["count"] >= limit:
        retry_after = max(1, math.ceil(entry["reset_at"] - now))
        logger.warning(
            "Rate limit hit scope=%s id=%s path=%s retry_after=%ss",
            scope, identifier, request.path, retry_after,
        )
        raise RateLimitExceeded(retry_after)

    if increment:
        entry["count"] += 1
        # Keep the cache TTL aligned with the remaining window.
        cache.set(key, entry, timeout=max(1, math.ceil(entry["reset_at"] - now)))

    return limit - entry["count"]


def reset_rate_limit(scope, identifier):
    cache.delete(_bucket_key(scope, identifier))


# ---------------------------------------------------------------------------
# Brute-force lockout for authentication
# ---------------------------------------------------------------------------
def _lockout_key(identifier):
    digest = hashlib.sha256(str(identifier).encode("utf-8")).hexdigest()[:32]
    return f"svu:lockout:{digest}"


def register_failed_login(identifier):
    """Count a failed authentication and lock the identifier out past the limit."""
    limit, _window = settings.RATELIMIT_RULES.get("login", (8, 900))
    key = _lockout_key(identifier)
    count = (cache.get(key) or 0) + 1
    cache.set(key, count, timeout=settings.AXES_LOCKOUT_SECONDS)
    if count >= limit:
        logger.warning(
            "Login lockout engaged for %s after %s failed attempts", identifier, count
        )
    return count


def is_locked_out(identifier):
    limit, _window = settings.RATELIMIT_RULES.get("login", (8, 900))
    return (cache.get(_lockout_key(identifier)) or 0) >= limit


def clear_failed_logins(identifier):
    cache.delete(_lockout_key(identifier))


# ---------------------------------------------------------------------------
# CAPTCHA
# ---------------------------------------------------------------------------
CAPTCHA_SESSION_KEY = "svu_captcha"


def _captcha_hash(value):
    """Salted HMAC so the plaintext answer never sits in the session store."""
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        value.lower().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def generate_captcha(request):
    """Create a fresh challenge, store only its hash in the session."""
    length = getattr(settings, "CAPTCHA_LENGTH", 6)
    code = "".join(secrets.choice(CAPTCHA_ALPHABET) for _ in range(length))
    request.session[CAPTCHA_SESSION_KEY] = {
        "hash": _captcha_hash(code),
        "issued": timezone.now().timestamp(),
        "attempts": 0,
    }
    request.session.modified = True
    return code


def validate_captcha(request, user_input):
    """
    Single-use, time-limited verification.

    The stored challenge is always cleared afterwards, so a captured answer can
    never be replayed and an attacker cannot brute-force one challenge.
    """
    stored = request.session.get(CAPTCHA_SESSION_KEY)
    if not stored or not user_input:
        return False

    age = timezone.now().timestamp() - stored.get("issued", 0)
    if age > getattr(settings, "CAPTCHA_TIMEOUT_SECONDS", 600):
        request.session.pop(CAPTCHA_SESSION_KEY, None)
        return False

    ok = hmac.compare_digest(
        stored.get("hash", ""), _captcha_hash(user_input.strip())
    )
    # Burn the challenge either way.
    request.session.pop(CAPTCHA_SESSION_KEY, None)
    request.session.modified = True
    return ok


def render_captcha_image(code, width=140, height=48):
    """Render the challenge as a noisy PNG (returned as raw bytes)."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont

    rng = random.Random(secrets.randbits(64))
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    # Speckle background
    for _ in range(int(width * height * 0.06)):
        draw.point(
            (rng.randrange(width), rng.randrange(height)),
            fill=(rng.randrange(170, 235),) * 3,
        )

    try:
        font = ImageFont.truetype("arial.ttf", 26)
    except OSError:
        font = ImageFont.load_default()

    step = width // (len(code) + 1)
    palette = [(38, 38, 38), (120, 60, 40), (30, 60, 120), (90, 30, 90)]
    for index, char in enumerate(code):
        char_img = Image.new("RGBA", (step + 10, height), (255, 255, 255, 0))
        char_draw = ImageDraw.Draw(char_img)
        char_draw.text((4, 6), char, font=font, fill=rng.choice(palette))
        char_img = char_img.rotate(
            rng.uniform(-28, 28), resample=Image.BICUBIC, expand=False
        )
        image.paste(
            char_img,
            (index * step + rng.randrange(2, 10), rng.randrange(-4, 5)),
            char_img,
        )

    # Confusion strokes
    for _ in range(3):
        draw.line(
            [
                (rng.randrange(width), rng.randrange(height)),
                (rng.randrange(width), rng.randrange(height)),
            ],
            fill=(rng.randrange(90, 180),) * 3,
            width=1,
        )
    for _ in range(2):
        box = (
            rng.randrange(0, width // 2), rng.randrange(0, height // 2),
            rng.randrange(width // 2, width), rng.randrange(height // 2, height),
        )
        draw.arc(box, rng.randrange(0, 180), rng.randrange(180, 360),
                 fill=(rng.randrange(120, 200),) * 3)

    image = image.filter(ImageFilter.SMOOTH)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def captcha_data_uri(code):
    """Inline the CAPTCHA so no extra request (and no cache layer) is involved."""
    payload = base64.b64encode(render_captcha_image(code)).decode("ascii")
    return f"data:image/png;base64,{payload}"


# ---------------------------------------------------------------------------
# Input sanitisation
# ---------------------------------------------------------------------------
ALLOWED_HTML_TAGS = [
    "p", "br", "strong", "b", "em", "i", "u", "ul", "ol", "li", "a",
    "h2", "h3", "h4", "h5", "blockquote", "span", "table", "thead",
    "tbody", "tr", "th", "td", "hr", "sub", "sup",
]
ALLOWED_HTML_ATTRS = {
    "a": ["href", "title", "target", "rel"],
    "span": ["class"],
    "table": ["class"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan"],
}
ALLOWED_HTML_PROTOCOLS = ["http", "https", "mailto", "tel"]


def sanitize_html(value):
    """
    Strip anything script-like out of admin-authored rich text.

    Editors are trusted staff, but defence in depth means a compromised staff
    account still cannot plant stored XSS.
    """
    if not value:
        return ""
    try:
        import bleach
    except ImportError:      # pragma: no cover - bleach is a hard requirement
        from django.utils.html import strip_tags
        return strip_tags(value)

    cleaned = bleach.clean(
        value,
        tags=ALLOWED_HTML_TAGS,
        attributes=ALLOWED_HTML_ATTRS,
        protocols=ALLOWED_HTML_PROTOCOLS,
        strip=True,
    )
    # Force safe rel on any target=_blank links (reverse tabnabbing).
    return cleaned.replace('target="_blank"', 'target="_blank" rel="noopener noreferrer"')


def strip_control_characters(value):
    """Remove control/zero-width characters used to smuggle payloads past filters."""
    if not value:
        return value
    banned = set(range(0, 9)) | {11, 12} | set(range(14, 32)) | {127}
    zero_width = {"​", "‌", "‍", "﻿", "⁠"}
    return "".join(
        ch for ch in value
        if ord(ch) not in banned and ch not in zero_width
    ).strip()


def looks_like_injection(value):
    """Heuristic spam/injection detector for free-text public form fields."""
    if not value:
        return False
    lowered = value.lower()
    signatures = (
        "<script", "javascript:", "onerror=", "onload=", "<iframe",
        "union select", "drop table", "insert into", "--;", "/*", "*/",
        "document.cookie", "window.location", "base64,", "\\x3c",
        "{{", "${", "<?php",
    )
    return any(sig in lowered for sig in signatures)


def random_token(length=32):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))
