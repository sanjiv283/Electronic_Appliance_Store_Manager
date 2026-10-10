"""Environment-based configuration. Error messages name variables, never values."""
import os
from dataclasses import dataclass, field

FORBIDDEN_USERS = {"SYS", "SYSTEM", "SYSDBA", "SYSOPER"}
REQUIRED_DB_VARS = ("DB_HOST", "DB_PORT", "DB_SERVICE_NAME", "DB_USER", "DB_PASSWORD")


class ConfigError(Exception):
    """Configuration is missing or unsafe. The message is safe to show to users."""


def _missing(env, names):
    # A value still in "<placeholder>" form (copied from .env.example) counts as missing.
    return [n for n in names if not (env.get(n) or "").strip() or env[n].strip().startswith("<")]


@dataclass(frozen=True)
class DbSettings:
    host: str
    port: int
    service_name: str
    user: str
    password: str = field(repr=False)

    @property
    def dsn(self):
        return f"{self.host}:{self.port}/{self.service_name}"


def load_db_settings(env=None):
    env = os.environ if env is None else env
    missing = _missing(env, REQUIRED_DB_VARS)
    if missing:
        raise ConfigError("Missing database configuration: " + ", ".join(missing)
                          + ". Copy .env.example to .env and fill in the values.")
    try:
        port = int(env["DB_PORT"])
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        raise ConfigError("DB_PORT must be a number between 1 and 65535.") from None
    user = env["DB_USER"].strip()
    if user.upper() in FORBIDDEN_USERS:
        raise ConfigError("DB_USER must be the least-privilege application account, not an administrator.")
    return DbSettings(env["DB_HOST"].strip(), port, env["DB_SERVICE_NAME"].strip(), user, env["DB_PASSWORD"])


def load_flask_config(env=None):
    env = os.environ if env is None else env
    if _missing(env, ("FLASK_SECRET_KEY",)):
        raise ConfigError("Missing FLASK_SECRET_KEY. Generate one with: "
                          'python -c "import secrets; print(secrets.token_hex(32))" and put it in .env.')
    production = env.get("APP_ENV", "development").lower() == "production"
    return {
        "SECRET_KEY": env["FLASK_SECRET_KEY"],
        "SESSION_COOKIE_HTTPONLY": True,
        "SESSION_COOKIE_SAMESITE": "Lax",
        "SESSION_COOKIE_SECURE": production,   # needs HTTPS; off for local http://127.0.0.1
        "DEBUG": (not production) and env.get("FLASK_DEBUG") == "1",
        "APP_ENV": "production" if production else "development",
    }
