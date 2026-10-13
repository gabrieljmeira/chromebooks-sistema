import secrets
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import pytest
import services as s
from database import connect, init_db, rows


def token():
    return secrets.token_urlsafe(32)


def ask(q=2, end="15:00", kind="now", start=None, key=None, name="Prof. Ana"):
    return s.request_loan(name, "203", str(q), end, kind, start, key or token())


def devices(*numbers):
    return [f"CH-{n:03}" for n in numbers]


def history():
    return s.get_history()["loans"]


def test_request_does_not_deliver():
    loan = ask()
    assert s.stock_count() == 20
    assert history()[0]["status"] == "pending"
    assert history()[0]["confirmed_at"] is None
    assert history()[0]["devices"] == []
    s.deliver_loan(loan, devices(7, 13), token())
    assert s.stock_count() == 18
    assert {d["code"] for d in history()[0]["devices"]} == set(devices(7, 13))
    assert history()[0]["confirmed_at"] == s.stamp()
    s.return_loan(loan, devices(13), token())
    assert s.stock_count() == 19
    assert history()[0]["status"] == "active"
    assert [d["code"] for d in history()[0]["outstanding"]] == devices(7)
    s.return_loan(loan, devices(7), token())
    assert s.stock_count() == 20
    assert history()[0]["status"] == "returned"
    assert len(s.get_history()["audit"]) == 4


def test_delivery_time_is_actual_not_requested(monkeypatch):
    loan = ask(kind="scheduled", start="11:00")
    moment = s.now() + timedelta(hours=1, minutes=4)
    monkeypatch.setattr(s, "now", lambda: moment)
    s.deliver_loan(loan, devices(2, 9), token())
    assert history()[0]["confirmed_at"] == s.stamp(moment)


@pytest.mark.parametrize("q", [0, 21, -1, "1.5", "01", "", None, True])
def test_invalid_quantity(q):
    with pytest.raises(s.ValidationError):
        ask(q=q)
    assert history() == []


@pytest.mark.parametrize(
    "end",
    [
        "",
        "xx",
        "24:00",
        "12:60",
        "1:2",
        "15000",
        "09:59",
        "10:00",
        "2026-10-14T15:00",
        None,
    ],
)
def test_invalid_end(end):
    with pytest.raises(s.ValidationError):
        ask(end=end)
    assert history() == []


@pytest.mark.parametrize(
    "start,end",
    [
        ("10:00", "11:00"),
        ("09:00", "12:00"),
        ("12:00", "12:00"),
        ("15:00", "14:00"),
        ("", "15:00"),
    ],
)
def test_invalid_schedule(start, end):
    with pytest.raises(s.ValidationError):
        ask(kind="scheduled", start=start, end=end)


def test_numeric_time_and_injection_safe():
    ask(end="1530", name="<script>alert(1)</script>")
    assert history()[0]["expected_return_at"].endswith("15:30:00-03:00")
    assert history()[0]["professor_name"] == "<script>alert(1)</script>"


@pytest.mark.parametrize(
    "start,end,allowed",
    [
        ("10:30", "11:00", True),
        ("12:00", "13:00", True),
        ("10:30", "11:01", False),
        ("11:59", "13:00", False),
        ("11:00", "12:00", False),
        ("10:30", "13:00", False),
    ],
)
def test_interval_boundaries(start, end, allowed):
    ask(15, "12:00", "scheduled", "11:00")
    if allowed:
        ask(6, end, "scheduled", start)
    else:
        with pytest.raises(s.ValidationError, match="intervalo"):
            ask(6, end, "scheduled", start)


def test_nonoverlapping_reservations_use_peak_not_sum():
    ask(12, "12:00", "scheduled", "11:00")
    ask(12, "14:00", "scheduled", "13:00")
    ask(8, "14:00", "scheduled", "10:30")
    with pytest.raises(s.ValidationError):
        ask(1, "13:30", "scheduled", "11:30")


def test_immediate_reserves_capacity_until_cancelled():
    first = ask(20)
    with pytest.raises(s.ValidationError):
        ask(1)
    assert s.stock_count() == 20
    s.cancel_loan(first, token())
    ask(20)
    assert {l["status"] for l in history()} == {"pending", "cancelled"}


def test_overdue_remains_unavailable_even_for_future_booking(monkeypatch):
    loan = ask(20, end="11:00")
    s.deliver_loan(loan, devices(*range(1, 21)), token())
    moment = s.now() + timedelta(hours=2)
    monkeypatch.setattr(s, "now", lambda: moment)
    with pytest.raises(s.ValidationError):
        ask(1, "16:00", "scheduled", "15:00")
    assert s.stock_count() == 0
    assert s.get_dashboard()["active"][0]["overdue"]
    s.return_loan(loan, devices(1), token())
    ask(1, "16:00", "scheduled", "15:00")


def test_future_reservation_does_not_assume_physical_return(monkeypatch):
    first = ask(20, "11:00")
    s.deliver_loan(first, devices(*range(1, 21)), token())
    second = ask(2, "12:00", "scheduled", "11:00")
    moment = s.now() + timedelta(hours=1)
    monkeypatch.setattr(s, "now", lambda: moment)
    with pytest.raises(s.ValidationError):
        s.deliver_loan(second, devices(1, 2), token())
    s.return_loan(first, devices(1, 2), token())
    s.deliver_loan(second, devices(1, 2), token())


def test_early_delivery_rechecks_interval():
    first = ask(20, "11:00")
    second = ask(20, "12:00", "scheduled", "11:00")
    with pytest.raises(s.ValidationError):
        s.deliver_loan(second, devices(*range(1, 21)), token())
    s.cancel_loan(first, token())
    s.deliver_loan(second, devices(*range(1, 21)), token())


@pytest.mark.parametrize(
    "selected",
    [
        [],
        ["CH-001"],
        ["CH-001", "CH-001"],
        ["CH-000", "CH-002"],
        ["CH-021", "CH-002"],
        ["1", "2"],
        [1, 2],
        None,
    ],
)
def test_invalid_delivery_selection(selected):
    loan = ask()
    with pytest.raises(s.ValidationError):
        s.deliver_loan(loan, selected, token())
    assert history()[0]["status"] == "pending"
    assert s.stock_count() == 20


def test_returns_require_exact_outstanding_codes():
    loan = ask()
    s.deliver_loan(loan, devices(9, 10), token())
    for selected in (devices(1), devices(9, 1), devices(9, 9), []):
        with pytest.raises(s.ValidationError):
            s.return_loan(loan, selected, token())
    s.return_loan(loan, devices(9), token())
    with pytest.raises(s.ValidationError):
        s.return_loan(loan, devices(9), token())
    assert s.stock_count() == 19


def test_unavailable_device_rejected():
    a = ask()
    b = ask()
    s.deliver_loan(a, devices(1, 2), token())
    with pytest.raises(s.ValidationError):
        s.deliver_loan(b, devices(2, 3), token())
    assert s.stock_count() == 18


def test_duplicate_submission_is_idempotent(monkeypatch):
    key = token()
    first = ask(key=key)
    moment = s.now() + timedelta(minutes=1)
    monkeypatch.setattr(s, "now", lambda: moment)
    assert ask(key=key) == first
    assert len(history()) == 1
    with pytest.raises(s.ValidationError):
        ask(q=3, key=key)


@pytest.mark.parametrize("action", ["delivery", "return", "cancel"])
def test_actions_are_idempotent(action):
    loan = ask()
    key = token()
    if action == "delivery":
        fn = lambda: s.deliver_loan(loan, devices(2, 3), key)
    elif action == "cancel":
        fn = lambda: s.cancel_loan(loan, key)
    else:
        s.deliver_loan(loan, devices(2, 3), token())
        fn = lambda: s.return_loan(loan, devices(2), key)
    fn()
    before = s.get_history()["audit"]
    fn()
    assert s.get_history()["audit"] == before


def test_same_token_cannot_change_action():
    key = token()
    loan = ask(key=key)
    with pytest.raises(s.ValidationError):
        s.cancel_loan(loan, key)


def test_cancel_and_expired_delivery(monkeypatch):
    loan = ask(end="11:00")
    moment = s.now() + timedelta(hours=2)
    monkeypatch.setattr(s, "now", lambda: moment)
    with pytest.raises(s.ValidationError):
        s.deliver_loan(loan, devices(1, 2), token())
    s.cancel_loan(loan, token())
    with pytest.raises(s.ValidationError):
        s.deliver_loan(loan, devices(1, 2), token())


def test_cannot_cancel_active_or_return_pending():
    loan = ask()
    with pytest.raises(s.ValidationError):
        s.return_loan(loan, devices(1), token())
    s.deliver_loan(loan, devices(1, 2), token())
    with pytest.raises(s.ValidationError):
        s.cancel_loan(loan, token())


def concurrent(function, args):
    def attempt(arg):
        try:
            function(arg)
            return True
        except s.ValidationError:
            return False

    with ThreadPoolExecutor(max_workers=2) as ex:
        return sorted(ex.map(attempt, args))


def test_concurrent_reservations():
    assert concurrent(lambda _: ask(12), range(2)) == [False, True]
    assert len(history()) == 1


def test_concurrent_same_request():
    key = token()
    assert concurrent(lambda _: ask(key=key), range(2)) == [True, True]
    assert len(history()) == 1


def test_concurrent_delivery_same_device():
    a = ask(1)
    b = ask(1)
    assert concurrent(
        lambda loan: s.deliver_loan(loan, devices(7), token()), [a, b]
    ) == [False, True]
    assert s.stock_count() == 19


def test_concurrent_returns():
    loan = ask()
    s.deliver_loan(loan, devices(1, 2), token())
    assert concurrent(lambda _: s.return_loan(loan, devices(1), token()), range(2)) == [
        False,
        True,
    ]
    assert s.stock_count() == 19


def test_delivery_rolls_back_after_partial_failure():
    loan = ask()
    db = connect()
    db.execute(
        "CREATE TRIGGER fail BEFORE INSERT ON allocations WHEN NEW.device_id=2 BEGIN SELECT RAISE(ABORT,'failure'); END"
    )
    db.close()
    with pytest.raises(sqlite3.IntegrityError):
        s.deliver_loan(loan, devices(1, 2), token())
    assert s.stock_count() == 20 and history()[0]["status"] == "pending"
    assert len(s.get_history()["audit"]) == 1


def test_database_rejects_duplicate_outstanding_device():
    a = ask(1)
    b = ask(1)
    s.deliver_loan(a, devices(1), token())
    db = connect()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(
                "INSERT INTO allocations(loan_id,device_id,delivered_at) VALUES (?,?,?)",
                (b, 1, s.stamp()),
            )
    finally:
        db.close()


def test_initialization_preserves_state():
    loan = ask()
    s.deliver_loan(loan, devices(5, 6), token())
    s.return_loan(loan, devices(6), token())
    before = s.get_history()
    init_db()
    init_db()
    assert s.get_history() == before


def test_login_rate_limit_persists_and_expires(monkeypatch):
    import time

    monkeypatch.setattr(time, "time", lambda: 1000)
    assert s.rate_limit("test", 2, 60)
    assert s.rate_limit("test", 2, 60)
    assert not s.rate_limit("test", 2, 60)
    monkeypatch.setattr(time, "time", lambda: 1061)
    assert s.rate_limit("test", 2, 60)


def test_concurrent_cancel_and_delivery_are_exclusive():
    loan = ask(1)
    actions = [
        lambda: s.cancel_loan(loan, token()),
        lambda: s.deliver_loan(loan, devices(1), token()),
    ]
    assert concurrent(lambda fn: fn(), actions) == [False, True]
    row = history()[0]
    assert row["status"] in ("cancelled", "active")
    assert s.stock_count() == (19 if row["status"] == "active" else 20)


def test_concurrent_same_delivery_token_has_one_audit_event():
    loan = ask(1)
    key = token()
    assert concurrent(lambda _: s.deliver_loan(loan, devices(1), key), range(2)) == [
        True,
        True,
    ]
    assert len([a for a in s.get_history()["audit"] if a["action"] == "entrega"]) == 1


def test_pending_is_excluded_from_return_alerts_after_due(monkeypatch):
    ask(end="11:00")
    moment = s.now() + timedelta(hours=2)
    monkeypatch.setattr(s, "now", lambda: moment)
    assert s.get_dashboard()["active"] == []
    assert not s.get_dashboard()["pending"][0]["overdue"]
