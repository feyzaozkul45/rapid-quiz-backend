import factory

from apps.quiz.models import Category, Choice, Question


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Kategori {n}")
    slug = factory.Sequence(lambda n: f"kategori-{n}")
    order = factory.Sequence(lambda n: n)
    is_active = True


class QuestionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Question
        skip_postgeneration_save = True

    category = factory.SubFactory(CategoryFactory)
    text = factory.Sequence(lambda n: f"Soru {n}?")
    difficulty = 1
    is_active = True

    @factory.post_generation
    def choices(self, create, extracted, **kwargs):
        if not create:
            return
        for i in range(4):
            Choice.objects.create(
                question=self, text=f"Seçenek {i}", is_correct=(i == self.pk % 4), order=i
            )


def make_category(question_count=20, **kwargs):
    category = CategoryFactory(**kwargs)
    QuestionFactory.create_batch(question_count, category=category)
    return category
