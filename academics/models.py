"""Schools, departments and the course catalogue."""
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from core.models import OrderedContent, TimeStampedModel
from core.security import sanitize_html
from core.utils import unique_slug, upload_path
from core.validators import validate_image_file


class Program(OrderedContent):
    """Award level — UG, PG, Ph.D, Diploma."""

    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True, blank=True)
    description = models.CharField(max_length=250, blank=True)

    class Meta(OrderedContent.Meta):
        verbose_name = _("Programme level")
        verbose_name_plural = _("Programme levels")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Program, self.name, self)
        super().save(*args, **kwargs)


class School(OrderedContent):
    """Top-level academic unit shown in the 'SVU Schools' carousel."""

    name = models.CharField(max_length=160, unique=True)
    slug = models.SlugField(max_length=160, unique=True, blank=True)
    short_description = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    card_image = models.ImageField(
        upload_to=upload_path("schools"), blank=True,
        validators=[validate_image_file],
        help_text=_("Shown on the home-page carousel card (approx. 700x400 px)."),
    )
    banner_image = models.ImageField(
        upload_to=upload_path("schools"), blank=True, validators=[validate_image_file]
    )
    meta_description = models.CharField(max_length=300, blank=True)

    class Meta(OrderedContent.Meta):
        verbose_name = _("School")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(School, self.name, self)
        self.description = sanitize_html(self.description)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("academics:school_detail", kwargs={"slug": self.slug})


class Department(OrderedContent):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=160, unique=True, blank=True)
    description = models.TextField(blank=True)
    head_name = models.CharField(max_length=120, blank=True)
    head_designation = models.CharField(max_length=120, blank=True)
    image = models.ImageField(
        upload_to=upload_path("departments"), blank=True, validators=[validate_image_file]
    )

    class Meta(OrderedContent.Meta):
        verbose_name = _("Department")
        unique_together = [("school", "name")]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Department, f"{self.name}", self)
        self.description = sanitize_html(self.description)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("academics:department_detail", kwargs={"slug": self.slug})


class Course(OrderedContent):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="courses")
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="courses"
    )
    program = models.ForeignKey(
        Program, on_delete=models.PROTECT, related_name="courses",
        verbose_name=_("programme level"),
    )

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    duration = models.CharField(max_length=60, blank=True, help_text=_("e.g. 4 Years / 8 Semesters"))
    eligibility = models.TextField(blank=True)
    description = models.TextField(blank=True)
    total_seats = models.PositiveIntegerField(null=True, blank=True)
    is_featured = models.BooleanField(default=False, db_index=True)

    class Meta(OrderedContent.Meta):
        verbose_name = _("Course")
        unique_together = [("school", "name", "program")]
        indexes = [models.Index(fields=["is_active", "is_featured"])]

    def __str__(self):
        return f"{self.name} ({self.program.name})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Course, f"{self.name}-{self.program.name}", self)
        self.description = sanitize_html(self.description)
        self.eligibility = sanitize_html(self.eligibility)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("academics:course_detail", kwargs={"slug": self.slug})


class Facility(OrderedContent):
    """Campus facilities gallery (library, labs, hostel, sports...)."""

    title = models.CharField(max_length=140)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(
        upload_to=upload_path("facilities"), blank=True, validators=[validate_image_file]
    )

    class Meta(OrderedContent.Meta):
        verbose_name = _("Facility")
        verbose_name_plural = _("Facilities")

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Facility, self.title, self)
        self.description = sanitize_html(self.description)
        super().save(*args, **kwargs)


class IndustryPartner(OrderedContent):
    name = models.CharField(max_length=160)
    logo = models.ImageField(
        upload_to=upload_path("partners"), blank=True, validators=[validate_image_file]
    )
    url = models.URLField(blank=True)

    class Meta(OrderedContent.Meta):
        verbose_name = _("Industry partner")

    def __str__(self):
        return self.name
