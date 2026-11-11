import prior_auth_agent


def test_package_exposes_version() -> None:
    assert prior_auth_agent.__version__ == "0.1.0"
