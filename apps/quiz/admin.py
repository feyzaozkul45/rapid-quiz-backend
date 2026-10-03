from django import forms
from django.contrib import admin

from .models import Category, Choice, Question

CHOICES_PER_QUESTION = 4


class ChoiceInlineFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        alive = [
            f for f in self.forms if f.cleaned_data and not f.cleaned_data.get("DELETE", False)
        ]
        if len(alive) != CHOICES_PER_QUESTION:
            raise forms.ValidationError(f"Her soru tam {CHOICES_PER_QUESTION} seçenek içermelidir.")
        correct = sum(1 for f in alive if f.cleaned_data.get("is_correct"))
        if correct != 1:
            raise forms.ValidationError("Her soruda tam 1 doğru seçenek olmalıdır.")


class ChoiceInline(admin.TabularInline):
    model = Choice
    formset = ChoiceInlineFormSet
    extra = CHOICES_PER_QUESTION
    max_num = CHOICES_PER_QUESTION


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "order", "is_active")
    list_editable = ("order", "is_active")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("text", "category", "difficulty", "is_active")
    list_filter = ("category", "difficulty", "is_active")
    search_fields = ("text",)
    inlines = [ChoiceInline]
