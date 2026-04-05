# Phase 1: Research — Firestone API 验证

## 发现

### 1. npm 包安装
- `@firestone-hs/simulate-bgs-battle` v1.1.695 + `@firestone-hs/reference-data` 安装成功
- 首次运行会 fetch `cards_enUS.gz.json` (~4MB)，后续有缓存

### 2. API 入口
```js
const { simulateBattle, assignCards } = require('@firestone-hs/simulate-bgs-battle');
// simulateBattle(input, cards, cardsData) → Generator<SimulationResult>
```

### 3. 输入格式 (BgsBattleInfo)
- `playerBoard` / `opponentBoard`: 各含 `player: BgsPlayerEntity` + `board: BoardEntity[]`
- `BoardEntity` 关键字段: entityId, cardId, attack, health, taunt, divineShield, poisonous, venomous, reborn, cleave, windfury, stealth, enchantments
- `BgsPlayerEntity`: cardId(英雄), hpLeft, tavernTier, heroPowers, questEntities, trinkets, globalInfo
- `options`: numberOfSimulations, maxAcceptableDuration, skipInfoLogs
- `gameState`: currentTurn, validTribes, anomalies

### 4. 输出格式 (SimulationResult)
- wonPercent, tiedPercent, lostPercent, wonLethalPercent, lostLethalPercent
- averageDamageWon, averageDamageLost
- damageWons[], damageLosts[] (完整分布)

### 5. 性能实测
| 场景 | 次数 | 耗时 |
|------|------|------|
| 1v1 简单 | 5,000 | 96ms |
| 3v3 含亡语 | 10,000 | 477ms |

### 6. 卡牌数据
- AllCardsService 提供全部卡牌数据
- BG minions (techLevel > 0): **1,563** 张（含金卡/token）
- 基础非金卡: **507** 张
- 分布: T1=167, T2=182, T3=349, T4=286, T5=393, T6=152, T7=34

### 7. 关键注意点
- 必须调 `assignCards(cards)` 注册卡牌数据
- `CardsData.inititialize(validTribes, anomalies)` 注意拼写是 `inititialize`（原代码如此）
- Generator 模式需要 `while(!r.done)` 循环到完成
- cardId 传入正确的 BG 专属 ID（如 `BGS_061`），不是构筑 ID

## 结论
Firestone npm 包完全可用，API 稳定，性能优异。建议通过持久 Node 子进程桥接 Python。
