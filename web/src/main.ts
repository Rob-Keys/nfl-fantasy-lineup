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

type ProjectedStat = {
  value: number;
  sources?: string[];
  market_over_probability?: number;
};

type PlayerProjection = {
  player: Player;
  stats: Record<string, ProjectedStat>;
  fantasy_points: number;
};

type GeneratedLineup = {
  total_points: number;
  slots: Record<string, PlayerProjection[]>;
};

type LineupResponse = {
  lineup: GeneratedLineup;
  projections: PlayerProjection[];
  warnings?: string[];
};

type SavedTeam = {
  id: string;
  name: string;
  playerIds: string[];
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
const SELECTED_PLAYERS_STORAGE_KEY = 'roster-room:selected-player-ids';
const SAVED_TEAMS_STORAGE_KEY = 'roster-room:saved-teams';
const MAX_SAVED_TEAMS = 20;

const searchInput = document.querySelector<HTMLInputElement>('#player-search')!;
const results = document.querySelector<HTMLDivElement>('#player-results')!;
const selectedList = document.querySelector<HTMLDivElement>('#selected-players')!;
const selectedCount = document.querySelector<HTMLSpanElement>('#selected-count')!;
const playerStatus = document.querySelector<HTMLParagraphElement>('#player-status')!;
const requestStatus = document.querySelector<HTMLParagraphElement>('#request-status')!;
const requestResult = document.querySelector<HTMLDivElement>('#request-result')!;
const submitButton = document.querySelector<HTMLButtonElement>('#submit-lineup')!;
const teamNameInput = document.querySelector<HTMLInputElement>('#team-name')!;
const saveTeamButton = document.querySelector<HTMLButtonElement>('#save-team')!;
const savedTeamsList = document.querySelector<HTMLDivElement>('#saved-teams-list')!;
const savedTeamCount = document.querySelector<HTMLSpanElement>('#saved-team-count')!;
const savedTeamStatus = document.querySelector<HTMLParagraphElement>('#saved-team-status')!;

let players: Player[] = [];
const selected = new Map<string, Player>();

function createSavedTeamId(): string {
  return typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `team-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function readSavedTeams(): SavedTeam[] {
  try {
    const stored = window.localStorage.getItem(SAVED_TEAMS_STORAGE_KEY);
    if (!stored) return [];

    const parsed: unknown = JSON.parse(stored);
    if (!Array.isArray(parsed)) return [];

    return parsed.flatMap((item): SavedTeam[] => {
      if (!isRecord(item) || typeof item.id !== 'string' || typeof item.name !== 'string' || !Array.isArray(item.playerIds)) {
        return [];
      }
      const playerIds = [...new Set(item.playerIds.filter((id): id is string => typeof id === 'string'))];
      return item.name.trim() && playerIds.length ? [{ id: item.id, name: item.name.trim(), playerIds }] : [];
    }).slice(0, MAX_SAVED_TEAMS);
  } catch (error) {
    console.warn('Could not read saved teams.', error);
    return [];
  }
}

function persistSavedTeams(savedTeams: SavedTeam[]): void {
  try {
    window.localStorage.setItem(SAVED_TEAMS_STORAGE_KEY, JSON.stringify(savedTeams));
  } catch (error) {
    console.warn('Could not save teams.', error);
    savedTeamStatus.textContent = 'Could not save teams in this browser.';
  }
}

function readPersistedPlayerIds(): string[] {
  try {
    const stored = window.localStorage.getItem(SELECTED_PLAYERS_STORAGE_KEY);
    if (!stored) return [];

    const parsed: unknown = JSON.parse(stored);
    if (!Array.isArray(parsed)) return [];

    return [...new Set(parsed.filter((id): id is string => typeof id === 'string'))];
  } catch (error) {
    console.warn('Could not read the saved player selection.', error);
    return [];
  }
}

function persistSelectedPlayerIds(): void {
  try {
    window.localStorage.setItem(
      SELECTED_PLAYERS_STORAGE_KEY,
      JSON.stringify([...selected.keys()]),
    );
  } catch (error) {
    // Storage can be unavailable in private browsing or when disabled.
    console.warn('Could not save the player selection.', error);
  }
}

function hydrateSelectedPlayers(): void {
  const playersById = new Map(players.map((player) => [player.id, player]));
  const persistedIds = readPersistedPlayerIds();

  for (const id of persistedIds) {
    const player = playersById.get(id);
    if (player) selected.set(player.id, player);
  }

  // Rewrite the cache so stale catalog entries and duplicate IDs are removed.
  if (persistedIds.length > 0) persistSelectedPlayerIds();
}

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

function renderSavedTeams(): void {
  const savedTeams = readSavedTeams();
  savedTeamCount.textContent = savedTeams.length ? `${savedTeams.length} saved` : '';

  savedTeamsList.innerHTML = savedTeams.length
    ? savedTeams.map((team) => `
        <div class="saved-team-row">
          <div class="saved-team-details">
            <strong>${escapeText(team.name)}</strong>
            <small>${team.playerIds.length} ${team.playerIds.length === 1 ? 'player' : 'players'}</small>
          </div>
          <div class="saved-team-actions">
            <button class="saved-team-button" type="button" data-load-team="${escapeText(team.id)}">Load</button>
            <button class="saved-team-delete" type="button" data-delete-team="${escapeText(team.id)}" aria-label="Delete ${escapeText(team.name)}">×</button>
          </div>
        </div>
      `).join('')
    : '<p class="muted saved-team-empty">Save your current player pool for next week.</p>';
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value);
}

function parseLineupResponse(value: unknown): LineupResponse {
  if (!isRecord(value) || !isRecord(value.lineup)) {
    throw new Error('The backend returned an invalid lineup.');
  }

  const rawLineup = value.lineup;
  if (!isFiniteNumber(rawLineup.total_points) || !isRecord(rawLineup.slots)) {
    throw new Error('The backend returned an invalid lineup.');
  }

  const slots: Record<string, PlayerProjection[]> = {};
  for (const [slot, rawPlayers] of Object.entries(rawLineup.slots)) {
    if (!Array.isArray(rawPlayers)) throw new Error('The backend returned an invalid lineup.');
    slots[slot] = rawPlayers.map(parseProjection);
  }

  const rawProjections = value.projections;
  if (!Array.isArray(rawProjections)) throw new Error('The backend returned an invalid lineup.');

  return {
    lineup: { total_points: rawLineup.total_points, slots },
    projections: rawProjections.map(parseProjection),
    warnings: Array.isArray(value.warnings)
      ? value.warnings.filter((warning): warning is string => typeof warning === 'string')
      : [],
  };
}

function parseProjection(value: unknown): PlayerProjection {
  if (!isRecord(value) || !isRecord(value.player) || !isRecord(value.stats)) {
    throw new Error('The backend returned an invalid lineup.');
  }

  const rawPlayer = value.player;
  if (typeof rawPlayer.id !== 'string' || typeof rawPlayer.name !== 'string' || typeof rawPlayer.position !== 'string') {
    throw new Error('The backend returned an invalid lineup.');
  }
  if (!isFiniteNumber(value.fantasy_points)) throw new Error('The backend returned an invalid lineup.');

  const stats: Record<string, ProjectedStat> = {};
  for (const [stat, rawStat] of Object.entries(value.stats)) {
    if (!isRecord(rawStat) || !isFiniteNumber(rawStat.value)) {
      throw new Error('The backend returned an invalid lineup.');
    }
    stats[stat] = {
      value: rawStat.value,
      ...(Array.isArray(rawStat.sources)
        ? { sources: rawStat.sources.filter((source): source is string => typeof source === 'string') }
        : {}),
      ...(isFiniteNumber(rawStat.market_over_probability)
        ? { market_over_probability: rawStat.market_over_probability }
        : {}),
    };
  }

  return {
    player: {
      id: rawPlayer.id,
      name: rawPlayer.name,
      position: rawPlayer.position,
    },
    stats,
    fantasy_points: value.fantasy_points,
  };
}

function formatNumber(value: number): string {
  return Number.isInteger(value) ? value.toString() : value.toFixed(1);
}

function formatStatName(stat: string): string {
  const knownNames: Record<string, string> = {
    passing_yards: 'Pass yds',
    passing_tds: 'Pass TDs',
    interceptions: 'INT',
    rushing_yards: 'Rush yds',
    rushing_tds: 'Rush TDs',
    receptions: 'Rec',
    receiving_yards: 'Rec yds',
    receiving_tds: 'Rec TDs',
    fumbles_lost: 'Fumbles',
    field_goals_made: 'FG made',
    extra_points_made: 'XP made',
    defense_sacks: 'Sacks',
    defense_interceptions: 'INT',
    defense_fumble_recoveries: 'Fumble rec',
    defense_tds: 'Def TDs',
    defense_points_allowed: 'Pts allowed',
  };
  return knownNames[stat] || stat.replace(/_/g, ' ');
}

function renderGeneratedLineup(response: LineupResponse): void {
  const slots = Object.entries(response.lineup.slots);
  const slotMarkup = slots.map(([slot, slotPlayers]) => `
    <section class="generated-slot" aria-labelledby="generated-${escapeText(slot)}">
      <div class="generated-slot-heading">
        <h4 id="generated-${escapeText(slot)}">${escapeText(slot)}</h4>
        <span>${slotPlayers.length} ${slotPlayers.length === 1 ? 'player' : 'players'}</span>
      </div>
      <div class="generated-players">
        ${slotPlayers.map((projection) => {
          const stats = Object.entries(projection.stats);
          return `
            <article class="generated-player">
              <div class="generated-player-heading">
                <div>
                  <strong>${escapeText(projection.player.name)}</strong>
                  <small>${escapeText(projection.player.position)}</small>
                </div>
                <span class="points"><b>${formatNumber(projection.fantasy_points)}</b> pts</span>
              </div>
              ${stats.length ? `<div class="stat-list">${stats.map(([stat, item]) => `
                <span class="stat-chip"><b>${escapeText(formatStatName(stat))}</b> ${formatNumber(item.value)}</span>
              `).join('')}</div>` : '<p class="muted generated-no-stats">No supporting projections</p>'}
            </article>
          `;
        }).join('')}
      </div>
    </section>
  `).join('');

  const warnings = response.warnings?.length
    ? `<aside class="warnings"><strong>Notes</strong><ul>${response.warnings.map((warning) => `<li>${escapeText(warning)}</li>`).join('')}</ul></aside>`
    : '';

  requestResult.innerHTML = `
    <div class="result-header">
      <div>
        <p class="eyebrow">Recommended roster</p>
        <h3>Projected lineup</h3>
      </div>
      <div class="total-points"><b>${formatNumber(response.lineup.total_points)}</b><span>total pts</span></div>
    </div>
    <div class="generated-slots">${slotMarkup}</div>
    ${warnings}
  `;
  requestResult.hidden = false;
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

function hasCompleteStartingLineup(): boolean {
  return assignRosterPlayers([...selected.values()]).starters.size === STARTING_SLOTS.length;
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
  submitButton.disabled = !hasCompleteStartingLineup();
  saveTeamButton.disabled = selected.size === 0;

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

function loadTeam(teamId: string): void {
  const team = readSavedTeams().find((candidate) => candidate.id === teamId);
  if (!team) return;

  const playersById = new Map(players.map((player) => [player.id, player]));
  selected.clear();
  for (const playerId of team.playerIds) {
    const player = playersById.get(playerId);
    if (player) selected.set(player.id, player);
  }

  persistSelectedPlayerIds();
  teamNameInput.value = team.name;
  savedTeamStatus.textContent = `Loaded “${team.name}” with ${selected.size} ${selected.size === 1 ? 'player' : 'players'}.`;
  renderSelected();
  renderResults();
}

function saveCurrentTeam(): void {
  const name = teamNameInput.value.trim();
  if (!name) {
    savedTeamStatus.textContent = 'Give this team a name first.';
    teamNameInput.focus();
    return;
  }
  if (selected.size === 0) {
    savedTeamStatus.textContent = 'Add at least one player before saving.';
    return;
  }

  const savedTeams = readSavedTeams();
  const existingTeam = savedTeams.find((team) => team.name.toLowerCase() === name.toLowerCase());
  const team: SavedTeam = {
    id: existingTeam?.id || createSavedTeamId(),
    name,
    playerIds: [...selected.keys()],
  };

  if (existingTeam) {
    savedTeams[savedTeams.indexOf(existingTeam)] = team;
  } else {
    if (savedTeams.length >= MAX_SAVED_TEAMS) {
      savedTeamStatus.textContent = `You can save up to ${MAX_SAVED_TEAMS} teams.`;
      return;
    }
    savedTeams.unshift(team);
  }

  persistSavedTeams(savedTeams);
  teamNameInput.value = name;
  savedTeamStatus.textContent = existingTeam ? `Updated “${name}”.` : `Saved “${name}”.`;
  renderSavedTeams();
}

async function loadPlayers(): Promise<void> {
  try {
    const response = await fetch('/players.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data: unknown = await response.json();
    if (!Array.isArray(data)) throw new Error('Player catalog must be an array');
    players = data as Player[];
    hydrateSelectedPlayers();
    playerStatus.textContent = selected.size > 0
      ? `${players.length} players available. Your saved roster was restored.`
      : `${players.length} players available. Search to narrow the list.`;
    renderSelected();
    renderResults();
    renderSavedTeams();
  } catch (error) {
    playerStatus.textContent = 'Could not load the player catalog.';
    console.error(error);
  }
}

async function submitLineup(): Promise<void> {
  submitButton.disabled = true;
  requestStatus.textContent = 'Generating…';
  requestResult.hidden = true;
  requestResult.innerHTML = '';

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
    const lineupResponse = parseLineupResponse(body);
    requestStatus.textContent = 'Lineup generated.';
    renderGeneratedLineup(lineupResponse);
  } catch (error) {
    requestStatus.textContent = error instanceof Error ? error.message : 'Request failed.';
  } finally {
    submitButton.disabled = !hasCompleteStartingLineup();
  }
}

searchInput.addEventListener('input', renderResults);
results.addEventListener('click', (event) => {
  const button = (event.target as HTMLElement).closest<HTMLButtonElement>('[data-player-id]');
  if (!button) return;
  const player = players.find((candidate) => candidate.id === button.dataset.playerId);
  if (player) {
    selected.set(player.id, player);
    persistSelectedPlayerIds();
  }
  renderSelected();
  renderResults();
});

selectedList.addEventListener('click', (event) => {
  const button = (event.target as HTMLElement).closest<HTMLButtonElement>('[data-remove-id]');
  if (!button) return;
  selected.delete(button.dataset.removeId || '');
  persistSelectedPlayerIds();
  renderSelected();
  renderResults();
});

savedTeamsList.addEventListener('click', (event) => {
  const target = event.target as HTMLElement;
  const loadButton = target.closest<HTMLButtonElement>('[data-load-team]');
  if (loadButton) {
    loadTeam(loadButton.dataset.loadTeam || '');
    return;
  }

  const deleteButton = target.closest<HTMLButtonElement>('[data-delete-team]');
  if (!deleteButton) return;
  const teamId = deleteButton.dataset.deleteTeam || '';
  const team = readSavedTeams().find((candidate) => candidate.id === teamId);
  if (!team || !window.confirm(`Delete “${team.name}”?`)) return;

  persistSavedTeams(readSavedTeams().filter((candidate) => candidate.id !== teamId));
  savedTeamStatus.textContent = `Deleted “${team.name}”.`;
  renderSavedTeams();
});

saveTeamButton.addEventListener('click', saveCurrentTeam);
teamNameInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') saveCurrentTeam();
});
submitButton.addEventListener('click', submitLineup);
renderSelected();
renderSavedTeams();
void loadPlayers();
