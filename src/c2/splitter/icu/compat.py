"""Names that moved between Plone versions."""

try:
    # Plone 6.2: adds "*" to every unquoted term.
    from plone.base.utils import munge_search_term
except ImportError:
    # Plone 6.0 and 6.1: adds "*" once, at the end of the query.
    from Products.CMFPlone.browser.search import munge_search_term


__all__ = ["munge_search_term"]
