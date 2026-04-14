/* ═══════════════════════════════════════════════════════════════
   2026 FIFA World Cup Predictor — app.js
   All data comes from /api/predict (Flask → API-Football).
   ═══════════════════════════════════════════════════════════════ */

'use strict';

// ── Flag emoji map (used when API doesn't supply a logo URL) ────
const FLAGS = {
  "Argentina": "🇦🇷", "Australia":   "🇦🇺", "Belgium":     "🇧🇪",
  "Brazil":    "🇧🇷", "Canada":      "🇨🇦", "Colombia":    "🇨🇴",
  "Croatia":   "🇭🇷", "England":     "🏴󠁧󠁢󠁥󠁮󠁧󠁿", "France":     "🇫🇷",
  "Germany":   "🇩🇪", "Italy":       "🇮🇹", "Japan":       "🇯🇵",
  "Mexico":    "🇲🇽", "Morocco":     "🇲🇦", "Netherlands": "🇳🇱",
  "Portugal":  "🇵🇹", "Senegal":     "🇸🇳", "Spain":       "🇪🇸",
  "Uruguay":   "🇺🇾", "USA":         "🇺🇸", "South Korea": "🇰🇷",
  "Ecuador":   "🇪🇨", "Venezuela":   "🇻🇪", "Switzerland": "🇨🇭",
  "Denmark":   "🇩🇰", "Austria":     "🇦🇹", "Poland":      "🇵🇱",
  "Czechia":   "🇨🇿", "Serbia":      "🇷🇸", "Slovakia":    "🇸🇰",
  "Scotland":  "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "Turkey":     "🇹🇷", "Ukraine":    "🇺🇦",
  "Hungary":   "🇭🇺", "Romania":     "🇷🇴", "Greece":      "🇬🇷",
  "Slovenia":  "🇸🇮", "Albania":     "🇦🇱", "Georgia":     "🇬🇪",
  "Costa Rica":"🇨🇷", "Panama":      "🇵🇦", "Jamaica":     "🇯🇲",
  "Iran":      "🇮🇷", "Saudi Arabia":"🇸🇦", "Qatar":       "🇶🇦",
  "Iraq":      "🇮🇶", "Jordan":      "🇯🇴", "Nigeria":     "🇳🇬",
  "Egypt":     "🇪🇬",
};

const MEDAL_ICONS = { 1: "🥇", 2: "🥈", 3: "🥉", 4: "4th", 5: "5th" };

const METRIC_INFO = {
  "FIFA Ranking Score": {
    weight: "20%",
    desc: "Current FIFA world ranking inverted & normalised — #1 = 100/100. Uses live API data with embedded April 2026 rankings as fallback.",
  },
  "Player Performance": {
    weight: "20%",
    desc: "Per-team player quality score based on squad stars, depth, and individual club-level output (e.g. Mbappé, Bellingham, Vinicius Jr.).",
  },
  "Recent Form": {
    weight: "20%",
    desc: "Points earned in the last 10 competitive international fixtures, correctly attributed from each team's own perspective (home & away).",
  },
  "WC History": {
    weight: "12%",
    desc: "Average World Cup round reached across 2006–2022 tournaments.",
  },
  "Goal Difference": {
    weight: "10%",
    desc: "Goals scored minus conceded in the recent 10-match window.",
  },
  "Tournament Experience": {
    weight: "10%",
    desc: "Number of distinct World Cup appearances (up to 2022).",
  },
  "Squad Strength": {
    weight: "8%",
    desc: "Squad completeness bonus — rewards a full 23-man roster returned by the API.",
  },
};

// ── HTML escape (prevents XSS from API-returned data) ───────────
function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ── State ────────────────────────────────────────────────────────
let predictionData = null;
let allRows        = [];

// ── DOM refs ─────────────────────────────────────────────────────
const btnPredict      = document.getElementById('btnPredict');
const btnRefresh      = document.getElementById('btnRefresh');
const loadingOverlay  = document.getElementById('loadingOverlay');
const simCountEl      = document.getElementById('simCount');
const loadingBarFill  = document.getElementById('loadingBarFill');
const apiKeyBanner    = document.getElementById('apiKeyBanner');
const errorBanner     = document.getElementById('errorBanner');
const errorMsg        = document.getElementById('errorMsg');

// ── Init ──────────────────────────────────────────────────────────
checkHealth();

btnPredict.addEventListener('click',  () => runPrediction('/api/predict'));
btnRefresh.addEventListener('click',  () => runPrediction('/api/predict/refresh', true));
document.getElementById('searchInput').addEventListener('input',  filterTable);
document.getElementById('confFilter').addEventListener('change', filterTable);

// ── Health check (warns about missing API key) ────────────────────
async function checkHealth() {
  try {
    const res  = await fetch('/api/health');
    const data = await res.json();
    if (!data.api_key_set) {
      apiKeyBanner.classList.remove('hidden');
    }
  } catch (_) { /* server not reachable yet */ }
}

// ── Main flow ─────────────────────────────────────────────────────
async function runPrediction(endpoint, isPost = false) {
  hideBanners();
  showLoading();

  try {
    const res = await fetch(endpoint, { method: isPost ? 'POST' : 'GET' });
    const data = await res.json();

    if (!res.ok || data.status === 'error') {
      throw new Error(data.message || `HTTP ${res.status}`);
    }

    predictionData = data;
  } catch (err) {
    hideLoading();
    showError(err.message);
    return;
  }

  hideLoading();
  renderAll();
}

// ── Render everything ─────────────────────────────────────────────
function renderAll() {
  renderWinner();
  renderPodium();
  renderMetrics();
  renderWinnerRadar();
  renderRankings();

  document.querySelectorAll('.hidden[id$="Section"]').forEach(s => s.classList.remove('hidden'));
  btnPredict.style.display = 'none';
  btnRefresh.style.display = 'inline-flex';

  setTimeout(() => {
    document.getElementById('winnerSection').scrollIntoView({ behavior: 'smooth', block: 'start' });
  }, 100);

  setTimeout(animateMetricBars, 500);
  setTimeout(animateProbBars,   700);
  setTimeout(animateRadarBars,  900);
}

// ── Winner card ───────────────────────────────────────────────────
function renderWinner() {
  const w = predictionData.winner;
  const flag = w.flag || FLAGS[w.name] || '🏳';
  document.getElementById('winnerFlag').textContent     = flag;
  document.getElementById('winnerName').textContent     = w.name;
  document.getElementById('winnerProb').textContent     = `${w.win_probability}%`;
  document.getElementById('winnerFinal').textContent    = `${w.final_prob}%`;
  document.getElementById('winnerStrength').textContent = `${w.strength}/100`;
  document.getElementById('winnerRank').textContent     = `#${w.fifa_rank}`;
  spawnConfetti();
}

// ── Podium ────────────────────────────────────────────────────────
function renderPodium() {
  const top5 = predictionData.top_5;
  // Visual order: 2nd, 1st, 3rd, 4th, 5th
  const order = [1, 0, 2, 3, 4];
  const podiumEl = document.getElementById('podium');

  podiumEl.innerHTML = order.map(idx => {
    const t = top5[idx];
    if (!t) return '';
    const rank  = idx + 1;
    const sfx   = rank === 1 ? '1st' : rank === 2 ? '2nd' : rank === 3 ? '3rd' : rank === 4 ? '4th' : '5th';
    const flag  = t.flag || FLAGS[t.name] || '🏳';
    return `
      <div class="podium-item podium-item--${sfx}">
        <span class="podium-rank-badge">#${rank}</span>
        <div class="podium-item__medal">${MEDAL_ICONS[rank] || rank}</div>
        <div class="podium-item__flag">${esc(flag)}</div>
        <div class="podium-item__name">${esc(t.name)}</div>
        <div class="podium-item__prob">${esc(t.win_probability)}%</div>
        <div class="podium-item__label">Win Probability</div>
      </div>`;
  }).join('');
}

// ── Methodology metrics ───────────────────────────────────────────
function renderMetrics() {
  const grid = document.getElementById('metricsGrid');
  grid.innerHTML = Object.entries(METRIC_INFO).map(([name, info]) => {
    const pct = parseFloat(info.weight);
    return `
      <div class="metric-card">
        <div class="metric-card__header">
          <span class="metric-card__name">${name}</span>
          <span class="metric-card__weight">${info.weight}</span>
        </div>
        <div class="metric-bar-track">
          <div class="metric-bar-fill" data-target="${pct}" style="width:0%"></div>
        </div>
        <p class="metric-card__desc">${info.desc}</p>
      </div>`;
  }).join('');
}

function animateMetricBars() {
  document.querySelectorAll('.metric-bar-fill').forEach(bar => {
    bar.style.width = `${parseFloat(bar.dataset.target) * 4}%`;
  });
}

// ── Winner radar / metric breakdown ───────────────────────────────
function renderWinnerRadar() {
  const w = predictionData.winner;
  document.getElementById('radarSubtitle').textContent =
    `Live metric scores for ${w.name}`;

  const grid = document.getElementById('radarGrid');
  grid.innerHTML = Object.entries(w.metrics).map(([key, val]) => `
    <div class="radar-card">
      <div class="radar-card__name">${esc(key)}</div>
      <div class="radar-card__value">${esc(val)}</div>
      <div class="radar-card__bar-track">
        <div class="radar-card__bar-fill" data-target="${parseFloat(val) || 0}" style="width:0%"></div>
      </div>
    </div>`).join('');
}

function animateRadarBars() {
  document.querySelectorAll('.radar-card__bar-fill').forEach(bar => {
    bar.style.width = `${parseFloat(bar.dataset.target)}%`;
  });
}

// ── Rankings table ────────────────────────────────────────────────
function renderRankings() {
  const maxProb = predictionData.rankings[0].win_probability;

  allRows = predictionData.rankings.map((t, i) => {
    const flag      = t.flag || FLAGS[t.name] || '🏳';
    const rowCls    = i === 0 ? 'row--gold' : i === 1 ? 'row--silver' : i === 2 ? 'row--bronze' : '';
    const rankDisp  = i < 3
      ? `<span class="rank-badge rank-badge--${i+1}">${i+1}</span>`
      : `<span style="color:var(--clr-text-muted);padding-left:6px;">${i+1}</span>`;
    const barWidth  = maxProb > 0 ? (t.win_probability / maxProb * 100).toFixed(1) : 0;
    const hostTag   = ["USA","Canada","Mexico"].includes(t.name)
      ? `<span class="host-badge">Host</span>` : '';
    const confCls   = `conf-${t.confederation.replace(/[^A-Za-z0-9]/g, '')}`;

    return {
      team:          t.name,
      confederation: t.confederation,
      html: `
        <tr class="${rowCls}" data-team="${esc(t.name)}" data-conf="${esc(t.confederation)}"
            style="animation-delay:${i * 0.025}s">
          <td>${rankDisp}</td>
          <td>
            <div class="team-cell">
              <span class="team-flag-sm">${esc(flag)}</span>
              <span class="team-name-text">${esc(t.name)}</span>
              ${hostTag}
            </div>
          </td>
          <td class="prob-bar-cell">
            <div class="prob-bar">
              <div class="prob-bar__track">
                <div class="prob-bar__fill" data-width="${barWidth}" style="width:0%"></div>
              </div>
              <span class="prob-bar__val">${esc(t.win_probability)}%</span>
            </div>
          </td>
          <td>${esc(t.final_prob)}%</td>
          <td>${esc(t.semifinal_prob)}%</td>
          <td>${esc(t.strength)}/100</td>
          <td>#${esc(t.fifa_rank)}</td>
          <td><span class="conf-tag ${confCls}">${esc(t.confederation)}</span></td>
        </tr>`
    };
  });

  renderTableRows(allRows);
}

function renderTableRows(rows) {
  document.getElementById('rankingsBody').innerHTML = rows.map(r => r.html).join('');
}

function animateProbBars() {
  document.querySelectorAll('.prob-bar__fill').forEach(bar => {
    bar.style.width = `${bar.dataset.width}%`;
  });
}

function filterTable() {
  const query = document.getElementById('searchInput').value.toLowerCase().trim();
  const conf  = document.getElementById('confFilter').value;
  const filtered = allRows.filter(r => {
    const matchesSearch = !query || r.team.toLowerCase().includes(query);
    const matchesConf   = conf === 'ALL' || r.confederation === conf;
    return matchesSearch && matchesConf;
  });
  renderTableRows(filtered);
  setTimeout(animateProbBars, 80);
}

// ── Loading helpers ───────────────────────────────────────────────
function showLoading() {
  loadingOverlay.classList.remove('hidden');
  loadingBarFill.style.width = '0%';
  simCountEl.textContent = '0';
  let progress = 0;
  const timer = setInterval(() => {
    progress = Math.min(progress + Math.random() * 2.5, 94);
    loadingBarFill.style.width = `${progress}%`;
    simCountEl.textContent = Math.floor((progress / 100) * 50000).toLocaleString();
  }, 70);
  loadingOverlay._timer = timer;
}

function hideLoading() {
  clearInterval(loadingOverlay._timer);
  loadingBarFill.style.width = '100%';
  simCountEl.textContent = '50,000';
  setTimeout(() => loadingOverlay.classList.add('hidden'), 350);
}

// ── Error / banner helpers ────────────────────────────────────────
function showError(msg) {
  errorMsg.textContent = msg;
  errorBanner.classList.remove('hidden');
}

function hideBanners() {
  errorBanner.classList.add('hidden');
}

// ── Confetti ──────────────────────────────────────────────────────
function spawnConfetti() {
  const container = document.getElementById('confetti');
  container.innerHTML = '';
  const colours = ['#ffd200','#ff6d00','#00e676','#00b8d9','#fff','#ffea00'];
  for (let i = 0; i < 70; i++) {
    const p = document.createElement('div');
    p.className = 'confetti-piece';
    p.style.cssText = `
      left: ${Math.random() * 100}%;
      background: ${colours[Math.floor(Math.random() * colours.length)]};
      animation-duration: ${1.2 + Math.random() * 2}s;
      animation-delay: ${Math.random() * 1.8}s;
      border-radius: ${Math.random() > 0.5 ? '50%' : '2px'};
      width:  ${4 + Math.random() * 8}px;
      height: ${4 + Math.random() * 8}px;
    `;
    container.appendChild(p);
  }
}
