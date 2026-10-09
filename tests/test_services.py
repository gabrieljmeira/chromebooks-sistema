from datetime import timedelta

import pytest

from database import connect, init_db
from services import (
    ValidationError, cancel_loan, confirm_loan, get_dashboard,
    get_history, now, request_loan, return_loan, stock_count,
)


def expected():
    return (now() + timedelta(hours=5)).strftime('%Y-%m-%dT%H:%M')


def test_inventory_lifecycle():
    assert stock_count() == 20
    loan_id = request_loan('Prof. Ana', '203', '4', expected())
    assert stock_count() == 20  # pedido não reserva
    assert get_dashboard()['pending_count'] == 1
    confirm_loan(loan_id)
    assert stock_count() == 16
    assert get_dashboard()['active'][0]['devices'] == 'CH-001, CH-002, CH-003, CH-004'
    return_loan(loan_id)
    assert stock_count() == 20
    assert get_history()[0]['status'] == 'returned'


def test_overbook_is_rejected_at_confirmation():
    first = request_loan('Prof. Ana', '203', '12', expected())
    second = request_loan('Prof. Bruno', '204', '12', expected())
    confirm_loan(first)
    assert stock_count() == 8
    with pytest.raises(ValidationError, match='suficientes'):
        confirm_loan(second)
    assert stock_count() == 8
    assert get_dashboard()['pending_count'] == 1


def test_invalid_and_duplicate_actions():
    with pytest.raises(ValidationError):
        request_loan('A', 'A', '100', expected())
    loan_id = request_loan('Prof. Ana', '203', '2', expected())
    with pytest.raises(ValidationError):
        return_loan(loan_id)
    confirm_loan(loan_id)
    with pytest.raises(ValidationError):
        confirm_loan(loan_id)
    with pytest.raises(ValidationError):
        cancel_loan(loan_id)
    return_loan(loan_id)
    with pytest.raises(ValidationError):
        return_loan(loan_id)


def test_pending_can_be_cancelled():
    loan_id = request_loan('Prof. Ana', '203', '2', expected())
    cancel_loan(loan_id)
    assert get_history()[0]['status'] == 'cancelled'
    assert stock_count() == 20


def test_simultaneous_confirmations_do_not_overbook():
    from concurrent.futures import ThreadPoolExecutor

    first = request_loan('Prof. Ana', '203', '12', expected())
    second = request_loan('Prof. Bruno', '204', '12', expected())

    def confirm_and_report(loan_id):
        try:
            confirm_loan(loan_id)
            return True
        except ValidationError:
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(confirm_and_report, (first, second)))
    assert sorted(results) == [False, True]
    assert stock_count() == 8
    assert sum(l['quantity'] for l in get_dashboard()['active']) == 12


def test_initialization_is_repeatable():
    init_db()
    db = connect()
    try:
        codes = [row[0] for row in db.execute('SELECT code FROM devices ORDER BY id')]
    finally:
        db.close()
    assert codes == [f'CH-{i:03}' for i in range(1, 21)]


def test_dashboard_keeps_active_loans_after_many_pending_requests():
    active_id = request_loan('Prof. Ana', '203', '1', expected())
    confirm_loan(active_id)
    for _ in range(101):
        request_loan('Prof. Bruno', '204', '1', expected())
    dashboard = get_dashboard()
    assert dashboard['pending_count'] == 101
    assert [loan['id'] for loan in dashboard['active']] == [active_id]
