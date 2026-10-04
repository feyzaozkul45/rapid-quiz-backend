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


def test_bundled_pool_is_large_and_answers_are_not_guessable():
    """Havuz tekrarı azaltacak kadar büyük; doğru şık konumu ve uzunluğu ipucu vermiyor."""
    for name, data in seeding.load_files(FIXTURE_DIR):
        questions = data["questions"]
        assert len(questions) >= 40, name
        positions = [q["answer"] for q in questions]
        for position in (1, 2, 3, 4):
            share = positions.count(position) / len(questions)
            assert 0.15 <= share <= 0.35, (name, position, share)
        longest = sum(
            1
            for q in questions
            if (lengths := [len(c) for c in q["choices"]])
            and lengths[q["answer"] - 1] == max(lengths)
            and lengths.count(max(lengths)) == 1
        )
        # Rastgele beklenti %25; belirgin biçimde fazlası "en uzun şık doğrudur" ipucu olur.
        assert longest / len(questions) <= 0.40, (name, longest)


# ---- --deactivate-missing ------------------------------------------------------------


def _write_yaml(directory, slug, texts, name=None):
    import yaml

    data = {
        "name": name or slug.upper(),
        "slug": slug,
        "questions": [
            {"text": t, "difficulty": 1, "choices": ["a", "b", "c", "d"], "answer": 1}
            for t in texts
        ],
    }
    (directory / f"{slug}.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), "utf-8")


def _active_texts(slug):
    return set(
        Question.objects.filter(category__slug=slug, is_active=True).values_list("text", flat=True)
    )


@pytest.mark.django_db
def test_deactivate_missing_is_off_by_default(tmp_path):
    _write_yaml(tmp_path, "x", [f"Eski {i}" for i in range(20)])
    run_seed(path=str(tmp_path))
    _write_yaml(tmp_path, "x", [f"Eski {i}" for i in range(1, 20)] + ["Yeni 0"])

    out = run_seed(path=str(tmp_path))

    assert "Pasifleştirilen" not in out
    assert "Eski 0" in _active_texts("x")  # eski metin aktif kalır
    assert "Yeni 0" in _active_texts("x")


@pytest.mark.django_db
def test_deactivate_missing_deactivates_removed_questions_without_deleting(tmp_path):
    _write_yaml(tmp_path, "x", [f"Eski {i}" for i in range(20)])
    run_seed(path=str(tmp_path))
    _write_yaml(tmp_path, "x", [f"Eski {i}" for i in range(2, 20)] + ["Yeni 0", "Yeni 1"])

    out = run_seed(path=str(tmp_path), deactivate_missing=True)

    assert "Pasifleştirilen soru: 2" in out
    assert "Eski 0" in out and "Eski 1" in out  # hangileri olduğu yazılır
    active = _active_texts("x")
    assert len(active) == 20
    assert not {"Eski 0", "Eski 1"} & active
    assert {"Yeni 0", "Yeni 1"} <= active
    # silinmedi: kayıt duruyor, yalnızca pasif
    assert Question.objects.filter(text="Eski 0", is_active=False).exists()
    assert Question.objects.filter(category__slug="x").count() == 22


@pytest.mark.django_db
def test_deactivate_missing_is_idempotent_and_reactivates_if_text_returns(tmp_path):
    _write_yaml(tmp_path, "x", [f"S{i}" for i in range(20)])
    run_seed(path=str(tmp_path))
    _write_yaml(tmp_path, "x", [f"S{i}" for i in range(1, 20)] + ["Yeni"])
    run_seed(path=str(tmp_path), deactivate_missing=True)

    assert "Pasifleştirilen soru: 0" in run_seed(path=str(tmp_path), deactivate_missing=True)

    _write_yaml(tmp_path, "x", [f"S{i}" for i in range(20)])  # S0 geri döndü
    run_seed(path=str(tmp_path), deactivate_missing=True)
    assert "S0" in _active_texts("x")
    assert "Yeni" not in _active_texts("x")


@pytest.mark.django_db
def test_deactivate_missing_only_touches_categories_in_the_files(tmp_path):
    other = Category.objects.create(name="Başka", slug="baska")
    Question.objects.create(category=other, text="Başka soru", difficulty=1, is_active=True)
    _write_yaml(tmp_path, "x", [f"S{i}" for i in range(20)])

    run_seed(path=str(tmp_path), deactivate_missing=True)

    assert _active_texts("baska") == {"Başka soru"}  # YAML'da olmayan kategoriye dokunulmaz


@pytest.mark.django_db
def test_deactivate_missing_keeps_active_pool_valid_for_quiz(tmp_path, api):
    _write_yaml(tmp_path, "x", [f"S{i}" for i in range(20)])
    run_seed(path=str(tmp_path))
    _write_yaml(tmp_path, "x", [f"T{i}" for i in range(20)])
    run_seed(path=str(tmp_path), deactivate_missing=True)

    response = api.post("/api/v1/quiz-sessions/", {"category": "x"}, format="json")

    assert response.status_code == 201  # aktif havuz hâlâ 20 soru


def test_deactivate_missing_flag_defaults_to_false():
    from apps.quiz.management.commands.seed_questions import Command

    parser = Command().create_parser("manage.py", "seed_questions")
    assert parser.parse_args([]).deactivate_missing is False
    assert parser.parse_args(["--deactivate-missing"]).deactivate_missing is True


# ---- içerik: İspanya kara komşusu sorusu -----------------------------------------------


def test_spain_land_border_question_has_only_one_real_neighbour():
    """Fransa, Andorra ve Fas (Ceuta/Melilla) İspanya'nın komşusudur: yanlış şıklarda olmamalı."""
    files = dict(seeding.load_files(FIXTURE_DIR))
    question = next(
        q for q in files["ulkeler.yaml"]["questions"] if "İspanya ile kara sınırı" in q["text"]
    )
    wrong = [c for i, c in enumerate(question["choices"], 1) if i != question["answer"]]
    neighbours = {"fransa", "andorra", "fas", "portekiz", "cebelitarık", "birleşik krallık"}
    assert question["choices"][question["answer"] - 1] == "Portekiz"
    assert not neighbours & {c.lower() for c in wrong}
