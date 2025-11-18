const API_BASE = 'http://localhost:8001';

const countInput = document.getElementById('count');
const startBtn = document.getElementById('startBtn');
const runIdEl = document.getElementById('runId');
const statusEl = document.getElementById('status');
const summaryEl = document.getElementById('summaryJson');
const rowsBody = document.getElementById('rowsBody');
const csvLink = document.getElementById('csvLink');
const jsonSummaryLink = document.getElementById('jsonSummaryLink');
const domainsContainer = document.getElementById('domainsContainer');
const interpretationEl = document.getElementById('interpretationText');
const kldiStatsEl = document.getElementById('kldiStatsText');
const progressText = document.getElementById('progressText');
const progressBar = document.getElementById('progressBar');
const errorBox = document.getElementById('errorBox');
const perDomainChart = document.getElementById('perDomainChart');
const statsCharts = document.getElementById('statsCharts');

let currentRunId = null;
let pollTimer = null;

async function loadDomains() {
  try {
    const res = await fetch(`${API_BASE}/domains`);
    if (!res.ok) throw new Error('Fehler beim Laden der Domänen');
    const domains = await res.json();
    if (!domains.length) {
      domainsContainer.textContent = 'Keine Domänen konfiguriert.';
      return;
    }
    domainsContainer.innerHTML = '';
    for (const dom of domains) {
      const id = `domain-${dom.slug}`;
      const wrapper = document.createElement('label');
      wrapper.style.display = 'inline-flex';
      wrapper.style.alignItems = 'center';
      wrapper.style.marginRight = '0.75rem';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.id = id;
      checkbox.name = 'domains';
      checkbox.value = dom.slug;
      checkbox.checked = true;
      checkbox.style.marginRight = '0.25rem';
      const span = document.createElement('span');
      span.textContent = dom.name;
      wrapper.appendChild(checkbox);
      wrapper.appendChild(span);
      domainsContainer.appendChild(wrapper);
    }
  } catch (err) {
    console.error(err);
    domainsContainer.textContent = 'Fehler beim Laden der Domänen.';
  }
}

// Domänen direkt beim Laden der Seite holen
loadDomains();

function renderSummary(summary) {
  if (!summary) {
    summaryEl.textContent = '–';
    return;
  }

  const lines = [];

  if (summary.stage) {
    lines.push(`Schritt: ${summary.stage}`);
  }

  const processed =
    typeof summary.processed === 'number'
      ? summary.processed
      : typeof summary.documents_processed === 'number'
      ? summary.documents_processed
      : null;
  const expected = typeof summary.expected === 'number' ? summary.expected : null;
  if (processed != null && expected != null) {
    lines.push(`Dokumente: ${processed} / ${expected}`);
  }

  if (Array.isArray(summary.domains) && summary.domains.length) {
    lines.push(`Themenfelder: ${summary.domains.join(', ')}`);
  }

  if (summary.per_domain) {
    lines.push('Pro Domäne:');
    for (const [domain, stats] of Object.entries(summary.per_domain)) {
      const avg =
        typeof stats.avg_kld === 'number' ? stats.avg_kld.toFixed(4) : stats.avg_kld;
      lines.push(
        `  - ${domain}: count=${stats.count}, avg_kld=${avg}, human_like=${stats.human_like}, detectable=${stats.detectable}`
      );
    }
  }

  const stats = summary.stats || {};
  if (Object.keys(stats).length > 0) {
    lines.push('Statistik:');
    if (typeof stats.human_human_count === 'number') {
      lines.push(`  - Human→Human Paare: ${stats.human_human_count}`);
    }
    if (typeof stats.human_ki_count === 'number') {
      lines.push(`  - Human→KI Paare: ${stats.human_ki_count}`);
    }
    if (typeof stats.adaptive_threshold === 'number') {
      lines.push(`  - Adaptive Schwelle: ${stats.adaptive_threshold.toFixed(4)}`);
    }
    if (typeof stats.mannwhitney_p === 'number') {
      lines.push(`  - Mann-Whitney p: ${stats.mannwhitney_p.toExponential(3)}`);
    }
    if (typeof stats.roc_auc === 'number') {
      lines.push(`  - ROC AUC: ${stats.roc_auc.toFixed(4)}`);
    }
    if (typeof stats.kldi_initial_avg === 'number') {
      lines.push(`  - KLDI initial (avg): ${stats.kldi_initial_avg.toFixed(4)}`);
    }
    if (typeof stats.kldi_best_avg === 'number') {
      lines.push(`  - KLDI best (avg): ${stats.kldi_best_avg.toFixed(4)}`);
    }
    if (typeof stats.kldi_avg_improvement === 'number') {
      lines.push(
        `  - KLDI Verbess. (avg): ${stats.kldi_avg_improvement.toFixed(4)}`
      );
    }
  }

  summaryEl.textContent = lines.length ? lines.join('\n') : '–';

  // Statistische Mini-Grafiken
  if (statsCharts) {
    statsCharts.innerHTML = '';
    const stats = summary.stats || {};

    // ROC AUC (0–1)
    if (typeof stats.roc_auc === 'number') {
      const auc = Math.max(0, Math.min(1, stats.roc_auc));
      const pct = Math.round(auc * 100);
      const row = document.createElement('div');
      row.className = 'stat-row';
      row.innerHTML = `
        <span class="stat-label">ROC AUC</span>
        <div class="stat-bar"><div class="stat-bar-inner" style="width: ${pct}%"></div></div>
        <span class="stat-value">${auc.toFixed(3)}</span>
      `;
      statsCharts.appendChild(row);
    }

    // KLDI Verbesserung (avg) – auf 0–0,5 clampen für die Anzeige
    if (typeof stats.kldi_avg_improvement === 'number') {
      const maxImprovement = 0.5;
      const imp = Math.max(0, Math.min(maxImprovement, stats.kldi_avg_improvement));
      const pct = Math.round((imp / maxImprovement) * 100);
      const row = document.createElement('div');
      row.className = 'stat-row';
      row.innerHTML = `
        <span class="stat-label">KLDI Δ (avg)</span>
        <div class="stat-bar"><div class="stat-bar-inner" style="width: ${pct}%"></div></div>
        <span class="stat-value">${stats.kldi_avg_improvement.toFixed(4)}</span>
      `;
      statsCharts.appendChild(row);
    }

    // Human vs. KI Paare (zwei Balken, relativ zur Gesamtzahl)
    if (
      typeof stats.human_human_count === 'number' &&
      typeof stats.human_ki_count === 'number' &&
      (stats.human_human_count > 0 || stats.human_ki_count > 0)
    ) {
      const total = stats.human_human_count + stats.human_ki_count;
      const humanPct = Math.round((stats.human_human_count / total) * 100);
      const kiPct = Math.round((stats.human_ki_count / total) * 100);

      const humanRow = document.createElement('div');
      humanRow.className = 'stat-row';
      humanRow.innerHTML = `
        <span class="stat-label">Human→Human</span>
        <div class="stat-bar"><div class="stat-bar-inner" style="width: ${humanPct}%"></div></div>
        <span class="stat-value">${stats.human_human_count}</span>
      `;
      statsCharts.appendChild(humanRow);

      const kiRow = document.createElement('div');
      kiRow.className = 'stat-row';
      kiRow.innerHTML = `
        <span class="stat-label">Human→KI</span>
        <div class="stat-bar"><div class="stat-bar-inner" style="width: ${kiPct}%"></div></div>
        <span class="stat-value">${stats.human_ki_count}</span>
      `;
      statsCharts.appendChild(kiRow);
    }
  }

  // Einfache grafische Darstellung: Balken pro Domäne basierend auf Dokumentanzahl
  if (perDomainChart) {
    perDomainChart.innerHTML = '';
    if (summary.per_domain) {
      const entries = Object.entries(summary.per_domain);
      const maxCount = Math.max(
        1,
        ...entries.map(([, s]) => (typeof s.count === 'number' ? s.count : 0))
      );

      for (const [domain, stats] of entries) {
        const count = typeof stats.count === 'number' ? stats.count : 0;
        const pct = maxCount > 0 ? Math.round((count / maxCount) * 100) : 0;

        const row = document.createElement('div');
        row.className = 'per-domain-row';
        row.innerHTML = `
          <span class="per-domain-label">${escapeHtml(domain)}</span>
          <div class="per-domain-bar">
            <div class="per-domain-bar-inner" style="width: ${pct}%"></div>
          </div>
          <span class="per-domain-count">${count}</span>
        `;
        perDomainChart.appendChild(row);
      }
    }
  }
}

startBtn.addEventListener('click', async () => {
  const count = parseInt(countInput.value, 10);
  if (!count || count < 1 || count > 2000) {
    alert('Bitte eine Zahl zwischen 1 und 2000 eingeben.');
    return;
  }

  const selectedDomains = Array.from(
    document.querySelectorAll('input[name="domains"]:checked')
  ).map((el) => el.value);
  if (!selectedDomains.length) {
    alert('Bitte mindestens ein Themenfeld auswählen.');
    return;
  }

  startBtn.disabled = true;
  statusEl.textContent = 'Starte Analyse...';
  rowsBody.innerHTML = '<tr><td colspan="7" class="small">Warte auf Ergebnisse...</td></tr>';
  summaryEl.textContent = '–';
  interpretationEl.textContent = '–';
  progressText.textContent = '–';
  progressBar.style.width = '0%';
  errorBox.style.display = 'none';

  try {
    const res = await fetch(`${API_BASE}/runs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ count, domains: selectedDomains }),
    });
    if (!res.ok) {
      throw new Error(`Fehler beim Starten: ${res.status}`);
    }
    const data = await res.json();
    currentRunId = data.id;
    runIdEl.textContent = data.id;
    csvLink.href = `${API_BASE}/runs/${data.id}/export?format=csv`;
    jsonSummaryLink.href = `${API_BASE}/runs/${data.id}/summary_export`;
    pollRunStatus();
  } catch (err) {
    console.error(err);
    statusEl.textContent = 'Fehler beim Starten der Analyse.';
    startBtn.disabled = false;
  }
});

async function pollRunStatus() {
  if (!currentRunId) return;
  if (pollTimer) clearInterval(pollTimer);

  const poll = async () => {
    try {
      const res = await fetch(`${API_BASE}/runs/${currentRunId}`);
      if (!res.ok) throw new Error('Run nicht gefunden');
      const data = await res.json();
      updateStatus(data);

      const status = (data.status || '').toLowerCase();
      if (status === 'completed') {
        clearInterval(pollTimer);
        await loadRows();
        startBtn.disabled = false;
      } else if (status === 'failed') {
        clearInterval(pollTimer);
        startBtn.disabled = false;
      }
    } catch (err) {
      console.error(err);
      statusEl.textContent = 'Fehler beim Abfragen des Run-Status.';
      clearInterval(pollTimer);
      startBtn.disabled = false;
    }
  };

  await poll();
  pollTimer = setInterval(poll, 5000);
}

function updateStatus(run) {
  const status = (run.status || '').toLowerCase();
  const badgeClass =
    status === 'completed'
      ? 'completed'
      : status === 'failed'
      ? 'failed'
      : 'running';
  const summary = run.summary || {};
  const stage = summary.stage || (run.status === 'COMPLETED' ? 'completed' : null);
  const stageLabelMap = {
    initializing: 'Initialisierung',
    processing: 'Scraping & Paraphrasing',
    computing_stats: 'Statistische Auswertung',
    completed: 'Abgeschlossen',
    failed: 'Fehlgeschlagen',
  };
  const stageLabel = stage ? (stageLabelMap[stage] || stage) : '–';
  statusEl.innerHTML = `Status: <span class="badge ${badgeClass}">${run.status}</span><br/><span class="small">Schritt: ${stageLabel}</span>`;
  const interpretation = summary.analysis && summary.analysis.interpretation
    ? summary.analysis.interpretation
    : '–';
  interpretationEl.textContent = interpretation;
  renderSummary(summary);

  // Aggregierte KLDI-Iterationswerte (falls vorhanden)
  const stats = summary.stats || {};
  if (
    typeof stats.kldi_initial_avg === 'number' &&
    typeof stats.kldi_best_avg === 'number' &&
    typeof stats.kldi_avg_improvement === 'number'
  ) {
    const init = stats.kldi_initial_avg.toFixed(4);
    const best = stats.kldi_best_avg.toFixed(4);
    const diff = stats.kldi_avg_improvement.toFixed(4);
    kldiStatsEl.textContent = `erst: ${init}, best: ${best}, Verbesserung: ${diff}`;
  } else {
    kldiStatsEl.textContent = '–';
  }

  // Fortschritt
  const processed =
    typeof summary.processed === 'number'
      ? summary.processed
      : typeof summary.documents_processed === 'number'
      ? summary.documents_processed
      : null;
  const expected =
    typeof summary.expected === 'number'
      ? summary.expected
      : typeof run.requested_count === 'number'
      ? run.requested_count
      : null;

  if (processed != null && expected != null && expected > 0) {
    const pct = Math.min(100, Math.round((processed / expected) * 100));
    progressText.textContent = `${processed} / ${expected} Texte (${pct}%)`;
    progressBar.style.width = `${pct}%`;
  } else {
    progressText.textContent = '–';
    progressBar.style.width = '0%';
  }

  // Fehleranzeige
  if (run.status === 'FAILED' || summary.error) {
    errorBox.style.display = 'block';
    errorBox.textContent = `Fehler: ${summary.error || 'Unbekannter Fehler im Backend'}`;
  } else {
    errorBox.style.display = 'none';
  }
}

async function loadRows() {
  if (!currentRunId) return;
  try {
    const res = await fetch(`${API_BASE}/runs/${currentRunId}/rows`);
    if (!res.ok) throw new Error('Fehler beim Laden der Zeilen');
    const rows = await res.json();
    if (!rows.length) {
      rowsBody.innerHTML = '<tr><td colspan="7" class="small">Keine Zeilen gefunden.</td></tr>';
      return;
    }
    rowsBody.innerHTML = '';
    for (const row of rows) {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td class="mono small">${escapeHtml(row.id)}</td>
        <td>${escapeHtml(row.domain)}</td>
        <td class="small"><a href="${escapeHtml(row.source_url)}" target="_blank" rel="noopener noreferrer">Quelle</a></td>
        <td class="small">${escapeHtml(row.original_text)}</td>
        <td class="small">${escapeHtml(row.paraphrased_text)}</td>
        <td class="mono">${row.kldi.toFixed(4)}</td>
        <td class="small">${escapeHtml(row.classification || '')}</td>
        <td class="mono">${
          typeof row.kldi_initial === 'number' ? row.kldi_initial.toFixed(4) : ''
        }</td>
        <td class="mono">${
          typeof row.kldi_best === 'number' ? row.kldi_best.toFixed(4) : ''
        }</td>
        <td class="mono">${
          typeof row.iterations === 'number' ? row.iterations : ''
        }</td>
      `;
      rowsBody.appendChild(tr);
    }
  } catch (err) {
    console.error(err);
    rowsBody.innerHTML = '<tr><td colspan="7" class="small">Fehler beim Laden der Zeilen.</td></tr>';
  }
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
