(function (root) {
  function pendingAlerts(loans, nowMs) {
    const result = [];
    for (const loan of loans) {
      const due = Date.parse(loan.expected);
      if (!(loan.remaining > 0) || !Number.isFinite(due)) continue;
      const phase = nowMs >= due ? 'due' : nowMs >= due - 300000 ? 'soon' : null;
      if (phase) result.push({ key: `${loan.id}:${loan.expected}:${phase}`, id: loan.id, phase });
    }
    return result;
  }
  root.LoanAlerts = { pendingAlerts };
  if (typeof module !== 'undefined') module.exports = root.LoanAlerts;
})(typeof window === 'undefined' ? globalThis : window);
