import copy
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.db import IntegrityError, transaction

from apps.quiz import seeding
from apps.quiz.models import Category, Choice, Question

FIXTURE_DIR = seeding.Path(__file__).resolve().parent.parent / "apps" / "quiz" / "fixtures"


def run_seed(**kwargs):
    out = StringIO()
    call_command("seed_questions", stdout=out, **kwargs)
    return out.getvalue()


@pytest.mark.django_db
def test_seed_loads_real_fixtures():
    run_seed()
    assert Category.objects.count() == 5
    for category in Category.objects.all():
        assert category.questions.count() >= 20
    for question in Question.objects.prefetch_related("choices"):
        choices = list(question.choices.all())
        assert len(choices) == 4
        assert sum(c.is_correct for c in choices) == 1
        assert question.difficulty in (1, 2, 3)


@pytest.mark.django_db
def test_seed_is_idempotent():
    run_seed()
    counts = (Category.objects.count(), Question.objects.count(), Choice.objects.count())
    choice_ids = set(Choice.objects.values_list("id", flat=True))
    run_seed()
    assert (Category.objects.count(), Question.objects.count(), Choice.objects.count()) == counts
    assert set(Choice.objects.values_list("id", flat=True)) == choice_ids


@pytest.mark.django_db
def test_seed_updates_changed_correct_answer_in_place():
    files = seeding.load_files(FIXTURE_DIR)
    seeding.seed(files)
    changed = copy.deepcopy(files)
    q = changed[0][1]["questions"][0]
    q["answer"] = 1 if q["answer"] != 1 else 2
    seeding.seed(changed)
    question = Question.objects.get(text=q["text"])
    correct = question.choices.get(is_correct=True)
    assert correct.order == q["answer"] - 1


def _valid_file(n=20):
    return (
        "x.yaml",
        {
            "name": "X",
            "slug": "x",
            "questions": [
                {"text": f"S{i}", "difficulty": 1, "choices": ["a", "b", "c", "d"], "answer": 1}
                for i in range(n)
            ],
        },
    )


def test_validate_ok():
    assert seeding.validate([_valid_file()]) == []


def test_validate_too_few_questions():
    errors = seeding.validate([_valid_file(19)])
    assert any("en az 20 soru" in e for e in errors)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda q: q.update(choices=["a", "b", "c"]),
        lambda q: q.update(answer=5),
        lambda q: q.update(answer=None),
        lambda q: q.update(choices=["a", "a", "c", "d"]),
        lambda q: q.update(difficulty=4),
        lambda q: q.update(text=""),
    ],
)
def test_validate_rejects_bad_question(mutate):
    name, data = _valid_file()
    mutate(data["questions"][0])
    assert seeding.validate([(name, data)])


def test_validate_duplicate_text_and_slug():
    name, data = _valid_file()
    data["questions"][1]["text"] = data["questions"][0]["text"]
    errors = seeding.validate([(name, data), _valid_file()])
    assert any("tekrarlanan" in e for e in errors)
    assert any("slug" in e for e in errors)


@pytest.mark.django_db
def test_command_fails_without_writing_on_invalid_data(tmp_path):
    (tmp_path / "bad.yaml").write_text("name: X\nslug: x\nquestions: []\n", encoding="utf-8")
    with pytest.raises(CommandError):
        run_seed(path=str(tmp_path))
    assert Category.objects.count() == 0


@pytest.mark.django_db
def test_only_one_correct_choice_per_question_constraint():
    category = Category.objects.create(name="C", slug="c")
    question = Question.objects.create(category=category, text="Q")
    Choice.objects.create(question=question, text="a", is_correct=True)
    with pytest.raises(IntegrityError), transaction.atomic():
        Choice.objects.create(question=question, text="b", is_correct=True)


@pytest.mark.django_db
def test_difficulty_constraint():
    category = Category.objects.create(name="C", slug="c")
    with pytest.raises(IntegrityError), transaction.atomic():
        Question.objects.create(category=category, text="Q", difficulty=7)
