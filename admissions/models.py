"""Admission enquiries and the geography lookups behind the enquiry form."""
from django.db import models
from django.utils.translation import gettext_lazy as _

from academics.models import Course, Department, Program, School
from core.models import OrderedContent, TimeStampedModel
from core.validators import name_validator, phone_validator


class State(OrderedContent):
    name = models.CharField(max_length=80, unique=True)
    code = models.CharField(max_length=5, blank=True)

    class Meta(OrderedContent.Meta):
        ordering = ("name",)
        verbose_name = _("State")

    def __str__(self):
        return self.name


class City(OrderedContent):
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name="cities")
    name = models.CharField(max_length=80)

    class Meta(OrderedContent.Meta):
        ordering = ("name",)
        unique_together = [("state", "name")]
        verbose_name = _("City")
        verbose_name_plural = _("Cities")

    def __str__(self):
        return f"{self.name}, {self.state.name}"


class Enquiry(TimeStampedModel):
    """
    A prospective student's enquiry.

    Holds personal data, so: never rendered as HTML, admin-only visibility, and
    `purge_old_enquiries` exists to enforce a retention window.
    """

    STATUS_NEW = "new"
    STATUS_CONTACTED = "contacted"
    STATUS_ENROLLED = "enrolled"
    STATUS_CLOSED = "closed"
    STATUS_SPAM = "spam"
    STATUS_CHOICES = [
        (STATUS_NEW, _("New")),
        (STATUS_CONTACTED, _("Contacted")),
        (STATUS_ENROLLED, _("Enrolled")),
        (STATUS_CLOSED, _("Closed")),
        (STATUS_SPAM, _("Spam")),
    ]

    full_name = models.CharField(max_length=80, validators=[name_validator])
    email = models.EmailField()
    country_code = models.CharField(max_length=5, default="+91")
    mobile = models.CharField(max_length=10, validators=[phone_validator])

    state = models.ForeignKey(State, on_delete=models.PROTECT, related_name="enquiries")
    city = models.ForeignKey(City, on_delete=models.PROTECT, related_name="enquiries")
    program = models.ForeignKey(
        Program, on_delete=models.PROTECT, related_name="enquiries",
        verbose_name=_("programme level"),
    )
    course = models.ForeignKey(
        Course, on_delete=models.SET_NULL, null=True, blank=True, related_name="enquiries"
    )
    school = models.ForeignKey(
        School, on_delete=models.SET_NULL, null=True, blank=True, related_name="enquiries"
    )
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="enquiries"
    )
    message = models.TextField(max_length=1000, blank=True)

    # Consent + provenance (audit trail for DPDP/consent compliance)
    consent_given = models.BooleanField(default=False)
    consent_text = models.TextField(blank=True, editable=False)
    source_page = models.CharField(max_length=200, blank=True, editable=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True, editable=False)
    user_agent = models.CharField(max_length=300, blank=True, editable=False)

    status = models.CharField(
        max_length=12, choices=STATUS_CHOICES, default=STATUS_NEW, db_index=True
    )
    staff_notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Admission enquiry")
        verbose_name_plural = _("Admission enquiries")
        indexes = [
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self):
        return f"{self.full_name} — {self.program}"

    @property
    def masked_mobile(self):
        """Used in list views so a shoulder-surfer cannot harvest numbers."""
        return f"{self.country_code} ******{self.mobile[-4:]}" if self.mobile else ""


class AdmissionStep(OrderedContent):
    """'How to apply' steps rendered on the admission landing page."""

    title = models.CharField(max_length=140)
    description = models.TextField(max_length=600)

    class Meta(OrderedContent.Meta):
        verbose_name = _("Admission step")

    def __str__(self):
        return self.title


class Scholarship(OrderedContent):
    title = models.CharField(max_length=160)
    description = models.TextField(max_length=1000)
    percentage = models.CharField(max_length=40, blank=True, help_text=_("e.g. Up to 100%"))
    criteria = models.TextField(blank=True)

    class Meta(OrderedContent.Meta):
        verbose_name = _("Scholarship")

    def __str__(self):
        return self.title
