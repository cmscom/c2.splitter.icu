# Notes for contributors and coding agents

## Rules

- This is a public package. Write code, comments, documentation, commit
  messages and pull requests in English.
- Do not add design documents, specs or plans to the repository.
- Record user-facing changes as towncrier fragments in `news/`
  (`news/+<name>.<type>` or `news/<issue>.<type>`, types as in
  `pyproject.toml`), not in `CHANGELOG.md`.

## Layout

- `src/c2/splitter/icu/`: the package. `c2` and `c2.splitter` are PEP 420
  namespace packages, so they have no `__init__.py`.
  - `splitter.py`: `ICUSplitter`; importing it registers "ICU word
    splitter" with ZCTextIndex (the package's `__init__` imports it).
  - `setuphandlers.py`: the evaluation profiles (`icu_lexicon` and
    `SearchableText_icu`), made in code and not in `catalog.xml`, because
    GenericSetup's lexicon importer clears the words on every import.
  - `browser/compare.py`: `@@icu-compare`.
  - `compat.py`: `munge_search_term` for Plone 6.0-6.2.
- `tests/`: pytest tests (not shipped in the wheel).
  - `test_splitter.py`: unit tests of the splitter, no Plone site.
  - `test_setup.py`, `test_search.py`, `test_compare.py`: integration
    tests in a Plone site.

## Development

PyICU is built from source when the test environments are created, so the
ICU development files, `pkg-config` and a C++ compiler must be installed
(see `README.md`).

Run the tests and the linters with tox:

```shell
tox -e py314-Plone62      # one Python and Plone version
tox -e ruff-check         # lint and format check
tox -e ruff-fix           # fix and format
tox                       # the whole matrix
```

Extra arguments go to pytest, for example
`tox -e py314-Plone62 -- tests/test_imports.py`.

Write expected values in tests as literals.

### Words that depend on the ICU version

The words ICU finds in Japanese text come from its dictionary and can change
with the ICU version. `tests/test_splitter.py` keeps them per ICU major
version in `EXPECTED_WORDS` and `EXPECTED_GLOBS` (74 for the ubuntu-24.04
runner, 76 for Debian 13). With another ICU the tests fail and say so. To add
a version, run the splitter on each input with that ICU, add a column with
the words it returns, and look at every difference before you accept it.
Tests that do not depend on the ICU version (types, positions, wildcards,
pickling, registration) must not use these tables.

### Building PyICU without system packages

CI installs `libicu-dev`, `pkg-config` and `g++` with apt and needs nothing
of this. Without root access on Debian or Ubuntu, the build can still be
pointed at unpacked packages:

- ICU headers: `apt-get download libicu-dev` and unpack it with
  `dpkg-deb -x` into a directory of your own. Set `prefix` in its
  `icu-*.pc` files to the unpacked `usr` directory, point the unversioned
  `libicu*.so` links in it to the system's `libicu*.so.<major>`, and export
  `PKG_CONFIG_PATH` to its `pkgconfig` directory. The runtime library of
  the same version must be installed.
- Python headers for a system Python without the `-dev` package: unpack
  `libpython3.X-dev` the same way and export
  `CPPFLAGS="-I<dir>/usr/include/python3.X -I<dir>/usr/include"`.
- Pythons from uv or other standalone builds may name `clang++` as the
  C++ compiler; export `CXX=g++` if clang is not installed.

tox passes `PKG_CONFIG_PATH`, `CC`, `CXX` and `CPPFLAGS` to the build by
default.
