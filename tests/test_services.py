from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import sqlite3

import pytest

import services
from database import connect, init_db
from services import (
    ValidationError, get_dashboard, get_history, request_loan, return_loan, stock_count,
)


def test_inventory_lifecycle():
    loan_id = request_loan('Prof. Ana', '203', '4', '15:00')
    assert stock_count() == 16
    loan = get_dashboard()['active'][0]
    assert loan['devices'] == 'CH-001, CH-002, CH-003, CH-004'
    assert loan['status'] == 'active'
    assert loan['requested_at'] == loan['confirmed_at'] == services.now().isoformat(timespec='seconds')
    assert loan['expected_return_at'].endswith('15:00:00-03:00')
    return_loan(loan_id, '4')
    assert stock_count() == 20
    assert get_dashboard()['active'] == []
    assert get_history()[0]['status'] == 'returned'


def test_partial_return_and_reuse():
    first = request_loan('Prof. Ana', '203', '8', '15:00')
    return_loan(first, '3')
    assert stock_count() == 15
    loan = get_dashboard()['active'][0]
    assert (loan['quantity'], loan['returned_quantity'], loan['remaining_quantity']) == (8, 3, 5)
    assert loan['returned_at'] is None
    second = request_loan('Prof. Bruno', '204', '3', '16:00')
    assert get_history()[0]['devices'] == 'CH-001, CH-002, CH-003'
    init_db()  # Inicialização repetida preserva devoluções parciais.
    assert stock_count() == 12
    return_loan(first, '5')
    assert stock_count() == 17
    return_loan(second, '3')
    assert stock_count() == 20
    assert all(l['status'] == 'returned' for l in get_history())


@pytest.mark.parametrize('quantity', [None, '', '0', '-1', '3.5', 'nove', '9'])
def test_invalid_return_does_not_change_stock(quantity):
    loan_id = request_loan('Prof. Ana', '203', '8', '15:00')
    with pytest.raises(ValidationError):
        return_loan(loan_id, quantity)
    assert stock_count() == 12
    assert get_history()[0]['returned_quantity'] == 0


def test_duplicate_full_return_and_unknown_loan_are_rejected():
    loan_id = request_loan('Prof. Ana', '203', '2', '15:00')
    return_loan(loan_id, '2')
    for missing in (loan_id, 999):
        with pytest.raises(ValidationError):
            return_loan(missing, '2')
    assert stock_count() == 20


@pytest.mark.parametrize('expected', [None, '', 'ontem', '25:00', '12:60', 'abc15:00', '1:5', '15000', '10:00', '09:59', '2026-10-10T15:00'])
def test_invalid_return_time_does_not_create_a_loan(expected):
    with pytest.raises(ValidationError):
        request_loan('Prof. Ana', '203', '4', expected)
    assert stock_count() == 20
    assert get_history() == []


@pytest.mark.parametrize('quantity', ['0', '21', '-1', '1.5', '', None])
def test_invalid_withdrawal_quantity(quantity):
    with pytest.raises(ValidationError):
        request_loan('Prof. Ana', '203', quantity, '15:00')
    assert get_history() == []


def test_overbook_is_rejected_immediately():
    request_loan('Prof. Ana', '203', '12', '15:00')
    with pytest.raises(ValidationError, match='disponível'):
        request_loan('Prof. Bruno', '204', '12', '15:00')
    assert stock_count() == 8
    assert len(get_history()) == 1


def test_simultaneous_withdrawals_do_not_overbook():
    def take(name):
        try:
            request_loan(name, '203', '12', '15:00')
            return True
        except ValidationError:
            return False
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(take, ('Prof. Ana', 'Prof. Bruno')))
    assert sorted(results) == [False, True]
    assert stock_count() == 8
    assert len(get_history()) == 1


def test_simultaneous_full_returns_do_not_inflate_stock():
    loan_id = request_loan('Prof. Ana', '203', '8', '15:00')
    def give_back(_):
        try:
            return_loan(loan_id, '8')
            return True
        except ValidationError:
            return False
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(give_back, range(2)))
    assert sorted(results) == [False, True]
    assert stock_count() == 20


def test_expected_time_does_not_automatically_release_stock(monkeypatch):
    request_loan('Prof. Ana', '203', '8', '15:00')
    later = services.now() + timedelta(hours=6)
    monkeypatch.setattr(services, 'now', lambda: later)
    assert stock_count() == 12
    assert get_dashboard()['overdue_count'] == 1


def test_failed_assignment_rolls_back_loan_and_stock():
    db = connect()
    db.execute("""CREATE TRIGGER reject_second BEFORE INSERT ON loan_devices
        WHEN NEW.device_id = 2 BEGIN SELECT RAISE(ABORT, 'test failure'); END""")
    db.close()
    with pytest.raises(sqlite3.IntegrityError, match='test failure'):
        request_loan('Prof. Ana', '203', '4', '15:00')
    assert get_history() == []
    assert stock_count() == 20
    db = connect()
    try:
        assert db.execute('SELECT COUNT(*) FROM loan_devices').fetchone()[0] == 0
    finally:
        db.close()


def test_initialization_is_repeatable():
    init_db()
    db = connect()
    try:
        codes = [row[0] for row in db.execute('SELECT code FROM devices ORDER BY id')]
    finally:
        db.close()
    assert codes == [f'CH-{i:03}' for i in range(1, 21)]


def test_legacy_database_is_upgraded_without_losing_history():
    first = request_loan('Prof. Ana', '203', '2', '15:00')
    second = request_loan('Prof. Bruno', '204', '2', '15:00')
    return_loan(first, '2')
    db = connect()
    try:
        db.execute('ALTER TABLE loan_devices DROP COLUMN returned_at')
    finally:
        db.close()
    init_db()
    init_db()
    history = {loan['id']: loan for loan in get_history()}
    assert history[first]['returned_quantity'] == 2
    assert history[first]['status'] == 'returned'
    assert history[second]['remaining_quantity'] == 2
    assert stock_count() == 18
    return_loan(second, '1')
    assert stock_count() == 19


def test_return_time_accepts_four_digits_without_javascript():
    request_loan('Prof. Ana', '203', '1', '1530')
    assert get_history()[0]['expected_return_at'].endswith('15:30:00-03:00')
