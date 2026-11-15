"""Tests for annotation models."""

import pytest
from pydantic import ValidationError

from shared.annotations import Annotation, AnnotationIn, InkData, TextData


def test_ink_and_text_parse_by_kind():
    ink = AnnotationIn.model_validate(
        {"page": 2, "data": {"kind": "ink", "points": [[0.1, 0.2], [0.3, 0.4]]}}
    )
    assert isinstance(ink.data, InkData)
    assert ink.data.color == "#e11d48"
    text = AnnotationIn.model_validate(
        {"page": 1, "data": {"kind": "text", "x": 0.5, "y": 0.5, "text": "breathe"}}
    )
    assert isinstance(text.data, TextData)
    assert text.data.text == "breathe"


@pytest.mark.parametrize(
    "body",
    [
        {"page": 0, "data": {"kind": "text", "x": 0, "y": 0, "text": "a"}},
        {"page": 1, "data": {"kind": "text", "x": 1.5, "y": 0, "text": "a"}},
        {"page": 1, "data": {"kind": "text", "x": 0, "y": 0, "text": ""}},
        {"page": 1, "data": {"kind": "ink", "points": []}},
        {"page": 1, "data": {"kind": "ink", "points": [[0, 0]], "color": "red"}},
        {"page": 1, "data": {"kind": "ink", "points": [[0, 0]], "width": 1}},
        {"page": 1, "data": {"kind": "stamp"}},
    ],
)
def test_invalid_annotations_are_rejected(body):
    with pytest.raises(ValidationError):
        AnnotationIn.model_validate(body)


def test_annotation_defaults_timestamps():
    a = Annotation(score_id=1, user_id=1, page=1, kind="text", data={})
    assert a.created_at is not None
    assert a.updated_at is not None
