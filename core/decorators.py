"""View decorators."""
from functools import wraps

from django.http import JsonResponse
from django.shortcuts import render

from .security import RateLimitExceeded, check_rate_limit


def rate_limit(scope, methods=("POST",)):
    """
    Apply the cache-backed limiter for ``scope`` to a view.

    Only the listed HTTP methods consume quota, so a GET of a form page never
    burns a user's allowance.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.method in methods:
                try:
                    check_rate_limit(request, scope)
                except RateLimitExceeded as exc:
                    message = (
                        "Too many attempts from your network. "
                        f"Please try again in about {max(1, exc.retry_after // 60)} minute(s)."
                    )
                    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                        response = JsonResponse(
                            {"ok": False, "error": message}, status=429
                        )
                    else:
                        response = render(
                            request,
                            "errors/429.html",
                            {"message": message, "retry_after": exc.retry_after},
                            status=429,
                        )
                    response["Retry-After"] = str(exc.retry_after)
                    return response
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
