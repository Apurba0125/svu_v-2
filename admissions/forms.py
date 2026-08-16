"""The home-page / admission enquiry form."""
from django import forms
from django.utils.translation import gettext_lazy as _

from academics.models import Course, Department, Program
from core.forms import SecureForm
from core.security import get_client_ip
from core.validators import name_validator, phone_validator

from .models import City, Enquiry, State

CONSENT_TEXT = _(
    "I authorise Swami Vivekananda University to contact me with updates & "
    "notifications via email, SMS, RCS, WhatsApp, and voice call. This consent "
    "will override any registration for DNC/NDNC."
)


class EnquiryForm(SecureForm):
    """
    Mirrors the enquiry panel on the home page.

    Every relational choice is validated against the database, so a crafted POST
    cannot smuggle in an arbitrary primary key or an inactive record.
    """

    full_name = forms.CharField(
        max_length=80,
        validators=[name_validator],
        label=_("Name"),
        widget=forms.TextInput(
            attrs={"placeholder": _("Enter Name *"), "autocomplete": "name"}
        ),
    )
    email = forms.EmailField(
        max_length=254,
        label=_("Email Address"),
        widget=forms.EmailInput(
            attrs={"placeholder": _("Enter Email Address *"), "autocomplete": "email"}
        ),
    )
    mobile = forms.CharField(
        max_length=10,
        validators=[phone_validator],
        label=_("Mobile Number"),
        widget=forms.TextInput(
            attrs={
                "placeholder": _("Enter Mobile Number *"),
                "inputmode": "numeric",
                "pattern": "[6-9][0-9]{9}",
                "maxlength": "10",
                "autocomplete": "tel-national",
            }
        ),
    )
    state = forms.ModelChoiceField(
        queryset=State.objects.none(),
        label=_("State"),
        empty_label=_("Select State *"),
    )
    city = forms.ModelChoiceField(
        queryset=City.objects.none(),
        label=_("City"),
        empty_label=_("Select City *"),
    )
    program = forms.ModelChoiceField(
        queryset=Program.objects.none(),
        label=_("Programme"),
        empty_label=_("Select Programme *"),
    )
    course = forms.ModelChoiceField(
        queryset=Course.objects.none(),
        label=_("Course"),
        empty_label=_("Select Course *"),
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.none(),
        required=False,
        label=_("Department"),
        empty_label=_("Select Department"),
    )
    consent_given = forms.BooleanField(
        required=True,
        label=CONSENT_TEXT,
        error_messages={"required": _("Please tick the consent box to continue.")},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Bind the live querysets here (not at class level) so the choices stay
        # fresh and only ever contain active rows.
        self.fields["state"].queryset = State.objects.published().order_by("name")
        self.fields["program"].queryset = Program.objects.published().order_by("order", "name")
        self.fields["department"].queryset = (
            Department.objects.published().select_related("school").order_by("name")
        )

        # City and course are narrowed by the parent selection when one is posted;
        # otherwise the full active list is accepted (progressive enhancement —
        # the form must still work with JavaScript disabled).
        self.fields["city"].queryset = City.objects.published().select_related("state").order_by("name")
        self.fields["course"].queryset = (
            Course.objects.published().select_related("program", "school").order_by("name")
        )

    def clean(self):
        cleaned = super().clean()
        state = cleaned.get("state")
        city = cleaned.get("city")
        program = cleaned.get("program")
        course = cleaned.get("course")

        # Cross-field integrity: the child must belong to the chosen parent.
        if state and city and city.state_id != state.pk:
            self.add_error("city", _("Please choose a city inside the selected state."))
        if program and course and course.program_id != program.pk:
            self.add_error(
                "course", _("The selected course is not offered under that programme level.")
            )
        return cleaned

    def save(self):
        data = self.cleaned_data
        course = data.get("course")
        ip = get_client_ip(self.request) if self.request else None
        return Enquiry.objects.create(
            full_name=data["full_name"],
            email=data["email"],
            mobile=data["mobile"],
            state=data["state"],
            city=data["city"],
            program=data["program"],
            course=course,
            school=course.school if course else None,
            department=data.get("department"),
            consent_given=data["consent_given"],
            consent_text=str(CONSENT_TEXT),
            source_page=(self.request.path[:200] if self.request else ""),
            ip_address=ip if ip and ip != "unknown" else None,
            user_agent=(
                self.request.META.get("HTTP_USER_AGENT", "")[:300] if self.request else ""
            ),
        )
