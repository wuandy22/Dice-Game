// ── Constants ─────────────────────────────────────────────────────────────
const DICE_EMOJI = ['', '⚀', '⚁', '⚂', '⚃', '⚄', '⚅'];
const COUNTDOWN_TOTAL = 10;

// ── State ─────────────────────────────────────────────────────────────────
let myName = localStorage.getItem('diceAuctionName') || null;
let myDice = [];
let publicState = {};
let countdownVal = COUNTDOWN_TOTAL;

// ── Socket ────────────────────────────────────────────────────────────────
const socket = io();

socket.on('connect', () => {
  if (myName) {
    socket.emit('request_rejoin', { name: myName });
  } else {
    showJoinModal();
  }
});

socket.on('rejoin_result', (data) => {
  if (data.success) {
    myName = data.name;
    hideJoinModal();
  } else {
    myName = null;
    localStorage.removeItem('diceAuctionName');
    showJoinModal();
  }
});

socket.on('register_result', (data) => {
  if (data.success) {
    myName = data.name;
    localStorage.setItem('diceAuctionName', myName);
    hideJoinModal();
  } else {
    document.getElementById('join-error').textContent = data.error;
  }
});

socket.on('public_state', (state) => {
  publicState = state;
  renderAll(state);
});

socket.on('private_dice', (data) => {
  if (data.name === myName) {
    myDice = data.dice;
    renderMyDiceTab();
    renderRollingDice();
    renderChooseDice();
    renderExchangeDice();
  }
});

socket.on('auction_tick', (data) => {
  countdownVal = data.remaining;
  updateCountdown(data.remaining, data.bid, data.leader);
});

socket.on('bid_error', (data) => {
  const el = document.getElementById('bid-error-msg');
  if (el) { el.textContent = data.message; }
});

socket.on('error_msg', (data) => {
  alert(data.message);
});

// ── Join modal ─────────────────────────────────────────────────────────────
function showJoinModal() {
  document.getElementById('join-modal').classList.remove('hidden');
}
function hideJoinModal() {
  document.getElementById('join-modal').classList.add('hidden');
}

document.getElementById('join-form').addEventListener('submit', (e) => {
  e.preventDefault();
  const name = document.getElementById('name-input').value.trim();
  if (!name) return;
  document.getElementById('join-error').textContent = '';
  socket.emit('register', { name });
});

// ── Main render ────────────────────────────────────────────────────────────
function renderAll(s) {
  if (s.phase !== 'auction_choose') chooseSelectedIndices = [];
  renderHeader(s);
  renderPhasePanel(s);
  renderChipsTab(s);
  renderHistory(s);
  // Refresh dice sub-renders for phase-aware UI
  renderMyDiceTab();
  renderRollingDice();
  renderChooseDice();
  renderExchangeDice();
}

function renderHeader(s) {
  const roundLabel = s.total_rounds > 0
    ? `Round ${s.round_num} of ${s.total_rounds}`
    : (s.round_num > 0 ? `Round ${s.round_num}` : '');
  const subRoundLabel = s.four_dice_mode && ['auction_choose','auction_live','exchange'].includes(s.phase)
    ? `  ·  Auction ${s.auction_sub_round}/2` : '';
  document.getElementById('header-center').textContent =
    phaseLabel(s.phase) + (roundLabel ? `  ·  ${roundLabel}` : '') + subRoundLabel;
  document.getElementById('pot-chips').textContent = s.pot;
  document.getElementById('mode-badge').classList.toggle('hidden', !s.four_dice_mode);
  document.getElementById('exit-game-btn').classList.toggle('hidden', s.phase === 'lobby');
}

function phaseLabel(phase) {
  return {
    lobby:          'Lobby',
    rolling:        'Roll Phase',
    auction_choose: 'Auction',
    auction_live:   'Live Auction',
    exchange:       'Exchange',
    payout:         'Scoring',
    game_over:      'Game Over',
  }[phase] || phase;
}

// ── Phase panels ───────────────────────────────────────────────────────────
const PANELS = ['lobby','rolling','auction-choose','auction-live','exchange','payout','game-over'];

function renderPhasePanel(s) {
  showPanel(s.phase);

  switch (s.phase) {
    case 'lobby':          renderLobby(s);        break;
    case 'rolling':        renderRolling(s);      break;
    case 'auction_choose': renderChoose(s);       break;
    case 'auction_live':   renderAuctionLive(s);  break;
    case 'exchange':       renderExchange(s);     break;
    case 'payout':         renderPayout(s);       break;
    case 'game_over':      renderGameOver(s);     break;
  }
}

function showPanel(phase) {
  PANELS.forEach(p => document.getElementById('p-' + p).classList.add('hidden'));
  const id = 'p-' + phase.replace(/_/g, '-');
  const el = document.getElementById(id);
  if (el) el.classList.remove('hidden');
}

// ── Lobby ──────────────────────────────────────────────────────────────────
function renderLobby(s) {
  const list = document.getElementById('lobby-player-list');
  list.innerHTML = s.players.map(p =>
    `<span class="player-chip${p.name === myName ? ' you' : ''}">${esc(p.name)}${p.name === myName ? ' (you)' : ''}</span>`
  ).join('');

  const myRegistered = s.players.some(p => p.name === myName);
  document.getElementById('start-area').classList.toggle('hidden', !myRegistered);

  const hint = document.getElementById('lobby-hint');
  hint.textContent = s.players.length < 3
    ? `Waiting for players… (${s.players.length}/3 minimum joined)`
    : `${s.players.length} players ready.`;

  document.getElementById('start-btn').disabled = s.players.length < 3;

  const on = s.four_dice_mode;
  document.getElementById('mode-toggle-btn').textContent = `4 Dice Mode: ${on ? 'ON' : 'OFF'}`;
  document.getElementById('mode-toggle-btn').className = `btn ${on ? 'btn-warning' : 'btn-neutral'}`;
  document.getElementById('mode-desc').textContent = on
    ? '4 dice per player · Four-of-a-kind = 4 shares · Trips don\'t score'
    : '';
}

document.getElementById('start-btn').addEventListener('click', () => {
  const rounds = parseInt(document.getElementById('rounds-input').value) || 0;
  socket.emit('start_game', { total_rounds: rounds });
});

document.getElementById('mode-toggle-btn').addEventListener('click', () => {
  socket.emit('toggle_mode');
});

document.getElementById('leave-lobby-btn').addEventListener('click', () => {
  socket.emit('leave_lobby');
});

document.getElementById('exit-game-btn').addEventListener('click', () => {
  if (confirm('End the current game and return everyone to the lobby?')) {
    socket.emit('exit_game');
  }
});

socket.on('left_lobby', () => {
  myName = null;
  localStorage.removeItem('diceAuctionName');
  showJoinModal();
});

// ── Rolling ────────────────────────────────────────────────────────────────
function renderRolling(s) {
  const waiting = s.players
    .filter(p => !s.ready_players.includes(p.name))
    .map(p => esc(p.name))
    .join(', ');
  document.getElementById('rolling-waiting').textContent =
    waiting ? `Waiting for: ${waiting}` : 'Everyone is ready!';

  const btn = document.getElementById('ready-btn');
  const alreadyReady = s.ready_players.includes(myName);
  btn.disabled = alreadyReady;
  btn.textContent = alreadyReady ? '✓ Ready' : 'I\'ve seen my dice — Ready';
}

function renderRollingDice() {
  const el = document.getElementById('rolling-my-dice');
  if (!el) return;
  el.innerHTML = diceRowHtml(myDice, false, null);
}

document.getElementById('ready-btn').addEventListener('click', () => {
  socket.emit('mark_ready');
});

// ── Auction choose ─────────────────────────────────────────────────────────
let chooseSelectedIndices = [];

function renderChoose(s) {
  const isAuctioner = s.auctioner === myName;
  document.getElementById('choose-own').classList.toggle('hidden', !isAuctioner);
  document.getElementById('choose-waiting').classList.toggle('hidden', isAuctioner);

  if (!isAuctioner) {
    document.getElementById('choose-waiting-name').textContent = s.auctioner || '…';
    chooseSelectedIndices = [];
  }
}

function renderChooseDice() {
  if (!publicState || publicState.phase !== 'auction_choose') return;
  if (publicState.auctioner !== myName) return;
  const el = document.getElementById('choose-dice-row');
  const confirmBtn = document.getElementById('auction-confirm-btn');
  if (!el || !confirmBtn) return;

  // Determine which indices should be dulled
  const dulledIndices = new Set();
  if (chooseSelectedIndices.length === 1) {
    const selVal = myDice[chooseSelectedIndices[0]]?.value;
    myDice.forEach((d, i) => {
      if (!chooseSelectedIndices.includes(i) && d.value !== selVal) dulledIndices.add(i);
    });
  } else if (chooseSelectedIndices.length === 2) {
    myDice.forEach((d, i) => { if (!chooseSelectedIndices.includes(i)) dulledIndices.add(i); });
  }

  el.innerHTML = `<div class="dice-row">${myDice.map((d, i) => {
    const face = d.value ? DICE_EMOJI[d.value] : '?';
    const isSelected = chooseSelectedIndices.includes(i);
    const isDulled   = dulledIndices.has(i);
    const cls = ['die', 'clickable', isSelected ? 'selected' : '', isDulled ? 'dulled' : ''].filter(Boolean).join(' ');
    return `<div style="text-align:center">
      <div class="${cls}" onclick="handleChooseDieClick(${i})">${face}</div>
      <div class="die-label">Die ${i + 1}</div>
    </div>`;
  }).join('')}</div>`;

  const isPair = chooseSelectedIndices.length === 2;
  confirmBtn.classList.remove('hidden');
  confirmBtn.disabled = chooseSelectedIndices.length === 0;
  confirmBtn.textContent = isPair ? 'Auction Pair' : 'Auction Die';
}

window.handleChooseDieClick = (idx) => {
  if (chooseSelectedIndices.includes(idx)) {
    // Deselect
    chooseSelectedIndices = chooseSelectedIndices.filter(i => i !== idx);
  } else if (chooseSelectedIndices.length === 0) {
    chooseSelectedIndices = [idx];
  } else if (chooseSelectedIndices.length === 1) {
    const selVal = myDice[chooseSelectedIndices[0]]?.value;
    if (myDice[idx]?.value === selVal && publicState.four_dice_mode) {
      chooseSelectedIndices = [chooseSelectedIndices[0], idx];  // form pair
    } else {
      chooseSelectedIndices = [idx];  // replace selection
    }
  } else {
    chooseSelectedIndices = [idx];  // start over
  }
  renderChooseDice();
};

function confirmAuction() {
  if (chooseSelectedIndices.length === 0) return;
  socket.emit('confirm_auction_dice', { indices: [...chooseSelectedIndices] });
  chooseSelectedIndices = [];
}

// ── Auction live ───────────────────────────────────────────────────────────
function renderAuctionLive(s) {
  document.getElementById('auction-auctioner').textContent = s.auctioner || '…';
  const dieEl = document.getElementById('auction-die');
  const dice = s.auctioned_dice && s.auctioned_dice.length > 0 ? s.auctioned_dice : (s.auctioned_die !== null ? [s.auctioned_die] : []);
  if (dice.length > 1) {
    dieEl.outerHTML = `<div id="auction-die" style="display:flex;gap:8px">${dice.map(v => `<div class="die revealed">${DICE_EMOJI[v]}</div>`).join('')}</div>`;
  } else {
    const singleDie = document.getElementById('auction-die');
    if (singleDie.tagName === 'DIV' && singleDie.style.display === 'flex') {
      singleDie.outerHTML = `<div class="die revealed" id="auction-die">${dice.length ? DICE_EMOJI[dice[0]] : '?'}</div>`;
    } else {
      singleDie.textContent = dice.length ? DICE_EMOJI[dice[0]] : '?';
      singleDie.className = 'die' + (dice.length ? ' revealed' : '');
    }
  }

  updateBidStatus(s.current_bid, s.bid_leader);

  const isSelling = s.auctioner === myName;
  const isLeader  = s.bid_leader === myName;
  document.getElementById('bid-controls').classList.toggle('hidden', isSelling);
  document.getElementById('you-are-selling').classList.toggle('hidden', !isSelling);

  if (!isSelling) {
    const nextBid = (s.current_bid || 0) + 1;
    document.getElementById('quick-bid-label').textContent = nextBid;
    const canBid = !isLeader;
    document.getElementById('quick-bid-btn').disabled = !canBid;
    document.getElementById('custom-bid-btn').disabled = !canBid;
    document.getElementById('bid-error-msg').textContent =
      isLeader ? 'You are the current leader.' : '';
  }

  // Init countdown bar width if we just entered this phase
  updateCountdown(s.countdown || COUNTDOWN_TOTAL, s.current_bid, s.bid_leader);
}

function updateBidStatus(bid, leader) {
  const el = document.getElementById('bid-status');
  if (!el) return;
  if (!leader) {
    el.innerHTML = 'No bids yet.';
  } else {
    const you = leader === myName ? ' <em>(you)</em>' : '';
    el.innerHTML = `Current bid: <strong>${bid}</strong> chips — <span class="leader">${esc(leader)}${you}</span>`;
  }
  // Update quick-bid button label
  const lbl = document.getElementById('quick-bid-label');
  if (lbl) lbl.textContent = (bid || 0) + 1;
}

function updateCountdown(remaining, bid, leader) {
  const fill = document.getElementById('countdown-fill');
  const text = document.getElementById('countdown-text');
  if (!fill || !text) return;
  const pct = Math.max(0, Math.min(100, (remaining / COUNTDOWN_TOTAL) * 100));
  fill.style.width = pct + '%';
  text.textContent = remaining.toFixed(1) + 's';
  if (bid !== undefined) updateBidStatus(bid, leader);
}

document.getElementById('quick-bid-btn').addEventListener('click', () => {
  const next = (publicState.current_bid || 0) + 1;
  document.getElementById('bid-error-msg').textContent = '';
  socket.emit('bid', { amount: next });
});

document.getElementById('custom-bid-btn').addEventListener('click', () => {
  const raw = document.getElementById('custom-bid-input').value.trim();
  const val = parseInt(raw, 10);
  document.getElementById('bid-error-msg').textContent = '';
  if (!Number.isInteger(val) || val < 1 || String(val) !== raw) {
    document.getElementById('bid-error-msg').textContent = 'Enter a positive whole number.';
    return;
  }
  socket.emit('bid', { amount: val });
  document.getElementById('custom-bid-input').value = '';
});

document.getElementById('custom-bid-input').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') document.getElementById('custom-bid-btn').click();
});

// ── Exchange ───────────────────────────────────────────────────────────────
function renderExchange(s) {
  const isWinner = s.exchange_winner === myName;
  document.getElementById('exchange-winner-view').classList.toggle('hidden', !isWinner);
  document.getElementById('exchange-waiting-view').classList.toggle('hidden', isWinner);

  if (isWinner) {
    const dice = s.auctioned_dice && s.auctioned_dice.length > 0 ? s.auctioned_dice : (s.auctioned_die !== null ? [s.auctioned_die] : []);
    document.getElementById('received-dice-display').innerHTML =
      dice.map(v => `<span class="die revealed" style="display:inline-flex;width:44px;height:44px;font-size:24px;vertical-align:middle">${DICE_EMOJI[v] || '?'}</span>`).join(' ');
    const stillNeeded = (s.exchange_picks_needed || 1) - (s.exchange_picks_so_far || 0);
    document.getElementById('exchange-pick-msg').textContent =
      stillNeeded > 1 ? `Pick ${stillNeeded} of your dice to give back:` : 'Pick one of your dice to give back:';
  } else {
    document.getElementById('exchange-winner-name').textContent = s.exchange_winner || '…';
    document.getElementById('exchange-bid-amount').textContent = s.current_bid;
  }
}

function renderExchangeDice() {
  if (!publicState || publicState.phase !== 'exchange') return;
  if (publicState.exchange_winner !== myName) return;
  const el = document.getElementById('exchange-dice-row');
  if (!el) return;
  el.innerHTML = diceRowHtml(myDice, true, (idx) => {
    socket.emit('choose_exchange_die', { index: idx });
  });
}

// ── Payout ─────────────────────────────────────────────────────────────────
function renderPayout(s) {
  const tbody = document.getElementById('payout-tbody');
  tbody.innerHTML = (s.payout_data || []).map(r => {
    const diceStr = (r.dice || []).map(v => DICE_EMOJI[v] || v).join(' ');
    const badges = [
      r.is_highest      ? '<span class="badge badge-high">Highest</span>'    : '',
      r.is_lowest       ? '<span class="badge badge-low">Lowest</span>'      : '',
      r.three_of_a_kind ? '<span class="badge badge-trips">Trips</span>'     : '',
      r.four_of_a_kind  ? '<span class="badge badge-quads">Quads ×2</span>'  : '',
    ].join('');
    const youMark = r.name === myName ? ' <span class="you-badge">you</span>' : '';
    return `<tr${r.chips_won > 0 ? ' class="winner-row"' : ''}>
      <td>${esc(r.name)}${youMark}</td>
      <td>${diceStr} <span style="color:var(--text-muted);font-size:.8rem">= ${r.total}</span>${badges}</td>
      <td>${r.shares}</td>
      <td>${r.chips_won > 0 ? '+' + r.chips_won : '—'}</td>
      <td><strong>${r.chips_now}</strong></td>
    </tr>`;
  }).join('');
}

document.getElementById('next-round-btn').addEventListener('click', () => {
  socket.emit('next_round');
});

// ── Game over ──────────────────────────────────────────────────────────────
function renderGameOver(s) {
  const sorted = [...s.players].sort((a, b) => b.chips - a.chips);
  const medals = ['🥇', '🥈', '🥉'];
  document.getElementById('standings').innerHTML = sorted.map((p, i) => {
    const you = p.name === myName ? ' <span class="you-badge">you</span>' : '';
    return `<div class="standing-row">
      <div class="standing-rank">${medals[i] || (i + 1)}</div>
      <div class="standing-name">${esc(p.name)}${you}</div>
      <div class="standing-chips">${p.chips} chips</div>
    </div>`;
  }).join('');
}

// ── Chips tab ──────────────────────────────────────────────────────────────
function renderChipsTab(s) {
  const maxChips = Math.max(...s.players.map(p => p.chips), 1);
  document.getElementById('chips-tbody').innerHTML = s.players.map(p => {
    const pct = Math.min(100, Math.round((p.chips / maxChips) * 100));
    const you = p.name === myName ? '<span class="you-badge">you</span>' : '';
    const dot = p.connected ? '<span class="online-dot"></span>' : '<span class="offline-dot"></span>';
    return `<tr>
      <td>${dot}${esc(p.name)} ${you}</td>
      <td><strong>${p.chips}</strong></td>
      <td style="width:120px">
        <div class="chips-bar-track">
          <div class="chips-bar-fill" style="width:${pct}%"></div>
        </div>
      </td>
    </tr>`;
  }).join('');
}

// ── History ────────────────────────────────────────────────────────────────
let renderedHistoryLen = 0;

function renderHistory(s) {
  const list = document.getElementById('history-list');
  if ((s.history || []).length === renderedHistoryLen) return;
  renderedHistoryLen = (s.history || []).length;
  list.innerHTML = [...(s.history || [])].reverse().map(h => {
    if (typeof h === 'object') {
      if (h.type === 'exchange') {
        const winnerGot   = (Array.isArray(h.winner_got)   ? h.winner_got   : [h.winner_got]).map(v => DICE_EMOJI[v]).join(' ');
        const auctionerGot = (Array.isArray(h.auctioner_got) ? h.auctioner_got : [h.auctioner_got]).map(v => DICE_EMOJI[v]).join(' ');
        const inner =
          `<span class="hist-player">${esc(h.winner)}</span>: ${winnerGot}<br>` +
          `<span class="hist-player">${esc(h.auctioner)}</span>: ${auctionerGot}<br>` +
          `<span class="hist-meta">${esc(h.winner)} paid ${h.bid} to ${esc(h.auctioner)}</span>`;
        return `<div class="history-item">R${h.round}·${h.auction} &nbsp;${inner}</div>`;
      }
      if (h.type === 'no_bid') {
        const diceStr = (Array.isArray(h.dice) ? h.dice : [h.die]).map(v => DICE_EMOJI[v]).join(' ');
        return `<div class="history-item no-bid">R${h.round}·${h.auction} &nbsp;${esc(h.auctioner)}: ${diceStr} — no bids</div>`;
      }
      if (h.type === 'payout') {
        return `<div class="history-item payout">R${h.round} payout: ${esc(h.summary)}</div>`;
      }
    }
    // plain-string fallback (payout lines)
    let cls = 'history-item';
    if (String(h).includes('payout')) cls += ' payout';
    return `<div class="${cls}">${esc(String(h))}</div>`;
  }).join('');
}

// ── My dice tab ────────────────────────────────────────────────────────────
function renderMyDiceTab() {
  const el = document.getElementById('my-dice-row');
  if (!el) return;
  el.innerHTML = myDice.length > 0
    ? diceRowHtml(myDice, false, null)
    : '<span style="color:var(--text-muted);font-size:.9rem">Dice not yet dealt.</span>';
}

// ── Tabs ───────────────────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + tab).classList.add('active');
  });
});

// ── Helpers ────────────────────────────────────────────────────────────────

// Global die-click handler (set before rendering clickable dice)
window._dieClickHandler = null;
window.handleDieClick = (idx) => {
  if (window._dieClickHandler) window._dieClickHandler(idx);
};

function diceRowHtml(dice, clickable, onClick) {
  if (!dice || dice.length === 0) return '';
  if (clickable && onClick) window._dieClickHandler = onClick;
  return `<div class="dice-row">${dice.map((d, i) => {
    const face    = d.value ? DICE_EMOJI[d.value] : '?';
    const cls     = ['die', clickable ? 'clickable' : ''].filter(Boolean).join(' ');
    const handler = clickable && onClick ? `onclick="handleDieClick(${i})"` : '';
    const label   = clickable ? `<div class="die-label">Die ${i + 1}</div>` : '';
    return `<div style="text-align:center"><div class="${cls}" ${handler}>${face}</div>${label}</div>`;
  }).join('')}</div>`;
}

function esc(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
