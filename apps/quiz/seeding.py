"""Kategori başına YAML dosyasından soru yükleme (idempotent) ve doğrulama."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from django.db import transaction

from .models import Category, Choice, Question

CHOICES_PER_QUESTION = 4
MIN_QUESTIONS_PER_CATEGORY = 20


class SeedValidationError(Exception):
    def __init__(self, errors):
        self.errors = errors
        super().__init__("\n".join(errors))


@dataclass
class SeedStats:
    categories_created: int = 0
    questions_created: int = 0
    questions_updated: int = 0
    questions_deactivated: int = 0
    deactivated_texts: list[str] = field(default_factory=list)


def load_files(directory):
    files = sorted(Path(directory).glob("*.yaml"))
    return [(f.name, yaml.safe_load(f.read_text(encoding="utf-8"))) for f in files]


def validate(files):
    errors = []
    if not files:
        errors.append("YAML dosyası bulunamadı.")
    slugs = set()
    for name, data in files:
        if not isinstance(data, dict):
            errors.append(f"{name}: kök öğe bir sözlük olmalı.")
            continue
        for key in ("name", "slug", "questions"):
            if not data.get(key):
                errors.append(f"{name}: '{key}' zorunlu.")
        slug = data.get("slug")
        if slug in slugs:
            errors.append(f"{name}: slug '{slug}' başka bir dosyada da var.")
        slugs.add(slug)
        questions = data.get("questions") or []
        if len(questions) < MIN_QUESTIONS_PER_CATEGORY:
            errors.append(
                f"{name}: en az {MIN_QUESTIONS_PER_CATEGORY} soru gerekli, {len(questions)} var."
            )
        seen = set()
        for i, q in enumerate(questions, start=1):
            where = f"{name} soru #{i}"
            text = (q.get("text") or "").strip() if isinstance(q, dict) else ""
            if not text:
                errors.append(f"{where}: soru metni boş.")
                continue
            if text in seen:
                errors.append(f"{where}: tekrarlanan soru metni.")
            seen.add(text)
            if q.get("difficulty") not in (1, 2, 3):
                errors.append(f"{where}: difficulty 1, 2 veya 3 olmalı.")
            choices = q.get("choices")
            if not isinstance(choices, list) or len(choices) != CHOICES_PER_QUESTION:
                errors.append(f"{where}: tam {CHOICES_PER_QUESTION} seçenek olmalı.")
                continue
            if any(not isinstance(c, str) or not c.strip() or len(c) > 255 for c in choices):
                errors.append(f"{where}: seçenekler boş olamaz ve 255 karakteri geçemez.")
            if len({str(c).strip() for c in choices}) != len(choices):
                errors.append(f"{where}: seçenekler birbirinden farklı olmalı.")
            if q.get("answer") not in range(1, CHOICES_PER_QUESTION + 1):
                errors.append(
                    f"{where}: 'answer' 1-{CHOICES_PER_QUESTION} arasında bir sıra olmalı."
                )
    return errors


@transaction.atomic
def seed(files, deactivate_missing=False):
    """YAML'daki kategori ve soruları yükler.

    `deactivate_missing=True` ise yüklenen kategorilerde, YAML'da artık bulunmayan aktif sorular
    pasifleştirilir (silinmez; mevcut oturumların cevap kayıtları korunur). YAML'da olmayan
    kategorilere dokunulmaz. Varsayılan kapalıdır.
    """
    errors = validate(files)
    if errors:
        raise SeedValidationError(errors)
    stats = SeedStats()
    for _, data in files:
        category, created = Category.objects.update_or_create(
            slug=data["slug"],
            defaults={
                "name": data["name"],
                "description": data.get("description"),
                "icon": data.get("icon"),
                "order": data.get("order", 0),
                "is_active": True,
            },
        )
        stats.categories_created += created
        yaml_texts = {q["text"].strip() for q in data["questions"]}
        for q in data["questions"]:
            question, q_created = Question.objects.update_or_create(
                category=category,
                text=q["text"].strip(),
                defaults={"difficulty": q["difficulty"], "is_active": True},
            )
            if q_created:
                stats.questions_created += 1
            else:
                stats.questions_updated += 1
            _sync_choices(question, q)
        if deactivate_missing:
            stale = category.questions.filter(is_active=True).exclude(text__in=yaml_texts)
            texts = list(stale.order_by("id").values_list("text", flat=True))
            stats.questions_deactivated += stale.update(is_active=False)
            stats.deactivated_texts.extend(texts)
    return stats


def _sync_choices(question, q):
    existing = list(question.choices.order_by("order", "id"))
    # Seçenekler yerinde güncellenir: cevaplarda referans verilen satırlar silinmez.
    if len(existing) != CHOICES_PER_QUESTION:
        question.choices.all().delete()
        existing = []
    # Tek-doğru kısıtına çarpmamak için önce tüm bayraklar kapatılır.
    Choice.objects.filter(question=question, is_correct=True).update(is_correct=False)
    for idx, text in enumerate(q["choices"]):
        is_correct = idx + 1 == q["answer"]
        if existing:
            Choice.objects.filter(pk=existing[idx].pk).update(
                text=text.strip(), is_correct=is_correct, order=idx
            )
        else:
            Choice.objects.create(
                question=question, text=text.strip(), is_correct=is_correct, order=idx
            )
