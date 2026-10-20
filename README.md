# c2.splitter.icu

A word splitter for Plone's ZCTextIndex based on ICU word boundaries.

Plone's default splitter cuts Chinese and Japanese text into overlapping
pairs of characters (bigrams). This package splits it into words with the
word break rules of [ICU](https://icu.unicode.org/), through
[PyICU](https://pypi.org/project/PyICU/), so that a search does not match
character pairs inside unrelated words.

## Supported versions

- Plone 6.0, 6.1 and 6.2
- Python 3.10 to 3.14 (as far as each Plone version supports them)
- PyICU 2.16 or later

## Installation

PyICU is published as source only, so installing it builds it against the
ICU library of the system. The build needs the ICU development files,
`pkg-config` and a C++ compiler.

On Debian and Ubuntu:

```shell
sudo apt-get install libicu-dev pkg-config g++
```

At run time only the ICU shared library is needed (`libicu76` on
Debian 13, `libicu74` on Ubuntu 24.04), so a multi-stage image can leave
the development files out of the final stage.

On macOS with Homebrew (and the Xcode command line tools for the compiler):

```shell
brew install icu4c pkg-config
export PKG_CONFIG_PATH="$(brew --prefix icu4c)/lib/pkgconfig"
```

Then add `c2.splitter.icu` to your project's dependencies, for example with
pip:

```shell
pip install c2.splitter.icu
```

Restart Zope and activate **c2.splitter.icu** in the add-ons control panel
(or apply the `c2.splitter.icu:default` profile). The package registers a
ZCTextIndex word splitter named **ICU word splitter** when it is imported;
activating it does not change the catalog, and neither does deactivating
it.

## How text is split

The splitter normalizes the text with NFKC and keeps the words that ICU's
word break iterator finds: numbers, letters, kana and ideographs. Spaces,
punctuation, symbols and emoji are dropped. For example, with ICU 74 and 76:

| Text | Words |
| --- | --- |
| `東京都庁に行く` | `東京` `都庁` `に` `行く` |
| `大阪府立図書館` | `大阪` `府立` `図書館` |
| `ChatGPTとPython3.14で開発` | `ChatGPT` `と` `Python3.14` `で` `開発` |
| `ﾊﾟｲｿﾝ` (half-width) | `パイ` `ソン` |

The bigram splitter stores `東京` `京都` `都庁` `庁` for `東京都庁`, so a
search for `京都` (Kyoto) finds it. With this splitter it does not. The
other side of it: a search for `東京都` does not find `東京都庁` either,
because `都` and `都庁` are different words, and `14` does not find
`Python3.14`. Evaluate with the words your users search for before you
switch.

### Locale

The splitter takes its ICU locale from the language of the Plone site
(`plone.default_language`) when it is made, that is when its lexicon is
made, for example by the evaluation profile. Plone's codes such as `en-us`
become ICU locales such as `en_US`. Without a site, or with a language that
ICU does not know, the locale is `ja`.

The locale stays with the lexicon: changing the site language later does
not change it, so that the words in the index and the words of a search are
split by the same rules. `@@icu-compare` shows the locale of `icu_lexicon`.
To use another locale, make the lexicon again (for example: apply
`c2.splitter.icu:evaluation-uninstall`, change the site language, apply
`c2.splitter.icu:evaluation`) and reindex the indexes that use it.

ICU uses its dictionary for Chinese and Japanese text with any locale, so
the locale does not change those words. It changes a few rules for other
text: with `fi` or `sv`, `a:b` is one word, with `ja` or `en` it is two.

Text is processed as `str`. `bytes` are read as UTF-8; invalid UTF-8 is
replaced with U+FFFD and logged as a warning (with the length and the
position, not the text), so that indexing never fails.

### Searching

Plone's search adds `*` to the search terms, so every term matches words
that start with it: in Plone 6.2 every term gets a `*`, in Plone 6.0 and
6.1 only the last one. It also removes `*` and `?` that the user typed.

A term that ICU splits into several words, such as `東京都庁*`, becomes
`東京` `都庁*`. ZCTextIndex searches several words as a phrase and does
not use the `*` there, so `東京都庁` finds the words `東京` `都庁` next to
each other, as the bigram splitter does. A single word keeps its
wildcards (`Python*`, `te?t`). A search term is split like the text, so a
word with `.`, `,`, `'` or `:` inside, such as `Python3.14`, `10,000` or
`example.com`, stays one word and `Python3.14*` finds it. Quotes, `AND`, `OR` and `NOT` are handled
by ZCTextIndex's query parser.

### Using the splitter in a lexicon

Put **ICU word splitter** first and **Unicode Ignoring Accents Case
Normalizer** after it, as in Plone's `plone_lexicon`. Do not use **Unicode
Case Normalizer**: it stores the words as UTF-8 `bytes`, and searches with
`*` or `?` stop working.

## Comparing with the bigram index

The optional `c2.splitter.icu:evaluation` profile adds a second index next
to `SearchableText` and changes nothing else:

- `icu_lexicon`: a ZCTextIndex lexicon with ICU word splitter and Unicode
  Ignoring Accents Case Normalizer.
- `SearchableText_icu`: a ZCTextIndex (Okapi BM25 Rank) on the same
  `SearchableText` text, using `icu_lexicon`.

1. Apply the profile in the ZMI: `portal_setup`, **Import** tab, select
   **c2.splitter.icu: Evaluation index** and **Import all steps**. Applying
   it again does not change the existing lexicon or index.
2. Reindex `SearchableText_icu`. The profile does not index anything,
   because that can take long on a large site. In the ZMI: `portal_catalog`,
   **Indexes** tab, select `SearchableText_icu` and **Reindex**. Or in a
   script that has the Zope `app` (for example with `zconsole run`):

   ```python
   from zope.component.hooks import setSite

   import transaction

   portal = app["Plone"]  # the id of your site
   setSite(portal)
   portal.portal_catalog.reindexIndex("SearchableText_icu", None)
   transaction.commit()
   ```

   New and changed content is indexed in both indexes from then on.
3. As a Manager, open `@@icu-compare` on the site root, for example
   `https://example.org/Plone/@@icu-compare?q=京都`. It shows the query
   after Plone's processing, the words each lexicon makes of it, and the
   number and the first 20 results of both indexes, marking the results
   that only one of them finds.

To remove the evaluation index, apply the
`c2.splitter.icu:evaluation-uninstall` profile in `portal_setup`. It
removes `SearchableText_icu`, then `icu_lexicon`; the lexicon is kept
(with a warning in the log) while another index uses it. Deactivating the
add-on does not remove them. Remove them, or switch `SearchableText` back,
before you remove the package: the lexicon stores the splitter, and loading
it needs this package.

## Switching SearchableText to ICU

This package does not switch Plone's search for you. To do it, replace the
`SearchableText` index with one that uses `icu_lexicon`, and reindex it.
In a script, as above:

```python
from types import SimpleNamespace

catalog = portal.portal_catalog
catalog.delIndex("SearchableText")
extra = SimpleNamespace(
    doc_attr="SearchableText",
    lexicon_id="icu_lexicon",
    index_type="Okapi BM25 Rank",
)
catalog.addIndex("SearchableText", "ZCTextIndex", extra)
catalog.reindexIndex("SearchableText", None)
transaction.commit()
```

- Do not change the pipeline of `plone_lexicon` instead: the `Title` and
  `Description` indexes use it as well, and its words would no longer match
  the ones in those indexes.
- Reindex the whole index. Words of the bigram splitter and of ICU must not
  be mixed in one index.
- To roll back, do the same with `lexicon_id="plone_lexicon"` and reindex
  `SearchableText` again.

## Upgrading ICU

The words ICU finds depend on its version and its dictionaries. After
upgrading ICU (or rebuilding PyICU against a different ICU), reindex every
index that uses this splitter, so that the stored words and the words of new
searches come from the same rules.

## License

GPL version 2 or later. See `LICENSE.txt` and `LICENSE.GPL`.
