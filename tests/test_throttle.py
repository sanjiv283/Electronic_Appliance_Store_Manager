"""Login throttle unit tests (fake clock) and the proxy-address handling."""
import pytest

import app as app_module
import config
from services import users
from services.throttle import LoginThrottle


class Clock:
    now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def clock():
    return Clock()


def fail(t, name, ip, n=1):
    for _ in range(n):
        t.record_failure(name, ip)


def test_user_locked_after_five_failures_with_retry_after(clock):
    """5 failures for one user+address | blocked with the seconds until the oldest failure expires"""
    t = LoginThrottle(clock=clock)
    fail(t, "meera", "1.1.1.1", 4)
    assert t.retry_after("meera", "1.1.1.1") == 0
    clock.now += 10
    fail(t, "meera", "1.1.1.1")
    assert t.retry_after("meera", "1.1.1.1") == 290          # oldest failure was 10 s ago, window 300 s


def test_other_address_or_other_user_is_not_locked_out(clock):
    """Lockout is per user+address | the same user from another address, and another user at the same address, still sign in"""
    t = LoginThrottle(clock=clock)
    fail(t, "meera", "1.1.1.1", 5)
    assert t.retry_after("meera", "1.1.1.1") > 0
    assert t.retry_after("meera", "2.2.2.2") == 0 and t.retry_after("karan", "1.1.1.1") == 0


def test_one_address_spraying_many_usernames_is_blocked(clock):
    """20 failures from one address across different usernames | the address is blocked for every username"""
    t = LoginThrottle(clock=clock)
    for i in range(20):
        fail(t, f"user{i}", "9.9.9.9")
    assert t.retry_after("brand-new-user", "9.9.9.9") > 0 and t.retry_after("brand-new-user", "8.8.8.8") == 0


def test_lock_expires_and_success_clears_user_counter(clock):
    """After the window passes, or after a successful sign-in | the user may try again"""
    t = LoginThrottle(clock=clock)
    fail(t, "meera", "1.1.1.1", 5)
    clock.now += 301
    assert t.retry_after("meera", "1.1.1.1") == 0
    fail(t, "karan", "1.1.1.1", 5)
    t.clear("karan", "1.1.1.1")
    assert t.retry_after("karan", "1.1.1.1") == 0


def test_memory_is_bounded_and_expired_entries_are_dropped(clock):
    """Flood of random usernames | at most max_entries kept; entries older than the window are pruned"""
    t = LoginThrottle(max_entries=50, clock=clock)
    for i in range(500):
        fail(t, f"u{i}", f"10.0.{i % 250}.1")
    assert len(t._data) <= 50
    clock.now += 301
    fail(t, "later", "5.5.5.5")
    assert len(t._data) == 2                                  # only the fresh user+address and address keys remain


def make_app(**extra):
    return app_module.create_app({"SECRET_KEY": "k", "TESTING": True, **extra})


def post_login(client, ip_header=None):
    with client.session_transaction() as s:
        s["csrf"] = "tok"
    headers = {"X-Forwarded-For": ip_header} if ip_header else {}
    return client.post("/login", data={"username": "meera", "password": "bad", "csrf_token": "tok"}, headers=headers)


def test_429_response_carries_retry_after(monkeypatch):
    """6th failed sign-in | HTTP 429 with a Retry-After header and the friendly message"""
    monkeypatch.setattr(users, "authenticate", lambda u, p: None)
    c = make_app().test_client()
    for _ in range(5):
        assert post_login(c).status_code == 401
    resp = post_login(c)
    assert resp.status_code == 429 and int(resp.headers["Retry-After"]) > 0 and "Too many failed" in resp.get_data(as_text=True)


def test_forwarded_header_ignored_unless_proxy_is_trusted(monkeypatch):
    """X-Forwarded-For with TRUSTED_PROXIES=0 | spoofed addresses do not dodge the limit; with 1 hop the real client address is used"""
    monkeypatch.setattr(users, "authenticate", lambda u, p: None)
    c = make_app().test_client()                               # no proxy: header is ignored
    codes = [post_login(c, ip_header=f"7.7.7.{i}").status_code for i in range(6)]
    assert codes[-1] == 429
    c = make_app(TRUSTED_PROXIES=1).test_client()              # one proxy: each real client is separate
    for _ in range(5):
        post_login(c, ip_header="7.7.7.1")
    assert post_login(c, ip_header="7.7.7.1").status_code == 429
    assert post_login(c, ip_header="7.7.7.2").status_code == 401


@pytest.mark.parametrize("value,ok", [(None, 0), ("0", 0), ("1", 1), ("5", 5), ("6", None), ("-1", None), ("x", None)])
def test_trusted_proxies_setting_is_validated(value, ok):
    """TRUSTED_PROXIES env value | 0-5 accepted (default 0); anything else raises ConfigError"""
    env = {"FLASK_SECRET_KEY": "k" * 32, **({} if value is None else {"TRUSTED_PROXIES": value})}
    if ok is None:
        with pytest.raises(config.ConfigError, match="TRUSTED_PROXIES"):
            config.load_flask_config(env)
    else:
        assert config.load_flask_config(env)["TRUSTED_PROXIES"] == ok
