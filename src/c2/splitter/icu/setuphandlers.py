"""Add and remove the evaluation lexicon and index.

The lexicon is made here and not in catalog.xml: GenericSetup's lexicon
importer compares the new pipeline elements with the stored ones, finds them
always different (the elements have no ``__eq__``) and clears the words, so
applying the profile again would empty the lexicon.
"""

from c2.splitter.icu import logger
from c2.splitter.icu.splitter import SPLITTER_NAME
from plone.base.interfaces import INonInstallable
from Products.CMFCore.utils import getToolByName
from Products.ZCTextIndex.PipelineFactory import element_factory
from Products.ZCTextIndex.ZCTextIndex import PLexicon
from types import SimpleNamespace
from typing import Any
from zope.interface import implementer


LEXICON_ID = "icu_lexicon"
INDEX_ID = "SearchableText_icu"

# The same normalizer as plone_lexicon, so that only the splitter differs.
# "Unicode Case Normalizer" would store bytes and break glob searches.
PIPELINE = (
    ("Word Splitter", SPLITTER_NAME),
    ("Case Normalizer", "Unicode Ignoring Accents Case Normalizer"),
)


@implementer(INonInstallable)
class HiddenProfiles:
    def getNonInstallableProfiles(self) -> list[str]:
        """Hide the uninstall profiles from site creation and the add-ons list."""
        return [
            "c2.splitter.icu:uninstall",
            "c2.splitter.icu:evaluation-uninstall",
        ]


def add_evaluation_index(context: Any) -> None:
    """Add icu_lexicon and SearchableText_icu unless they exist.

    ``context`` is the setup tool. Nothing is indexed here; reindex
    SearchableText_icu afterwards.
    """
    catalog = getToolByName(context, "portal_catalog")
    if LEXICON_ID in catalog.objectIds():
        logger.info("%s already exists in portal_catalog; skipped", LEXICON_ID)
    else:
        elements = [element_factory.instantiate(*element) for element in PIPELINE]
        catalog._setObject(LEXICON_ID, PLexicon(LEXICON_ID, "", *elements))
        logger.info("%s added to portal_catalog", LEXICON_ID)

    if INDEX_ID in catalog.indexes():
        logger.info("%s already exists in portal_catalog; skipped", INDEX_ID)
        return
    extra = SimpleNamespace(
        doc_attr="SearchableText",
        lexicon_id=LEXICON_ID,
        index_type="Okapi BM25 Rank",
    )
    catalog.addIndex(INDEX_ID, "ZCTextIndex", extra)
    logger.info("%s added to portal_catalog; reindex it to fill it", INDEX_ID)


def remove_evaluation_index(context: Any) -> None:
    """Remove SearchableText_icu, then icu_lexicon.

    The index goes first, so that a failure never leaves an index without
    its lexicon. The lexicon stays while another index uses it, for example
    after SearchableText was switched to it.
    """
    catalog = getToolByName(context, "portal_catalog")
    if INDEX_ID in catalog.indexes():
        catalog.delIndex(INDEX_ID)
        logger.info("%s removed from portal_catalog", INDEX_ID)
    if LEXICON_ID not in catalog.objectIds():
        return
    users = [
        index.getId()
        for index in catalog.Indexes.objectValues()
        if getattr(index, "lexicon_id", None) == LEXICON_ID
    ]
    if users:
        logger.warning("%s is kept: it is used by %s", LEXICON_ID, ", ".join(users))
        return
    catalog.manage_delObjects([LEXICON_ID])
    logger.info("%s removed from portal_catalog", LEXICON_ID)
