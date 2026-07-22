from tavern.wc3codec import ESC, decode_file, encode_file, escape, unescape


def test_escape_unescape_roundtrip():
    for s in ['{"a":1}', f'quotes " and {ESC} esc', "plain", "", '"' * 10]:
        assert unescape(escape(s)) == s


def test_file_encode_decode_roundtrip():
    for s in ["CHAT|1|Dakkar|hi", "x" * 600, '{"game_time":"01:34"}', ""]:
        assert decode_file(encode_file(s)) == s


def test_encoded_has_preload_wrapping():
    disk = encode_file("hello")
    assert "function PreloadFiles" in disk
    assert "BlzSetAbilityIcon(1097690227,o)" in disk  # w3ts dummy ability


def test_decode_non_file_returns_none():
    assert decode_file("just some prose, not a preload file") is None


def test_chunking_over_259():
    # a payload longer than the 259 Preload limit must split into multiple chunks
    disk = encode_file("y" * 700)
    assert disk.count("call Preload( ") >= 3 + 2  # >=3 content chunks + header/footer empties
    assert decode_file(disk) == "y" * 700
