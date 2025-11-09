def test_uipath_dev_has_developer_console() -> None:
    from uipath.dev import UiPathDeveloperConsole

    assert UiPathDeveloperConsole is not None
