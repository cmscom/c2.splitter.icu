"""The locale of ICUSplitter comes from the site language when it is made."""

from c2.splitter.icu.splitter import ICUSplitter
from typing import Any
from zope.component.hooks import getSite

import pytest
import transaction


EVALUATION = "profile-c2.splitter.icu:evaluation"
LANGUAGE = "plone.default_language"


def set_language(portal: Any, language: str) -> None:
    portal.portal_registry[LANGUAGE] = language


def set_unchecked(portal: Any, value: object) -> None:
    """Store a value the field would not take, as an old site might have."""
    records = portal.portal_registry.records
    records._values[LANGUAGE] = value
    if hasattr(records, "_invalidate_key_cache"):
        records._invalidate_key_cache(LANGUAGE)


def test_the_site_is_set(portal):
    assert getSite() is portal


@pytest.mark.parametrize(
    ("language", "locale"),
    [("ja", "ja"), ("en", "en"), ("en-us", "en_US"), ("fi", "fi")],
)
def test_locale_is_the_site_language(portal, language, locale):
    set_language(portal, language)
    assert ICUSplitter().locale == locale


@pytest.mark.parametrize("value", ["", None, "!!!", "xx"])
def test_empty_or_invalid_language_gives_ja(portal, value):
    set_unchecked(portal, value)
    assert portal.portal_registry[LANGUAGE] == value
    assert ICUSplitter().locale == "ja"


def test_missing_record_gives_ja(portal):
    del portal.portal_registry.records[LANGUAGE]
    assert ICUSplitter().locale == "ja"


def test_changing_the_site_language_keeps_the_locale(portal):
    set_language(portal, "fi")
    splitter = ICUSplitter()
    set_language(portal, "ja")
    assert splitter.locale == "fi"
    assert splitter.process(["a:b"]) == ["a:b"]


def test_evaluation_lexicon_uses_the_site_language(portal, setup_tool):
    set_language(portal, "fi")
    setup_tool.runAllImportStepsFromProfile(EVALUATION)
    lexicon = portal.portal_catalog.icu_lexicon
    assert lexicon._pipeline[0].locale == "fi"
    assert lexicon.parseTerms("a:b") == ["a:b"]


def test_locale_survives_a_commit_and_a_language_change(functional):
    portal = functional["portal"]
    set_language(portal, "fi")
    portal.portal_setup.runAllImportStepsFromProfile(EVALUATION)
    transaction.commit()
    set_language(portal, "ja")
    transaction.commit()

    connection = functional["app"]._p_jar.db().open()
    try:
        portal = connection.root()["Application"][portal.getId()]
        assert portal.portal_registry[LANGUAGE] == "ja"
        lexicon = portal.portal_catalog.icu_lexicon
        assert lexicon._pipeline[0].locale == "fi"
        assert lexicon.parseTerms("a:b") == ["a:b"]
    finally:
        connection.close()
