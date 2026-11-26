"""Tests for app.sources (only links the agent's searches returned survive)."""

from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, ToolReturnPart

from app import agent, sources
from shared.scores import Score

WIKI = "https://en.wikipedia.org/wiki/Piano_Sonata_No._8_(Beethoven)"


def _messages(*contents):
    return [
        ModelResponse(parts=[TextPart(content="https://invented.example/not-a-tool")]),
        *(
            ModelRequest(parts=[ToolReturnPart(tool_name="search", content=c, tool_call_id="1")])
            for c in contents
        ),
    ]


def test_found_urls_reads_only_tool_results():
    seen = sources.found_urls(_messages([{"href": WIKI}, {"href": "https://x.org/a/"}]))
    assert sources.is_found(WIKI, seen)
    assert sources.is_found("https://X.org/a", seen)
    assert not sources.is_found("https://invented.example/not-a-tool", seen)


def test_keep_found_sources_drops_unknown_links_and_empty_sections():
    seen = sources.found_urls(_messages([{"href": WIKI}]))
    text = (
        "## History\nSee https://made.up/page for more.\n\n"
        "## Sources\n- Wikipedia: " + WIKI + "\n- Fake: https://made.up/x\n\n"
        "## Links\n- Other: https://made.up/y"
    )
    assert sources.keep_found_sources(text, seen) == (
        "## History\nSee  for more.\n\n## Sources\n- Wikipedia: " + WIKI
    )


def test_keep_found_sources_trims_a_dangling_label():
    assert sources.keep_found_sources("Read more: https://made.up/x", set()) == "Read more"


def test_only_found_links_cleans_score():
    seen = sources.found_urls(_messages("watch https://www.youtube.com/watch?v=abc " + WIKI))
    score = Score(
        title="t",
        composer="c",
        long_description="## Sources\n- W: " + WIKI + "\n- F: https://made.up",
        long_description_fr="## Sources\n- F: https://made.up",
        youtube_url="https://www.youtube.com/watch?v=abc",
    )
    out = agent._only_found_links(score, seen)
    assert out.long_description == "## Sources\n- W: " + WIKI
    assert out.long_description_fr == ""
    assert out.youtube_url == "https://www.youtube.com/watch?v=abc"
    out.youtube_url = "https://www.youtube.com/watch?v=invented"
    assert agent._only_found_links(out, seen).youtube_url == ""
