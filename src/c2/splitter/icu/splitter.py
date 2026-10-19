"""A ZCTextIndex word splitter that splits text at ICU word boundaries.

Importing this module registers the splitter as "ICU word splitter" in the
"Word Splitter" group, like Products.CMFPlone's UnicodeSplitter does. When
PyICU is missing, the import fails; there is no fallback to another
splitter.
"""

from Products.ZCTextIndex.interfaces import ISplitter
from Products.ZCTextIndex.PipelineFactory import element_factory
from zope.interface import implementer

import contextlib
import icu
import logging
import unicodedata


logger = logging.getLogger("c2.splitter.icu")

SPLITTER_NAME = "ICU word splitter"

WILDCARDS = "*?"

# Rule statuses of the word break iterator: NONE (0-99) is spaces,
# punctuation, symbols and emoji. ICU only promises a status inside these
# ranges, so they are compared as ranges.
WORD_STATUS_MIN = icu.UWordBreak.NUMBER
WORD_STATUS_LIMIT = icu.UWordBreak.IDEO_LIMIT


def to_str(value):
    """Return ``value`` as str. bytes are read as UTF-8.

    Invalid UTF-8 is replaced with U+FFFD and logged without the text, so
    that indexing a document never fails here.
    """
    if isinstance(value, str):
        return value
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as error:
        logger.warning(
            "Could not decode %d bytes as UTF-8 (first invalid byte at "
            "position %d); invalid bytes were replaced with U+FFFD",
            len(value),
            error.start,
        )
        return value.decode("utf-8", "replace")


def _segments(text, locale):
    """Yield ``(segment, is_word)`` for the word break segments of ``text``.

    ICU positions are UTF-16 offsets, so the text is cut as an
    icu.UnicodeString and not with str indices.
    """
    ustring = icu.UnicodeString(text)
    breaker = icu.BreakIterator.createWordInstance(icu.Locale(locale))
    breaker.setText(ustring)
    start = breaker.first()
    for end in breaker:
        status = breaker.getRuleStatus()
        yield str(ustring[start:end]), WORD_STATUS_MIN <= status < WORD_STATUS_LIMIT
        start = end


def split_words(text, locale):
    """Return the words of ``text`` (already NFKC normalized)."""
    return [segment for segment, is_word in _segments(text, locale) if is_word]


def _is_pattern_char(char):
    """Letters, marks, digits, ``_`` and wildcards make a glob pattern."""
    return char in WILDCARDS or char == "_" or unicodedata.category(char)[0] in "LMN"


def _runs(text):
    """Split ``text`` into ``(run, has_wildcard)`` parts.

    A run of pattern characters that contains a wildcard is a glob pattern;
    everything else is plain text.
    """
    parts = []
    plain = []
    index = 0
    while index < len(text):
        end = index
        while end < len(text) and _is_pattern_char(text[end]):
            end += 1
        run = text[index:end]
        if any(char in WILDCARDS for char in run):
            parts.append(("".join(plain), False))
            plain = []
            parts.append((run, True))
        else:
            plain.append(run)
        if end < len(text):
            plain.append(text[end])
        index = end + 1
    parts.append(("".join(plain), False))
    return [(run, has_wildcard) for run, has_wildcard in parts if run]


def split_glob(pattern, locale):
    """Split a glob pattern and keep its wildcards on the last word only.

    ``東京都庁*`` gives ``東京`` and ``都庁*``, like the bigrams of the
    UnicodeSplitter. Several words become a phrase, which does not match
    patterns, so the wildcards of the other words are dropped. A wildcard
    between two words belongs to the word before it.
    """
    letters = ""
    wildcards = {}  # offset in ``letters`` -> the wildcards that stand there
    for char in pattern:
        if char in WILDCARDS:
            wildcards[len(letters)] = wildcards.get(len(letters), "") + char
        else:
            letters += char

    words = []  # (word, offset in ``letters``)
    offset = 0
    for segment, is_word in _segments(letters, locale):
        if is_word:
            words.append((segment, offset))
        offset += len(segment)
    if not words:
        return []

    last, start = words[-1]
    previous_end = words[-2][1] + len(words[-2][0]) if len(words) > 1 else None
    first = wildcards.get(start, "") if start != previous_end else ""
    rest = [wildcards.get(start + i, "") + char for i, char in enumerate(last) if i]
    end = wildcards.get(start + len(last), "")
    pattern_word = first + last[0] + "".join(rest) + end
    return [word for word, _ in words[:-1]] + [pattern_word]


@implementer(ISplitter)
class ICUSplitter:
    """Split text into words with ICU's word break rules.

    Instances are stored in the ZODB as part of a lexicon, so they hold no
    ICU object; the break iterator is made for every call.
    """

    locale = "ja"

    def process(self, lst):
        """Split the texts to index; also used for search terms by default."""
        result = []
        for value in lst:
            text = unicodedata.normalize("NFKC", to_str(value))
            result.extend(split_words(text, self.locale))
        return result

    def processGlob(self, lst):
        """Split search terms; ``*`` and ``?`` stay on the last word."""
        result = []
        for value in lst:
            text = unicodedata.normalize("NFKC", to_str(value))
            for run, has_wildcard in _runs(text):
                if has_wildcard:
                    result.extend(split_glob(run, self.locale))
                else:
                    result.extend(split_words(run, self.locale))
        return result

    def process_post_glob(self, lst):
        """Words of a phrase: remove the wildcards, but do not split again."""
        result = []
        for value in lst:
            word = unicodedata.normalize("NFKC", to_str(value))
            word = word.replace("*", "").replace("?", "")
            if word:
                result.append(word)
        return result


# ValueError: already registered, for example when the module is reloaded.
with contextlib.suppress(ValueError):
    element_factory.registerFactory("Word Splitter", SPLITTER_NAME, ICUSplitter)
