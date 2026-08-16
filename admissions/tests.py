"""End-to-end tests for the admission enquiry pipeline and its abuse controls."""
from django.core import signing
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from academics.models import Course, Program, School
from core.forms import FORM_TIMESTAMP_SALT
from core.security import CAPTCHA_SESSION_KEY, _captcha_hash

from .models import City, Enquiry, State

CAPTCHA_ANSWER = "ab12cd"


class EnquiryFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.state = State.objects.create(name="West Bengal")
        cls.other_state = State.objects.create(name="Bihar")
        cls.city = City.objects.create(state=cls.state, name="Kolkata")
        cls.other_city = City.objects.create(state=cls.other_state, name="Patna")
        cls.program = Program.objects.create(name="UG")
        cls.other_program = Program.objects.create(name="PG")
        cls.school = School.objects.create(name="School of Engineering")
        cls.course = Course.objects.create(
            school=cls.school, program=cls.program, name="B.Tech CSE"
        )
        cls.pg_course = Course.objects.create(
            school=cls.school, program=cls.other_program, name="M.Tech CSE"
        )

    def setUp(self):
        cache.clear()
        self.url = reverse("admissions:enquiry_submit")

    def tearDown(self):
        cache.clear()

    # -- helpers ---------------------------------------------------------
    def _prime_captcha(self, answer=CAPTCHA_ANSWER):
        session = self.client.session
        session[CAPTCHA_SESSION_KEY] = {
            "hash": _captcha_hash(answer),
            "issued": timezone.now().timestamp(),
            "attempts": 0,
        }
        session.save()

    def _timestamp(self, seconds_ago=30):
        return signing.dumps(
            timezone.now().timestamp() - seconds_ago, salt=FORM_TIMESTAMP_SALT
        )

    def _payload(self, **overrides):
        data = {
            "full_name": "Anita Sharma",
            "email": "anita@example.com",
            "mobile": "9876543210",
            "state": self.state.pk,
            "city": self.city.pk,
            "program": self.program.pk,
            "course": self.course.pk,
            "department": "",
            "captcha": CAPTCHA_ANSWER,
            "consent_given": "on",
            "website": "",
            "form_ts": self._timestamp(),
        }
        data.update(overrides)
        return data

    def _post(self, payload):
        return self.client.post(self.url, payload, HTTP_X_REQUESTED_WITH="XMLHttpRequest")

    # -- happy path ------------------------------------------------------
    def test_valid_enquiry_is_saved(self):
        self._prime_captcha()
        response = self._post(self._payload())
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["ok"])

        enquiry = Enquiry.objects.get()
        self.assertEqual(enquiry.full_name, "Anita Sharma")
        self.assertEqual(enquiry.mobile, "9876543210")
        self.assertTrue(enquiry.consent_given)
        self.assertTrue(enquiry.consent_text, "Consent wording must be recorded")
        self.assertEqual(enquiry.school, self.school)

    # -- anti-abuse ------------------------------------------------------
    def test_honeypot_submission_is_rejected(self):
        self._prime_captcha()
        response = self._post(self._payload(website="http://spam.example"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Enquiry.objects.count(), 0)

    def test_submission_faster_than_a_human_is_rejected(self):
        self._prime_captcha()
        response = self._post(self._payload(form_ts=self._timestamp(seconds_ago=0)))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Enquiry.objects.count(), 0)

    def test_tampered_timestamp_is_rejected(self):
        self._prime_captcha()
        response = self._post(self._payload(form_ts="forged-value"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Enquiry.objects.count(), 0)

    def test_wrong_captcha_is_rejected(self):
        self._prime_captcha()
        response = self._post(self._payload(captcha="zzzzzz"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("captcha", response.json()["errors"])
        self.assertEqual(Enquiry.objects.count(), 0)

    def test_captcha_cannot_be_replayed(self):
        self._prime_captcha()
        self.assertTrue(self._post(self._payload()).json()["ok"])
        # Same answer, no fresh challenge issued -> must fail.
        response = self._post(self._payload(email="second@example.com"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Enquiry.objects.count(), 1)

    def test_missing_consent_is_rejected(self):
        self._prime_captcha()
        payload = self._payload()
        payload.pop("consent_given")
        response = self._post(payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn("consent_given", response.json()["errors"])

    @override_settings(RATELIMIT_RULES={"enquiry": (3, 3600)})
    def test_rate_limit_blocks_a_flood(self):
        statuses = []
        for index in range(5):
            self._prime_captcha()
            statuses.append(self._post(self._payload(email=f"user{index}@example.com")).status_code)
        self.assertEqual(statuses[-1], 429, "Enquiry endpoint must throttle repeated submissions")

    def test_a_human_retrying_the_captcha_is_not_locked_out(self):
        """Five fumbled CAPTCHA attempts must still leave the door open."""
        for _ in range(5):
            self._prime_captcha()
            self.assertEqual(self._post(self._payload(captcha="wrong!")).status_code, 400)

        self._prime_captcha()
        response = self._post(self._payload())
        self.assertEqual(response.status_code, 200, "Genuine visitor was locked out too early")
        self.assertEqual(Enquiry.objects.count(), 1)

    # -- validation ------------------------------------------------------
    def test_city_must_belong_to_the_selected_state(self):
        self._prime_captcha()
        response = self._post(self._payload(city=self.other_city.pk))
        self.assertEqual(response.status_code, 400)
        self.assertIn("city", response.json()["errors"])

    def test_course_must_belong_to_the_selected_programme(self):
        self._prime_captcha()
        response = self._post(self._payload(course=self.pg_course.pk))
        self.assertEqual(response.status_code, 400)
        self.assertIn("course", response.json()["errors"])

    def test_inactive_course_cannot_be_selected(self):
        self.pg_course.is_active = False
        self.pg_course.save()
        self._prime_captcha()
        response = self._post(self._payload(course=self.pg_course.pk))
        self.assertEqual(response.status_code, 400)

    def test_invalid_mobile_is_rejected(self):
        self._prime_captcha()
        response = self._post(self._payload(mobile="1234567890"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("mobile", response.json()["errors"])

    def test_script_payload_in_name_is_rejected(self):
        self._prime_captcha()
        response = self._post(self._payload(full_name="<script>alert(1)</script>"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Enquiry.objects.count(), 0)

    def test_csrf_is_enforced(self):
        enforcing = self.client_class(enforce_csrf_checks=True)
        response = enforcing.post(self.url, self._payload())
        self.assertEqual(response.status_code, 403)

    def test_get_is_not_allowed_on_the_submit_endpoint(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)


class DependentDropdownTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.state = State.objects.create(name="West Bengal")
        City.objects.create(state=cls.state, name="Kolkata")
        City.objects.create(state=cls.state, name="Howrah", is_active=False)

    def setUp(self):
        cache.clear()

    def test_cities_endpoint_returns_only_active_rows(self):
        response = self.client.get(
            reverse("admissions:cities_for_state"), {"state": self.state.pk}
        )
        names = [row["name"] for row in response.json()["results"]]
        self.assertEqual(names, ["Kolkata"])

    def test_invalid_state_id_returns_empty_list(self):
        response = self.client.get(
            reverse("admissions:cities_for_state"), {"state": "'; DROP TABLE--"}
        )
        self.assertEqual(response.json()["results"], [])


class EnquiryPrivacyTests(TestCase):
    def test_mobile_is_masked_in_listings(self):
        state = State.objects.create(name="West Bengal")
        city = City.objects.create(state=state, name="Kolkata")
        program = Program.objects.create(name="UG")
        enquiry = Enquiry.objects.create(
            full_name="Test User", email="t@example.com", mobile="9876543210",
            state=state, city=city, program=program, consent_given=True,
        )
        self.assertNotIn("987654", enquiry.masked_mobile)
        self.assertTrue(enquiry.masked_mobile.endswith("3210"))
