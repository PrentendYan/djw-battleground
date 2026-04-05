# Battleground Simulator — 开发计划与现状

## 项目概览

炉石传说酒馆战棋（Battlegrounds）战斗模拟工具。支持构建双方阵容、设置英雄技能/饰品/异常等完整游戏机制，通过 Firestone 引擎运行 Monte Carlo 模拟，输出胜率/伤害分布。

**技术栈**: Python 3.13 + Node.js (Firestone) + Streamlit + Plotly

---

## 已完成模块

### S1: 核心战斗引擎 ✅
- `src/battleground/types.py` — 枚举 (Tribe, CombatResult) + SimulationResult
- `src/battleground/minion.py` — Minion 基类，13 个 hook 方法
- `src/battleground/board.py` — Board 管理，7 slots，目标选择
- `src/battleground/combat.py` — 战斗引擎，两步死亡处理，亡语队列，复生
- `src/battleground/simulator.py` — 自有 Monte Carlo 模拟器
- `tests/test_combat.py` — 26 tests

### S1.5: Firestone 桥接 ✅ (DARF 审查通过)
- `src/battleground/bridge/bridge.js` — Node.js 持久进程，JSON-lines 协议
- `src/battleground/bridge/firestone.py` — Python 封装 (FirestoneSimulator)
- `tests/test_bridge.py` — 15 tests
- `data/cards_cache.json` — 34,578 cards 本地缓存

| 引擎 | 场景 | 10k sims |
|------|------|----------|
| 自有 Python | 7v7 vanilla | 1.37s |
| Firestone (Node) | 7v7 vanilla | 0.96s |

### S4: 游戏状态管理 + 战斗 API ✅
- `src/battleground/game/state.py` — GameState, PlayerState, MinionState, HeroState (frozen dataclasses)
- `src/battleground/game/battle_api.py` — BattleAPI: PlayerState → Firestone dict 转换 + 模拟
- `src/battleground/game/matchmaking.py` — Matchmaker: 3 回合防重复配对 + 幽灵玩家
- `src/battleground/game/player.py` — Player Protocol (预留)
- `src/battleground/game/actions.py` — Action 类型定义 (预留)
- `tests/test_state.py` + `tests/test_battle_api.py` — 48 tests

### S5: 战斗可视化 UI ✅
- `src/battleground/ui/app.py` — Streamlit 主应用
- `src/battleground/ui/components/board_editor.py` — 7-slot 阵容编辑器 + 英雄栏
- `src/battleground/ui/components/card_picker.py` — 卡牌数据加载 + 图片显示
- `src/battleground/ui/components/results.py` — 胜率饼图 + 伤害直方图 (Plotly)
- `src/battleground/ui/components/lobby_view.py` — 8 人 Lobby 总览 (预留)

### S5.1: UI 自检与修复 ✅
已修复的 7 个问题：
1. ✅ Streamlit 1.51.0 兼容性（`st.popover` 可用）
2. ✅ Widget key 冲突排查（`{side}_s{idx}_*` 前缀隔离）
3. ✅ MinionState 构造改为显式关键字参数（不再用 `**kwargs` 展开）
4. ✅ 图片 404 处理（本地图片缓存 + 文字 fallback）
5. ✅ 切换卡牌时 attack/health 不同步（`on_change` 回调清除 session_state）
6. ✅ 空 board 模拟显示 warning
7. ✅ session_state key 一致性（共享 `hero_hp_key()` / `hero_tier_key()` helpers）

代码审查修复：
- ✅ XSS 防御：`html.escape()` 处理所有插入 HTML 的用户数据
- ✅ `_KEYWORD_NAMES` + `_MECHANIC_MAP` 单一数据源，防漂移
- ✅ `_CACHE_PATH` 改用 `.parents[4]`
- ✅ `# noqa: E402` 抑制 Streamlit 特有的 import 顺序 lint

### S5.2: 卡牌图片展示 ✅
- 本地图片缓存：`data/card_images/` (~34MB, ~1,272 张)
  - 113 张经典卡：full render PNG (`{cardId}.png`, ~150KB)
  - ~1,159 张：256x artwork JPG (`{cardId}_art.jpg`, ~14KB)
- 覆盖范围：

| 类型 | 数量 |
|------|------|
| Minions | 393 |
| Hero Powers | 81 |
| Trinkets | 256 |
| Anomalies | 104 |
| Tavern Spells | 193 |
| Quest Rewards | 73 |
| Heroes (portraits) | 59 |
| **合计** | **~1,159** |

- CDN 源：`https://art.hearthstonejson.com/v1/256x/{cardId}.jpg`（需浏览器 UA）
- 下载脚本：`scripts/download_card_images.py`（多线程，render → art fallback）
- 显示逻辑：`card_image_local()` 查找本地文件（`_art.jpg` 优先 → `.png`），`render_card_image()` 统一显示

### S5.3: 游戏化界面 — 英雄选择 + Global Info ✅
- **英雄选择器**：59 位 BG 英雄下拉，选择后显示头像（80px），自动填充 Armor
- **英雄头像**：未选择时显示圆形占位符，选择后显示 artwork
- **Armor 字段**：从英雄数据自动填充（0-20），可手动覆盖
- **Global Info 编辑器**（折叠面板内）：
  - Eternal Knight Deaths — 永恒骑士本局死亡数
  - Pirate Atk Bonus — 海盗攻击加成
  - Blood Gem Atk — 血宝石攻击值
- 数据流：英雄 → `HeroState(card_id=...)` → `playerBoard.player.cardId`；Global Info → `PlayerState.global_info` → `playerBoard.player.globalInfo`

### S5.5: 手牌支持（战斗模拟准确性修复）✅
**问题**: Firestone 引擎的 `player.hand` 字段未传入，导致十余张依赖手牌的卡牌模拟不准确。

受影响卡牌：
- **Choral Mrrrglr / Timewarped Mrrrglr** — 战斗开始获得手牌总攻/血
- **Dramaloc** — 攻击时获取手牌最高攻击随从属性
- **Expert Aviator** — 攻击时 buff 手牌第一个随从
- **Murcules / Timewarped Murcules** — 攻击时召唤手牌随从
- **Bassgill / Timewarped Bassgill** — 亡语 buff 手牌最高血量鱼人
- **Pilot the Shredder** — 亡语 buff 手牌最高血量随从
- **Friendly Bouncer** — 战斗中将随从送回手牌
- **Tinyfin Onesie** (饰品) — 给手牌最高血量随从加圣盾
- **Crocheted Sungill** (饰品) — buff 手牌最高血量随从

修复内容：
1. ✅ `battle_api.py` — `_build_player_board` 传入 `hand` 实体列表
2. ✅ `board_editor.py` — 新增手牌编辑器（折叠面板，最多 10 张）
3. ✅ `app.py` — 将手牌数据接入 `_build_player_state`

数据流：手牌编辑器 → `MinionState` list → `PlayerState.hand` → `BattleAPI._build_player_board()` → `playerBoard.player.hand` → Firestone

### S5.4: S6 游戏机制 UI 控件 ✅
游戏风格英雄栏布局：
```
[Trinket1] [Lesser ▼ ]  [Hero   ] [Hero ▼   ] [Hero Power 1 ▼] [HP1 64px]
[Trinket2] [Greater ▼]  [Portrait] [HP Armor ] [Hero Power 2 ▼] [HP2 64px]
                                   [Tier     ] [Quest Reward ▼ ] [QR 64px]
▸ Secrets & Global Info (折叠)
```

已实现的控件：

| 控件 | 位置 | 数据量 | Firestone 字段 |
|------|------|--------|---------------|
| Hero Select | 英雄栏中间 | 59 位 | `playerBoard.player.cardId` |
| Hero Power ×2 | 英雄栏右侧 | 81 种 | `playerBoard.player.heroPowers` |
| Quest Reward | 英雄栏右侧 | 73 种 | `playerBoard.player.questEntities` |
| Lesser Trinket | 英雄栏左侧 | 128 种 | `playerBoard.player.trinkets` |
| Greater Trinket | 英雄栏左侧 | 128 种 | `playerBoard.player.trinkets` |
| Secrets / Spells | 折叠面板 | 193 种 | `playerBoard.secrets` |
| Global Info | 折叠面板 | 3 字段 | `playerBoard.player.globalInfo` |
| Anomalies | Sidebar | 104 种 | `gameState.anomalies` |

数据流：UI selectbox → `app.py` resolve helpers → `PlayerState` fields → `BattleAPI._build_battle_info()` → Firestone JSON

### S6: 完善游戏机制 ✅
PlayerState 已支持的字段：
- `hero_powers: tuple[dict, ...]` — 英雄技能（1-2 个）
- `secrets: tuple[dict, ...]` — 酒馆奥秘
- `trinkets: tuple[dict, ...]` — 饰品（Lesser + Greater）
- `quest_entities: tuple[dict, ...]` — 任务奖励
- `global_info: dict | None` — 持久性全局状态
- `hero: HeroState` — 英雄身份 + 技能使用状态

BattleAPI 将所有字段转换为 Firestone 格式传入模拟引擎。

---

## 待实现

### UI 进一步优化
1. [ ] **站位拖拽** — 拖拽调整随从站位顺序（Streamlit 原生不支持，需 custom component 或上下箭头按钮替代）
2. [ ] **战斗回放** — 逐步展示战斗过程（阻塞：需 Firestone 引擎输出 action log，当前 bridge 不支持）
3. [ ] **Duos 模式 UI** — 双人组队界面（低优先级，需扩展 PlayerState 和配对逻辑）

### S7: 招募阶段 + 对局循环 ✅
1. [x] **招募阶段核心** — MinionPool（按星级有限池）、ShopState（冻结/刷新）、CoinManager（turn+2 cap 10）、TavernUpgrade（[6,7,8,9,10] 每回合-1 折扣）、TripleMerge（三连→金色 2×base+buffs + 发现）、HandManager（最多 10 张）
2. [x] **Player 实现** — `RandomPlayer`（加权随机买/卖/升级/刷新），Player Protocol 预留 RuleBasedPlayer/HumanPlayer
3. [x] **完整对局循环** — 招募 → 配对 → 战斗(Firestone/Simple) → 伤害(tavern_tier+Σminion_tiers, turn<8 cap 15) → 淘汰 → 直到剩 1 人

新增模块：
- `src/battleground/game/minion_pool.py` — MinionPool + MinionTemplate
- `src/battleground/game/shop.py` — ShopState + refresh_shop
- `src/battleground/game/recruit.py` — 完整招募阶段逻辑（gold/buy/sell/refresh/upgrade/freeze/triple）
- `src/battleground/game/game_loop.py` — GameLoop（支持 Firestone 和 Simple 两种战斗模式）
- `src/battleground/game/random_player.py` — RandomPlayer
- `tests/test_minion_pool.py` + `test_shop.py` + `test_recruit.py` + `test_random_player.py` + `test_game_loop.py` — 90 新测试

覆盖率：game 模块 91%（182 tests 全通过）

### S8: Agent 训练（未来）
4. [ ] **训练基础设施** — self-play 环境、奖励设计、训练循环
5. [ ] **RuleBasedPlayer** — 基于启发式的强化基线
6. [ ] **RLPlayer** — 强化学习玩家

---

## 技术债务

- [ ] Pyright 类型标注修复（`_process` 可选类型等）
- [ ] 自有引擎随从效果实现（对比 Firestone 验证正确性）
- [ ] 性能优化：Python 热路径用 PyO3/Rust 加速
- [ ] .gitignore 完善（node_modules, data/, __pycache__）
- [ ] CI 设置（GitHub Actions: pytest + type check）
- [ ] 卡牌数据更新机制（当前为手动运行 bridge 生成缓存）

---

## 项目结构

```
battleground/
├── pyproject.toml
├── package.json + package-lock.json
├── scripts/
│   └── download_card_images.py     # 卡牌图片批量下载
├── data/
│   ├── cards_cache.json            # 34,578 cards (auto-generated)
│   ├── cards_cache_meta.json
│   └── card_images/                # 1,213 张本地图片缓存 (33MB)
│       ├── {cardId}.png            # 113 full renders
│       └── {cardId}_art.jpg        # 1,100 artwork
├── src/battleground/
│   ├── __init__.py
│   ├── types.py                    # Tribe, CombatResult, SimulationResult
│   ├── minion.py                   # Minion 基类
│   ├── board.py                    # Board 管理
│   ├── combat.py                   # 战斗引擎
│   ├── simulator.py                # Monte Carlo 模拟器
│   ├── bridge/                     # Firestone 桥接
│   │   ├── bridge.js
│   │   └── firestone.py
│   ├── game/                       # 游戏状态 + API + 招募 + 对局
│   │   ├── state.py                # GameState, PlayerState, MinionState
│   │   ├── battle_api.py           # BattleAPI
│   │   ├── matchmaking.py          # Matchmaker
│   │   ├── player.py               # Player Protocol
│   │   ├── actions.py              # Action types (含 S7 新增)
│   │   ├── minion_pool.py          # MinionPool + MinionTemplate (S7)
│   │   ├── shop.py                 # ShopState + refresh_shop (S7)
│   │   ├── recruit.py              # 招募阶段逻辑 (S7)
│   │   ├── game_loop.py            # 完整对局循环 (S7)
│   │   └── random_player.py        # RandomPlayer (S7)
│   └── ui/                         # Streamlit UI
│       ├── app.py                  # 主应用 + S6 resolve helpers
│       └── components/
│           ├── board_editor.py     # 英雄栏 + 7-slot 阵容编辑
│           ├── card_picker.py      # 卡牌数据加载 (8 个 loader) + 图片
│           ├── results.py          # 模拟结果 (Plotly)
│           └── lobby_view.py       # Lobby 总览 (预留)
├── tests/                          # 182 tests
│   ├── test_combat.py              # 26 tests
│   ├── test_bridge.py              # 15 tests
│   ├── test_state.py               # 15 tests
│   ├── test_battle_api.py          # 33 tests
│   └── test_integration_battle_api.py
├── darf-workspace/                 # DARF 审查记录
└── docs/
    └── PLAN.md                     # 本文件
```

## 快速启动

```bash
cd ~/Documents/battleground
pip install -e ".[dev]"                    # Python deps
npm install                                 # Node deps (Firestone)
python -m pytest tests/ -v                  # 89 tests should pass
python scripts/download_card_images.py      # 下载卡牌图片 (首次)
streamlit run src/battleground/ui/app.py    # 启动 UI
```

## 使用示例

```python
from battleground.bridge import FirestoneSimulator
from battleground.game.state import PlayerState, MinionState
from battleground.game.battle_api import BattleAPI

m1 = MinionState(card_id="BG_GVG_085", attack=1, health=2, taunt=True, divine_shield=True)
m2 = MinionState(card_id="BGS_039", attack=2, health=3, taunt=True)

player = PlayerState(player_id=0, health=40, tavern_tier=1, board=(m1,))
opponent = PlayerState(player_id=1, health=40, tavern_tier=1, board=(m2,))

with FirestoneSimulator() as sim:
    api = BattleAPI(sim)
    result = api.run_combat(player, opponent, num_simulations=10000)
    print(result.summary())
```

## 卡牌数据统计

`card_picker.py` 提供 8 个 `@st.cache_data` 加载函数：

| 类型 | 数量 | type 字段 | 加载函数 |
|------|------|-----------|---------|
| Heroes | 59 | `Hero` (battlegroundsHero) | `load_bg_heroes()` |
| Minions | 393 | `Minion` (isBaconPool) | `load_bg_cards()` |
| Hero Powers | 81 | `Hero_power` (BG id) | `load_bg_hero_powers()` |
| Trinkets (Lesser) | 128 | `Battleground_trinket` | `load_bg_trinkets()` |
| Trinkets (Greater) | 128 | `Battleground_trinket` | `load_bg_trinkets()` |
| Anomalies | 104 | `Battleground_anomaly` | `load_bg_anomalies()` |
| Tavern Spells | 193 | `Battleground_spell` | `load_bg_spells()` |
| Quest Rewards | 73 | `Battleground_quest_reward` | `load_bg_quest_rewards()` |

区分字段：
- Trinket tier: `spellSchool` = `LESSER_TRINKET` / `GREATER_TRINKET`
- BG Hero: `type == "Hero"` AND `"BG" in id` AND `battlegroundsHero == True`
- BG Hero Power: `type == "Hero_power"` AND `"BG" in id`
