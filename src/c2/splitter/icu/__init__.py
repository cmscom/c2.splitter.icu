"""A word splitter for Plone's ZCTextIndex based on ICU word boundaries."""

# Importing splitter registers the ICU word splitter with ZCTextIndex.
from c2.splitter.icu import splitter  # noqa: F401

from importlib.metadata import version

import logging


PACKAGE_NAME = "c2.splitter.icu"

# The version is kept only in pyproject.toml, where zest.releaser changes it.
__version__ = version(PACKAGE_NAME)

logger = logging.getLogger(PACKAGE_NAME)
