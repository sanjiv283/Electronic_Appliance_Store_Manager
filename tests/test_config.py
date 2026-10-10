import pytest

import config

GOOD = {"DB_HOST": "localhost", "DB_PORT": "1521", "DB_SERVICE_NAME": "XEPDB1",
        "DB_USER": "appliance_app", "DB_PASSWORD": "not-a-real-secret-123"}


def test_valid_settings_build_dsn():
    """Valid DB_* variables produce settings and the XEPDB1 DSN | host:port/service DSN, no error"""
    assert config.load_db_settings(GOOD).dsn == "localhost:1521/XEPDB1"


def test_missing_variables_named_without_values():
    """Missing DB_PASSWORD and DB_HOST are reported by NAME only | ConfigError lists names, leaks no value"""
    env = {**GOOD, "DB_PASSWORD": "", "DB_HOST": "   "}
    with pytest.raises(config.ConfigError) as err:
        config.load_db_settings(env)
    assert "DB_PASSWORD" in str(err.value) and "DB_HOST" in str(err.value)
    assert GOOD["DB_SERVICE_NAME"] not in str(err.value)


def test_placeholder_values_count_as_missing():
    """Values copied unchanged from .env.example (<set-locally>) | treated as missing configuration"""
    with pytest.raises(config.ConfigError, match="DB_PASSWORD"):
        config.load_db_settings({**GOOD, "DB_PASSWORD": "<set-locally>"})


@pytest.mark.parametrize("user", ["SYS", "system", "SYSDBA"])
def test_administrator_accounts_rejected(user):
    """DB_USER set to an administrator account | ConfigError (app must use appliance_app only)"""
    with pytest.raises(config.ConfigError, match="administrator"):
        config.load_db_settings({**GOOD, "DB_USER": user})


@pytest.mark.parametrize("port", ["abc", "0", "70000"])
def test_invalid_port_rejected(port):
    """Non-numeric or out-of-range DB_PORT | ConfigError"""
    with pytest.raises(config.ConfigError, match="DB_PORT"):
        config.load_db_settings({**GOOD, "DB_PORT": port})


def test_password_never_in_repr():
    """repr() of the settings object | does not contain the password"""
    assert GOOD["DB_PASSWORD"] not in repr(config.load_db_settings(GOOD))


def test_flask_secret_required():
    """FLASK_SECRET_KEY missing or placeholder | ConfigError with generation hint"""
    with pytest.raises(config.ConfigError, match="FLASK_SECRET_KEY"):
        config.load_flask_config({"FLASK_SECRET_KEY": "<set-locally>"})


def test_production_flask_config_is_hardened():
    """APP_ENV=production | secure cookies on, debug off even if FLASK_DEBUG=1"""
    cfg = config.load_flask_config({"FLASK_SECRET_KEY": "k" * 32, "APP_ENV": "production", "FLASK_DEBUG": "1"})
    assert cfg["SESSION_COOKIE_SECURE"] is True and cfg["DEBUG"] is False
    assert cfg["SESSION_COOKIE_HTTPONLY"] is True and cfg["SESSION_COOKIE_SAMESITE"] == "Lax"
