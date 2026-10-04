from django.core.management.base import BaseCommand, CommandError

from apps.quiz_sessions import purge


class Command(BaseCommand):
    help = (
        "Eski, bitmemiş veya ismi girilmemiş quiz oturumlarını (ve cevaplarını) siler. "
        "İsmi girilmiş tamamlanmış oturumlara (skor tablosu) dokunmaz."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=purge.DEFAULT_DAYS,
            help=f"Bu günden eski oturumlar silinir (en az {purge.MIN_DAYS}, varsayılan "
            f"{purge.DEFAULT_DAYS}).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=purge.DEFAULT_LIMIT,
            help="Tek çalıştırmada silinecek en fazla oturum sayısı "
            f"(varsayılan {purge.DEFAULT_LIMIT}); sunucu açılışını uzatmamak için.",
        )
        parser.add_argument("--dry-run", action="store_true", help="Silmeden yalnızca say.")

    def handle(self, *args, **options):
        try:
            sessions, answers = purge.purge_stale_sessions(
                days=options["days"], limit=options["limit"], dry_run=options["dry_run"]
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        verb = "Silinecek" if options["dry_run"] else "Silinen"
        self.stdout.write(self.style.SUCCESS(f"{verb}: {sessions} oturum, {answers} cevap satırı."))
