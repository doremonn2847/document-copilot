import pytest

from app.chat.titles import clean_title


@pytest.mark.parametrize(
    "raw,title",
    [
        ('"Microsoft Azure in 2025 Filing."', "Microsoft Azure in 2025 Filing"),
        ("  Apple   revenue\nmix  ", "Apple revenue mix"),
        ("“Greeting”", "Greeting"),
        ("", None),
        ("  ...  ", None),
        (
            "Amazon AWS operating income versus North America and International segments 2021 to 2025",
            "Amazon AWS operating income versus North America and",
        ),
    ],
)
def test_titles_are_one_short_plain_line(raw, title):
    assert clean_title(raw) == title
    assert title is None or len(title) <= 60
