# CurveStrike · 函数战局

> A chess-like game where mathematical functions are your weapons.
> 以函数为武器的棋盘策略对战。

🎮 **在线试玩 / Play Now:** https://skl-666666.github.io/paint-chess/

---

## ✨ Features / 特性

- **Function Lasers / 函数激光** — Draw any curve `y=f(x)` or parametric curve as a laser beam. Mirrors reflect it. / 绘制任意函数曲线作为激光，镜面反射。
- **Blind Duel / 盲眼博弈** — You only see your own pieces. Predict the enemy. / 仅可见己方棋子，推断敌方位置。
- **21 Presets / 21 种预设函数** — Lines, parabolas, sine, rose curves, cardioids... / 直线、抛物线、正弦、玫瑰线、心形线……
- **4 Game Modes / 4 种模式** — Hot-seat, AI, Online P2P, Spectator. / 同屏、人机、公网联机、观战。
- **3 Difficulties / 3 种难度** — Easy (no traps), Normal, Hard (mandatory blocks). / 简单(无陷阱)、普通、困难(强制方块)。
- **Traps & Resonance / 陷阱与共振** — Hidden traps, cluster bonuses. / 隐蔽陷阱、密集命中加成。
- **Smart AI / 智能AI** — Probability map, king corner-hide, guard diversion tactics. / 概率图推断、王死角隐蔽、护卫声东击西。
- **Mobile Friendly / 手机适配** — Responsive layout, touch controls. / 响应式布局，触控操作。

---

## 🎯 How to Play / 玩法

1. **Setup / 布阵** — Place 1 King + Guards in your zone. / 在己方区域放置 1 王 + 护卫。
2. **Fire / 发射** — Input a function, the curve becomes a laser from your piece. / 输入函数，曲线即为从棋子射出的激光。
3. **Reflect / 反射** — Laser bounces off mirrors. Hit enemies to kill. / 激光遇镜面反射，命中敌方棋子即消灭。
4. **Win / 胜利** — Kill the enemy King. / 消灭敌方王即胜。

> The laser must pass within 0.5 units of your anchor piece.
> 激光曲线必须经过发射棋子 0.5 格范围内。

---

## 🛠 Tech Stack / 技术栈

- HTML5 Canvas + vanilla JS (no framework)
- [math.js](https://mathjs.org/) for expression parsing
- [PeerJS](https://peerjs.com/) for WebRTC P2P online
- GitHub Pages static hosting

---

## 🚀 Run Locally / 本地运行

```bash
git clone https://github.com/SKL-666666/paint-chess.git
cd paint-chess
# Open index.html in browser / 用浏览器打开 index.html
```

No build step required. / 无需构建。

---

## 📜 Rules / 规则速览

| Item / 项目 | Detail / 说明 |
|---|---|
| Board / 棋盘 | 11×11, coordinates -5 to 5 / 11×11，坐标 -5 到 5 |
| King / 王 | 1 piece, dies = lose / 1 个，被消灭即败 |
| Guard / 护卫 | 3 pieces / 3 个 |
| Setup zone / 布阵区 | A: y∈[-3,0], B: y∈[0,3] (shared centerline / 共享中线) |
| Traps / 陷阱 | Max 3 per player, only visible to owner / 每方上限 3，仅己方可见 |
| Hard mode / 困难模式 | Mandatory block every 2 turns, must pass through / 每两回合强制方块，函数必经 |

---

Made with functions. / 以函数为刃。
