"""
Public-facing forms.

``SecureForm`` layers four cheap, privacy-respecting anti-abuse checks on top of
Django's CSRF protection:

  1. a honeypot field that only a bot fills in,
  2. a signed timestamp that rejects sub-3-second (scripted) submissions,
  3. an image CAPTCHA validated against a salted hash held in the session,
  4. content heuristics that reject injection/spam payloads.
"""
import logging

from django import forms
from django.conf import settings
from django.core import signing
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import ContactMessage
from .security import (
    captcha_data_uri,
    generate_captcha,
    get_client_ip,
    looks_like_injection,
    strip_control_characters,
    validate_captcha,
)
from .validators import name_validator, phone_validator

logger = logging.getLogger("svu.security")

MIN_FILL_SECONDS = 3
MAX_FORM_AGE_SECONDS = 60 * 60 * 2      # 2 hours
FORM_TIMESTAMP_SALT = "svu.form.timestamp"


class SecureForm(forms.Form):
    """Base class carrying the anti-abuse machinery."""

    # Bots fill everything in; humans never see this (hidden in CSS + aria-hidden).
    website = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "class": "hp-field",
                "tabindex": "-1",
                "autocomplete": "off",
                "aria-hidden": "true",
            }
        ),
        label="",
    )
    form_ts = forms.CharField(required=False, widget=forms.HiddenInput())
    captcha = forms.CharField(
        max_length=12,
        required=True,
        label=_("Enter Captcha"),
        widget=forms.TextInput(
            attrs={
                "placeholder": _("Enter Captcha"),
                "autocomplete": "off",
                "autocapitalize": "none",
                "spellcheck": "false",
                "inputmode": "text",
            }
        ),
    )

    #: Set to False on forms that should skip the CAPTCHA.
    require_captcha = True

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)

        if not self.require_captcha:
            self.fields.pop("captcha", None)

        # Stamp a fresh, tamper-proof timestamp on every rendered form.
        self.fields["form_ts"].initial = signing.dumps(
            timezone.now().timestamp(), salt=FORM_TIMESTAMP_SALT
        )

        self.captcha_image = ""
        if self.require_captcha and self.request is not None and not self.is_bound:
            self.refresh_captcha()

    # -- CAPTCHA ---------------------------------------------------------
    def refresh_captcha(self):
        code = generate_captcha(self.request)
        self.captcha_image = captcha_data_uri(code)
        return self.captcha_image

    def clean_website(self):
        value = self.cleaned_data.get("website", "")
        if value:
            logger.info("Honeypot triggered on %s", self.__class__.__name__)
            # Deliberately vague: never tell a bot which check it failed.
            raise forms.ValidationError(_("Your submission could not be processed."))
        return ""

    def clean_form_ts(self):
        raw = self.cleaned_data.get("form_ts", "")
        if not raw:
            raise forms.ValidationError(_("Your session expired. Please reload the page."))
        try:
            issued = signing.loads(raw, salt=FORM_TIMESTAMP_SALT, max_age=MAX_FORM_AGE_SECONDS)
        except signing.SignatureExpired:
            raise forms.ValidationError(_("This form expired. Please reload the page."))
        except signing.BadSignature:
            logger.info("Tampered form timestamp on %s", self.__class__.__name__)
            raise forms.ValidationError(_("Your submission could not be processed."))

        elapsed = timezone.now().timestamp() - float(issued)
        if elapsed < MIN_FILL_SECONDS:
            logger.info("Too-fast submission (%.2fs) on %s", elapsed, self.__class__.__name__)
            raise forms.ValidationError(
                _("That was submitted a little too quickly. Please try again.")
            )
        return raw

    def clean_captcha(self):
        value = strip_control_characters(self.cleaned_data.get("captcha", ""))
        if self.request is None:
            return value
        if not validate_captcha(self.request, value):
            raise forms.ValidationError(_("The captcha text does not match. Please try again."))
        return value

    #: Machine-generated fields that must not go through the spam heuristics.
    SCAN_EXEMPT_FIELDS = {"form_ts", "website", "captcha"}

    def clean(self):
        cleaned = super().clean()
        # Reject injection payloads in every free-text field.
        for name, value in list(cleaned.items()):
            if isinstance(value, str) and name not in self.SCAN_EXEMPT_FIELDS:
                cleaned[name] = strip_control_characters(value)
                if looks_like_injection(cleaned[name]):
                    logger.warning(
                        "Injection-like payload rejected in field '%s' of %s",
                        name, self.__class__.__name__,
                    )
                    self.add_error(name, _("This value contains characters that are not allowed."))
        return cleaned

    def add_error(self, field, error):
        """Re-issue a CAPTCHA whenever the form comes back with errors."""
        super().add_error(field, error)
        if self.require_captcha and self.request is not None and not self.captcha_image:
            self.refresh_captcha()


class ContactForm(SecureForm):
    name = forms.CharField(
        max_length=80, validators=[name_validator],
        widget=forms.TextInput(attrs={"placeholder": _("Your name *"), "autocomplete": "name"}),
        label=_("Name"),
    )
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(
            attrs={"placeholder": _("Email address *"), "autocomplete": "email"}
        ),
        label=_("Email"),
    )
    phone = forms.CharField(
        max_length=10, required=False, validators=[phone_validator],
        widget=forms.TextInput(
            attrs={
                "placeholder": _("10-digit mobile"),
                "inputmode": "numeric",
                "autocomplete": "tel-national",
                "maxlength": "10",
            }
        ),
        label=_("Mobile"),
    )
    subject = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": _("Subject *")}),
        label=_("Subject"),
    )
    message = forms.CharField(
        max_length=2000,
        widget=forms.Textarea(attrs={"placeholder": _("Your message *"), "rows": 5}),
        label=_("Message"),
    )

    def save(self):
        data = self.cleaned_data
        ip = user_agent = None
        if self.request is not None:
            ip = get_client_ip(self.request)
            user_agent = self.request.META.get("HTTP_USER_AGENT", "")[:300]
        return ContactMessage.objects.create(
            name=data["name"],
            email=data["email"],
            phone=data.get("phone", ""),
            subject=data["subject"],
            message=data["message"],
            ip_address=ip if ip and ip != "unknown" else None,
            user_agent=user_agent or "",
        )


class SearchForm(forms.Form):
    """Site search — no CAPTCHA (read-only), but tightly bounded input."""

    q = forms.CharField(
        max_length=80, min_length=2, required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": _("Search..."),
                "type": "search",
                "autocomplete": "off",
                "aria-label": _("Search this website"),
            }
        ),
        label=_("Search"),
    )

    def clean_q(self):
        value = strip_control_characters(self.cleaned_data["q"])
        if looks_like_injection(value):
            raise forms.ValidationError(_("Please enter a plain search term."))
        return value
