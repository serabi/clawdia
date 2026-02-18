"""Shared test fixtures."""

import pytest


@pytest.fixture
def authorized_user_id():
    return 123456789


@pytest.fixture
def unauthorized_user_id():
    return 987654321
