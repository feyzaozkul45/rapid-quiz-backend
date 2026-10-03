from django.db import models
from django.db.models import Q


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    icon = models.CharField(max_length=50, blank=True, null=True)
    order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "categories"
        ordering = ["order", "id"]
        verbose_name = "Kategori"
        verbose_name_plural = "Kategoriler"

    def __str__(self):
        return self.name


class Question(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    difficulty = models.PositiveSmallIntegerField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "questions"
        verbose_name = "Soru"
        verbose_name_plural = "Sorular"
        constraints = [
            models.CheckConstraint(
                condition=Q(difficulty__isnull=True) | Q(difficulty__gte=1, difficulty__lte=3),
                name="question_difficulty_1_3",
            ),
        ]

    def __str__(self):
        return self.text[:60]


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "choices"
        ordering = ["order", "id"]
        verbose_name = "Seçenek"
        verbose_name_plural = "Seçenekler"
        constraints = [
            # Soru başına en fazla 1 doğru seçenek; "en az 1" ve "tam 4 seçenek"
            # admin formset'i ve seed komutu tarafından doğrulanır.
            models.UniqueConstraint(
                fields=["question"],
                condition=Q(is_correct=True),
                name="choice_one_correct_per_question",
            ),
        ]

    def __str__(self):
        return self.text
