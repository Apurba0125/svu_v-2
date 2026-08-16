"""Notice board and campus events."""
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from core.models import TimeStampedModel
from core.security import sanitize_html
from core.utils import truncate_words, unique_slug, upload_path
from core.validators import validate_document_file, validate_image_file


class PublishedQuerySet(models.QuerySet):
    def published(self):
        return self.filter(is_published=True, publish_from__lte=timezone.now())


class Notice(TimeStampedModel):
    """Notice-board entry, optionally linking to a PDF circular."""

    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True, blank=True)
    notice_date = models.DateField(_("notice date"), default=timezone.localdate, db_index=True)
    summary = models.TextField(blank=True, max_length=1000)
    attachment = models.FileField(
        upload_to=upload_path("notices"), blank=True,
        validators=[validate_document_file],
        help_text=_("PDF or Office document, max 4 MB."),
    )
    external_url = models.CharField(max_length=300, blank=True)
    is_important = models.BooleanField(default=False, db_index=True)
    is_published = models.BooleanField(default=True, db_index=True)
    publish_from = models.DateTimeField(default=timezone.now, db_index=True)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        ordering = ("-notice_date", "-created_at")
        verbose_name = _("Notice")
        indexes = [models.Index(fields=["is_published", "-notice_date"])]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Notice, self.title, self)
        self.summary = sanitize_html(self.summary)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        if self.external_url:
            return self.external_url
        return reverse("events:notice_detail", kwargs={"slug": self.slug})

    @property
    def target_url(self):
        """Where the notice-board item should point."""
        if self.attachment:
            return self.attachment.url
        return self.get_absolute_url()


class Event(TimeStampedModel):
    """Campus event / news story shown in the 'Latest Events' carousel."""

    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=300, unique=True, blank=True)
    event_date = models.DateField(default=timezone.localdate, db_index=True)
    venue = models.CharField(max_length=200, blank=True)
    excerpt = models.TextField(
        max_length=400, blank=True,
        help_text=_("Short teaser for the card. Auto-filled from the description if blank."),
    )
    description = models.TextField(blank=True)
    cover_image = models.ImageField(
        upload_to=upload_path("events"), blank=True, validators=[validate_image_file]
    )
    alt_text = models.CharField(max_length=160, blank=True)

    is_featured = models.BooleanField(default=False, db_index=True)
    is_published = models.BooleanField(default=True, db_index=True)
    publish_from = models.DateTimeField(default=timezone.now, db_index=True)
    meta_description = models.CharField(max_length=300, blank=True)

    objects = PublishedQuerySet.as_manager()

    class Meta:
        ordering = ("-event_date", "-created_at")
        verbose_name = _("Event")
        indexes = [models.Index(fields=["is_published", "-event_date"])]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_slug(Event, self.title, self)
        self.description = sanitize_html(self.description)
        if not self.excerpt and self.description:
            from django.utils.html import strip_tags

            self.excerpt = truncate_words(strip_tags(self.description), 30)
        if not self.alt_text:
            self.alt_text = self.title[:160]
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("events:event_detail", kwargs={"slug": self.slug})


class EventImage(TimeStampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="gallery")
    image = models.ImageField(upload_to=upload_path("events"), validators=[validate_image_file])
    caption = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("order", "id")
        verbose_name = _("Event photo")

    def __str__(self):
        return self.caption or f"Photo #{self.pk}"
