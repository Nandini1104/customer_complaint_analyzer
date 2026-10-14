// Draws Chart.js charts from the JSON API (/api/analytics, /api/categories). All values come from the database.
const COLORS = {Positive: '#16a34a', Negative: '#dc2626', Neutral: '#9ca3af',
  New: '#4f46e5', 'In Progress': '#f59e0b', Resolved: '#16a34a', Closed: '#6b7280',
  Low: '#9ca3af', Medium: '#f59e0b', High: '#dc2626'};
const charts = {};

function draw(id, config) {
  const el = document.getElementById(id);
  if (!el) return;
  if (charts[id]) charts[id].destroy();
  config.options = Object.assign({responsive: true, maintainAspectRatio: false}, config.options || {});
  charts[id] = new Chart(el, config);
}

async function fetchJSON(url) {
  const response = await fetch(url, {headers: {'Accept': 'application/json'}, credentials: 'same-origin'});
  if (!response.ok) throw new Error('Request failed (' + response.status + ')');
  return response.json();
}

function showEmpty(id, isEmpty) {
  const note = document.getElementById(id + '-empty');
  if (note) note.classList.toggle('d-none', !isEmpty);
}

function sentimentChart(id, dist) {
  const labels = Object.keys(dist.sentiment);
  draw(id, {type: 'doughnut', data: {labels: labels.map(l => l + ' (' + dist.sentiment_pct[l] + '%)'),
    datasets: [{data: labels.map(l => dist.sentiment[l]), backgroundColor: labels.map(l => COLORS[l])}]},
    options: {plugins: {legend: {position: 'bottom'}}}});
  showEmpty(id, dist.total === 0);
}

function barChart(id, obj, horizontal, colorFn) {
  const labels = Object.keys(obj);
  draw(id, {type: 'bar', data: {labels, datasets: [{label: 'Complaints', data: labels.map(l => obj[l]),
    backgroundColor: labels.map(l => (colorFn ? colorFn(l) : '#4f46e5'))}]},
    options: {indexAxis: horizontal ? 'y' : 'x', plugins: {legend: {display: false}},
      scales: {[horizontal ? 'x' : 'y']: {beginAtZero: true, ticks: {precision: 0}}}}});
  showEmpty(id, Object.values(obj).every(v => v === 0));
}

function trendChart(id, t) {
  draw(id, {type: 'line', data: {labels: t.labels, datasets: [
    {label: 'All complaints', data: t.total, borderColor: '#4f46e5', backgroundColor: 'rgba(79,70,229,.12)', fill: true, tension: .3},
    {label: 'Negative', data: t.Negative, borderColor: COLORS.Negative, tension: .3},
    {label: 'Positive', data: t.Positive, borderColor: COLORS.Positive, tension: .3},
    {label: 'Neutral', data: t.Neutral, borderColor: COLORS.Neutral, tension: .3}]},
    options: {scales: {y: {beginAtZero: true, ticks: {precision: 0}}}, plugins: {legend: {position: 'bottom'}}}});
  showEmpty(id, t.labels.length === 0);
}

function queryFromForm(formId) {
  const form = document.getElementById(formId);
  return form ? new URLSearchParams(new FormData(form)).toString() : '';
}

async function loadAnalytics(formId, period) {
  const params = new URLSearchParams(queryFromForm(formId));
  if (period) params.set('period', period);
  try {
    const data = await fetchJSON('/api/analytics?' + params.toString());
    sentimentChart('sentimentChart', data.distributions);
    barChart('categoryChart', data.distributions.category, true);
    barChart('statusChart', data.distributions.status, false, l => COLORS[l]);
    barChart('priorityChart', data.distributions.priority, false, l => COLORS[l]);
    trendChart('trendChart', data.trend);
    const total = document.getElementById('totalCount');
    if (total) total.textContent = data.summary.total;
  } catch (err) {
    document.querySelectorAll('.chart-error').forEach(n => { n.textContent = 'Could not load chart data. ' + err.message; n.classList.remove('d-none'); });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const page = document.body.dataset.page;
  if (page === 'dashboard') loadAnalytics(null, 'daily');
  if (page === 'analytics') {
    loadAnalytics('filterForm');
    document.querySelectorAll('#filterForm select, #filterForm input').forEach(e => e.addEventListener('change', () => loadAnalytics('filterForm')));
  }
  if (page === 'categories') loadAnalytics(null);
  if (page === 'trends') {
    const run = () => loadAnalytics('filterForm', document.getElementById('period').value);
    document.querySelectorAll('#filterForm select, #filterForm input').forEach(e => e.addEventListener('change', run));
    run();
  }
  // show custom date inputs only for "Custom range"
  const range = document.querySelector('select[name="date_range"]');
  const toggle = () => document.querySelectorAll('.custom-dates').forEach(n => n.classList.toggle('d-none', !range || range.value !== 'custom'));
  if (range) { range.addEventListener('change', toggle); toggle(); }
});
