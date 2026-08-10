"""Unit tests for Metadata and MetadataFilter (M3.0)."""

from __future__ import annotations

import pytest

from aiplatform.domain.knowledge.metadata import Metadata, MetadataFilter


def test_of_builds_from_mapping_and_is_order_independent() -> None:
    a = Metadata.of({"source": "a.md", "page": 3})
    b = Metadata.of({"page": 3, "source": "a.md"})
    assert a == b  # sorted items → content equality regardless of insertion order
    assert a.get("source") == "a.md"
    assert a.get("page") == 3
    assert a.get("missing") is None


def test_empty_metadata() -> None:
    assert Metadata().as_dict() == {}
    assert Metadata.of(None).as_dict() == {}


def test_rejects_non_scalar_value() -> None:
    with pytest.raises(ValueError, match="scalar"):
        Metadata.of({"tags": ["a", "b"]})  # type: ignore[dict-item]


def test_rejects_empty_key() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        Metadata((("", "x"),))


def test_empty_filter_matches_everything() -> None:
    assert MetadataFilter.none().is_empty
    assert MetadataFilter.none().matches(Metadata.of({"any": "thing"}))


def test_equals_filter() -> None:
    md = Metadata.of({"lang": "en", "kind": "faq"})
    assert MetadataFilter(equals=(("lang", "en"),)).matches(md)
    assert not MetadataFilter(equals=(("lang", "fr"),)).matches(md)


def test_any_of_filter() -> None:
    md = Metadata.of({"lang": "en"})
    assert MetadataFilter(any_of=(("lang", ("en", "de")),)).matches(md)
    assert not MetadataFilter(any_of=(("lang", ("fr", "de")),)).matches(md)


def test_combined_constraints_all_must_hold() -> None:
    md = Metadata.of({"lang": "en", "kind": "faq"})
    f = MetadataFilter(equals=(("kind", "faq"),), any_of=(("lang", ("en", "de")),))
    assert f.matches(md)
    assert not f.matches(Metadata.of({"lang": "en", "kind": "manual"}))
