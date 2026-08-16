"""Tests for the site chrome, content rendering and the security middleware."""
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from core.models import FAQ, Page, SiteConfiguration
from core.security import (
    RateLimitExceeded,
    check_rate_limit,
    looks_like_injection,
    sanitize_html,
    strip_control_characters,
)
from core.validators import validate_document_file, validate_image_file


class SecurityHeaderTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_all_security_headers_present(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        expected = {
            "Content-Security-Policy",
            "X-Frame-Options",
            "X-Content-Type-Options",
            "Referrer-Policy",
            "Permissions-Policy",
            "Cross-Origin-Opener-Policy",
            "Cross-Origin-Resource-Policy",
            "X-Permitted-Cross-Domain-Policies",
        }
        missing = expected - set(response.headers)
        self.assertEqual(missing, set(), f"Missing security headers: {missing}")

    def test_csp_blocks_inline_and_objects(self):
        csp = self.client.get("/").headers["Content-Security-Policy"]
        self.assertIn("object-src 'none'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("base-uri 'self'", csp)
        self.assertIn("form-action 'self'", csp)
        # No blanket unsafe-inline / unsafe-eval anywhere in the policy.
        self.assertNotIn("unsafe-inline", csp)
        self.assertNotIn("unsafe-eval", csp)

    def test_csp_nonce_is_unique_per_request(self):
        first = self.client.get("/").headers["Content-Security-Policy"]
        second = self.client.get("/").headers["Content-Security-Policy"]
        self.assertNotEqual(first, second, "CSP nonce must be regenerated per request")

    def test_x_frame_options_denies_framing(self):
        self.assertEqual(self.client.get("/").headers["X-Frame-Options"], "DENY")


class RequestSanityTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_common_probe_paths_are_blocked(self):
        for path in ("/wp-login.php", "/.env", "/phpmyadmin/", "/xmlrpc.php"):
            self.assertEqual(
                self.client.get(path).status_code, 403, f"{path} should be rejected"
            )

    def test_path_traversal_is_blocked(self):
        self.assertEqual(self.client.get("/page/..%2f..%2fetc/passwd").status_code, 403)

    def test_oversized_query_string_is_blocked(self):
        response = self.client.get("/search/", {"q": "a" * 3000})
        self.assertEqual(response.status_code, 403)


class AdminSurfaceTests(TestCase):
    def test_admin_is_not_at_the_default_path(self):
        self.assertNotEqual(settings.ADMIN_URL, "admin/")
        self.assertEqual(self.client.get("/admin/").status_code, 404)

    def test_admin_requires_authentication(self):
        response = self.client.get("/" + settings.ADMIN_URL, follow=False)
        self.assertIn(response.status_code, (301, 302))
        self.assertIn("login", response.headers.get("Location", ""))

    def test_robots_txt_disallows_admin(self):
        body = self.client.get("/robots.txt").content.decode()
        self.assertIn("Disallow: /" + settings.ADMIN_URL.lstrip("/"), body)


class SanitisationTests(TestCase):
    def test_script_tags_are_stripped(self):
        dirty = '<p>Hello</p><script>alert("xss")</script>'
        self.assertNotIn("<script", sanitize_html(dirty))
        self.assertIn("<p>Hello</p>", sanitize_html(dirty))

    def test_event_handlers_are_stripped(self):
        self.assertNotIn("onerror", sanitize_html('<img src=x onerror="alert(1)">'))

    def test_javascript_protocol_is_stripped(self):
        cleaned = sanitize_html('<a href="javascript:alert(1)">click</a>')
        self.assertNotIn("javascript:", cleaned)

    def test_page_content_is_sanitised_on_save(self):
        page = Page.objects.create(
            title="XSS attempt", content='<p>ok</p><script>alert(1)</script>'
        )
        page.refresh_from_db()
        self.assertNotIn("<script", page.content)

    def test_stored_xss_does_not_reach_the_rendered_page(self):
        Page.objects.create(
            title="Injected", slug="injected",
            content='<p>safe</p><script>alert("pwn")</script>',
        )
        body = self.client.get("/page/injected/").content.decode()
        self.assertNotIn("<script>alert", body)

    def test_control_characters_are_removed(self):
        self.assertEqual(strip_control_characters("hel\x00lo​"), "hello")

    def test_injection_heuristics(self):
        self.assertTrue(looks_like_injection("<script>alert(1)</script>"))
        self.assertTrue(looks_like_injection("1 UNION SELECT password FROM users"))
        self.assertFalse(looks_like_injection("I would like to know about B.Tech CSE"))


class RateLimitTests(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @override_settings(RATELIMIT_RULES={"test": (3, 60)})
    def test_quota_is_enforced(self):
        request = self.client.get("/").wsgi_request
        for _ in range(3):
            check_rate_limit(request, "test")
        with self.assertRaises(RateLimitExceeded):
            check_rate_limit(request, "test")

    @override_settings(RATELIMIT_RULES={"contact": (3, 3600)})
    def test_contact_form_is_rate_limited(self):
        payload = {"name": "Test", "email": "t@example.com", "subject": "Hi",
                   "message": "Hello", "captcha": "wrong", "form_ts": "x"}
        statuses = [self.client.post("/contact/", payload).status_code for _ in range(5)]
        self.assertEqual(statuses[-1], 429, "Contact form should refuse once the quota is spent")
        self.assertEqual(
            self.client.post("/contact/", payload).headers.get("Retry-After") is not None,
            True,
            "A 429 must tell the client when to retry",
        )


class UploadValidatorTests(TestCase):
    def test_executable_disguised_as_image_is_rejected(self):
        bogus = SimpleUploadedFile("payload.png", b"MZ\x90\x00 not a real png", "image/png")
        with self.assertRaises(ValidationError):
            validate_image_file(bogus)

    def test_svg_with_script_is_rejected(self):
        evil = SimpleUploadedFile(
            "logo.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
            "image/svg+xml",
        )
        with self.assertRaises(ValidationError):
            validate_image_file(evil)

    def test_disallowed_extension_is_rejected(self):
        php = SimpleUploadedFile("shell.php", b"<?php system($_GET['c']); ?>", "image/png")
        with self.assertRaises(ValidationError):
            validate_image_file(php)

    def test_document_magic_bytes_must_match_extension(self):
        fake_pdf = SimpleUploadedFile("notice.pdf", b"NOT-A-PDF-AT-ALL", "application/pdf")
        with self.assertRaises(ValidationError):
            validate_document_file(fake_pdf)

    def test_oversized_upload_is_rejected(self):
        big = SimpleUploadedFile("big.png", b"\x89PNG\r\n\x1a\n" + b"0" * (6 * 1024 * 1024), "image/png")
        with self.assertRaises(ValidationError):
            validate_image_file(big)


class ContentRenderingTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_home_page_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/home.html")

    def test_singleton_config_cannot_be_duplicated(self):
        SiteConfiguration.get_solo()
        # save() pins the row to pk=1, so a second INSERT is refused outright.
        with self.assertRaises(IntegrityError), transaction.atomic():
            SiteConfiguration.objects.create(site_name="Second")
        self.assertEqual(SiteConfiguration.objects.count(), 1)

    def test_singleton_config_cannot_be_deleted(self):
        with self.assertRaises(RuntimeError):
            SiteConfiguration.get_solo().delete()

    def test_unpublished_page_is_not_reachable(self):
        Page.objects.create(title="Draft", slug="draft", content="<p>x</p>", is_published=False)
        self.assertEqual(self.client.get("/page/draft/").status_code, 404)

    def test_faq_page_groups_by_category(self):
        FAQ.objects.create(question="Q1?", answer="<p>A1</p>", category="Admission")
        response = self.client.get("/faq/")
        self.assertContains(response, "Q1?")

    def test_404_page_uses_the_branded_template(self):
        response = self.client.get("/no-such-page/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "PAGE NOT FOUND", status_code=404)

    def test_search_rejects_injection_input(self):
        response = self.client.get("/search/", {"q": "<script>alert(1)</script>"})
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<script>alert(1)</script>")
