def test_version():
    from c2.splitter.icu import __version__

    assert __version__ == "1.0.0.dev0"


def test_c2_is_a_pep420_namespace():
    import c2
    import c2.splitter

    assert getattr(c2, "__file__", None) is None
    assert getattr(c2.splitter, "__file__", None) is None


def test_pyicu_is_importable():
    import icu

    assert icu.ICU_VERSION.split(".")[0].isdigit()
