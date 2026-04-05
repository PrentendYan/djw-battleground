# Blind Brief — Phase 1 Review

## Context
We are building a Hearthstone Battlegrounds combat simulator in Python. Phase 1 evaluated using the `@firestone-hs/simulate-bgs-battle` npm package as a simulation backend, called from Python via a Node.js subprocess bridge.

## Facts (no conclusions)

### Installation
- npm packages: `@firestone-hs/simulate-bgs-battle` v1.1.695, `@firestone-hs/reference-data`
- First run fetches `https://static.zerotoheroes.com/data/cards/cards_enUS.gz.json` (~4MB)

### API Surface
- Entry: `simulateBattle(battleInput, cards, cardsData)` returns `Generator<SimulationResult>`
- Requires: `AllCardsService.initializeCardsDb()` (async, network fetch), `assignCards(cards)`, `CardsData.inititialize(validTribes, anomalies)`
- Note: the method is spelled `inititialize` (extra "it") in the source

### Input structure
- `BgsBattleInfo` with `playerBoard`, `opponentBoard`, `options`, `gameState`
- `BoardEntity`: entityId, cardId, attack, health, ~30 optional keyword/state fields
- `BgsPlayerEntity`: hero cardId, hpLeft, tavernTier, heroPowers[], questEntities[], trinkets[], globalInfo{}

### Output structure
- `SimulationResult`: wonPercent, tiedPercent, lostPercent, wonLethalPercent, lostLethalPercent, averageDamageWon/Lost, damageWons[], damageLosts[]

### Test results
- Test 1: 5/5 DS vs 3/4 Taunt → wonPercent=100, 5000 sims in 96ms
- Test 2: 3 minions (Scallywag + Harvest Golem + 5/5 Taunt) vs 3x 3/3 → won=24.5%, tied=64.2%, lost=11.3%, 10000 sims in 477ms

### Card data
- AllCardsService provides full card DB
- BG minions (techLevel > 0): 1,563 cards total, 507 base non-golden
- Tier distribution: T1=167, T2=182, T3=349, T4=286, T5=393, T6=152, T7=34

## Review Questions
1. Are there risks in depending on the remote card data fetch (`cards_enUS.gz.json`)? What if the URL goes down?
2. Is the subprocess bridge approach (Python → Node.js persistent process) sound for production use?
3. Any security concerns with executing npm packages from Python?
4. Is the `Generator` pattern handled correctly (iterate until `done`)?
5. Are there potential issues with the `inititialize` misspelling being fixed in a future version?
