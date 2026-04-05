/**
 * Persistent Node.js bridge for Firestone BG simulator.
 *
 * Protocol: JSON-lines over stdin (requests) / stdout (responses).
 * All logs go to stderr exclusively — stdout is reserved for protocol.
 *
 * Requests:  {"id": N, "method": "simulate"|"get_card"|"get_bg_cards"|"shutdown", "params": {...}}
 * Responses: {"id": N, "result": ..., "error": null} or {"id": N, "result": null, "error": {...}}
 */

const fs = require('fs');
const path = require('path');
const readline = require('readline');

const { simulateBattle, assignCards } = require('@firestone-hs/simulate-bgs-battle');
const { AllCardsService } = require('@firestone-hs/reference-data');
const { CardsData } = require('@firestone-hs/simulate-bgs-battle/dist/cards/cards-data');

const CACHE_DIR = process.env.BG_CACHE_DIR || path.join(__dirname, '..', '..', '..', 'data');
const CACHE_FILE = path.join(CACHE_DIR, 'cards_cache.json');
const CACHE_META_FILE = path.join(CACHE_DIR, 'cards_cache_meta.json');

let cards = null;
let cardsData = null;

// --- Logging (stderr only) ---
function log(msg) {
    process.stderr.write(`[bridge] ${msg}\n`);
}

// --- Response helper ---
function respond(id, result, error) {
    const line = JSON.stringify({ id, result: result ?? null, error: error ?? null });
    process.stdout.write(line + '\n');
}

// --- Card data caching ---
async function loadCards() {
    cards = new AllCardsService();

    // Try local cache first
    if (fs.existsSync(CACHE_FILE)) {
        try {
            const cached = JSON.parse(fs.readFileSync(CACHE_FILE, 'utf8'));
            // Use the official initialization path
            cards.initializeCardsDbFromCards(cached);
            log(`Loaded ${cached.length} cards from cache`);
        } catch (e) {
            log(`Cache read failed: ${e.message}, fetching remote`);
            await cards.initializeCardsDb();
            saveCache();
        }
    } else {
        log('No cache found, fetching remote card data...');
        await cards.initializeCardsDb();
        saveCache();
    }

    assignCards(cards);

    // Initialize CardsData with typo-safe method
    cardsData = new CardsData(cards, false);
    if (typeof cardsData.inititialize === 'function') {
        cardsData.inititialize([], []);
    } else if (typeof cardsData.initialize === 'function') {
        cardsData.initialize([], []);
    } else {
        log('WARNING: No initialize method found on CardsData');
    }
}

function saveCache() {
    try {
        if (!fs.existsSync(CACHE_DIR)) {
            fs.mkdirSync(CACHE_DIR, { recursive: true });
        }
        const allCards = cards.getCards();
        fs.writeFileSync(CACHE_FILE, JSON.stringify(allCards));
        const meta = {
            saved_at: new Date().toISOString(),
            card_count: allCards.length,
            npm_version: require('@firestone-hs/simulate-bgs-battle/package.json').version,
        };
        fs.writeFileSync(CACHE_META_FILE, JSON.stringify(meta, null, 2));
        log(`Saved ${allCards.length} cards to cache`);
    } catch (e) {
        log(`Cache save failed: ${e.message}`);
    }
}

// --- Request handlers ---
function handleSimulate(id, params) {
    try {
        const battleInput = params;
        // Ensure options defaults
        if (!battleInput.options) {
            battleInput.options = { numberOfSimulations: 10000, skipInfoLogs: true };
        }
        if (battleInput.options.skipInfoLogs === undefined) {
            battleInput.options.skipInfoLogs = true;
        }
        if (!battleInput.gameState) {
            battleInput.gameState = { currentTurn: 1, validTribes: [], anomalies: [] };
        }

        // Re-initialize CardsData per request with the correct validTribes/anomalies
        // (Codex finding: stale CardsData causes incorrect simulation when tribes/anomalies differ)
        const tribes = battleInput.gameState.validTribes || [];
        const anomalies = battleInput.gameState.anomalies || [];
        if (typeof cardsData.inititialize === 'function') {
            cardsData.inititialize(tribes, anomalies);
        } else if (typeof cardsData.initialize === 'function') {
            cardsData.initialize(tribes, anomalies);
        }

        const iterator = simulateBattle(battleInput, cards, cardsData);
        let r = iterator.next();
        while (!r.done) {
            r = iterator.next();
        }
        respond(id, r.value, null);
    } catch (e) {
        respond(id, null, { code: 'SIMULATION_ERROR', message: e.message });
    }
}

function handleGetCard(id, params) {
    try {
        const card = cards.getCard(params.cardId);
        if (!card || !card.id) {
            respond(id, null, { code: 'CARD_NOT_FOUND', message: `Card ${params.cardId} not found` });
        } else {
            respond(id, {
                id: card.id,
                dbfId: card.dbfId,
                name: card.name,
                attack: card.attack,
                health: card.health,
                techLevel: card.techLevel,
                races: card.races || [],
                type: card.type,
                text: card.text,
                mechanics: card.mechanics || [],
                battlegroundsPremiumDbfId: card.battlegroundsPremiumDbfId,
                battlegroundsNormalDbfId: card.battlegroundsNormalDbfId,
                set: card.set,
            }, null);
        }
    } catch (e) {
        respond(id, null, { code: 'CARD_ERROR', message: e.message });
    }
}

function handleGetBgCards(id) {
    try {
        const allCards = cards.getCards();
        const bgCards = allCards
            .filter(c => c.techLevel > 0 && c.type === 'Minion')
            .map(c => ({
                id: c.id,
                dbfId: c.dbfId,
                name: c.name,
                attack: c.attack,
                health: c.health,
                techLevel: c.techLevel,
                races: c.races || [],
                text: c.text || '',
                mechanics: c.mechanics || [],
                battlegroundsPremiumDbfId: c.battlegroundsPremiumDbfId,
                battlegroundsNormalDbfId: c.battlegroundsNormalDbfId,
            }));
        respond(id, bgCards, null);
    } catch (e) {
        respond(id, null, { code: 'BG_CARDS_ERROR', message: e.message });
    }
}

async function handleRefreshCards(id) {
    try {
        cards = new AllCardsService();
        await cards.initializeCardsDb();
        saveCache();
        assignCards(cards);
        cardsData = new CardsData(cards, false);
        if (typeof cardsData.inititialize === 'function') {
            cardsData.inititialize([], []);
        } else if (typeof cardsData.initialize === 'function') {
            cardsData.initialize([], []);
        }
        respond(id, { success: true }, null);
    } catch (e) {
        respond(id, null, { code: 'REFRESH_ERROR', message: e.message });
    }
}

// --- Main loop ---
async function main() {
    await loadCards();

    // Signal ready
    respond(0, { ready: true, card_count: cards.getCards().length }, null);

    const rl = readline.createInterface({ input: process.stdin, terminal: false });

    rl.on('line', async (line) => {
        let req;
        try {
            req = JSON.parse(line);
        } catch (e) {
            respond(-1, null, { code: 'PARSE_ERROR', message: `Invalid JSON: ${e.message}` });
            return;
        }

        const { id, method, params } = req;

        switch (method) {
            case 'simulate':
                handleSimulate(id, params || {});
                break;
            case 'get_card':
                handleGetCard(id, params || {});
                break;
            case 'get_bg_cards':
                handleGetBgCards(id);
                break;
            case 'refresh_cards':
                await handleRefreshCards(id);
                break;
            case 'ping':
                respond(id, { pong: true }, null);
                break;
            case 'shutdown':
                respond(id, { shutdown: true }, null);
                process.exit(0);
                break;
            default:
                respond(id, null, { code: 'UNKNOWN_METHOD', message: `Unknown method: ${method}` });
        }
    });

    rl.on('close', () => {
        log('stdin closed, exiting');
        process.exit(0);
    });
}

main().catch(e => {
    log(`Fatal error: ${e.message}`);
    process.exit(1);
});
