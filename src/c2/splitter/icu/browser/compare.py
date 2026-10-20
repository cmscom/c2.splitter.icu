"""@@icu-compare: search SearchableText and SearchableText_icu side by side.

A page for managers who evaluate the ICU splitter. It only reads the
catalog. It is in English and not translated.
"""

from c2.splitter.icu.compat import munge_search_term
from c2.splitter.icu.setuphandlers import INDEX_ID
from c2.splitter.icu.setuphandlers import LEXICON_ID
from plone.base.utils import safe_text
from Products.CMFCore.utils import getToolByName
from Products.Five.browser import BrowserView
from Products.ZCTextIndex.ParseTree import ParseError
from Products.ZCTextIndex.ParseTree import QueryError
from Products.ZCTextIndex.ZCTextIndex import PLexicon
from typing import Any


NGRAM_INDEX = "SearchableText"
MAX_ROWS = 20


class CompareView(BrowserView):
    @property
    def catalog(self) -> Any:
        return getToolByName(self.context, "portal_catalog")

    @property
    def query(self) -> str:
        query = self.request.form.get("q", "")
        if isinstance(query, list):
            # ?q=a&q=b
            query = query[0] if query else ""
        return safe_text(query).strip()

    @property
    def munged(self) -> str:
        return munge_search_term(self.query)

    @property
    def icu_available(self) -> bool:
        catalog = self.catalog
        return INDEX_ID in catalog.indexes() and LEXICON_ID in catalog.objectIds()

    @property
    def indexes(self) -> list[str]:
        return [NGRAM_INDEX, INDEX_ID] if self.icu_available else [NGRAM_INDEX]

    def _lexicon(self, index: str) -> PLexicon:
        return getattr(self.catalog, self.catalog.Indexes[index].lexicon_id)

    def search_terms(self) -> dict[str, list[str]]:
        """The words each lexicon looks up for the munged query."""
        munged = self.munged
        return {
            index: self._lexicon(index).parseTerms(munged) for index in self.indexes
        }

    def index_words(self) -> dict[str, list[str]]:
        """The words each lexicon would store for the query as text."""
        words = {}
        for index in self.indexes:
            last = [self.query]
            for element in self._lexicon(index)._pipeline:
                last = element.process(last)
            words[index] = last
        return words

    def _paths(self, index: str) -> list[str]:
        try:
            return [brain.getPath() for brain in self.catalog(**{index: self.munged})]
        except (ParseError, QueryError):
            return []

    def results(self, index: str) -> dict[str, Any]:
        """Count, top rows and query error of ``index``."""
        try:
            brains = self.catalog(**{index: self.munged})
        except (ParseError, QueryError) as error:
            return {"count": 0, "rows": [], "error": str(error)}
        others = set()
        for other in self.indexes:
            if other != index:
                others.update(self._paths(other))
        rows = [
            {
                "title": brain.Title,
                "path": brain.getPath(),
                "url": brain.getURL(),
                "only_here": brain.getPath() not in others,
            }
            for brain in brains[:MAX_ROWS]
        ]
        return {"count": len(brains), "rows": rows, "error": None}
