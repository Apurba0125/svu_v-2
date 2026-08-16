from django.core.management.base import BaseCommand
from django.core.management.utils import get_random_secret_key


class Command(BaseCommand):
    help = "Print a fresh cryptographically-random SECRET_KEY for .env"

    def handle(self, *args, **options):
        self.stdout.write(f"DJANGO_SECRET_KEY={get_random_secret_key()}{get_random_secret_key()[:20]}")
