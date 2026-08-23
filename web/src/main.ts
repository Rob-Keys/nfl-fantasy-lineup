import './style.css';

type Player = {
  id: string;
  name: string;
  position: string;
  team?: string;
};

type RosterSlot = {
  id: string;
  label: string;
  position: string;
};

const STARTING_SLOTS: RosterSlot[] = [
  { id: 'qb', label: 'QB', position: 'QB' },
  { id: 'rb-1', label: 'RB', position: 'RB' },
  { id: 'rb-2', label: 'RB', position: 'RB' },
  { id: 'wr-1', label: 'WR', position: 'WR' },
  { id: 'wr-2', label: 'WR', position: 'WR' },
  { id: 'te', label: 'TE', position: 'TE' },
  { id: 'flex', label: 'Flex', position: 'FLEX' },
  { id: 'k', label: 'K', position: 'K' },
  { id: 'dst', label: 'D/ST', position: 'DEF' },
];

const INITIAL_BENCH_SLOTS = 5;
const MAX_VISIBLE_RESULTS = 8;

const searchInput = document.querySelector<HTMLInputElement>('#player-search')!;
const results = document.querySelector<HTMLDivElement>('#player-results')!;
const selectedList = document.querySelector<HTMLDivElement>('#selected-players')!;
const selectedCount = document.querySelector<HTMLSpanElement>('#selected-count')!;
const playerStatus = document.querySelector<HTMLParagraphElement>('#player-status')!;
const requestStatus = document.querySelector<HTMLParagraphElement>('#request-status')!;
const requestResult = document.querySelector<HTMLPreElement>('#request-result')!;
const submitButton = document.querySelector<HTMLButtonElement>('#submit-lineup')!;

let players: Player[] = [];
const selected = new Map<string, Player>();

function escapeText(value: string): string {
  return value.replace(/[&<>'"]/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;'
  })[character] || character);
}

function playerLabel(player: Player): string {
  return `${player.name} · ${player.position}${player.team ? ` · ${player.team}` : ''}`;
}

function slotAcceptsPlayer(slot: RosterSlot, player: Player): boolean {
  return slot.position === 'FLEX'
    ? ['RB', 'WR', 'TE'].includes(player.position)
    : slot.position === player.position;
}

function assignRosterPlayers(chosen: Player[]): { starters: Map<string, Player>; bench: Player[] } {
  const starters = new Map<string, Player>();
  const bench: Player[] = [];

  for (const player of chosen) {
    const dedicatedSlot = STARTING_SLOTS.find((slot) =>
      slot.position !== 'FLEX' && slotAcceptsPlayer(slot, player) && !starters.has(slot.id));
    const flexSlot = STARTING_SLOTS.find((slot) =>
      slot.position === 'FLEX' && slotAcceptsPlayer(slot, player) && !starters.has(slot.id));
    const slot = dedicatedSlot || flexSlot;

    if (slot) {
      starters.set(slot.id, player);
    } else {
      bench.push(player);
    }
  }

  return { starters, bench };
}

function renderResults(): void {
  const query = searchInput.value.trim().toLowerCase();
  const matches = players
    .filter((player) => !selected.has(player.id))
    .filter((player) => !query || playerLabel(player).toLowerCase().includes(query))
    .slice(0, MAX_VISIBLE_RESULTS);

  results.innerHTML = matches.length
    ? matches.map((player) => `
        <button class="player-row" type="button" data-player-id="${escapeText(player.id)}">
          <span>${escapeText(player.name)}</span>
          <small>${escapeText(player.position)}${player.team ? ` · ${escapeText(player.team)}` : ''}</small>
        </button>
      `).join('')
    : '<p class="muted">No matching players.</p>';
}

function renderSelected(): void {
  const chosen = [...selected.values()];
  const { starters, bench } = assignRosterPlayers(chosen);
  const benchSlotCount = Math.max(
    INITIAL_BENCH_SLOTS,
    bench.length + (bench.length >= INITIAL_BENCH_SLOTS ? 1 : 0),
  );

  selectedCount.textContent = `${chosen.length} ${chosen.length === 1 ? 'player' : 'players'}`;
  submitButton.disabled = chosen.length === 0;

  const starterMarkup = STARTING_SLOTS.map((slot) => {
    const player = starters.get(slot.id);
    return `
      <div class="roster-slot${player ? ' roster-slot-filled' : ''}">
        <span class="roster-slot-label">${escapeText(slot.label)}</span>
        ${player
          ? `<span class="roster-player"><strong>${escapeText(player.name)}</strong><small>${escapeText(player.team || player.position)}</small></span>
             <button class="remove-button" type="button" data-remove-id="${escapeText(player.id)}" aria-label="Remove ${escapeText(player.name)}">×</button>`
          : '<span class="roster-empty">Open slot</span><span aria-hidden="true"></span>'}
      </div>
    `;
  }).join('');

  const benchMarkup = Array.from({ length: benchSlotCount }, (_, index) => {
    const player = bench[index];
    return `
      <div class="roster-slot${player ? ' roster-slot-filled' : ''}${index >= INITIAL_BENCH_SLOTS ? ' roster-slot-optional' : ''}">
        <span class="roster-slot-label">BE${index + 1}</span>
        ${player
          ? `<span class="roster-player"><strong>${escapeText(player.name)}</strong><small>${escapeText(player.team || player.position)}</small></span>
             <button class="remove-button" type="button" data-remove-id="${escapeText(player.id)}" aria-label="Remove ${escapeText(player.name)}">×</button>`
          : `<span class="roster-empty">${index >= INITIAL_BENCH_SLOTS ? 'Optional slot' : 'Open slot'}</span><span aria-hidden="true"></span>`}
      </div>
    `;
  }).join('');

  selectedList.innerHTML = `
    <div class="roster-group">
      <p class="roster-group-label">Starting lineup</p>
      <div class="roster-slots">${starterMarkup}</div>
    </div>
    <div class="roster-group bench-group">
      <p class="roster-group-label">Bench</p>
      <div class="roster-slots">${benchMarkup}</div>
    </div>
  `;
}

async function loadPlayers(): Promise<void> {
  try {
    const response = await fetch('/players.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data: unknown = await response.json();
    if (!Array.isArray(data)) throw new Error('Player catalog must be an array');
    players = data as Player[];
    playerStatus.textContent = `${players.length} players available. Search to narrow the list.`;
    renderResults();
  } catch (error) {
    playerStatus.textContent = 'Could not load the player catalog.';
    console.error(error);
  }
}

async function submitLineup(): Promise<void> {
  submitButton.disabled = true;
  requestStatus.textContent = 'Generating…';
  requestResult.hidden = true;

  try {
    const response = await fetch('/api/lineup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        players: [...selected.values()],
        scoring: 'ppr',
        lineup: { QB: 1, RB: 2, WR: 2, TE: 1, FLEX: 1, K: 1, DEF: 1 },
        sportsbooks: ['fanduel', 'betmgm', 'draftkings']
      })
    });
    const body: unknown = await response.json();
    if (!response.ok) throw new Error(typeof body === 'object' && body && 'error' in body
      ? String(body.error)
      : `Request failed with HTTP ${response.status}`);
    requestStatus.textContent = 'Lineup generated.';
    requestResult.textContent = JSON.stringify(body, null, 2);
    requestResult.hidden = false;
  } catch (error) {
    requestStatus.textContent = error instanceof Error ? error.message : 'Request failed.';
  } finally {
    submitButton.disabled = selected.size === 0;
  }
}

searchInput.addEventListener('input', renderResults);
results.addEventListener('click', (event) => {
  const button = (event.target as HTMLElement).closest<HTMLButtonElement>('[data-player-id]');
  if (!button) return;
  const player = players.find((candidate) => candidate.id === button.dataset.playerId);
  if (player) selected.set(player.id, player);
  renderSelected();
  renderResults();
});

selectedList.addEventListener('click', (event) => {
  const button = (event.target as HTMLElement).closest<HTMLButtonElement>('[data-remove-id]');
  if (!button) return;
  selected.delete(button.dataset.removeId || '');
  renderSelected();
  renderResults();
});

submitButton.addEventListener('click', submitLineup);
renderSelected();
void loadPlayers();
