// Quick verification: call Firestone simulateBattle from Node.js
const { simulateBattle, assignCards } = require('@firestone-hs/simulate-bgs-battle');
const { AllCardsService } = require('@firestone-hs/reference-data');
const { CardsData } = require('@firestone-hs/simulate-bgs-battle/dist/cards/cards-data');

async function main() {
    const cards = new AllCardsService();
    await cards.initializeCardsDb();
    assignCards(cards);
    const cardsData = new CardsData(cards, false);
    cardsData.inititialize([], []);

    // Test: 5/5 Divine Shield vs 3/4 Taunt
    const battleInput = {
        playerBoard: {
            player: {
                cardId: 'TB_BaconShop_HERO_01', // Bartender Bob (default hero)
                hpLeft: 40,
                tavernTier: 3,
                heroPowers: [],
                questEntities: [],
            },
            board: [
                {
                    entityId: 1,
                    cardId: 'BGS_039', // Dragonspawn Lieutenant (generic)
                    attack: 5,
                    health: 5,
                    divineShield: true,
                    friendly: true,
                },
            ],
        },
        opponentBoard: {
            player: {
                cardId: 'TB_BaconShop_HERO_01',
                hpLeft: 40,
                tavernTier: 3,
                heroPowers: [],
                questEntities: [],
            },
            board: [
                {
                    entityId: 2,
                    cardId: 'BGS_039',
                    attack: 3,
                    health: 4,
                    taunt: true,
                    friendly: false,
                },
            ],
        },
        options: {
            numberOfSimulations: 5000,
            skipInfoLogs: true,
        },
        gameState: {
            currentTurn: 5,
            validTribes: [],
            anomalies: [],
        },
    };

    const start = Date.now();
    const iterator = simulateBattle(battleInput, cards, cardsData);
    let result;
    let r = iterator.next();
    while (!r.done) { r = iterator.next(); }
    result = r.value;
    const elapsed = Date.now() - start;

    console.log(JSON.stringify({
        wonPercent: result.wonPercent,
        tiedPercent: result.tiedPercent,
        lostPercent: result.lostPercent,
        averageDamageWon: result.averageDamageWon,
        averageDamageLost: result.averageDamageLost,
        simulations: 5000,
        elapsed_ms: elapsed,
    }, null, 2));
}

main().catch(e => { console.error(e.message); process.exit(1); });
