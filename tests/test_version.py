from version import APP_VERSION


def test_app_version_matches_v194_candidate() -> None:
    assert APP_VERSION == "v1.9.4"
