const API_BASE = window.API_BASE || 'http://localhost:8101';

const countInput = document.getElementById('count');
const startBtn = document.getElementById('startBtn');
const runIdEl = document.getElementById('runId');
const statusEl = document.getElementById('status');
const summaryEl = document.getElementById('summaryJson');
const rowsBody = document.getElementById('rowsBody');
const csvLink = document.getElementById('csvLink');
const jsonSummaryLink = document.getElementById('jsonSummaryLink');
const reportLink = document.getElementById('reportLink');
const domainsContainer = document.getElementById('domainsContainer');
const interpretationEl = document.getElementById('interpretationText');
const llmInterpretationEl = document.getElementById('llmInterpretationText');
const kldiStatsEl = document.getElementById('kldiStatsText');
const progressText = document.getElementById('progressText');
const progressBar = document.getElementById('progressBar');
const errorBox = document.getElementById('errorBox');
const perDomainChart = document.getElementById('perDomainChart');
const statsCharts = document.getElementById('statsCharts');
const runsListContainer = document.getElementById('runsList');
const runCompareEl = document.getElementById('runCompare');
const filterDomain = document.getElementById('filterDomain');
const filterClass = document.getElementById('filterClass');
const filterKldiMin = document.getElementById('filterKldiMin');
const filterKldiMax = document.getElementById('filterKldiMax');
const runModelInfoEl = document.getElementById('runModelInfo');
const runsPanelHeader = document.getElementById('runsPanelHeader');
const runsPanelToggle = document.getElementById('runsPanelToggle');
const runsPanelBody = document.getElementById('runsPanelBody');
const envPanelHeader = document.getElementById('envPanelHeader');
const envPanelToggle = document.getElementById('envPanelToggle');
const envPanelBody = document.getElementById('envPanelBody');
const envOpenAiKey = document.getElementById('envOpenAiKey');
const envOpenAiModel = document.getElementById('envOpenAiModel');
const envOpenAiBaseUrl = document.getElementById('envOpenAiBaseUrl');
const envBackendPort = document.getElementById('envBackendPort');
const envFrontendPortBase = document.getElementById('envFrontendPortBase');
const envStatus = document.getElementById('envStatus');
const envSaveBtn = document.getElementById('envSaveBtn');

let currentRunId = null;
let pollTimer = null;
let allRows = [];
let compareSelection = [];

if (reportLink) {
  reportLink.addEventListener('click', (event) => {
    if (!currentRunId) {
      event.preventDefault();
      return;
    }
    const url = `${API_BASE}/runs/${currentRunId}/report`;
    event.preventDefault();
    window.open(url, '_blank');
  });
}

if (filterDomain) {
  filterDomain.addEventListener('change', applyFiltersAndRenderRows);
}
if (filterClass) {
  filterClass.addEventListener('change', applyFiltersAndRenderRows);
}
if (filterKldiMin) {
  filterKldiMin.addEventListener('input', applyFiltersAndRenderRows);
}
if (filterKldiMax) {
  filterKldiMax.addEventListener('input', applyFiltersAndRenderRows);
}

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

function applyFiltersAndRenderRows() {
  if (!rowsBody) return;

  if (!Array.isArray(allRows) || !allRows.length) {
    rowsBody.innerHTML = '<tr><td colspan="7" class="small">Keine Zeilen gefunden.</td></tr>';
    return;
  }

  const domainVal = filterDomain && filterDomain.value ? filterDomain.value : '';
  const classVal = filterClass && filterClass.value ? filterClass.value : '';

  let kldiMin = null;
  let kldiMax = null;
  if (filterKldiMin && filterKldiMin.value !== '') {
    const v = Number(filterKldiMin.value);
    if (!Number.isNaN(v)) kldiMin = v;
  }
  if (filterKldiMax && filterKldiMax.value !== '') {
    const v = Number(filterKldiMax.value);
    if (!Number.isNaN(v)) kldiMax = v;
  }

  const filtered = allRows.filter((row) => {
    if (domainVal && row.domain !== domainVal) return false;
    if (classVal && (row.classification || '') !== classVal) return false;

    if (typeof row.kldi === 'number') {
      if (kldiMin !== null && row.kldi < kldiMin) return false;
      if (kldiMax !== null && row.kldi > kldiMax) return false;
    }
    return true;
  });

  renderRows(filtered);
}

function renderRows(rows) {
  if (!rowsBody) return;

  if (!rows.length) {
    rowsBody.innerHTML = '<tr><td colspan="7" class="small">Keine Zeilen (Filter?) gefunden.</td></tr>';
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
      <td class="mono">${typeof row.kldi === 'number' ? row.kldi.toFixed(4) : ''}</td>
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
}

function toggleCompare(runId) {
  const idx = compareSelection.indexOf(runId);
  if (idx !== -1) {
    compareSelection.splice(idx, 1);
  } else {
    if (compareSelection.length >= 2) {
      compareSelection.shift();
    }
    compareSelection.push(runId);
  }
  updateRunComparePanel();
}

async function updateRunComparePanel() {
  if (!runCompareEl) return;

  if (!compareSelection.length) {
    runCompareEl.textContent = 'Keine Runs zum Vergleich ausgewählt.';
    return;
  }

  try {
    const details = await Promise.all(
      compareSelection.map((id) => fetch(`${API_BASE}/runs/${id}`).then((res) => {
        if (!res.ok) throw new Error('Run nicht gefunden');
        return res.json();
      }))
    );

    const headers = compareSelection.map((id) => `<th class="small">${escapeHtml(id)}</th>`).join('');

    const rows = [];

    const metrics = [
      {
        label: 'Status',
        get: (d) => String(d.status || ''),
      },
      {
        label: 'Texte (requested)',
        get: (d) => (typeof d.requested_count === 'number' ? String(d.requested_count) : '–'),
      },
      {
        label: 'Texte (processed)',
        get: (d) => {
          const s = d.summary || {};
          const processed =
            typeof s.processed === 'number'
              ? s.processed
              : typeof s.documents_processed === 'number'
              ? s.documents_processed
              : null;
          return processed != null ? String(processed) : '–';
        },
      },
      {
        label: 'ROC AUC',
        get: (d) => {
          const stats = (d.summary && d.summary.stats) || {};
          return typeof stats.roc_auc === 'number' ? stats.roc_auc.toFixed(3) : '–';
        },
      },
      {
        label: 'Mann-Whitney p',
        get: (d) => {
          const stats = (d.summary && d.summary.stats) || {};
          return typeof stats.mannwhitney_p === 'number'
            ? stats.mannwhitney_p.toExponential(3)
            : '–';
        },
      },
      {
        label: 'Adaptive Schwelle',
        get: (d) => {
          const stats = (d.summary && d.summary.stats) || {};
          return typeof stats.adaptive_threshold === 'number'
            ? stats.adaptive_threshold.toFixed(4)
            : '–';
        },
      },
      {
        label: 'KLDI best (avg)',
        get: (d) => {
          const stats = (d.summary && d.summary.stats) || {};
          return typeof stats.kldi_best_avg === 'number'
            ? stats.kldi_best_avg.toFixed(4)
            : '–';
        },
      },
      {
        label: 'KLDI initial (avg)',
        get: (d) => {
          const stats = (d.summary && d.summary.stats) || {};
          return typeof stats.kldi_initial_avg === 'number'
            ? stats.kldi_initial_avg.toFixed(4)
            : '–';
        },
      },
    ];

    for (const m of metrics) {
      const cells = details
        .map((d) => `<td class="small">${escapeHtml(m.get(d))}</td>`)
        .join('');
      rows.push(`<tr><th class="small">${escapeHtml(m.label)}</th>${cells}</tr>`);
    }

    runCompareEl.innerHTML = `
      <h3 class="small">Vergleich ausgewählter Runs</h3>
      <table>
        <thead>
          <tr>
            <th class="small">Metrik</th>
            ${headers}
          </tr>
        </thead>
        <tbody>
          ${rows.join('')}
        </tbody>
      </table>
    `;
  } catch (err) {
    console.error(err);
    runCompareEl.textContent = 'Fehler beim Laden der Vergleichsdaten.';
  }
}

// Domänen direkt beim Laden der Seite holen
loadDomains();

// Vergangene Runs beim Laden holen
loadRunList();

// .env-Konfiguration laden
async function loadEnvConfig() {
  if (!envPanelBody) return;
  try {
    const res = await fetch(`${API_BASE}/env-config`);
    if (!res.ok) throw new Error('Fehler beim Laden der Env-Konfiguration');
    const data = await res.json();

    if (envOpenAiKey) envOpenAiKey.value = data.openai_api_key || '';
    if (envOpenAiModel) envOpenAiModel.value = data.openai_model || '';
    if (envOpenAiBaseUrl) envOpenAiBaseUrl.value = data.openai_base_url || '';
    if (envBackendPort) envBackendPort.value = data.backend_port || '';
    if (envFrontendPortBase) envFrontendPortBase.value = data.frontend_port_base || '';

    if (envStatus) {
      envStatus.textContent = data.env_exists
        ? '.env gefunden. Änderungen überschreiben bestehende Werte.'
        : 'Noch keine .env gefunden. Beim Speichern wird eine neue .env angelegt.';
    }
  } catch (err) {
    console.error(err);
    if (envStatus) {
      envStatus.textContent = 'Fehler beim Laden der .env-Konfiguration.';
    }
  }
}

if (envPanelHeader && envPanelBody && envPanelToggle) {
  envPanelHeader.addEventListener('click', () => {
    const isOpen = envPanelBody.style.display === 'block';
    envPanelBody.style.display = isOpen ? 'none' : 'block';
    envPanelToggle.textContent = isOpen ? 'aufklappen' : 'zuklappen';
    if (!isOpen) {
      loadEnvConfig();
    }
  });
}

if (runsPanelHeader && runsPanelBody && runsPanelToggle) {
  runsPanelHeader.addEventListener('click', () => {
    const isOpen = runsPanelBody.style.display === 'block';
    runsPanelBody.style.display = isOpen ? 'none' : 'block';
    runsPanelToggle.textContent = isOpen ? 'aufklappen' : 'zuklappen';
  });
}

async function loadRunList() {
  if (!runsListContainer) return;
  try {
    runsListContainer.textContent = 'Lade vergangene Runs...';
    const res = await fetch(`${API_BASE}/runs`);
    if (!res.ok) throw new Error('Fehler beim Laden der Runs');
    const data = await res.json();
    const items = Array.isArray(data.items) ? data.items : [];
    if (!items.length) {
      runsListContainer.textContent = 'Noch keine Runs vorhanden.';
      return;
    }
    renderRunList(items.slice(0, 20));
  } catch (err) {
    console.error(err);
    runsListContainer.textContent = 'Fehler beim Laden der Runs.';
  }
}

function renderRunList(items) {
  if (!runsListContainer) return;

  const rowsHtml = items
    .map((run) => {
      const id = escapeHtml(run.id);
      const status = String(run.status || '');
      const statusLower = status.toLowerCase();
      const created = run.created_at ? new Date(run.created_at).toLocaleString() : '';
      const count =
        typeof run.requested_count === 'number' ? String(run.requested_count) : '';
      const model = run.llm_model ? String(run.llm_model) : '';
      const temp =
        typeof run.temperature === 'number' ? String(run.temperature) : '';

      return `
        <tr data-run-id="${id}">
          <td class="mono small">${id}</td>
          <td class="small">${escapeHtml(created)}</td>
          <td><span class="badge ${escapeHtml(statusLower)}">${escapeHtml(
        status
      )}</span></td>
          <td class="small">${escapeHtml(count)}</td>
          <td class="small">${escapeHtml(model)}</td>
          <td class="small">${escapeHtml(temp)}</td>
          <td class="small">
            <button type="button" class="primary small-btn" data-action="view" data-run-id="${id}">Anzeigen</button>
            <button type="button" class="primary small-btn" data-action="csv" data-run-id="${id}">CSV</button>
            <button type="button" class="primary small-btn" data-action="json" data-run-id="${id}">JSON</button>
            <button type="button" class="primary small-btn" data-action="report" data-run-id="${id}">Report</button>
            <button type="button" class="primary small-btn" data-action="compare" data-run-id="${id}">Vergleich</button>
            <button type="button" class="primary small-btn" data-action="delete" data-run-id="${id}">Löschen</button>
          </td>
        </tr>
      `;
    })
    .join('');

  runsListContainer.innerHTML = `
    <table>
      <thead>
        <tr>
          <th class="small">Run-ID</th>
          <th>Erstellt</th>
          <th>Status</th>
          <th>Texte</th>
          <th>Modell</th>
          <th>Temp</th>
          <th>Aktionen</th>
        </tr>
      </thead>
      <tbody>
        ${rowsHtml}
      </tbody>
    </table>
  `;

  const buttons = runsListContainer.querySelectorAll('button[data-run-id]');
  buttons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const action = btn.dataset.action;
      const runId = btn.dataset.runId;
      handleRunListAction(action, runId);
    });
  });
}

async function handleRunListAction(action, runId) {
  if (!runId) return;

  if (action === 'view') {
    await loadRunById(runId);
  } else if (action === 'csv') {
    window.open(`${API_BASE}/runs/${runId}/export?format=csv`, '_blank');
  } else if (action === 'json') {
    window.open(`${API_BASE}/runs/${runId}/summary_export`, '_blank');
  } else if (action === 'report') {
    window.open(`${API_BASE}/runs/${runId}/report`, '_blank');
  } else if (action === 'compare') {
    toggleCompare(runId);
  } else if (action === 'delete') {
    const confirmed = window.confirm('Diesen Run wirklich löschen?');
    if (!confirmed) return;
    try {
      const res = await fetch(`${API_BASE}/runs/${runId}`, { method: 'DELETE' });
      if (!res.ok && res.status !== 204) {
        throw new Error('Fehler beim Löschen');
      }
      if (currentRunId === runId) {
        currentRunId = null;
        runIdEl.textContent = '–';
        summaryEl.textContent = '–';
        interpretationEl.textContent = '–';
        if (llmInterpretationEl) llmInterpretationEl.textContent = '–';
        if (runModelInfoEl) runModelInfoEl.textContent = 'Modell: –';
        progressText.textContent = '–';
        progressBar.style.width = '0%';
        rowsBody.innerHTML =
          '<tr><td colspan="10" class="small">Noch keine Ergebnisse.</td></tr>';
      }
      await loadRunList();
    } catch (err) {
      console.error(err);
      window.alert('Fehler beim Löschen des Runs.');
    }
  }
}

async function loadRunById(runId) {
  try {
    currentRunId = runId;
    runIdEl.textContent = runId;
    csvLink.href = `${API_BASE}/runs/${runId}/export?format=csv`;
    jsonSummaryLink.href = `${API_BASE}/runs/${runId}/summary_export`;
    if (reportLink) {
      reportLink.href = `${API_BASE}/runs/${runId}/report`;
      reportLink.style.pointerEvents = 'auto';
      reportLink.style.opacity = '';
    }
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    const res = await fetch(`${API_BASE}/runs/${runId}`);
    if (!res.ok) throw new Error('Run nicht gefunden');
    const data = await res.json();
    if (runModelInfoEl) {
      const tempLabel =
        typeof data.temperature === 'number' ? String(data.temperature) : '–';
      runModelInfoEl.textContent = `Modell: ${data.llm_model || '–'} (Temp: ${tempLabel})`;
    }
    updateStatus(data);
    await loadRows();
  } catch (err) {
    console.error(err);
    statusEl.textContent = 'Fehler beim Laden des ausgewählten Runs.';
  }
}

if (envSaveBtn) {
  envSaveBtn.addEventListener('click', async () => {
    try {
      envSaveBtn.disabled = true;
      envStatus.textContent = 'Speichere .env...';
      const payload = {
        openai_api_key: envOpenAiKey.value || null,
        openai_model: envOpenAiModel.value || null,
        openai_base_url: envOpenAiBaseUrl.value || null,
        backend_port: envBackendPort.value ? Number(envBackendPort.value) : null,
        frontend_port_base: envFrontendPortBase.value
          ? Number(envFrontendPortBase.value)
          : null,
      };

      const res = await fetch(`${API_BASE}/env-config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error('Fehler beim Speichern der Env-Konfiguration');
      const data = await res.json();
      envStatus.textContent =
        'Gespeichert. Bitte Backend mit ./start.sh neu starten, damit die Änderungen wirksam werden.';

      // Felder mit normalisierten Werten aktualisieren
      if (envOpenAiModel) envOpenAiModel.value = data.openai_model || '';
      if (envOpenAiBaseUrl) envOpenAiBaseUrl.value = data.openai_base_url || '';
      if (envBackendPort) envBackendPort.value = data.backend_port || '';
      if (envFrontendPortBase) envFrontendPortBase.value = data.frontend_port_base || '';
    } catch (err) {
      console.error(err);
      envStatus.textContent = 'Fehler beim Speichern der .env.';
    } finally {
      envSaveBtn.disabled = false;
    }
  });
}

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
    if (runModelInfoEl) {
      const tempLabel =
        typeof data.temperature === 'number' ? String(data.temperature) : '–';
      runModelInfoEl.textContent = `Modell: ${data.llm_model || '–'} (Temp: ${tempLabel})`;
    }
    csvLink.href = `${API_BASE}/runs/${data.id}/export?format=csv`;
    jsonSummaryLink.href = `${API_BASE}/runs/${data.id}/summary_export`;
    if (reportLink) {
      reportLink.href = `${API_BASE}/runs/${data.id}/report`;
      reportLink.style.pointerEvents = 'none';
      reportLink.style.opacity = '0.5';
    }
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
  const analysis = summary.analysis || {};
  const interpretation = analysis.interpretation || '–';
  const llmInterpretation = analysis.llm_summary || '–';
  interpretationEl.textContent = interpretation;
  if (llmInterpretationEl) {
    llmInterpretationEl.textContent = llmInterpretation;
  }
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

  if (reportLink) {
    const isCompleted = String(run.status || '').toLowerCase() === 'completed';
    if (currentRunId && isCompleted) {
      reportLink.href = `${API_BASE}/runs/${currentRunId}/report`;
      reportLink.style.pointerEvents = 'auto';
      reportLink.style.opacity = '';
    } else {
      reportLink.href = '#';
      reportLink.style.pointerEvents = 'none';
      reportLink.style.opacity = '0.5';
    }
  }
}

async function loadRows() {
  if (!currentRunId) return;
  try {
    const res = await fetch(`${API_BASE}/runs/${currentRunId}/rows`);
    if (!res.ok) throw new Error('Fehler beim Laden der Zeilen');
    const rows = await res.json();
    allRows = rows;

    // Domänen-Filteroptionen aus den geladenen Zeilen ableiten
    if (filterDomain) {
      const domains = Array.from(new Set(allRows.map((r) => r.domain))).sort();
      filterDomain.innerHTML = '<option value="">Alle Domänen</option>' +
        domains.map((d) => `<option value="${escapeHtml(d)}">${escapeHtml(d)}</option>`).join('');
    }

    applyFiltersAndRenderRows();
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
