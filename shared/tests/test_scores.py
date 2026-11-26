"""test scores"""

from shared.scores import Score, Scores


def test_scores():
    """test scores"""
    score = Score(
        id=1,
        pdf_path="path",
        title="title",
        composer="composer",
        number_of_plays=1,
        user_id=0,
    )
    assert score.id == 1
    assert score.pdf_path == "path"
    assert score.title == "title"
    assert score.composer == "composer"
    assert score.number_of_plays == 1
    scores = Scores(scores=[score])
    assert scores.scores[0].id == 1
    assert len(scores) == 1


def test_toc_report_defaults():
    """A new report is open, timestamped, and holds an empty snapshot."""
    from shared.scores import TocReport, TocReportIn

    report = TocReport(score_id=1, user_id=1)
    assert report.resolved is False and report.sections == [] and report.created_at is not None
    assert TocReportIn().comment == ""


def test_score_inputs_are_capped_and_links_checked():
    import pytest
    from pydantic import ValidationError

    from shared.scores import NAME_MAX, ScoreCreate, ScoreUpdate

    with pytest.raises(ValidationError):
        ScoreCreate(title="t" * (NAME_MAX + 1), composer="c")
    with pytest.raises(ValidationError):
        ScoreUpdate(long_description="x" * 20001)
    for bad in ("javascript:alert(1)", "data:text/html,x", "//evil.example"):
        with pytest.raises(ValidationError):
            ScoreCreate(title="t", composer="c", youtube_url=bad)
        with pytest.raises(ValidationError):
            ScoreUpdate(youtube_url=bad)
    assert ScoreCreate(title="t", composer="c", youtube_url="").youtube_url == ""
    assert ScoreUpdate(youtube_url="https://youtu.be/x").youtube_url == "https://youtu.be/x"
    assert ScoreUpdate(youtube_url=None).youtube_url is None
