from Acquisition import aq_base
from c2.splitter.icu import PACKAGE_NAME
from c2.splitter.icu.splitter import ICUSplitter
from plone.app.testing import setRoles
from plone.app.testing import TEST_USER_ID
from plone.base.interfaces import INonInstallable
from Products.CMFCore.indexing import processQueue
from Products.CMFPlone.UnicodeSplitter.splitter import I18NNormalizer
from Products.CMFPlone.UnicodeSplitter.splitter import Splitter
from zope.component import getUtility

from types import SimpleNamespace

import logging
import pytest


EVALUATION = "profile-c2.splitter.icu:evaluation"
EVALUATION_UNINSTALL = "profile-c2.splitter.icu:evaluation-uninstall"


@pytest.fixture
def catalog(portal):
    return portal.portal_catalog


@pytest.fixture
def evaluation(setup_tool):
    setup_tool.runAllImportStepsFromProfile(EVALUATION)


def pipeline(lexicon):
    return [type(element) for element in lexicon._pipeline]


def test_addon_installed(installer):
    assert installer.is_product_installed(PACKAGE_NAME) is True


def test_latest_version(profile_last_version):
    assert profile_last_version(f"{PACKAGE_NAME}:default") == "1000"


def test_default_profile_does_not_change_the_catalog(catalog):
    assert "icu_lexicon" not in catalog.objectIds()
    assert "SearchableText_icu" not in catalog.indexes()


@pytest.mark.usefixtures("portal")
def test_uninstall_profiles_are_hidden():
    hidden = getUtility(INonInstallable, name=PACKAGE_NAME)
    assert hidden.getNonInstallableProfiles() == [
        "c2.splitter.icu:uninstall",
        "c2.splitter.icu:evaluation-uninstall",
    ]


def test_deactivate(installer):
    assert installer.uninstall_product(PACKAGE_NAME) is True
    assert installer.is_product_installed(PACKAGE_NAME) is False


@pytest.mark.usefixtures("evaluation")
def test_deactivate_keeps_the_evaluation_index(installer, catalog):
    installer.uninstall_product(PACKAGE_NAME)
    assert "icu_lexicon" in catalog.objectIds()
    assert "SearchableText_icu" in catalog.indexes()


@pytest.mark.usefixtures("evaluation")
class TestEvaluation:
    def test_lexicon_added(self, catalog):
        assert pipeline(catalog.icu_lexicon) == [ICUSplitter, I18NNormalizer]

    def test_index_added(self, catalog):
        index = catalog.Indexes["SearchableText_icu"]
        assert index.meta_type == "ZCTextIndex"
        assert index.lexicon_id == "icu_lexicon"
        assert index.getIndexType() == "Okapi BM25 Rank"
        assert index.getIndexSourceNames() == ["SearchableText"]

    def test_plone_lexicon_and_searchable_text_unchanged(self, catalog):
        assert pipeline(catalog.plone_lexicon) == [Splitter, I18NNormalizer]
        index = catalog.Indexes["SearchableText"]
        assert index.lexicon_id == "plone_lexicon"

    def test_only_the_icu_lexicon_uses_icu(self, catalog):
        assert catalog.plone_lexicon.parseTerms("東京都庁") == ["東京", "京都", "都庁"]
        assert catalog.icu_lexicon.parseTerms("東京都庁") == ["東京", "都庁"]

    def test_apply_twice_keeps_the_objects_and_logs(self, catalog, setup_tool, caplog):
        lexicon = aq_base(catalog.icu_lexicon)
        index = aq_base(catalog.Indexes["SearchableText_icu"])
        with caplog.at_level(logging.INFO, logger=PACKAGE_NAME):
            setup_tool.runAllImportStepsFromProfile(EVALUATION)
        assert aq_base(catalog.icu_lexicon) is lexicon
        assert aq_base(catalog.Indexes["SearchableText_icu"]) is index
        assert [r.getMessage() for r in caplog.records] == [
            "icu_lexicon already exists in portal_catalog; skipped",
            "SearchableText_icu already exists in portal_catalog; skipped",
        ]

    def test_apply_twice_keeps_the_words(self, portal, catalog, setup_tool):
        setRoles(portal, TEST_USER_ID, ["Manager"])
        portal.invokeFactory("Document", "doc", title="電子カルテの導入")
        processQueue()
        words = catalog.icu_lexicon.length()
        assert words > 0
        setup_tool.runAllImportStepsFromProfile(EVALUATION)
        assert catalog.icu_lexicon.length() == words
        assert len(catalog(SearchableText_icu="電子 カルテ")) == 1

    def test_uninstall(self, catalog, setup_tool):
        setup_tool.runAllImportStepsFromProfile(EVALUATION_UNINSTALL)
        assert "icu_lexicon" not in catalog.objectIds()
        assert "SearchableText_icu" not in catalog.indexes()
        assert "plone_lexicon" in catalog.objectIds()
        assert "SearchableText" in catalog.indexes()

    def test_uninstall_twice(self, catalog, setup_tool):
        setup_tool.runAllImportStepsFromProfile(EVALUATION_UNINSTALL)
        setup_tool.runAllImportStepsFromProfile(EVALUATION_UNINSTALL)
        assert "icu_lexicon" not in catalog.objectIds()

    def test_uninstall_removes_the_index_before_the_lexicon(
        self, catalog, setup_tool, monkeypatch
    ):
        def broken(*args, **kwargs):
            raise RuntimeError("broken")

        monkeypatch.setattr(type(aq_base(catalog)), "manage_delObjects", broken)
        with pytest.raises(RuntimeError):
            setup_tool.runAllImportStepsFromProfile(EVALUATION_UNINSTALL)
        assert "SearchableText_icu" not in catalog.indexes()
        assert "icu_lexicon" in catalog.objectIds()

    def test_uninstall_keeps_a_lexicon_that_another_index_uses(
        self, catalog, setup_tool, caplog
    ):
        extra = SimpleNamespace(
            doc_attr="SearchableText",
            lexicon_id="icu_lexicon",
            index_type="Okapi BM25 Rank",
        )
        catalog.addIndex("adopted", "ZCTextIndex", extra)
        with caplog.at_level(logging.WARNING, logger=PACKAGE_NAME):
            setup_tool.runAllImportStepsFromProfile(EVALUATION_UNINSTALL)
        assert "SearchableText_icu" not in catalog.indexes()
        assert "icu_lexicon" in catalog.objectIds()
        assert [r.getMessage() for r in caplog.records] == [
            "icu_lexicon is kept: it is used by adopted"
        ]

    def test_install_again_after_uninstall(self, catalog, setup_tool):
        setup_tool.runAllImportStepsFromProfile(EVALUATION_UNINSTALL)
        setup_tool.runAllImportStepsFromProfile(EVALUATION)
        assert pipeline(catalog.icu_lexicon) == [ICUSplitter, I18NNormalizer]
        assert "SearchableText_icu" in catalog.indexes()


def test_uninstall_without_evaluation_changes_nothing(catalog, setup_tool):
    indexes = list(catalog.indexes())
    setup_tool.runAllImportStepsFromProfile(EVALUATION_UNINSTALL)
    assert list(catalog.indexes()) == indexes
