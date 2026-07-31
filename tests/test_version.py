from version import APP_VERSION


def test_app_version_matches_v195_candidate() -> None:
    assert APP_VERSION == "v1.9.5"
