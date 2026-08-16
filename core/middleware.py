"""
Project security middleware.

  * ContentSecurityPolicyMiddleware  — per-request nonce + strict CSP
  * AdditionalSecurityHeadersMiddleware — Permissions-Policy, COOP/CORP, etc.
  * RequestSanityMiddleware — cheap request-shape checks + obvious probe blocking
  * AdminAccessLogMiddleware — audit trail for the admin surface
"""
import base64
import logging
import re
import secrets

from django.conf import settings
from django.http import HttpResponseForbidden
from django.utils.deprecation import MiddlewareMixin

from .security import get_client_ip

logger = logging.getLogger("svu.security")


class ContentSecurityPolicyMiddleware(MiddlewareMixin):
    """
    Emits a strict Content-Security-Policy with a fresh nonce per request.

    The nonce is exposed as ``request.csp_nonce`` and surfaced to templates by
    ``core.context_processors.security_context``.
    """

    NONCE_DIRECTIVES = ("script-src", "style-src")

    def process_request(self, request):
        request.csp_nonce = base64.b64encode(secrets.token_bytes(16)).decode("ascii")

    def process_response(self, request, response):
        header = (
            "Content-Security-Policy-Report-Only"
            if getattr(settings, "CSP_REPORT_ONLY", False)
            else "Content-Security-Policy"
        )
        if header in response or "Content-Security-Policy" in response:
            return response

        # The Django debug toolbar / technical 500 page relies on inline assets.
        if settings.DEBUG and response.status_code == 500:
            return response

        nonce = getattr(request, "csp_nonce", None)
        directives = []
        for directive, sources in settings.CSP_DIRECTIVES.items():
            values = list(sources)
            if nonce and directive in self.NONCE_DIRECTIVES:
                values.append(f"'nonce-{nonce}'")
            directives.append(f"{directive} {' '.join(values)}" if values else directive)

        # Not a source directive — appended verbatim.
        directives.append("upgrade-insecure-requests" if not settings.DEBUG else "")
        response[header] = "; ".join(d for d in directives if d)
        return response


class AdditionalSecurityHeadersMiddleware(MiddlewareMixin):
    """Headers Django does not set out of the box."""

    def process_response(self, request, response):
        response.setdefault("Permissions-Policy", settings.PERMISSIONS_POLICY)
        response.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        response.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        response.setdefault("X-DNS-Prefetch-Control", "off")

        # Never let a browser or proxy cache authenticated / admin responses.
        user = getattr(request, "user", None)
        is_authenticated = user is not None and user.is_authenticated
        in_admin = request.path.startswith("/" + settings.ADMIN_URL.lstrip("/"))
        if in_admin or is_authenticated:
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response["Pragma"] = "no-cache"

        # Do not advertise the stack.
        response.headers.pop("Server", None)
        return response


class RequestSanityMiddleware(MiddlewareMixin):
    """
    Rejects malformed or obviously hostile requests before they reach a view.

    This is a cheap first filter, not a replacement for a WAF — the real
    protection is Django's ORM/template escaping plus the form validation in
    ``core.forms`` and ``admissions.forms``.
    """

    MAX_QUERY_LENGTH = 2048
    MAX_URL_LENGTH = 2048

    # Common automated probes for stacks this site does not run.
    PROBE_PATHS = re.compile(
        r"(?:^|/)(?:wp-admin|wp-login\.php|wp-content|xmlrpc\.php|\.env|\.git/|"
        r"phpmyadmin|vendor/phpunit|\.aws/|\.ssh/|config\.php|shell\.php|"
        r"eval-stdin\.php|\.well-known/security\.txt/)",
        re.IGNORECASE,
    )

    TRAVERSAL = re.compile(r"(?:\.\./|\.\.\\|%2e%2e[/\\%])", re.IGNORECASE)

    def process_request(self, request):
        path = request.path or ""
        query = request.META.get("QUERY_STRING", "")

        if len(path) > self.MAX_URL_LENGTH or len(query) > self.MAX_QUERY_LENGTH:
            logger.warning("Oversized request from %s: %s", get_client_ip(request), path[:120])
            return HttpResponseForbidden("Request rejected.")

        if self.TRAVERSAL.search(path) or self.TRAVERSAL.search(query):
            logger.warning("Traversal attempt from %s: %s", get_client_ip(request), path[:120])
            return HttpResponseForbidden("Request rejected.")

        if self.PROBE_PATHS.search(path):
            logger.info("Blocked probe from %s: %s", get_client_ip(request), path[:120])
            return HttpResponseForbidden("Request rejected.")

        # Null bytes have no legitimate use in a URL.
        if "\x00" in path or "\x00" in query:
            return HttpResponseForbidden("Request rejected.")

        return None


class AdminAccessLogMiddleware(MiddlewareMixin):
    """Records every hit on the admin surface for later audit."""

    def process_response(self, request, response):
        admin_prefix = "/" + settings.ADMIN_URL.lstrip("/")
        if not request.path.startswith(admin_prefix):
            return response

        user = getattr(request, "user", None)
        username = (
            user.get_username() if user is not None and user.is_authenticated else "anonymous"
        )
        # Only log state-changing or failed requests to keep the log useful.
        if request.method != "GET" or response.status_code >= 400:
            logger.info(
                "ADMIN %s %s user=%s ip=%s status=%s",
                request.method,
                request.path,
                username,
                get_client_ip(request),
                response.status_code,
            )
        return response
