"""Unit tests of ICUSplitter. They need PyICU, not a Plone site."""

from c2.splitter.icu.splitter import ICUSplitter
from c2.splitter.icu.splitter import locale_from_language
from zope.component import getGlobalSiteManager
from zope.component.hooks import setSite

import icu
import logging
import pickle
import pytest


# Words that come from the ICU dictionary depend on the ICU version, so the
# expected values are kept per ICU major version: 74 is the version of the
# ubuntu-24.04 runner, 76 the one of Debian 13 (python:3.14-slim). Add a
# column when CI or a deployment moves to another ICU.
EXPECTED_WORDS = {
    # one-character words
    "私は猫が好き": {
        "74": ["私", "は", "猫", "が", "好き"],
        "76": ["私", "は", "猫", "が", "好き"],
    },
    # compound word and proper noun
    "大阪府立図書館": {
        "74": ["大阪", "府立", "図書館"],
        "76": ["大阪", "府立", "図書館"],
    },
    "東京都庁に行く": {
        "74": ["東京", "都庁", "に", "行く"],
        "76": ["東京", "都庁", "に", "行く"],
    },
    # product names
    "iPhone15を買った": {
        "74": ["iPhone15", "を", "買", "っ", "た"],
        "76": ["iPhone15", "を", "買", "っ", "た"],
    },
    # unknown words: one is kept, the other is cut
    "ピカチュウ": {
        "74": ["ピカチュウ"],
        "76": ["ピカチュウ"],
    },
    "クマモン": {
        "74": ["クマ", "モン"],
        "76": ["クマ", "モン"],
    },
    # Japanese and English, numbers
    "ChatGPTとPython3.14で開発": {
        "74": ["ChatGPT", "と", "Python3.14", "で", "開発"],
        "76": ["ChatGPT", "と", "Python3.14", "で", "開発"],
    },
    "2026年10月19日": {
        "74": ["2026", "年", "10", "月", "19", "日"],
        "76": ["2026", "年", "10", "月", "19", "日"],
    },
    # supplementary characters before the words do not shift them
    "😀𠮷野家で牛丼を食べた": {
        "74": ["𠮷", "野家", "で", "牛", "丼", "を", "食", "べた"],
        "76": ["𠮷", "野家", "で", "牛", "丼", "を", "食", "べた"],
    },
    # half-width katakana, after NFKC
    "ﾊﾟｲｿﾝ": {
        "74": ["パイ", "ソン"],
        "76": ["パイ", "ソン"],
    },
}

EXPECTED_GLOBS = {
    "東京*": {
        "74": ["東京*"],
        "76": ["東京*"],
    },
    # a pattern that ICU splits keeps the wildcard on the word it is in
    "東京都庁*": {
        "74": ["東京", "都庁*"],
        "76": ["東京", "都庁*"],
    },
    "東京都*": {
        "74": ["東京", "都*"],
        "76": ["東京", "都*"],
    },
    "東京*都庁*": {
        "74": ["東京*", "都庁*"],
        "76": ["東京*", "都庁*"],
    },
}


@pytest.fixture(scope="module")
def icu_major() -> str:
    major: str = icu.ICU_VERSION.split(".")[0]
    known = sorted({
        v
        for table in (EXPECTED_WORDS, EXPECTED_GLOBS)
        for row in table.values()
        for v in row
    })
    if major not in known:
        pytest.fail(
            f"No expected words for ICU {icu.ICU_VERSION} (known majors: "
            f"{', '.join(known)}). Add a column to EXPECTED_WORDS and "
            "EXPECTED_GLOBS in tests/test_splitter.py."
        )
    return major


@pytest.fixture
def splitter() -> ICUSplitter:
    # without a site the locale is ja
    setSite(None)
    return ICUSplitter()


@pytest.mark.parametrize("text", sorted(EXPECTED_WORDS))
def test_process_japanese(splitter, icu_major, text):
    assert splitter.process([text]) == EXPECTED_WORDS[text][icu_major]


@pytest.mark.parametrize("pattern", sorted(EXPECTED_GLOBS))
def test_process_glob_japanese(splitter, icu_major, pattern):
    assert splitter.processGlob([pattern]) == EXPECTED_GLOBS[pattern][icu_major]


# The tests below do not depend on the ICU version.


@pytest.mark.parametrize(
    ("text", "words"),
    [
        ("Hello, world!", ["Hello", "world"]),
        # order and duplicates are kept
        ("the cat the", ["the", "cat", "the"]),
        ("foo_bar baz9", ["foo_bar", "baz9"]),
        # full-width letters and digits, after NFKC
        ("１２３ＡＢＣ", ["123ABC"]),
        ("Ｐｙｔｈｏｎ", ["Python"]),
        ("①②", ["12"]),
        # a combining mark that has no precomposed form stays in the word
        ("x́y z", ["x́y", "z"]),
        # supplementary characters (UTF-16 surrogate pairs) before the words
        ("😀😀abc def", ["abc", "def"]),
        ("𠮷abc", ["𠮷", "abc"]),
    ],
)
def test_process(splitter, text, words):
    assert splitter.process([text]) == words


@pytest.mark.parametrize("text", ["", " ", "  、。！", "😀", "*", "?"])
def test_no_words(splitter, text):
    assert splitter.process([text]) == []
    assert splitter.processGlob([text]) == []


def test_empty_list(splitter):
    assert splitter.process([]) == []
    assert splitter.processGlob([]) == []
    assert splitter.process_post_glob([]) == []


def test_several_texts_are_joined_in_order(splitter):
    assert splitter.process(["b a", "", "c"]) == ["b", "a", "c"]


def test_words_are_str(splitter):
    words = splitter.process(["abc 図書館"]) + splitter.processGlob(["abc*"])
    assert {type(word) for word in words} == {str}


def test_utf8_bytes_are_split_like_str(splitter):
    assert splitter.process(["Ｐｙｔｈｏｎ 3.14".encode()]) == ["Python", "3.14"]


def test_invalid_utf8_is_replaced_and_logged_once(splitter, caplog):
    with caplog.at_level(logging.WARNING, logger="c2.splitter.icu"):
        words = splitter.process([b"secret \xff\xfe word"])
    # U+FFFD is not part of a word, so it is dropped like other symbols
    assert words == ["secret", "word"]
    assert caplog.record_tuples == [
        (
            "c2.splitter.icu",
            logging.WARNING,
            "Could not decode 14 bytes as UTF-8 (first invalid byte at "
            "position 7); invalid bytes were replaced with U+FFFD",
        )
    ]


def test_invalid_utf8_keeps_the_replacement_inside_a_glob(splitter, caplog):
    with caplog.at_level(logging.WARNING, logger="c2.splitter.icu"):
        assert splitter.processGlob([b"ab\xffcd*"]) == ["ab", "cd*"]
        assert splitter.process_post_glob([b"ab\xff*"]) == ["ab�"]
    assert [r.getMessage() for r in caplog.records] == [
        "Could not decode 6 bytes as UTF-8 (first invalid byte at position 2); "
        "invalid bytes were replaced with U+FFFD",
        "Could not decode 4 bytes as UTF-8 (first invalid byte at position 2); "
        "invalid bytes were replaced with U+FFFD",
    ]


def test_log_does_not_contain_the_text(splitter, caplog):
    with caplog.at_level(logging.DEBUG, logger="c2.splitter.icu"):
        splitter.process([b"password=hunter2 \xff"])
    assert len(caplog.records) == 1
    assert "hunter2" not in caplog.text
    assert "password" not in caplog.text


@pytest.mark.parametrize(
    ("pattern", "words"),
    [
        ("Python*", ["Python*"]),
        ("te?t", ["te?t"]),
        # a leading wildcard is kept; ZCTextIndex rejects the pattern
        ("*ython", ["*ython"]),
        # full-width wildcards are * and ? after NFKC
        ("Ｐｙｔｈｏｎ＊", ["Python*"]),
        ("ｔｅ？ｔ", ["te?t"]),
        ("foo Python* bar", ["foo", "Python*", "bar"]),
        ("a*b*", ["a*b*"]),
        ("te?*", ["te?*"]),
        ("Hello, wor*!", ["Hello", "wor*"]),
        # ICU keeps ".", ",", "'" and ":" inside a word, and so does the
        # pattern, so that it matches the word in the index
        ("Python3.14*", ["Python3.14*"]),
        ("10,000*", ["10,000*"]),
        ("example.com*", ["example.com*"]),
        ("don't*", ["don't*"]),
        ("ver1.2.3*", ["ver1.2.3*"]),
        ("foo_bar*", ["foo_bar*"]),
        # wildcards apart from words are dropped
        ("Python *", ["Python"]),
        # without wildcards processGlob is process
        ("Hello, world!", ["Hello", "world"]),
    ],
)
def test_process_glob(splitter, pattern, words):
    assert splitter.processGlob([pattern]) == words


@pytest.mark.parametrize(
    ("words", "result"),
    [
        (["都庁*", "te?t", "Python"], ["都庁", "tet", "Python"]),
        # NFKC, but no second split
        (["Ｐｙｔｈｏｎ＊"], ["Python"]),
        (["東京都庁"], ["東京都庁"]),
        (["Hello world"], ["Hello world"]),
        # nothing left: no empty word
        (["*", "?*"], []),
    ],
)
def test_process_post_glob(splitter, words, result):
    assert splitter.process_post_glob(words) == result


def test_nfkc_is_the_same_for_text_and_search_terms(splitter):
    text = splitter.process(["Ｐｙｔｈｏｎ３ ﾊﾟｲｿﾝ"])
    terms = splitter.processGlob(["Python3 パイソン"])
    assert text == terms
    assert splitter.process_post_glob(text) == text


def test_pickle_round_trip(splitter):
    # Our own object, as the ZODB stores it.
    splitter.locale = "fi"
    restored = pickle.loads(pickle.dumps(splitter))  # noqa: S301
    assert restored.locale == "fi"
    assert restored.process(["東京都庁に行く Python3.14 a:b"]) == splitter.process([
        "東京都庁に行く Python3.14 a:b"
    ])


def test_instance_holds_the_locale_and_no_icu_objects(splitter):
    splitter.process(["abc"])
    assert vars(splitter) == {"locale": "ja"}
    assert ICUSplitter.locale == "ja"


def test_without_a_site_the_locale_is_ja():
    setSite(None)
    assert ICUSplitter().locale == "ja"


class SiteWithoutRegistry:
    def getSiteManager(self) -> object:
        return getGlobalSiteManager()


def test_site_without_a_registry_gives_ja():
    setSite(SiteWithoutRegistry())
    try:
        assert ICUSplitter().locale == "ja"
    finally:
        setSite(None)


def test_splitter_stored_without_a_locale_uses_ja():
    # A splitter pickled before the locale was stored: no __init__ runs.
    old = ICUSplitter.__new__(ICUSplitter)
    assert vars(old) == {}
    assert old.locale == "ja"
    assert old.process(["a:b"]) == ["a", "b"]


@pytest.mark.parametrize(
    ("locale", "words", "globs"),
    [
        # ja and most locales cut at ":"; fi and sv keep it inside a word
        ("ja", ["a", "b"], ["a", "b*"]),
        ("fi", ["a:b"], ["a:b*"]),
        ("sv", ["a:b"], ["a:b*"]),
    ],
)
def test_the_locale_changes_the_words(splitter, locale, words, globs):
    splitter.locale = locale
    assert splitter.process(["a:b"]) == words
    assert splitter.processGlob(["a:b*"]) == globs


@pytest.mark.parametrize(
    ("language", "locale"),
    [
        ("ja", "ja"),
        ("en", "en"),
        # Plone's combined language codes
        ("en-us", "en_US"),
        ("pt-br", "pt_BR"),
        ("zh-tw", "zh_TW"),
        ("fi", "fi"),
        # nothing, or nothing ICU knows as a language: ja
        ("", "ja"),
        (None, "ja"),
        (42, "ja"),
        ("xx", "ja"),
        ("!!!", "ja"),
        ("123", "ja"),
        ("toolonglanguage", "ja"),
    ],
)
def test_locale_from_language(language, locale):
    assert locale_from_language(language) == locale


def test_registered_as_word_splitter():
    from Products.ZCTextIndex.PipelineFactory import element_factory

    assert "ICU word splitter" in element_factory.getFactoryNames("Word Splitter")
    assert (
        element_factory.instantiate("Word Splitter", "ICU word splitter").__class__
        is ICUSplitter
    )
