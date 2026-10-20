"""The @@icu-compare view."""

from AccessControl import Unauthorized
from c2.splitter.icu.browser import compare as compare_module
from c2.splitter.icu.browser.compare import CompareView
from collections.abc import Callable
from plone.app.testing import login
from plone.app.testing import logout
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.app.testing import TEST_USER_NAME
from Products.CMFCore.indexing import processQueue
from typing import Any
from zExceptions import NotFound

import html
import pytest


EVALUATION = "profile-c2.splitter.icu:evaluation"
ERROR = "pattern '*ython' shouldn't start with glob character"


@pytest.fixture
def manager(portal: Any) -> None:
    setRoles(portal, TEST_USER_ID, ["Manager"])
    login(portal, TEST_USER_NAME)


@pytest.fixture
def documents(portal: Any, setup_tool: Any, manager: None) -> None:
    setup_tool.runAllImportStepsFromProfile(EVALUATION)
    portal.invokeFactory("Document", "tocho", title="東京都庁の案内")
    portal.invokeFactory("Document", "kyoto", title="京都の寺")
    processQueue()


@pytest.fixture
def compare(portal: Any, http_request: Any) -> Callable[..., CompareView]:
    def compare(q: str | list[str] | None = None) -> CompareView:
        if q is not None:
            http_request.form["q"] = q
        view: CompareView = portal.restrictedTraverse("@@icu-compare")
        return view

    return compare


@pytest.mark.usefixtures("documents")
class TestCompare:
    def test_search_terms(self, compare):
        view = compare("京都")
        assert view.query == "京都"
        assert view.munged == "京都*"
        assert view.search_terms() == {
            # the UnicodeSplitter drops the "*" of a two-character bigram
            "SearchableText": ["京都"],
            "SearchableText_icu": ["京都*"],
        }

    def test_index_words(self, compare):
        assert compare("東京都庁").index_words() == {
            "SearchableText": ["東京", "京都", "都庁", "庁"],
            "SearchableText_icu": ["東京", "都庁"],
        }

    def test_results_side_by_side(self, compare):
        view = compare("京都")
        ngram = view.results("SearchableText")
        icu = view.results("SearchableText_icu")
        assert ngram["count"] == 2
        assert ngram["error"] is None
        assert {
            (row["title"], row["path"], row["only_here"]) for row in ngram["rows"]
        } == {
            ("東京都庁の案内", "/plone/tocho", True),
            ("京都の寺", "/plone/kyoto", False),
        }
        assert icu["count"] == 1
        assert [(row["title"], row["only_here"]) for row in icu["rows"]] == [
            ("京都の寺", False)
        ]

    def test_at_most_20_rows(self, portal, compare):
        for number in range(25):
            portal.invokeFactory("Document", f"doc{number}", title="電子カルテ")
        processQueue()
        result = compare("電子").results("SearchableText_icu")
        assert result["count"] == 25
        assert len(result["rows"]) == 20

    def test_query_error_is_shown(self, compare, monkeypatch):
        # munge_search_term removes "*" and "?", so the query is passed as it is
        monkeypatch.setattr(compare_module, "munge_search_term", lambda query: query)
        view = compare("*ython")
        result = view.results("SearchableText_icu")
        assert result == {"count": 0, "rows": [], "error": ERROR}
        assert ERROR in html.unescape(view())

    def test_page(self, compare):
        html = compare("京都")()
        assert "<h1>Compare SearchableText and SearchableText_icu</h1>" in html
        assert 'value="京都"' in html
        assert "<code>京都*</code>" in html
        assert "東京都庁の案内" in html
        assert "only here" in html

    def test_query_given_twice_uses_the_first(self, compare):
        # ?q=京都&q=東京 gives a list
        view = compare(["京都", "東京"])
        assert view.query == "京都"
        assert "<code>京都*</code>" in view()

    def test_empty_query_list(self, compare):
        assert compare([]).query == ""

    def test_page_without_query(self, compare):
        view = compare()
        assert view.query == ""
        html = view()
        assert 'name="q"' in html
        assert "Results" not in html


def test_without_evaluation_index(compare, manager):
    view = compare("京都")
    assert view.icu_available is False
    html = " ".join(view().split())
    assert (
        "SearchableText_icu does not exist. Apply the "
        "<code>c2.splitter.icu:evaluation</code> profile" in html
    )


@pytest.mark.parametrize("roles", [["Member"], ["Site Administrator"], ["Editor"]])
def test_only_managers(portal, compare, roles):
    setRoles(portal, TEST_USER_ID, roles)
    login(portal, TEST_USER_NAME)
    with pytest.raises(Unauthorized):
        compare("京都")


def test_anonymous(portal, compare):
    logout()
    with pytest.raises(Unauthorized):
        compare("京都")


def test_only_on_the_site_root(portal, manager):
    portal.invokeFactory("Folder", "folder")
    with pytest.raises((AttributeError, KeyError, NotFound)):
        portal.folder.restrictedTraverse("@@icu-compare")
