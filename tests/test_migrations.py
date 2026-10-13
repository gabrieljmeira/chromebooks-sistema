import secrets
import sqlite3
import pytest
from database import init_db, connect, rows
import services as s


@pytest.fixture
def legacy(monkeypatch, tmp_path):
    path = tmp_path / "legacy.db"
    monkeypatch.setenv("LOCAL_DB_PATH", str(path))
    db = sqlite3.connect(path)
    db.executescript(
        """CREATE TABLE devices(id INTEGER PRIMARY KEY,code TEXT NOT NULL UNIQUE);
    CREATE TABLE loans(id INTEGER PRIMARY KEY,professor_name TEXT NOT NULL,room TEXT NOT NULL,
      quantity INTEGER NOT NULL,requested_at TEXT NOT NULL,expected_return_at TEXT NOT NULL,
      confirmed_at TEXT,returned_at TEXT,status TEXT NOT NULL DEFAULT 'pending');
    CREATE TABLE loan_devices(loan_id INTEGER NOT NULL,device_id INTEGER NOT NULL,returned_at TEXT,
      PRIMARY KEY(loan_id,device_id));"""
    )
    for i in range(1, 21):
        db.execute("INSERT INTO devices VALUES (?,?)", (i, f"CH-{i:03}"))
    for id, status in [(1, "active"), (2, "returned"), (3, "pending")]:
        db.execute(
            "INSERT INTO loans VALUES (?,?,?,?,?,?,?,?,?)",
            (
                id,
                "Prof. Antigo",
                "10",
                2,
                s.stamp(),
                s.stamp(s.now().replace(hour=15)),
                s.stamp() if status != "pending" else None,
                s.stamp() if status == "returned" else None,
                status,
            ),
        )
    db.execute("INSERT INTO loan_devices VALUES (1,1,NULL)")
    db.execute("INSERT INTO loan_devices VALUES (1,2,?)", (s.stamp(),))
    db.execute("INSERT INTO loan_devices VALUES (2,3,NULL)")
    db.execute("INSERT INTO loan_devices VALUES (2,4,NULL)")
    db.commit()
    db.close()
    init_db()
    return path


def test_legacy_blocks_until_review_and_keeps_original(legacy):
    db = connect()
    original = rows(db.execute("SELECT * FROM loan_devices"))
    db.close()
    assert s.get_dashboard()["blocked"]
    assert s.stock_count() == 0
    with pytest.raises(s.ValidationError):
        s.request_loan("Prof. Nova", "1", 1, "15:00", token=secrets.token_urlsafe(32))
    with pytest.raises(s.ValidationError):
        s.return_loan(1, ["CH-001"], secrets.token_urlsafe(32))
    key = secrets.token_urlsafe(32)
    s.reconcile_loan(1, ["CH-009"], "Conferência física com o professor.", key)
    s.reconcile_loan(1, ["CH-009"], "Conferência física com o professor.", key)
    assert not s.get_dashboard()["blocked"]
    assert s.stock_count() == 19
    db = connect()
    assert rows(db.execute("SELECT * FROM loan_devices")) == original
    db.close()
    s.return_loan(1, ["CH-009"], secrets.token_urlsafe(32))
    init_db()
    assert s.stock_count() == 20
    assert any(
        a["action"] == "conferencia_legado" and "CH-009" in a["detail"]
        for a in s.get_history()["audit"]
    )


def test_legacy_history_remains_flagged(legacy):
    loan = next(l for l in s.get_history()["loans"] if l["id"] == 2)
    assert loan["needs_review"] and loan["devices"] == []
    s.reconcile_loan(
        2,
        ["CH-010", "CH-011"],
        "Conferido no registro físico da escola.",
        secrets.token_urlsafe(32),
    )
    loan = next(l for l in s.get_history()["loans"] if l["id"] == 2)
    assert not loan["needs_review"]
    assert all(d["returned_at"] for d in loan["devices"])


def test_review_wrong_count_or_reason(legacy):
    with pytest.raises(s.ValidationError):
        s.reconcile_loan(
            1,
            ["CH-005", "CH-006"],
            "Conferência física completa.",
            secrets.token_urlsafe(32),
        )
    with pytest.raises(s.ValidationError):
        s.reconcile_loan(1, ["CH-005"], "sim", secrets.token_urlsafe(32))
    assert s.get_dashboard()["blocked"]


def test_oldest_schema_without_return_column(legacy):
    db = connect()
    db.execute("ALTER TABLE loan_devices DROP COLUMN returned_at")
    db.close()
    init_db()
    init_db()
    assert s.get_dashboard()["blocked"]
    assert len(s.get_history()["loans"]) == 3


def test_vercel_never_falls_back_to_local(monkeypatch):
    monkeypatch.setenv("VERCEL", "1")
    with pytest.raises(RuntimeError, match="Turso"):
        connect()


def test_init_script_creates_readable_backup(monkeypatch, tmp_path):
    import os, subprocess, sys
    from pathlib import Path

    target = tmp_path / "existing.db"
    db = sqlite3.connect(target)
    db.execute("CREATE TABLE original(value TEXT)")
    db.execute("INSERT INTO original VALUES ('preservar')")
    db.commit()
    db.close()
    monkeypatch.setenv("LOCAL_DB_PATH", str(target))
    script = Path(__file__).resolve().parents[1] / "scripts/init_db.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    assert result.returncode == 0, result.stderr
    backups = list(tmp_path.glob("existing.db.backup-*.sqlite"))
    assert len(backups) == 1
    for file in (target, backups[0]):
        db = sqlite3.connect(file)
        assert db.execute("SELECT value FROM original").fetchone() == ("preservar",)
        db.close()


def test_init_script_requires_explicit_remote_flag(monkeypatch):
    import os, subprocess, sys
    from pathlib import Path

    monkeypatch.setenv("TURSO_DATABASE_URL", "https://example.invalid")
    script = Path(__file__).resolve().parents[1] / "scripts/init_db.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    assert result.returncode == 2 and "--remote" in result.stderr


def test_old_open_loan_is_not_hidden_by_history_limit(legacy):
    db = connect()
    try:
        for i in range(4, 305):
            db.execute(
                "INSERT INTO loans(id,professor_name,room,quantity,requested_at,expected_return_at,start_at,status) VALUES (?,?,?,?,?,?,?,'cancelled')",
                (i, "Prof. Novo", "1", 1, s.stamp(), s.stamp(), s.stamp()),
            )
    finally:
        db.close()
    assert any(loan["id"] == 1 for loan in s.get_history()["loans"])


def test_legacy_review_does_not_invent_missing_timestamps(legacy):
    db = connect()
    db.execute("UPDATE loans SET returned_at=NULL WHERE id=2")
    db.close()
    with pytest.raises(s.ValidationError, match="horário"):
        s.reconcile_loan(
            2,
            ["CH-010", "CH-011"],
            "Conferência com evidência física.",
            secrets.token_urlsafe(32),
        )
    row = next(l for l in s.get_history()["loans"] if l["id"] == 2)
    assert row["needs_review"] and row["returned_at"] is None and row["devices"] == []
