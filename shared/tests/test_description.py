from shared.description import reflow


def test_one_line_description_gets_its_lines_back():
    text = (
        "## History Beethoven wrote them between 1795 and 1822. "
        "## Playing it - Voice the melody. - Use the pedal sparingly. "
        "## Did you know? The 'Moonlight' name is not his. "
        "## Sources - Wikipedia: https://en.wikipedia.org/wiki/X - IMSLP: https://imslp.org/wiki/Y"
    )
    assert reflow(text) == (
        "## History\n"
        "Beethoven wrote them between 1795 and 1822.\n"
        "\n"
        "## Playing it\n"
        "- Voice the melody.\n"
        "- Use the pedal sparingly.\n"
        "\n"
        "## Did you know?\n"
        "The 'Moonlight' name is not his.\n"
        "\n"
        "## Sources\n"
        "- Wikipedia: https://en.wikipedia.org/wiki/X\n"
        "- IMSLP: https://imslp.org/wiki/Y"
    )


def test_french_and_unknown_headings():
    text = "## Histoire Écrite en 1893. ## Le saviez-vous ? Dédiée à Clara. ## Autre Texte libre."
    assert reflow(text) == (
        "## Histoire\nÉcrite en 1893.\n\n"
        "## Le saviez-vous ?\nDédiée à Clara.\n\n"
        "## Autre Texte libre."
    )


def test_text_with_line_breaks_or_without_headings_is_left_alone():
    assert reflow("## History\nText") == "## History\nText"
    assert reflow("A short text - with a dash.") == "A short text - with a dash."
    assert reflow("") == ""
