import './style.css';

type Player = {
  id: string;
  name: string;
  position: string;
  team?: string;
};

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

function renderResults(): void {
  const query = searchInput.value.trim().toLowerCase();
  const matches = players
    .filter((player) => !selected.has(player.id))
    .filter((player) => !query || playerLabel(player).toLowerCase().includes(query))
    .slice(0, 30);

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
  selectedCount.textContent = `${chosen.length} ${chosen.length === 1 ? 'player' : 'players'}`;
  submitButton.disabled = chosen.length === 0;
  selectedList.innerHTML = chosen.length
    ? chosen.map((player) => `
        <div class="selected-row">
          <span>${escapeText(playerLabel(player))}</span>
          <button class="remove-button" type="button" data-remove-id="${escapeText(player.id)}">Remove</button>
        </div>
      `).join('')
    : '<p class="muted">Your roster is waiting for its first pick.</p>';
}

async function loadPlayers(): Promise<void> {
  try {
    const response = await fetch('/players.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data: unknown = await response.json();
    if (!Array.isArray(data)) throw new Error('Player catalog must be an array');
    players = data as Player[];
    playerStatus.textContent = `${players.length} players available.`;
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
