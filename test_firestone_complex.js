// Complex test: verify actual minion effects work (deathrattles, tribes, etc.)
const { simulateBattle, assignCards } = require('@firestone-hs/simulate-bgs-battle');
const { AllCardsService } = require('@firestone-hs/reference-data');
const { CardsData } = require('@firestone-hs/simulate-bgs-battle/dist/cards/cards-data');

async function main() {
    const cards = new AllCardsService();
    await cards.initializeCardsDb();
    assignCards(cards);
    const cardsData = new CardsData(cards, false);
    cardsData.inititialize([], []);

    // Test: 7v7 with real card IDs and various effects
    const battleInput = {
        playerBoard: {
            player: {
                cardId: 'TB_BaconShop_HERO_01',
                hpLeft: 30, tavernTier: 4,
                heroPowers: [], questEntities: [],
            },
            board: [
                // Scallywag (1/1 Pirate, DR: summon 1/1 that attacks immediately)
                { entityId: 1, cardId: 'BGS_061', attack: 2, health: 1, friendly: true },
                // Harvest Golem (2/3 Mech, DR: summon 2/1)
                { entityId: 2, cardId: 'EX1_556', attack: 2, health: 3, friendly: true },
                // A 5/5 taunt
                { entityId: 3, cardId: 'BGS_039', attack: 5, health: 5, taunt: true, friendly: true },
            ],
        },
        opponentBoard: {
            player: {
                cardId: 'TB_BaconShop_HERO_01',
                hpLeft: 30, tavernTier: 4,
                heroPowers: [], questEntities: [],
            },
            board: [
                // Three 3/3 minions
                { entityId: 4, cardId: 'BGS_039', attack: 3, health: 3, friendly: false },
                { entityId: 5, cardId: 'BGS_039', attack: 3, health: 3, friendly: false },
                { entityId: 6, cardId: 'BGS_039', attack: 3, health: 3, friendly: false },
            ],
        },
        options: { numberOfSimulations: 10000, skipInfoLogs: true },
        gameState: { currentTurn: 7, validTribes: [], anomalies: [] },
    };

    const start = Date.now();
    const it = simulateBattle(battleInput, cards, cardsData);
    let r = it.next(); while (!r.done) { r = it.next(); }
    const result = r.value;
    const elapsed = Date.now() - start;

    console.log(JSON.stringify({
        won: result.wonPercent.toFixed(1),
        tied: result.tiedPercent.toFixed(1),
        lost: result.lostPercent.toFixed(1),
        avgDmgWon: result.averageDamageWon.toFixed(1),
        avgDmgLost: result.averageDamageLost.toFixed(1),
        elapsed_ms: elapsed,
    }, null, 2));

    // Also verify card lookup works
    const scallywag = cards.getCard('BGS_061');
    console.log(`\nCard lookup test: ${scallywag.name} (${scallywag.attack}/${scallywag.health}) Tier ${scallywag.techLevel}`);
    const golem = cards.getCard('EX1_556');
    console.log(`Card lookup test: ${golem.name} (${golem.attack}/${golem.health}) Tier ${golem.techLevel}`);
}

main().catch(e => { console.error(e); process.exit(1); });
