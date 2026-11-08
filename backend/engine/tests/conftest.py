import pytest

from absorb_engine import load_reference_data


@pytest.fixture(scope="session")
def ref():
    return load_reference_data()
