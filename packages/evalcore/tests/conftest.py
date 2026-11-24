import pytest

from evalcore.models import Case


@pytest.fixture
def case() -> Case:
    return Case(id="c1", title="t", category="c", description="d", input="hi")
