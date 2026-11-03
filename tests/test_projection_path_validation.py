from itertools import combinations, product
from random import Random

import pytest
from pydantic import ValidationError

from schemarouter import EndpointSpec, FieldSpec, models
from schemarouter.models import _overlapping_projection_pairs


def _quadratic_error(fields: list[FieldSpec]) -> str | None:
    """The original endpoint path checks, including phase and input-pair priority."""
    if len({field.name for field in fields}) != len(fields):
        return "duplicate output field name in endpoint 'paths'"
    paths = [field.projection_path for field in fields]
    if len(set(paths)) != len(paths):
        return "duplicate output field path in endpoint 'paths'"
    for index, left in enumerate(fields):
        for right in fields[index + 1 :]:
            source_shorter, source_longer = sorted(
                (left.projection_path, right.projection_path), key=len
            )
            result_shorter, result_longer = sorted(
                (left.result_projection_path, right.result_projection_path), key=len
            )
            if (
                source_longer[: len(source_shorter)] == source_shorter
                and result_longer[: len(result_shorter)] == result_shorter
                and not ("*" in source_longer and "*" in result_longer)
            ):
                return (
                    "overlapping output field paths in endpoint 'paths': "
                    f"{left.name!r} and {right.name!r}"
                )
    result_paths = [field.result_projection_path for field in fields]
    if len(set(result_paths)) != len(result_paths):
        return "duplicate output result path in endpoint 'paths'"
    for index, left in enumerate(fields):
        for right in fields[index + 1 :]:
            shorter, longer = sorted(
                (left.result_projection_path, right.result_projection_path), key=len
            )
            if longer[: len(shorter)] == shorter and "*" not in longer:
                return (
                    "overlapping output result paths in endpoint 'paths': "
                    f"{left.name!r} and {right.name!r}"
                )
    return None


def _check(fields: list[FieldSpec]) -> None:
    expected = _quadratic_error(fields)
    try:
        EndpointSpec(name="paths", output_fields=fields)
    except ValidationError as error:
        actual = str(error.errors()[0]["ctx"]["error"])
    else:
        actual = None
    assert actual == expected, [field.model_dump() for field in fields]


def _valid_paths() -> list[tuple[tuple[str, ...], tuple[str, ...]]]:
    paths = [
        (), ("a",), ("b",), ("a", "b"), ("a", "c"), ("a", "b", "c"),
        ("a.b",), ("a", "*", "b"), ("a", "*", "b", "c"),
        ("a", "*", "b", "*", "c"), ("b", "*", "c"), ("*",),
    ]
    valid = []
    for source, result in product(paths, repeat=2):
        try:
            FieldSpec(name="field", path=list(source), result_path=list(result))
        except ValidationError:
            continue
        valid.append((source, result))
    return valid


def _fields(specs: tuple | list) -> list[FieldSpec]:
    return [
        FieldSpec(name=f"f{index}", path=list(source), result_path=list(result))
        for index, (source, result) in enumerate(specs)
    ]


def test_path_validation_matches_quadratic_oracle_exhaustive_pairs() -> None:
    for specs in product(_valid_paths(), repeat=2):
        _check(_fields(specs))


def test_path_validation_matches_quadratic_oracle_exhaustive_triples() -> None:
    specs = [
        (("a",), ("a",)),
        (("a", "b"), ("a", "b")),
        (("a", "b", "c"), ("a", "b", "c")),
        (("b",), ("a", "b")),
        (("a", "b"), ("b",)),
        (("a", "*", "b"), ("a", "*", "b")),
        (("a", "*", "b", "c"), ("a", "*", "b", "c")),
        (("a", "*", "b", "*", "c"), ("a", "*", "b", "*", "c")),
        (("b",), ("a",)),
    ]
    for selected in product(specs, repeat=3):
        _check(_fields(selected))


def test_path_validation_matches_quadratic_oracle_random_and_reverse() -> None:
    random = Random(612)
    choices = _valid_paths()
    for _ in range(2000):
        fields = _fields(random.choices(choices, k=random.randrange(9)))
        _check(fields)
        _check(list(reversed(fields)))


@pytest.mark.parametrize("specs", [
    # The middle result ancestor has a disjoint source; only the outer pair conflicts.
    [(("a",), ("a",)), (("b",), ("a", "b")),
     (("a", "c"), ("a", "b", "c"))],
    # Prefix sorting visits the later input pair first.
    [(("z",), ("z",)), (("z", "b"), ("z", "b")),
     (("a",), ("a",)), (("a", "b"), ("a", "b"))],
    # Wildcard ancestor merges must not hide a later non-wildcard conflict.
    [(("a",), ("a",)), (("a", "*", "b"), ("a", "*", "b")),
     (("a", "z"), ("a", "z"))],
])
def test_nonadjacent_overlap_and_original_pair_priority(specs: list) -> None:
    _check(_fields(specs))


def test_duplicate_field_name_still_precedes_path_errors() -> None:
    fields = [FieldSpec(name="same", path=["a"]), FieldSpec(name="same", path=["a"])]
    _check(fields)


def test_prefix_candidates_match_all_overlapping_pairs_including_equal_paths() -> None:
    paths = [source for source, _ in _valid_paths()]
    expected = {
        (left, right)
        for left, right in combinations(range(len(paths)), 2)
        if paths[left][: len(paths[right])] == paths[right]
        or paths[right][: len(paths[left])] == paths[left]
    }
    candidates = list(_overlapping_projection_pairs(paths))
    assert len(candidates) == len(set(candidates))
    assert set(candidates) == expected


def test_wide_disjoint_paths_do_not_enter_pair_validation(monkeypatch) -> None:
    paths = [("result", f"field_{index}") for index in range(612)]
    assert list(_overlapping_projection_pairs(paths)) == []
    pair_counts = []

    def counted_pairs(paths):
        pair_counts.append(0)
        for pair in _overlapping_projection_pairs(paths):
            pair_counts[-1] += 1
            yield pair

    monkeypatch.setattr(models, "_overlapping_projection_pairs", counted_pairs)
    EndpointSpec(
        name="wide",
        output_fields=[FieldSpec(name=path[-1], path=list(path)) for path in paths],
    )
    assert pair_counts == [0, 0]
