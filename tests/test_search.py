"""Searching SearchableText_icu next to SearchableText in a Plone site."""

from c2.splitter.icu.compat import munge_search_term
from c2.splitter.icu.splitter import ICUSplitter
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from Products.CMFCore.indexing import processQueue
from Products.ZCTextIndex.ParseTree import QueryError

from types import SimpleNamespace

import pytest
import transaction


EVALUATION = "profile-c2.splitter.icu:evaluation"

DOCUMENTS = {
    "tocho": "東京都庁の案内",
    "tokyo": "東京都の観光",
    "kyoto": "京都の寺",
    "karte": "電子カルテの導入",
    "python": "Python3.14 test notes",
    "price": "10,000 yen",
    "domain": "example.com guide",
    "short": "e.f notes",
}


def add_documents(portal):
    setRoles(portal, TEST_USER_ID, ["Manager"])
    for id_, title in DOCUMENTS.items():
        portal.invokeFactory("Document", id_, title=title)
    processQueue()


@pytest.fixture
def search(portal, setup_tool):
    setup_tool.runAllImportStepsFromProfile(EVALUATION)
    add_documents(portal)
    catalog = portal.portal_catalog

    def search(index, query):
        return {brain.getId for brain in catalog(**{index: query})}

    return search


def test_munge_search_term_adds_a_wildcard():
    assert munge_search_term("東京都庁") == "東京都庁*"


@pytest.mark.parametrize(
    ("query", "ngram", "icu"),
    [
        ("Python", {"python"}, {"python"}),
        # several Japanese words become a phrase
        ("東京都庁", {"tocho"}, {"tocho"}),
        ("電子カルテ", {"karte"}, {"karte"}),
        ('"電子カルテの導入"', {"karte"}, {"karte"}),
        # two terms: Plone joins them with AND
        ("電子 導入", {"karte"}, {"karte"}),
        # a match inside other words is gone
        ("京都", {"tocho", "tokyo", "kyoto"}, {"kyoto"}),
        # and so are wanted matches inside longer words
        ("東京都", {"tocho", "tokyo"}, {"tokyo"}),
        # words with "." or "," are one word in the text and in the query
        ("Python3.14", {"python"}, {"python"}),
        ("10,000", {"price"}, {"price"}),
        ("example.com", {"domain"}, {"domain"}),
        ("e.f", {"short"}, {"short"}),
        ("14", {"python"}, set()),
        # neither finds it: the bigram index has "python3" and "14", the ICU
        # index has the one word "python3.14"
        ("3.14", set(), set()),
    ],
)
def test_plone_search(search, query, ngram, icu):
    """The query goes through munge_search_term, as in Plone's search."""
    munged = munge_search_term(query)
    assert (search("SearchableText", munged), search("SearchableText_icu", munged)) == (
        ngram,
        icu,
    )


@pytest.mark.parametrize(
    ("query", "found"),
    [
        ("電子 OR 観光", {"karte", "tokyo"}),
        ("東京 AND NOT 観光", {"tocho"}),
        ("Pyth*", {"python"}),
        ("te?t", {"python"}),
        ("都庁*", {"tocho"}),
        ('"東京 都庁"', {"tocho"}),
    ],
)
def test_query_syntax(search, query, found):
    """ZCTextIndex's own syntax; Plone's search quotes and, or and not."""
    assert search("SearchableText_icu", query) == found


def test_leading_wildcard_is_rejected(search):
    with pytest.raises(QueryError):
        search("SearchableText_icu", "*ython")


def test_icu_lexicon_survives_a_commit(functional):
    portal = functional["portal"]
    portal.portal_setup.runAllImportStepsFromProfile(EVALUATION)
    add_documents(portal)
    transaction.commit()

    connection = functional["app"]._p_jar.db().open()
    try:
        portal = connection.root()["Application"][portal.getId()]
        lexicon = portal.portal_catalog.icu_lexicon
        assert lexicon._p_jar is connection
        assert type(lexicon._pipeline[0]) is ICUSplitter
        assert lexicon.parseTerms("東京都庁") == ["東京", "都庁"]
        assert lexicon.termToWordIds("電子") != [0]
    finally:
        connection.close()


# The steps of the README, as code.


def test_reindex_after_applying_the_profile(portal, setup_tool):
    add_documents(portal)
    setup_tool.runAllImportStepsFromProfile(EVALUATION)
    catalog = portal.portal_catalog
    assert len(catalog(SearchableText_icu="京都*")) == 0

    catalog.reindexIndex("SearchableText_icu", None)

    assert {b.getId for b in catalog(SearchableText_icu="京都*")} == {"kyoto"}


def replace_searchable_text(catalog, lexicon_id):
    """The code of the README: SearchableText with another lexicon."""
    catalog.delIndex("SearchableText")
    extra = SimpleNamespace(
        doc_attr="SearchableText",
        lexicon_id=lexicon_id,
        index_type="Okapi BM25 Rank",
    )
    catalog.addIndex("SearchableText", "ZCTextIndex", extra)
    catalog.reindexIndex("SearchableText", None)


def test_adopt_and_roll_back(search, portal, setup_tool):
    catalog = portal.portal_catalog
    munged = munge_search_term("京都")
    assert search("SearchableText", munged) == {"tocho", "tokyo", "kyoto"}

    replace_searchable_text(catalog, "icu_lexicon")
    assert search("SearchableText", munged) == {"kyoto"}
    # Removing the evaluation index keeps the lexicon SearchableText uses.
    setup_tool.runAllImportStepsFromProfile(
        "profile-c2.splitter.icu:evaluation-uninstall"
    )
    # (the index caches its lexicon, so searching alone would not show it)
    assert "icu_lexicon" in catalog.objectIds()
    assert search("SearchableText", munged) == {"kyoto"}

    replace_searchable_text(catalog, "plone_lexicon")
    assert search("SearchableText", munged) == {"tocho", "tokyo", "kyoto"}
