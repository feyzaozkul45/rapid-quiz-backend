from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.quiz import seeding

DEFAULT_DIR = Path(__file__).resolve().parents[2] / "fixtures"


class Command(BaseCommand):
    help = "Kategori başına bir YAML dosyasından kategorileri ve soruları yükler (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument("--path", default=str(DEFAULT_DIR), help="YAML dosyalarının dizini")

    def handle(self, *args, **options):
        files = seeding.load_files(options["path"])
        try:
            stats = seeding.seed(files)
        except seeding.SeedValidationError as exc:
            raise CommandError("Doğrulama hatası:\n- " + "\n- ".join(exc.errors)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"Tamam: {stats.categories_created} yeni kategori, "
                f"{stats.questions_created} yeni soru, {stats.questions_updated} güncellenen soru."
            )
        )
