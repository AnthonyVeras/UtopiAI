from utopiai.telegram import split_text


def test_split_text_preserves_content_within_limit():
    value = ("linha longa com palavras\n" * 500).strip()
    chunks = split_text(value, 120)
    assert all(0 < len(chunk) <= 120 for chunk in chunks)
    assert "".join(chunks).replace(" ", "").replace("\n", "") == value.replace(" ", "").replace("\n", "")
