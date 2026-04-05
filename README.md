# Battleground — 炉石酒馆战棋模拟器

炉石传说酒馆战棋（Hearthstone Battlegrounds）完整对局模拟器。支持招募阶段（商店/购买/升级/三连）、战斗模拟（Firestone 引擎）、8人对局循环，以及 Streamlit 可视化界面。

## 功能

| 模块 | 说明 |
|------|------|
| **战斗引擎** | 自有 Python 引擎 + [Firestone](https://github.com/nicholasgasior/firestone-hs) Node.js 引擎桥接，支持 10k 次 Monte Carlo 模拟 |
| **招募阶段** | 随从池（按星级有限份数）、商店刷新/冻结、金币系统、酒馆升级（自动折扣）、三连合金 |
| **对局循环** | 招募 → 配对（防重复）→ 战斗 → 伤害结算 → 淘汰 → 直到剩1人 |
| **AI 玩家** | RandomPlayer（加权随机决策），预留 RuleBasedPlayer / HumanPlayer 接口 |
| **Streamlit UI** | 双人战斗模拟器 + 8人对局观战（逐回合推进、历史回放、招募日志） |
| **完整游戏机制** | 英雄技能、饰品、奥秘、任务奖励、异常、手牌，全部接入 Firestone |

## 快速启动

### 环境要求

- Python ≥ 3.11
- Node.js ≥ 18（Firestone 引擎）

### 安装

```bash
git clone https://github.com/YourUser/djw-battleground.git
cd djw-battleground

# Python 依赖
pip install -e ".[dev,ui]"

# Node 依赖（Firestone 战斗引擎）
npm install
```

### 生成卡牌数据

首次运行需要生成卡牌缓存（约 34,578 张卡牌）：

```python
from battleground.bridge.firestone import FirestoneSimulator
with FirestoneSimulator() as sim:
    pass  # 自动生成 data/cards_cache.json
```

下载卡牌图片（可选，约 34MB）：

```bash
python scripts/download_card_images.py
```

### 运行

**Streamlit UI**（双模式：战斗模拟 + 对局观战）：

```bash
streamlit run src/battleground/ui/app.py
```

**Python API — 跑一局完整对局**：

```python
from battleground.game import GameLoop, MinionPool, RandomPlayer
import json, random

with open("data/cards_cache.json") as f:
    cards = json.load(f)

pool = MinionPool.from_cards(cards)
players = [RandomPlayer(i, random.Random(i)) for i in range(8)]
loop = GameLoop(players, pool, rng=random.Random(42))
final = loop.run()

for p in sorted(final.players, key=lambda x: x.finished_position or 0):
    pos = f"#{p.finished_position}" if p.finished_position else "Winner"
    print(f"{pos} P{p.player_id} | HP={p.health} | Tier={p.tavern_tier} | Board={len(p.board)}")
```

**Python API — 战斗模拟**：

```python
from battleground.bridge import FirestoneSimulator
from battleground.game import BattleAPI, PlayerState, MinionState

m1 = MinionState(card_id="BG_GVG_085", attack=1, health=2, taunt=True, divine_shield=True)
m2 = MinionState(card_id="BGS_039", attack=2, health=3, taunt=True)

player = PlayerState(player_id=0, health=40, tavern_tier=1, board=(m1,))
opponent = PlayerState(player_id=1, health=40, tavern_tier=1, board=(m2,))

with FirestoneSimulator() as sim:
    api = BattleAPI(sim)
    result = api.run_combat(player, opponent, num_simulations=10000)
    print(result.summary())
```

## 项目结构

```
djw-battleground/
├── pyproject.toml                  # Python 项目配置
├── package.json                    # Node 依赖 (Firestone)
├── scripts/
│   └── download_card_images.py     # 卡牌图片批量下载
├── data/
│   └── cards_cache_meta.json       # 缓存元数据
├── docs/
│   └── PLAN.md                     # 开发计划与模块现状
├── src/battleground/
│   ├── types.py                    # 枚举 + SimulationResult
│   ├── minion.py                   # Minion 基类（13 个 hook）
│   ├── board.py                    # Board 管理（7 slots）
│   ├── combat.py                   # 自有战斗引擎
│   ├── simulator.py                # Monte Carlo 模拟器
│   ├── bridge/
│   │   ├── bridge.js               # Node.js 持久进程
│   │   └── firestone.py            # Python 封装
│   ├── game/
│   │   ├── state.py                # GameState / PlayerState / MinionState
│   │   ├── battle_api.py           # BattleAPI（PlayerState → Firestone）
│   │   ├── matchmaking.py          # 配对（防重复 + 幽灵玩家）
│   │   ├── actions.py              # 招募阶段 Action 类型
│   │   ├── player.py               # Player Protocol
│   │   ├── minion_pool.py          # 随从池（有限份数）
│   │   ├── shop.py                 # 商店状态 + 刷新
│   │   ├── recruit.py              # 招募阶段逻辑
│   │   ├── game_loop.py            # 完整对局循环
│   │   └── random_player.py        # 随机 AI
│   └── ui/
│       ├── app.py                  # Streamlit 主应用
│       └── components/
│           ├── board_editor.py     # 阵容编辑器
│           ├── card_picker.py      # 卡牌数据加载 + 图片
│           ├── results.py          # 模拟结果（Plotly）
│           ├── lobby_view.py       # Lobby 总览
│           └── simulation_viewer.py # 对局观战
└── tests/                          # 182 tests, 91% coverage
    ├── test_combat.py
    ├── test_bridge.py
    ├── test_state.py
    ├── test_battle_api.py
    ├── test_integration_battle_api.py
    ├── test_minion_pool.py
    ├── test_shop.py
    ├── test_recruit.py
    ├── test_random_player.py
    └── test_game_loop.py
```

## 核心机制数值

| 机制 | 数值 |
|------|------|
| 随从池份数 | T1: 16, T2: 15, T3: 13, T4: 11, T5: 9, T6: 7 |
| 商店大小 | T1: 3, T2-3: 4, T4-5: 5, T6: 6 |
| 金币 | 回合 N → min(N+2, 10) 金 |
| 消费 | 购买 3g, 出售 +1g, 刷新 1g |
| 升级费 | 基础 [6, 7, 8, 9, 10]，每回合自动 -1 折扣 |
| 三连 | 金色属性 = Σ(三份属性) - 基础属性，发现当前星级 +1 |
| 伤害 | 酒馆等级 + Σ(存活随从星级)，前 8 回合上限 15 |

## Firestone 引擎版本

当前使用的 npm 依赖版本：

```
@firestone-hs/simulate-bgs-battle: ^1.1.695
@firestone-hs/reference-data: ^3.0.183
```

## 测试

```bash
# 运行全部测试
python -m pytest tests/ -v

# 带覆盖率
python -m pytest tests/ --cov=src/battleground --cov-report=term-missing
```

182 tests, game 模块 91% coverage。

## 架构

```
┌─────────────┐     ┌──────────────┐
│  Streamlit  │────▶│  BattleAPI   │──────▶ Firestone (Node.js)
│    UI       │     │              │
└──────┬──────┘     └──────────────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  GameLoop   │────▶│ RecruitPhase │────▶│  MinionPool  │
│ (对局循环)   │     │ (招募阶段)    │     │  (随从池)     │
└──────┬──────┘     └──────────────┘     └──────────────┘
       │
       ▼
┌─────────────┐     ┌──────────────┐
│ Matchmaker  │     │   Player     │
│ (配对系统)   │     │ (AI / Human) │
└─────────────┘     └──────────────┘
```

## License

Private project.
