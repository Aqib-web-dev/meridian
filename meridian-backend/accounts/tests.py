import pytest
from django.contrib.auth import get_user_model


pytestmark = pytest.mark.django_db


def test_project_uses_custom_user_model():
    """Django should use accounts.User as the configured user model."""
    user = get_user_model().objects.create_user(username="sara", password="testpass123")

    assert user._meta.label == "accounts.User"
    assert user.check_password("testpass123")
