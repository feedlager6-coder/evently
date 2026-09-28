import time
import pytest
from app.services.auth_service import parse_and_validate_init_data, get_or_create_user, AuthenticationError
from tests.conftest import make_test_init_data


def test_valid_init_data():
    raw_data = make_test_init_data(user_id=555666777, username="alex", first_name="Alex")
    parsed = parse_and_validate_init_data(raw_data)
    assert parsed.user.id == 555666777
    assert parsed.user.username == "alex"
    assert parsed.user.first_name == "Alex"
    assert parsed.hash is not None


def test_tampered_hash_fails():
    raw_data = make_test_init_data(tamper_hash=True)
    with pytest.raises(AuthenticationError, match="Invalid initData cryptographic signature"):
        parse_and_validate_init_data(raw_data)


def test_modified_user_fails():
    raw_data = make_test_init_data(alter_user_after_hash=True)
    with pytest.raises(AuthenticationError, match="Invalid initData cryptographic signature"):
        parse_and_validate_init_data(raw_data)


def test_malformed_data_fails():
    with pytest.raises(AuthenticationError):
        parse_and_validate_init_data("not_a_valid_init_data_string_at_all")

    with pytest.raises(AuthenticationError):
        parse_and_validate_init_data("")


def test_expired_auth_date_fails():
    old_timestamp = int(time.time()) - 90000  # More than 86400 seconds ago
    raw_data = make_test_init_data(auth_date=old_timestamp)
    with pytest.raises(AuthenticationError, match="initData signature has expired"):
        parse_and_validate_init_data(raw_data)


@pytest.mark.asyncio
async def test_get_or_create_user(test_session):
    raw_data = make_test_init_data(user_id=888999000, username="newbie", first_name="John", last_name="Doe")
    parsed = parse_and_validate_init_data(raw_data)

    # First call: creates user
    user1 = await get_or_create_user(test_session, parsed.user)
    assert user1.id is not None
    assert user1.telegram_id == 888999000
    assert user1.username == "newbie"

    # Second call with updated first_name: updates user
    parsed.user.first_name = "Johnny"
    user2 = await get_or_create_user(test_session, parsed.user)
    assert user2.id == user1.id
    assert user2.first_name == "Johnny"
