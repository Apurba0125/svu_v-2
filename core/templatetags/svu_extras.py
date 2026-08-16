"""Template helpers used across the site templates."""
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from core.security import sanitize_html

register = template.Library()


@register.filter(name="richtext")
def richtext(value):
    """
    Render editor HTML after a final sanitising pass.

    Content is already cleaned on save; doing it again on output means a row
    written directly to the database (migration, fixture, SQL console) still
    cannot inject script into a page.
    """
    return mark_safe(sanitize_html(value or ""))


@register.filter(name="split_heading")
def split_heading(value, first_words=2):
    """
    Split a heading into a dark part and an accent part.

    "WELCOME TO SWAMI VIVEKANANDA UNIVERSITY" ->
    "<span class='h-dark'>WELCOME TO</span> <span class='h-accent'>SISTER…</span>"
    """
    words = (value or "").split()
    try:
        first_words = int(first_words)
    except (TypeError, ValueError):
        first_words = 2
    head = escape(" ".join(words[:first_words]))
    tail = escape(" ".join(words[first_words:]))
    if not tail:
        return mark_safe(f'<span class="h-dark">{head}</span>')
    return mark_safe(f'<span class="h-dark">{head}</span> <span class="h-accent">{tail}</span>')


@register.filter(name="file_url")
def file_url(field_file):
    """
    Safe ``.url`` for a possibly-empty File/ImageField.

    Accessing ``.url`` on an empty field raises ValueError, and Django's
    template engine does not silence that — so optional images need this.
    """
    try:
        return field_file.url
    except (ValueError, AttributeError):
        return ""


@register.filter(name="tel_href")
def tel_href(value):
    """Turn a display phone number into a dialable tel: target."""
    digits = "".join(ch for ch in str(value or "") if ch.isdigit() or ch == "+")
    return f"tel:{digits}"


@register.filter(name="initials")
def initials(value):
    parts = [p for p in str(value or "").split() if p]
    return "".join(p[0].upper() for p in parts[:2]) or "?"


@register.simple_tag(takes_context=True)
def is_current(context, path, css_class="is-current"):
    """Emit a CSS class when the given path matches the current URL."""
    request = context.get("request")
    if not request or not path or path == "#":
        return ""
    current = request.path
    if path == "/":
        return css_class if current == "/" else ""
    return css_class if current.startswith(path) else ""


@register.simple_tag
def query_string(request, **kwargs):
    """Rebuild the query string with overrides — keeps filters across pagination."""
    params = request.GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    encoded = params.urlencode()
    return f"?{encoded}" if encoded else ""


@register.filter(name="field_type")
def field_type(field):
    return field.field.widget.__class__.__name__.lower()


@register.filter(name="get_item")
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None
