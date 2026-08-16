"""
Field/upload validators.

Upload handling is the highest-risk surface in a CMS-backed site, so files are
checked on three axes: declared extension, real decoded content, and size.
"""
import os
import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils.deconstruct import deconstructible
from django.utils.translation import gettext_lazy as _

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".xls", ".xlsx"}

MAX_IMAGE_WIDTH = 6000
MAX_IMAGE_HEIGHT = 6000


def _max_bytes():
    return getattr(settings, "MAX_UPLOAD_SIZE_MB", 4) * 1024 * 1024


def _check_size(upload):
    limit = _max_bytes()
    if upload.size > limit:
        raise ValidationError(
            _("File is too large (%(size).1f MB). Maximum allowed is %(limit)s MB.")
            % {"size": upload.size / 1024 / 1024, "limit": limit // 1024 // 1024}
        )


def validate_image_file(upload):
    """Extension + real-content + size + dimension checks for image uploads."""
    _check_size(upload)

    ext = os.path.splitext(upload.name)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            _("Unsupported image type '%(ext)s'. Allowed: %(allowed)s.")
            % {"ext": ext, "allowed": ", ".join(sorted(ALLOWED_IMAGE_EXTENSIONS))}
        )

    # SVG is XML, not a raster image: scan it for active content instead.
    if ext == ".svg":
        return _validate_svg(upload)

    try:
        from PIL import Image
    except ImportError:      # pragma: no cover
        return

    try:
        upload.seek(0)
        image = Image.open(upload)
        image.verify()          # detects truncated/forged files
        upload.seek(0)
        # verify() invalidates the object, so reopen to read the size.
        width, height = Image.open(upload).size
    except Exception as exc:
        raise ValidationError(
            _("This file is not a valid image or is corrupted.")
        ) from exc
    finally:
        upload.seek(0)

    if width > MAX_IMAGE_WIDTH or height > MAX_IMAGE_HEIGHT:
        raise ValidationError(
            _("Image is too large (%(w)sx%(h)s px). Maximum %(mw)sx%(mh)s px.")
            % {"w": width, "h": height, "mw": MAX_IMAGE_WIDTH, "mh": MAX_IMAGE_HEIGHT}
        )


_SVG_DANGEROUS = re.compile(
    rb"<\s*script|javascript:|on\w+\s*=|<\s*foreignObject|<\s*iframe|"
    rb"<!ENTITY|xlink:href\s*=\s*[\"']\s*(?!#)",
    re.IGNORECASE,
)


def _validate_svg(upload):
    upload.seek(0)
    payload = upload.read(512 * 1024)
    upload.seek(0)
    if b"<svg" not in payload.lower():
        raise ValidationError(_("This file does not look like an SVG image."))
    if _SVG_DANGEROUS.search(payload):
        raise ValidationError(
            _("This SVG contains scripting or external references and was rejected.")
        )


def validate_document_file(upload):
    """Notice attachments: PDF/Office only, size-capped, magic-byte checked."""
    _check_size(upload)

    ext = os.path.splitext(upload.name)[1].lower()
    if ext not in ALLOWED_DOCUMENT_EXTENSIONS:
        raise ValidationError(
            _("Unsupported document type '%(ext)s'. Allowed: %(allowed)s.")
            % {"ext": ext, "allowed": ", ".join(sorted(ALLOWED_DOCUMENT_EXTENSIONS))}
        )

    upload.seek(0)
    header = upload.read(8)
    upload.seek(0)
    signatures = {
        ".pdf": [b"%PDF"],
        ".doc": [b"\xd0\xcf\x11\xe0"],
        ".xls": [b"\xd0\xcf\x11\xe0"],
        ".docx": [b"PK\x03\x04"],
        ".xlsx": [b"PK\x03\x04"],
    }
    expected = signatures.get(ext, [])
    if expected and not any(header.startswith(sig) for sig in expected):
        raise ValidationError(
            _("The file contents do not match its '%(ext)s' extension.") % {"ext": ext}
        )


@deconstructible
class SafeFileNameValidator:
    """Blocks path separators and double extensions in user-supplied names."""

    pattern = re.compile(r"^[A-Za-z0-9._\- ]+$")

    def __call__(self, upload):
        name = os.path.basename(getattr(upload, "name", "") or "")
        if not name or not self.pattern.match(name):
            raise ValidationError(
                _("File name may only contain letters, numbers, spaces, dots, "
                  "hyphens and underscores.")
            )
        if name.count(".") > 1:
            stem, ext = os.path.splitext(name)
            if os.path.splitext(stem)[1].lower() in (
                ALLOWED_IMAGE_EXTENSIONS | ALLOWED_DOCUMENT_EXTENSIONS
                | {".php", ".exe", ".sh", ".js", ".html"}
            ):
                raise ValidationError(_("Double file extensions are not allowed."))

    def __eq__(self, other):
        return isinstance(other, SafeFileNameValidator)


# ---------------------------------------------------------------------------
# Text validators for the public forms
# ---------------------------------------------------------------------------
phone_validator = RegexValidator(
    regex=r"^[6-9]\d{9}$",
    message=_("Enter a valid 10-digit Indian mobile number (starting 6-9)."),
)

name_validator = RegexValidator(
    regex=r"^[A-Za-z][A-Za-z .'\-]{1,79}$",
    message=_("Name may only contain letters, spaces, apostrophes, dots and hyphens."),
)

slug_validator = RegexValidator(
    regex=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    message=_("Use lowercase letters, numbers and hyphens only."),
)

_URL_IN_TEXT = re.compile(r"(https?://|www\.|\b\w+\.(?:com|net|org|ru|xyz|top|info)\b)", re.I)


def validate_no_links(value):
    """Public free-text fields have no legitimate reason to carry URLs — spam does."""
    if value and _URL_IN_TEXT.search(value):
        raise ValidationError(_("Links are not allowed in this field."))


def validate_youtube_id(value):
    if value and not re.match(r"^[A-Za-z0-9_-]{6,20}$", value):
        raise ValidationError(
            _("Enter only the YouTube video ID, e.g. dQw4w9WgXcQ (not the full URL).")
        )
