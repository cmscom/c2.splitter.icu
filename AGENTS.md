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
- `tests/`: pytest tests (not shipped in the wheel).
  - `test_imports.py`: the version, the namespaces and PyICU.

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
