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

## Upgrading ICU

The words ICU finds depend on its version and its dictionaries. After
upgrading ICU (or rebuilding PyICU against a different ICU), reindex every
index that uses this splitter, so that the stored words and the words of new
searches come from the same rules.

## License

GPL version 2 or later. See `LICENSE.txt` and `LICENSE.GPL`.
