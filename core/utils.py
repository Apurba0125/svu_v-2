"""Shared helpers used across apps."""
import os
import secrets

from django.utils.deconstruct import deconstructible
from django.utils.text import slugify


@deconstructible
class upload_path:
    """
    ``upload_to`` callable that discards the client-supplied filename.

    Keeping only a slugified stem plus a random suffix defeats path traversal,
    overwriting of existing media, and extension-smuggling tricks in one go.
    Declared as a deconstructible class so migrations can serialise it (a
    plain closure cannot be).
    """

    def __init__(self, folder):
        self.folder = folder.strip("/")

    def __call__(self, instance, filename):
        stem, ext = os.path.splitext(os.path.basename(filename))
        ext = ext.lower()[:10]
        safe_stem = slugify(stem)[:40] or "file"
        return f"{self.folder}/{safe_stem}-{secrets.token_hex(6)}{ext}"

    def __eq__(self, other):
        return isinstance(other, upload_path) and self.folder == other.folder

    def __hash__(self):
        return hash(("upload_path", self.folder))


def unique_slug(model, value, instance=None, field="slug", max_length=200):
    """Return a slug unique across ``model``, ignoring ``instance`` itself."""
    base = slugify(value)[:max_length] or secrets.token_hex(4)
    candidate = base
    counter = 2
    queryset = model._default_manager.all()
    if instance is not None and instance.pk:
        queryset = queryset.exclude(pk=instance.pk)
    while queryset.filter(**{field: candidate}).exists():
        suffix = f"-{counter}"
        candidate = f"{base[: max_length - len(suffix)]}{suffix}"
        counter += 1
    return candidate


def truncate_words(text, count):
    words = (text or "").split()
    if len(words) <= count:
        return " ".join(words)
    return " ".join(words[:count]) + "…"
