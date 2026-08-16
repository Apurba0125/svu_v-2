"""Site-wide content models: chrome, home-page sections and flat pages."""
from django.core.cache import cache
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from .security import sanitize_html
from .utils import unique_slug, upload_path
from .validators import (
    name_validator,
    validate_document_file,
    validate_image_file,
    validate_no_links,
    validate_youtube_id,
)


# ---------------------------------------------------------------------------
# Abstract bases
# ---------------------------------------------------------------------------
class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(_("created"), auto_now_add=True)
    updated_at = models.DateTimeField(_("updated"), auto_now=True)

    class Meta:
        abstract = True


class PublishedQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_active=True)


class OrderedContent(TimeStampedModel):
    """Anything the editors reorder on the front end."""

    order = models.PositiveIntegerField(_("display order"), default=0, db_index=True)
    is_active = models.BooleanField(_("visible on site"), default=True, db_index=True)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        abstract = True
        ordering = ("order", "-created_at")


# ---------------------------------------------------------------------------
# Global configuration (singleton)
# ---------------------------------------------------------------------------
class SiteConfiguration(TimeStampedModel):
    """One editable row holding everything in the header/footer chrome."""

    CACHE_KEY = "svu:site-configuration"

    site_name = models.CharField(max_length=120, default="Swami Vivekananda University")
    short_name = models.CharField(max_length=20, default="SVU")
    tagline = models.CharField(max_length=200, blank=True, default="Excellence in Education")

    logo = models.ImageField(
        upload_to=upload_path("branding"), blank=True,
        validators=[validate_image_file],
        help_text=_("Primary SVU logo shown in the header."),
    )
    group_logo = models.ImageField(
        upload_to=upload_path("branding"), blank=True,
        validators=[validate_image_file],
        help_text=_("Optional sponsoring-body / group logo shown left of the SVU crest."),
    )
    footer_logo = models.ImageField(
        upload_to=upload_path("branding"), blank=True,
        validators=[validate_image_file],
    )

    # Contact block.
    # NOTE: these defaults are deliberately non-routable placeholders. Set the
    # real campus address and helpline numbers in admin › Site configuration
    # before the site goes live.
    address_line1 = models.CharField(max_length=160, default="University Campus")
    address_line2 = models.CharField(max_length=160, default="Kolkata, West Bengal")
    admission_phones = models.TextField(
        default="+91 90000 00001\n+91 90000 00002",
        help_text=_("One phone number per line."),
    )
    toll_free = models.CharField(max_length=40, blank=True, default="1800 000 0000")
    toll_free_hours = models.CharField(max_length=60, blank=True, default="10AM to 6PM")
    email = models.EmailField(default="info@svu.ac.in")
    website = models.URLField(blank=True, default="https://www.svu.ac.in")
    whatsapp_number = models.CharField(
        max_length=20, blank=True, default="919000000001",
        help_text=_("International format without '+', e.g. 919000000001."),
    )

    # Call-to-action chrome
    marquee_text = models.CharField(
        max_length=400,
        default=("Beware of fake agents/consultants!! SVU does not take admission "
                 "through any agents/consultants. For any admission related query "
                 "please refer to SVU website only."),
    )
    admission_banner_text = models.CharField(max_length=60, default="ADMISSION OPEN 2026-27")
    apply_now_url = models.CharField(max_length=300, blank=True, default="/admission/apply/")
    pay_fee_url = models.CharField(max_length=300, blank=True, default="#")
    ugc_documents_url = models.CharField(max_length=300, blank=True, default="/page/ugc-compliance/")

    # Home-page welcome block
    welcome_heading = models.CharField(max_length=120, default="WELCOME TO SWAMI VIVEKANANDA UNIVERSITY")
    welcome_text = models.TextField(
        default=("Swami Vivekananda University (SVU) is a state private university "
                 "built on the ideals and teachings of Swami Vivekananda."),
    )
    admission_ad_image = models.ImageField(
        upload_to=upload_path("branding"), blank=True,
        validators=[validate_image_file],
        help_text=_("Creative shown under the enquiry form."),
    )

    # Footer
    facebook_page_url = models.URLField(blank=True, default="https://www.facebook.com/svu")
    copyright_text = models.CharField(
        max_length=200, default="Copyright © SVU. All Rights Reserved."
    )
    designer_credit = models.CharField(max_length=120, blank=True, default="")
    designer_url = models.URLField(blank=True)

    # SEO
    meta_description = models.CharField(
        max_length=300,
        default=("Swami Vivekananda University — offering UG, PG and Ph.D "
                 "programmes in engineering, management, law, media, design, "
                 "nursing and more."),
    )
    meta_keywords = models.CharField(max_length=300, blank=True)

    class Meta:
        verbose_name = _("Site configuration")
        verbose_name_plural = _("Site configuration")

    def __str__(self):
        return self.site_name

    def save(self, *args, **kwargs):
        # Enforce the singleton and drop the cached copy.
        self.pk = 1
        super().save(*args, **kwargs)
        cache.delete(self.CACHE_KEY)

    def delete(self, *args, **kwargs):     # pragma: no cover - guarded in admin too
        raise RuntimeError("The site configuration row cannot be deleted.")

    @classmethod
    def get_solo(cls):
        config = cache.get(cls.CACHE_KEY)
        if config is None:
            config, _created = cls.objects.get_or_create(pk=1)
            cache.set(cls.CACHE_KEY, config, timeout=300)
        return config

    @property
    def phone_list(self):
        return [line.strip() for line in self.admission_phones.splitlines() if line.strip()]

    @property
    def whatsapp_url(self):
        if not self.whatsapp_number:
            return ""
        digits = "".join(ch for ch in self.whatsapp_number if ch.isdigit())
        return f"https://wa.me/{digits}"


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
class MenuItem(OrderedContent):
    """Two-level main navigation, editable without touching templates."""

    LOCATION_MAIN = "main"
    LOCATION_TOP = "top"
    LOCATION_CHOICES = [
        (LOCATION_MAIN, _("Main navigation")),
        (LOCATION_TOP, _("Top utility bar")),
    ]

    title = models.CharField(max_length=80)
    location = models.CharField(
        max_length=10, choices=LOCATION_CHOICES, default=LOCATION_MAIN, db_index=True
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children",
        limit_choices_to={"parent__isnull": True},
    )
    url = models.CharField(
        max_length=300, blank=True,
        help_text=_("Relative path such as /academics/schools/ or a full https:// URL."),
    )
    open_in_new_tab = models.BooleanField(default=False)
    highlight = models.BooleanField(
        default=False, help_text=_("Render with the accent colour (e.g. Apply Now).")
    )

    class Meta(OrderedContent.Meta):
        verbose_name = _("Menu item")
        verbose_name_plural = _("Menu items")
        indexes = [models.Index(fields=["location", "order"])]

    def __str__(self):
        return f"{self.parent.title} › {self.title}" if self.parent_id else self.title

    @property
    def href(self):
        return self.url or "#"

    @property
    def is_external(self):
        return self.url.startswith(("http://", "https://"))


class SocialLink(OrderedContent):
    PLATFORMS = [
        ("facebook", "Facebook"),
        ("twitter", "Twitter / X"),
        ("youtube", "YouTube"),
        ("instagram", "Instagram"),
        ("linkedin", "LinkedIn"),
    ]
    platform = models.CharField(max_length=20, choices=PLATFORMS, unique=True)
    url = models.URLField()

    class Meta(OrderedContent.Meta):
        verbose_name = _("Social link")

    def __str__(self):
        return self.get_platform_display()


# ---------------------------------------------------------------------------
# Home-page sections
# ---------------------------------------------------------------------------
class HeroSlide(OrderedContent):
    """Full-width slides in the top carousel."""

    title = models.CharField(max_length=200, blank=True)
    subtitle = models.CharField(max_length=300, blank=True)
    image = models.ImageField(
        upload_to=upload_path("slides"), validators=[validate_image_file],
        help_text=_("Recommended 1920x780 px, under 400 KB."),
    )
    alt_text = models.CharField(
        max_length=160,
        help_text=_("Describes the image for screen readers — required for accessibility."),
    )
    link_url = models.CharField(max_length=300, blank=True)
    link_label = models.CharField(max_length=40, blank=True, default="Know More")

    class Meta(OrderedContent.Meta):
        verbose_name = _("Hero slide")

    def __str__(self):
        return self.title or self.alt_text


class QuickLink(OrderedContent):
    """The arrow-badge shortcuts beside the welcome text."""

    title = models.CharField(max_length=80)
    description = models.CharField(max_length=200, blank=True)
    url = models.CharField(max_length=300, blank=True)

    class Meta(OrderedContent.Meta):
        verbose_name = _("Quick link")

    def __str__(self):
        return self.title


class Offering(OrderedContent):
    """'Explore our offerings' — numbered feature cards."""

    ICONS = [
        ("curriculum", _("Curriculum")),
        ("classroom", _("Tech classroom")),
        ("experts", _("Experts")),
        ("library", _("Digital library")),
        ("lab", _("Laboratory")),
        ("sports", _("Sports")),
    ]
    title = models.CharField(max_length=80)
    description = models.TextField(max_length=400)
    icon = models.CharField(max_length=20, choices=ICONS, default="curriculum")

    class Meta(OrderedContent.Meta):
        verbose_name = _("Offering")

    def __str__(self):
        return self.title


class Enlistment(OrderedContent):
    """'We are now enlisted' — external platform logos (AIMA, UCEED, CLAT...)."""

    title = models.CharField(max_length=120)
    logo = models.ImageField(
        upload_to=upload_path("enlistments"), validators=[validate_image_file]
    )
    alt_text = models.CharField(max_length=160)
    url = models.URLField(blank=True)

    class Meta(OrderedContent.Meta):
        verbose_name = _("Enlistment")

    def __str__(self):
        return self.title


class VideoFeature(OrderedContent):
    """Embedded YouTube features on the home page."""

    title = models.CharField(max_length=120)
    highlight = models.CharField(
        max_length=120, blank=True,
        help_text=_("Portion of the heading rendered in the accent colour."),
    )
    youtube_id = models.CharField(max_length=20, validators=[validate_youtube_id])

    class Meta(OrderedContent.Meta):
        verbose_name = _("Video feature")

    def __str__(self):
        return self.title

    @property
    def embed_url(self):
        # youtube-nocookie + no related videos keeps third-party tracking down.
        return f"https://www.youtube-nocookie.com/embed/{self.youtube_id}?rel=0"

    @property
    def thumbnail_url(self):
        return f"https://i.ytimg.com/vi/{self.youtube_id}/hqdefault.jpg"


class ChancellorMessage(TimeStampedModel):
    """Singleton-ish block; the most recent active row is rendered."""

    name = models.CharField(max_length=120, default="The Chancellor")
    designation = models.CharField(max_length=120, default="CHANCELLOR")
    institution = models.CharField(max_length=160, default="SWAMI VIVEKANANDA UNIVERSITY (SVU)")
    excerpt = models.TextField(max_length=600)
    full_message = models.TextField(blank=True)
    photo = models.ImageField(
        upload_to=upload_path("people"), blank=True, validators=[validate_image_file]
    )
    background_image = models.ImageField(
        upload_to=upload_path("sections"), blank=True, validators=[validate_image_file]
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Chancellor's message")
        verbose_name_plural = _("Chancellor's message")

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.full_message = sanitize_html(self.full_message)
        super().save(*args, **kwargs)


class Centre(OrderedContent):
    """Timeline entries beside the chancellor's message."""

    ICONS = [
        ("innovation", _("Innovation")),
        ("industry", _("Industry")),
        ("excellence", _("Excellence")),
        ("women", _("Women studies")),
        ("research", _("Research")),
    ]
    title = models.CharField(max_length=140)
    description = models.TextField(max_length=500)
    icon = models.CharField(max_length=20, choices=ICONS, default="innovation")
    url = models.CharField(max_length=300, blank=True)

    class Meta(OrderedContent.Meta):
        verbose_name = _("Centre")

    def __str__(self):
        return self.title


class Testimonial(OrderedContent):
    """'The SVUites' student quotes."""

    name = models.CharField(max_length=120, validators=[name_validator])
    role = models.CharField(max_length=80, default="Student - SVU")
    department = models.CharField(max_length=160, blank=True)
    quote = models.TextField(max_length=800)
    photo = models.ImageField(
        upload_to=upload_path("people"), blank=True, validators=[validate_image_file]
    )
    detail_url = models.CharField(max_length=300, blank=True)

    class Meta(OrderedContent.Meta):
        verbose_name = _("Testimonial")

    def __str__(self):
        return self.name


class FooterLink(OrderedContent):
    SECTION_USEFUL = "useful"
    SECTION_EXTERNAL = "external"
    SECTIONS = [
        (SECTION_USEFUL, _("Useful links")),
        (SECTION_EXTERNAL, _("External links")),
    ]
    section = models.CharField(max_length=10, choices=SECTIONS, default=SECTION_USEFUL, db_index=True)
    title = models.CharField(max_length=120)
    url = models.CharField(max_length=300)
    open_in_new_tab = models.BooleanField(default=False)

    class Meta(OrderedContent.Meta):
        verbose_name = _("Footer link")

    def __str__(self):
        return f"{self.get_section_display()} — {self.title}"

    @property
    def is_external(self):
        return self.url.startswith(("http://", "https://"))


# ---------------------------------------------------------------------------
# Flat content pages & FAQ
# ---------------------------------------------------------------------------
class Page(TimeStampedModel):
    """Editor-managed content page (About, IQAC, policies, ...)."""

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    subtitle = models.CharField(max_length=250, blank=True)
    banner_image = models.ImageField(
        upload_to=upload_path("pages"), blank=True, validators=[validate_image_file]
    )
    content = models.TextField(
        help_text=_("Basic HTML is allowed; scripts and event handlers are stripped.")
    )
    attachment = models.FileField(
        upload_to=upload_path("documents"), blank=True,
        validators=[validate_document_file],
    )
    meta_description = models.CharField(max_length=300, blank=True)
    is_published = models.BooleanField(default=True, db_index=True)
    show_in_sitemap = models.BooleanField(default=True)

    objects = models.Manager()

    class Meta:
        ordering = ("title",)
        verbose_name = _("Content page")

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Page, self.title, self)
        self.content = sanitize_html(self.content)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("core:page_detail", kwargs={"slug": self.slug})


class FAQ(OrderedContent):
    question = models.CharField(max_length=300)
    answer = models.TextField()
    category = models.CharField(max_length=80, blank=True, default="General")

    class Meta(OrderedContent.Meta):
        verbose_name = _("FAQ")
        verbose_name_plural = _("FAQs")

    def __str__(self):
        return self.question

    def save(self, *args, **kwargs):
        self.answer = sanitize_html(self.answer)
        super().save(*args, **kwargs)


# ---------------------------------------------------------------------------
# Inbound messages
# ---------------------------------------------------------------------------
class ContactMessage(TimeStampedModel):
    """Submissions from the Contact Us form — never rendered as HTML."""

    name = models.CharField(max_length=80)
    email = models.EmailField()
    phone = models.CharField(max_length=15, blank=True)
    subject = models.CharField(max_length=150)
    message = models.TextField(max_length=2000)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    is_handled = models.BooleanField(default=False, db_index=True)
    staff_notes = models.TextField(blank=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = _("Contact message")

    def __str__(self):
        return f"{self.subject} — {self.name}"


class RatingChoice(models.IntegerChoices):
    """Shared 1-5 scale (used by feedback-style features)."""

    ONE = 1, "1"
    TWO = 2, "2"
    THREE = 3, "3"
    FOUR = 4, "4"
    FIVE = 5, "5"


class Feedback(TimeStampedModel):
    """Optional lightweight page feedback, kept out of the public HTML."""

    page_path = models.CharField(max_length=300)
    rating = models.PositiveSmallIntegerField(
        choices=RatingChoice.choices,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(max_length=1000, blank=True, validators=[validate_no_links])
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.page_path} ({self.rating}/5)"
