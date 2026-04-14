/* ═══════════════════════════════════════════════════════════════
   bracket.js — Build-Your-Bracket feature
   Single-sided layout: R32 → R16 → QF → SF → Final (left to right)
   Groups A–L are the official 2026 WC draw (Washington DC, Nov 2025).
   ═══════════════════════════════════════════════════════════════ */
'use strict';

// ── Layout constants ─────────────────────────────────────────────
const BT = {
  H:        1600,  // total bracket height (fits 16 R32 matches with spacing)
  SLOT_H:   36,    // each team slot height (px)
  SLOT_GAP: 3,     // gap between the two team slots in one match
  COL_W:    145,   // round-column width (px)
  COL_GAP:  30,    // gap between adjacent columns — connector lines draw here
};
BT.MATCH_H = BT.SLOT_H * 2 + BT.SLOT_GAP;  // 75px

// ── Embedded fallback (used if /api/groups is unreachable) ───────
const FALLBACK_GROUPS = {
  "A": [
    {id:16,   name:"Mexico",                flag:"🇲🇽", confederation:"CONCACAF", strength:67},
    {id:821,  name:"South Africa",          flag:"🇿🇦", confederation:"CAF",      strength:56},
    {id:31,   name:"South Korea",           flag:"🇰🇷", confederation:"AFC",      strength:73},
    {id:765,  name:"Czechia",               flag:"🇨🇿", confederation:"UEFA",     strength:62},
  ],
  "B": [
    {id:43,   name:"Canada",                flag:"🇨🇦", confederation:"CONCACAF", strength:74},
    {id:820,  name:"Bosnia and Herzegovina",flag:"🇧🇦", confederation:"UEFA",     strength:62},
    {id:803,  name:"Qatar",                 flag:"🇶🇦", confederation:"AFC",      strength:54},
    {id:773,  name:"Switzerland",           flag:"🇨🇭", confederation:"UEFA",     strength:70},
  ],
  "C": [
    {id:6,    name:"Brazil",                flag:"🇧🇷", confederation:"CONMEBOL", strength:89},
    {id:20,   name:"Morocco",               flag:"🇲🇦", confederation:"CAF",      strength:81},
    {id:822,  name:"Haiti",                 flag:"🇭🇹", confederation:"CONCACAF", strength:47},
    {id:772,  name:"Scotland",              flag:"🏴󠁧󠁢󠁳󠁣󠁴󠁿", confederation:"UEFA",     strength:60},
  ],
  "D": [
    {id:3,    name:"USA",                   flag:"🇺🇸", confederation:"CONCACAF", strength:74},
    {id:819,  name:"Paraguay",              flag:"🇵🇾", confederation:"CONMEBOL", strength:61},
    {id:800,  name:"Australia",             flag:"🇦🇺", confederation:"AFC",      strength:64},
    {id:1523, name:"Türkiye",               flag:"🇹🇷", confederation:"UEFA",     strength:68},
  ],
  "E": [
    {id:5,    name:"Germany",               flag:"🇩🇪", confederation:"UEFA",     strength:80},
    {id:823,  name:"Curaçao",               flag:"🇨🇼", confederation:"CONCACAF", strength:48},
    {id:824,  name:"Côte d'Ivoire",         flag:"🇨🇮", confederation:"CAF",      strength:69},
    {id:21,   name:"Ecuador",               flag:"🇪🇨", confederation:"CONMEBOL", strength:62},
  ],
  "F": [
    {id:770,  name:"Netherlands",           flag:"🇳🇱", confederation:"UEFA",     strength:79},
    {id:30,   name:"Japan",                 flag:"🇯🇵", confederation:"AFC",      strength:76},
    {id:825,  name:"Sweden",                flag:"🇸🇪", confederation:"UEFA",     strength:75},
    {id:826,  name:"Tunisia",               flag:"🇹🇳", confederation:"CAF",      strength:58},
  ],
  "G": [
    {id:762,  name:"Belgium",               flag:"🇧🇪", confederation:"UEFA",     strength:75},
    {id:806,  name:"Egypt",                 flag:"🇪🇬", confederation:"CAF",      strength:60},
    {id:801,  name:"IR Iran",               flag:"🇮🇷", confederation:"AFC",      strength:58},
    {id:827,  name:"New Zealand",           flag:"🇳🇿", confederation:"OFC",      strength:47},
  ],
  "H": [
    {id:15,   name:"Spain",                 flag:"🇪🇸", confederation:"UEFA",     strength:86},
    {id:828,  name:"Cabo Verde",            flag:"🇨🇻", confederation:"CAF",      strength:51},
    {id:802,  name:"Saudi Arabia",          flag:"🇸🇦", confederation:"AFC",      strength:56},
    {id:13,   name:"Uruguay",               flag:"🇺🇾", confederation:"CONMEBOL", strength:68},
  ],
  "I": [
    {id:9,    name:"France",                flag:"🇫🇷", confederation:"UEFA",     strength:87},
    {id:32,   name:"Senegal",               flag:"🇸🇳", confederation:"CAF",      strength:73},
    {id:804,  name:"Iraq",                  flag:"🇮🇶", confederation:"AFC",      strength:51},
    {id:829,  name:"Norway",                flag:"🇳🇴", confederation:"UEFA",     strength:77},
  ],
  "J": [
    {id:7,    name:"Argentina",             flag:"🇦🇷", confederation:"CONMEBOL", strength:88},
    {id:830,  name:"Algeria",               flag:"🇩🇿", confederation:"CAF",      strength:67},
    {id:769,  name:"Austria",               flag:"🇦🇹", confederation:"UEFA",     strength:69},
    {id:805,  name:"Jordan",                flag:"🇯🇴", confederation:"AFC",      strength:49},
  ],
  "K": [
    {id:768,  name:"Portugal",              flag:"🇵🇹", confederation:"UEFA",     strength:82},
    {id:831,  name:"Congo DR",              flag:"🇨🇩", confederation:"CAF",      strength:57},
    {id:832,  name:"Uzbekistan",            flag:"🇺🇿", confederation:"AFC",      strength:54},
    {id:26,   name:"Colombia",              flag:"🇨🇴", confederation:"CONMEBOL", strength:74},
  ],
  "L": [
    {id:10,   name:"England",               flag:"🏴󠁧󠁢󠁥󠁮󠁧󠁿", confederation:"UEFA",     strength:84},
    {id:764,  name:"Croatia",               flag:"🇭🇷", confederation:"UEFA",     strength:71},
    {id:833,  name:"Ghana",                 flag:"🇬🇭", confederation:"CAF",      strength:60},
    {id:45,   name:"Panama",                flag:"🇵🇦", confederation:"CONCACAF", strength:53},
  ],
};

const GROUPS     = ['A','B','C','D','E','F','G','H','I','J','K','L'];
const ROUND_NEXT = { r32:'r16', r16:'qf', qf:'sf', sf:'final' };
const LABEL      = { r32:'Round of 32', r16:'Round of 16', qf:'Quarter-Finals', sf:'Semi-Finals', final:'FINAL' };

// Single-sided column order (left to right)
const ROUND_DEFS = [
  { round:'r32',   n:16 },
  { round:'r16',   n:8  },
  { round:'qf',    n:4  },
  { round:'sf',    n:2  },
  { round:'final', n:1  },
];

// ── State ────────────────────────────────────────────────────────
let groupsData     = null;
let picks          = {};
let rounds         = {};
let bracketWinners = {};

// ── Bootstrap ────────────────────────────────────────────────────
(async function init() {
  try {
    const res  = await fetch('/api/groups');
    const data = await res.json();
    groupsData = (data.status === 'ok') ? data.groups : FALLBACK_GROUPS;
  } catch (_) {
    groupsData = FALLBACK_GROUPS;
  }
  renderGroups();
  document.getElementById('btnGenerateBracket').addEventListener('click', generateBracket);
  document.getElementById('btnResetBracket').addEventListener('click', resetAll);
  document.getElementById('btnBackToGroups').addEventListener('click', backToGroups);
})();

// ═══════════════════════════════════════════════════════════════
// PHASE 1 — Group stage
// ═══════════════════════════════════════════════════════════════

function renderGroups() {
  const grid = document.getElementById('groupPickGrid');
  grid.innerHTML = '';
  GROUPS.forEach(letter => {
    const teams = groupsData[letter] || [];
    const card  = document.createElement('div');
    card.className = 'gpc';
    card.id = `gpc-${letter}`;
    card.innerHTML = `
      <div class="gpc__hdr">
        <span class="gpc__letter">GROUP ${esc(letter)}</span>
        <span class="gpc__badge" id="gpc-badge-${letter}">Pick 2</span>
      </div>
      <div class="gpc__teams">
        ${teams.map(t => `
          <div class="gpc__team" id="gpt-${letter}-${t.id}"
               data-grp="${esc(letter)}" data-id="${t.id}">
            <span class="gpc__flag">${esc(t.flag)}</span>
            <span class="gpc__name">${esc(t.name)}</span>
            <span class="gpc__check">&#10003;</span>
          </div>`).join('')}
      </div>`;
    grid.appendChild(card);
  });
  grid.addEventListener('click', e => {
    const row = e.target.closest('.gpc__team');
    if (row) togglePick(row.dataset.grp, parseInt(row.dataset.id));
  });
  updateProgress();
}

function togglePick(letter, teamId) {
  const team = (groupsData[letter] || []).find(t => t.id === teamId);
  if (!team) return;
  if (!picks[letter]) picks[letter] = [];
  const arr = picks[letter];
  const idx = arr.findIndex(t => t.id === teamId);
  if (idx >= 0) {
    arr.splice(idx, 1);
  } else {
    if (arr.length >= 2) return;
    arr.push(team);
  }
  (groupsData[letter] || []).forEach(t => {
    const row   = document.getElementById(`gpt-${letter}-${t.id}`);
    if (!row) return;
    const chosen = arr.some(p => p.id === t.id);
    const maxed  = arr.length >= 2 && !chosen;
    row.classList.toggle('gpc__team--selected', chosen);
    row.classList.toggle('gpc__team--dimmed',   maxed);
  });
  const badge = document.getElementById(`gpc-badge-${letter}`);
  if (badge) {
    if      (arr.length === 0) { badge.textContent = 'Pick 2'; badge.className = 'gpc__badge'; }
    else if (arr.length === 1) { badge.textContent = '1 / 2';  badge.className = 'gpc__badge gpc__badge--partial'; }
    else                       { badge.textContent = '✓ Done'; badge.className = 'gpc__badge gpc__badge--done'; }
  }
  updateProgress();
}

function updateProgress() {
  const complete = GROUPS.filter(g => (picks[g] || []).length === 2).length;
  const fill  = document.getElementById('bpFill');
  const label = document.getElementById('bpLabel');
  if (fill)  fill.style.width = `${(complete / 12) * 100}%`;
  if (label) label.innerHTML  = `<strong>${complete} / 12</strong> groups decided`;
  const btn = document.getElementById('btnGenerateBracket');
  if (btn) btn.disabled = (complete < 12);
}

// ═══════════════════════════════════════════════════════════════
// PHASE 2 — Bracket generation
// ═══════════════════════════════════════════════════════════════

function generateBracket() {
  const wildcards = selectWildcards();
  const firsts = {}, seconds = {};
  GROUPS.forEach(g => {
    const sorted = [...(picks[g] || [])].sort((a, b) => b.strength - a.strength);
    firsts[g]  = sorted[0];
    seconds[g] = sorted[1];
  });

  // 12 group-paired matches + 4 wildcard matches = 16 R32 matches
  const pairGroups = [['A','B'],['C','D'],['E','F'],['G','H'],['I','J'],['K','L']];
  const r32 = [];
  pairGroups.forEach(([g1, g2]) => {
    r32.push([firsts[g1],  seconds[g2]]);
    r32.push([firsts[g2],  seconds[g1]]);
  });
  for (let i = 0; i < wildcards.length; i += 2) {
    r32.push([wildcards[i], wildcards[i + 1] || {name:'TBD', flag:'🏳', id:-1, strength:0}]);
  }

  rounds         = { r32, r16:[], qf:[], sf:[], final:[] };
  bracketWinners = {};

  document.getElementById('groupsPhase').classList.add('hidden');
  document.getElementById('knockoutPhase').classList.remove('hidden');
  document.getElementById('bracketChampion').classList.add('hidden');
  document.getElementById('knockoutPhase').scrollIntoView({ behavior:'smooth', block:'start' });

  renderWildcardBanner(wildcards);
  renderBracketTree();
}

function selectWildcards() {
  const thirds = GROUPS.map(g => {
    const picked   = picks[g] || [];
    const unpicked = (groupsData[g] || []).filter(t => !picked.find(p => p.id === t.id));
    unpicked.sort((a, b) => b.strength - a.strength);
    return unpicked[0] ? { ...unpicked[0], _group: g } : null;
  }).filter(Boolean);
  thirds.sort((a, b) => b.strength - a.strength);
  return thirds.slice(0, 8);
}

function renderWildcardBanner(wildcards) {
  const banner = document.getElementById('wildcardsBanner');
  if (!banner) return;
  banner.innerHTML = `
    <div class="wc-banner">
      <strong>&#127183; 8 Wild-Card Teams Auto-Qualified (best 3rd-place by strength)</strong>
      <div class="wc-banner__teams">
        ${wildcards.map(t =>
          `<span class="wc-chip">${esc(t.flag)} ${esc(t.name)} <em>(Group ${esc(t._group)})</em></span>`
        ).join('')}
      </div>
    </div>`;
}

// ═══════════════════════════════════════════════════════════════
// Visual bracket — single-sided left-to-right
// ═══════════════════════════════════════════════════════════════

// Y-center of match i within a column of n evenly-distributed matches
function matchCenter(i, n) {
  return Math.round((2 * i + 1) * BT.H / (2 * n));
}

function getMatch(round, idx) {
  return (rounds[round] || [])[idx] || [null, null];
}

function teamHtml(team, round, matchIdx, side, winner, pos) {
  const tbd      = !team || team.id === -1;
  const isWinner = !tbd && winner && winner.id === team.id;
  const isLoser  = !tbd && winner && winner.id !== team.id;
  const cls = ['bt-team',
    pos === 'top' ? 'bt-team--top' : 'bt-team--bot',
    isWinner ? 'bt-team--winner' : '',
    isLoser  ? 'bt-team--loser'  : '',
    tbd      ? 'bt-team--tbd'    : '',
  ].filter(Boolean).join(' ');
  return `
    <div class="${cls}" style="height:${BT.SLOT_H}px;"
         data-round="${round}" data-match="${matchIdx}" data-side="${side}">
      <span class="bt-flag">${team ? esc(team.flag) : ''}</span>
      <span class="bt-name">${team ? esc(team.name) : 'TBD'}</span>
      ${isWinner ? '<span class="bt-crown">&#128081;</span>' : ''}
    </div>`;
}

function renderBracketTree() {
  const container = document.getElementById('knockoutRounds');

  function colHtml({ round, n }) {
    const isFinal = round === 'final';
    const matches = Array.from({ length: n }, (_, i) => {
      const pair   = getMatch(round, i);
      const winner = bracketWinners[`${round}-${i}`];
      const top    = matchCenter(i, n) - Math.floor(BT.MATCH_H / 2);
      return `
        <div class="bt-match${isFinal ? ' bt-match--final' : ''}" id="btm-${round}-${i}" style="top:${top}px;">
          ${teamHtml(pair[0], round, i, 0, winner, 'top')}
          <div class="bt-gap"></div>
          ${teamHtml(pair[1], round, i, 1, winner, 'bot')}
        </div>`;
    }).join('');

    const finWinner = isFinal ? bracketWinners['final-0'] : null;
    const finTop    = isFinal ? matchCenter(0, 1) - Math.floor(BT.MATCH_H / 2) : 0;
    const champHtml = finWinner ? `
      <div class="bt-champion-inline" style="top:${finTop + BT.MATCH_H + 20}px;">
        <div class="bt-champ-flag">${esc(finWinner.flag)}</div>
        <div class="bt-champ-name">${esc(finWinner.name)}</div>
        <div class="bt-champ-label">&#127942; Champion</div>
      </div>` : '';

    return `
      <div class="bt-col${isFinal ? ' bt-col--final' : ''}" id="btcol-${round}"
           style="width:${BT.COL_W}px; height:${BT.H}px;">
        <div class="bt-col-label${isFinal ? ' bt-col-label--final' : ''}">${LABEL[round]}</div>
        ${matches}
        ${champHtml}
      </div>`;
  }

  container.innerHTML = `
    <div class="bt-scroll">
      <div class="bt" id="bt">
        ${ROUND_DEFS.map(d => colHtml(d)).join('')}
        <svg class="bt-svg" id="btSvg"></svg>
      </div>
    </div>`;

  container.querySelectorAll('.bt-team[data-round]').forEach(el => {
    el.addEventListener('click', () => {
      pickWinner(el.dataset.round, parseInt(el.dataset.match), parseInt(el.dataset.side));
    });
  });

  requestAnimationFrame(drawConnectors);
}

// ── SVG connector lines (left to right for all rounds) ──────────

function drawConnectors() {
  const svgEl = document.getElementById('btSvg');
  const btEl  = document.getElementById('bt');
  if (!svgEl || !btEl) return;

  const btRect = btEl.getBoundingClientRect();
  svgEl.setAttribute('width',   btRect.width);
  svgEl.setAttribute('height',  btRect.height);
  svgEl.setAttribute('viewBox', `0 0 ${btRect.width} ${btRect.height}`);
  svgEl.innerHTML = '';

  function line(x1, y1, x2, y2) {
    const el = document.createElementNS('http://www.w3.org/2000/svg', 'line');
    el.setAttribute('x1', x1); el.setAttribute('y1', y1);
    el.setAttribute('x2', x2); el.setAttribute('y2', y2);
    el.setAttribute('stroke', 'rgba(0,0,0,0.18)');
    el.setAttribute('stroke-width', '1.5');
    svgEl.appendChild(el);
  }

  const roundPairs = [
    { fromR:'r32',   toR:'r16',   fromN:16, toN:8 },
    { fromR:'r16',   toR:'qf',    fromN:8,  toN:4 },
    { fromR:'qf',    toR:'sf',    fromN:4,  toN:2 },
    { fromR:'sf',    toR:'final', fromN:2,  toN:1 },
  ];

  roundPairs.forEach(({ fromR, toR, fromN, toN }) => {
    const fromEl = document.getElementById(`btcol-${fromR}`);
    const toEl   = document.getElementById(`btcol-${toR}`);
    if (!fromEl || !toEl) return;

    const fx   = fromEl.getBoundingClientRect().right - btRect.left;
    const tx   = toEl.getBoundingClientRect().left    - btRect.left;
    const midX = (fx + tx) / 2;

    for (let i = 0; i < toN; i++) {
      const y0   = matchCenter(i * 2,     fromN);
      const y1   = matchCenter(i * 2 + 1, fromN);
      const yOut = matchCenter(i,          toN);
      line(fx, y0,   midX, y0);    // top arm from match
      line(midX, y0, midX, y1);    // vertical bar
      line(fx, y1,   midX, y1);    // bottom arm from match
      line(midX, yOut, tx, yOut);  // output line to next round
    }
  });
}

// ── Pick a winner ────────────────────────────────────────────────

function pickWinner(round, matchIdx, side) {
  const pair = (rounds[round] || [])[matchIdx];
  if (!pair) return;
  const winner = pair[side];
  if (!winner || winner.id === -1) return;

  bracketWinners[`${round}-${matchIdx}`] = winner;

  const allPicked = rounds[round].every((_, i) => bracketWinners[`${round}-${i}`]);
  if (allPicked) {
    const nextRound = ROUND_NEXT[round];
    if (nextRound) {
      const wins = rounds[round].map((_, i) => bracketWinners[`${round}-${i}`]);
      const next = [];
      for (let i = 0; i < wins.length; i += 2) next.push([wins[i], wins[i + 1]]);
      rounds[nextRound] = next;
    }
  }

  renderBracketTree();

  if (round === 'final' && bracketWinners['final-0']) {
    const champEl = document.getElementById('bracketChampion');
    const w = bracketWinners['final-0'];
    document.getElementById('champFlag').textContent = w.flag || '🏆';
    document.getElementById('champName').textContent = w.name;
    champEl.classList.remove('hidden');
    setTimeout(() => champEl.scrollIntoView({ behavior:'smooth', block:'center' }), 200);
  }
}

// ── Navigation ───────────────────────────────────────────────────

function resetAll() {
  picks = {};
  rounds = {};
  bracketWinners = {};
  GROUPS.forEach(g => {
    (groupsData[g] || []).forEach(t => {
      const row = document.getElementById(`gpt-${g}-${t.id}`);
      if (row) row.classList.remove('gpc__team--selected', 'gpc__team--dimmed');
    });
    const badge = document.getElementById(`gpc-badge-${g}`);
    if (badge) { badge.textContent = 'Pick 2'; badge.className = 'gpc__badge'; }
  });
  updateProgress();
}

function backToGroups() {
  document.getElementById('groupsPhase').classList.remove('hidden');
  document.getElementById('knockoutPhase').classList.add('hidden');
}
