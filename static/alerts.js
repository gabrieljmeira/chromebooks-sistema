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
  function pendingDeliveries(deliveries, nowMs) {
    return (deliveries || []).filter(loan => Number.isFinite(Date.parse(loan.start)) && nowMs >= Date.parse(loan.start) && nowMs < Date.parse(loan.expected))
      .map(loan => ({key: `delivery:${loan.id}:${loan.start}`, id: loan.id, phase: 'delivery'}));
  }
  root.LoanAlerts = { pendingAlerts, pendingDeliveries };
  if (typeof module !== 'undefined') module.exports = root.LoanAlerts;
})(typeof window === 'undefined' ? globalThis : window);
