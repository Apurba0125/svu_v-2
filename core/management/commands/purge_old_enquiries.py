"""
Data-retention job.

Enquiries hold personal data, so they must not be kept forever. Schedule this
(e.g. monthly) to drop records past the retention window.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from admissions.models import Enquiry
from core.models import ContactMessage


class Command(BaseCommand):
    help = "Delete admission enquiries and contact messages older than N days."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=730,
            help="Retention window in days (default: 730 / 2 years).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would be deleted without deleting anything.",
        )

    def handle(self, *args, **options):
        days = options["days"]
        if days < 30:
            self.stderr.write(self.style.ERROR("Refusing a retention window under 30 days."))
            return

        cutoff = timezone.now() - timezone.timedelta(days=days)
        enquiries = Enquiry.objects.filter(created_at__lt=cutoff)
        contacts = ContactMessage.objects.filter(created_at__lt=cutoff)

        e_count, c_count = enquiries.count(), contacts.count()
        if options["dry_run"]:
            self.stdout.write(
                f"[dry-run] Would delete {e_count} enquiry(ies) and "
                f"{c_count} contact message(s) older than {cutoff:%Y-%m-%d}."
            )
            return

        enquiries.delete()
        contacts.delete()
        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {e_count} enquiry(ies) and {c_count} contact message(s) "
                f"older than {cutoff:%Y-%m-%d}."
            )
        )
