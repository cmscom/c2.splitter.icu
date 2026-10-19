"""Searching SearchableText_icu next to SearchableText in a Plone site."""

from c2.splitter.icu.compat import munge_search_term
from c2.splitter.icu.splitter import ICUSplitter
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from Products.CMFCore.indexing import processQueue
from Products.ZCTextIndex.ParseTree import QueryError

import pytest
import transaction


EVALUATION = "profile-c2.splitter.icu:evaluation"

DOCUMENTS = {
    "tocho": "東京都庁の案内",
    "tokyo": "東京都の観光",
    "kyoto": "京都の寺",
    "kumadai": "熊本大学の入試",
    "python": "Python3.14 test notes",
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
        ("熊本大学", {"kumadai"}, {"kumadai"}),
        ('"熊本大学の入試"', {"kumadai"}, {"kumadai"}),
        # two terms: Plone joins them with AND
        ("熊本 入試", {"kumadai"}, {"kumadai"}),
        # a match inside other words is gone
        ("京都", {"tocho", "tokyo", "kyoto"}, {"kyoto"}),
        # and so are wanted matches inside longer words
        ("東京都", {"tocho", "tokyo"}, {"tokyo"}),
        ("14", {"python"}, set()),
        # neither finds it: the bigram index has "python3" and "14"
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
        ("熊本 OR 観光", {"kumadai", "tokyo"}),
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
        assert lexicon.termToWordIds("熊本") != [0]
    finally:
        connection.close()
