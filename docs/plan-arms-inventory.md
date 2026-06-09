# 军事装备库存 × 建筑生产 设计方案（待拍板）

> 目标：在「国库/内库/民心/皇威」四大全局指标之外，引入**军事装备实物链**——
> 军械建筑产出武器 → 进国家军备总库 → 皇帝下旨拨发给某军 → 该军装备提升。
> **不做军粮**（粮食已有 grain_stock 一套，军备只管武器实物）。
> 姊妹改动「兵种单价军费」（troop_cost.json）已落地。本文只出方案，未动代码。

## 已定的设计决策

1. **粒度＝具体武器型号**：火铳、燧发枪、火炮、红夷大炮、佛郎机… 不是「火器/甲胄」大类。
2. **两层库存（健全做全，不拆下轮）**：**总库**（国家军备仓，按型号记数）+ **拨发到军**
   （下旨拨 N 件给某军 → 总库减、该军 `equipment` 提升）。本轮一次建全。
3. **型号清单**：`content/weapons.json` 预定义主流型号打底（带属性），**允许推演中 LLM 新出
   未列型号**，落库时动态注册、属性给默认档。
4. **不做军粮、首版总库单仓**（不分地区）。
5. **拨发只拨有的（硬卡）**：总库有多少最多拨多少，库存不足按现有量拨、不欠拨。
6. **建筑产武器免费**（料钱已含在建筑维护费，不另扣采购）；**但部分型号需前置科技**——
   武器 `requires_tech`＝科技中文名，须在 `technologies` 表已结案解锁，否则建筑产不出/不可造。
   现成可挂：火器新法（燧发枪/抬枪/子母炮）、矿冶炼法（火炮/红夷大炮）。无门槛：火铳/鸟铳/三眼铳/虎蹲炮/佛郎机。

## 0. 现状地基（嫁接点）

- **建筑产出已有机制**（`flows.py:696`）：`buildings.output_metric` ∈ {国库,内库,民心,皇威,""}，
  `output_amount` 按 `condition/100` 折月产。→ 现只能产抽象指标，要扩成也能产武器。
- **军队 equipment**：0–100 装备分（`ARMY_SCORE_FIELDS`）。拨发武器＝提这个分（实物→武装水平）。
  总库存的是实物件数，equipment 是该军当前武装程度，两者解耦。
- **court tool 机制**：`tools.py:_COURT_TOOL_FUNCS` name→func 注册 + `skills.json` 按 office 授权。
  拨发武器是兵部/工部的下旨动作，走新 court tool（见 §5）。
- **军事建筑**：buildings.json 已有「京营火器局」「定海卫海防炮台」等军事类，是天然产出方。

## 1. 设定文件 `content/weapons.json`（已落地草版，10 型）

实际文件见 `content/weapons.json`。型号 + 前置科技：

| 型号 | tier | requires_tech |
|------|------|---------------|
| 火铳 / 鸟铳 / 三眼铳 | 轻火器 | 无 |
| 燧发枪 / 抬枪 | 轻火器 | 火器新法 |
| 虎蹲炮 / 佛郎机 | 火炮 | 无 |
| 火炮 | 火炮 | 矿冶炼法 |
| 子母炮 | 火炮 | 火器新法 |
| 红夷大炮 | 重炮 | 矿冶炼法 |

- **字段义**：`cost`＝每件造价/采购万两（采购外购扣账用；建筑产出免费）；`equip_per_unit`＝拨发 1 件
  提升的 equipment 分基数（拨发量 × 此值，再按军规模折算，钳 0–100）；`power`＝战力权重；
  `requires_tech`＝前置科技中文名（须 `technologies` 表已解锁，空＝无门槛）。
- **解锁判定**：`SELECT 1 FROM technologies WHERE name=?`（technologies 表 id 是序号，按 name 匹配最稳，
  add_technology 也按 name 查重）。产出 tick 与拨发/采购前都查；未解锁型号建筑产不出、不可拨造。
- **LLM 新型号兜底**：extractor 出未列型号名 → `tiers[*].keywords` 关键词归 tier（含「红夷/大炮」→重炮、
  「炮」→火炮，否则 default_tier 轻火器），取该 tier 默认属性 + `requires_tech` 默认空，动态注册进 weapons 表。
- 加载器无 fallback、缺字段 SystemExit（同 troop_cost.json）。`GameContent.weapons` 字段 +
  `content.weapon_meta(name_or_id)` 解析器（含动态归 tier）。

## 2. 数据表（新，`ming_sim/db/arms.py` Mixin）

```sql
-- 武器型号注册表（设定打底 + 运行时动态新增）
CREATE TABLE weapons (
  id TEXT PRIMARY KEY, name TEXT, tier TEXT,
  power INTEGER, cost INTEGER, equip_per_unit REAL,
  requires_tech TEXT DEFAULT '',   -- 前置科技中文名（空=无门槛）
  registered TEXT DEFAULT 'seed'   -- seed / runtime（LLM 新增）
);
-- 国家军备总库：一行一型号
CREATE TABLE arms_stock (
  weapon_id TEXT PRIMARY KEY,
  qty INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY(weapon_id) REFERENCES weapons(id)
);
-- 拨发到军（某军持有某型号几件）。本轮做全（健全）
CREATE TABLE army_arms (
  army_id TEXT, weapon_id TEXT, qty INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(army_id, weapon_id)
);
-- 变更流水（产出/拨发/战损溯源，喂邸报与前端）
CREATE TABLE arms_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  turn INTEGER, year INTEGER, period INTEGER,
  weapon_id TEXT, army_id TEXT,          -- army_id 为 NULL=总库变更
  old_value INTEGER, new_value INTEGER, delta INTEGER,
  reason TEXT, source TEXT                -- building/issue/dispatch/war
);
```

- seed：`init_weapons()` 按 weapons.json 灌 `weapons` 表；`arms_stock` 各型号初值 0
  （或设定给 initial）。版本化走 **`kv_store`**：`kv_get("weapons_version")` vs 设定 version，
  升版才 re-seed 型号结构（玩家运行时改的 qty 不动）——铁律照搬。
- 表↔模块登记进 `docs/db-schema.md`。

## 3. 建筑产出扩展（产武器入总库）

`output_metric` 取值集扩入武器——军械建筑的 `output_metric` 填武器 id（如 `huochong`），
`output_amount`＝月产件数。flows 建筑 tick（flows.py:711）加分支：

```python
elif metric in weapon_ids:        # 产武器入总库（前置科技已解锁才产）
    if db.weapon_unlocked(metric):
        db.add_arms_stock(metric, produced, source="building", reason=f"{name}月产")
    # 未解锁：建筑空转不产（可选：邸报提示「待解锁 X 科技方可量产」）
```

- `BUILDING_OUTPUT_METRICS` 常量扩成动态（含 weapons 表 id），或校验时放行武器 id。
- buildings.json：给火器局填 `output_metric:"huochong"`（无门槛即产）/ 若填需科技的型号
  （如 `huopao`），则解锁矿冶炼法前建筑空转、解锁后自动开产。海防炮台填 `output_metric:"folangji"` 等。
- `db.weapon_unlocked(weapon_id)`：查该武器 requires_tech，空→True；否则
  `SELECT 1 FROM technologies WHERE name=requires_tech`。
- 多数军械建筑只产一型号，单字段够用；要一建筑产多型号属下版（不在首版）。

## 4. 拨发到军（总库→军，皇帝下旨）

新 court tool **`dispatch_arms`**（授权给兵部、工部）：

- 大臣调 `dispatch_arms(army="关宁军", weapon="红夷大炮", qty=40, reason=...)`
  → 返回哨兵 `__pending_arms_dispatch__<json>`，`GameSession.chat` 截获 →
  入 pending 草案待皇帝准/驳（仿 propose_directive/propose_appointment 路径）。
- 准奏落地 `apply_arms_dispatch`（**只拨有的／硬卡**）：
  1. `actual = min(qty, arms_stock[weapon])`；总库为 0 → 驳回提示「库无此械」。
  2. 总库 `arms_stock[weapon] -= actual`；`army_arms[army][weapon] += actual`；
  3. 该军 `equipment += round(actual × weapon.equip_per_unit × 规模折算)`，钳 0–100；
  4. 写 arms_logs（source=dispatch）。实拨 < 请拨时回执注明「库存仅 N，照发」。
- 注册：`tools.py:_COURT_TOOL_FUNCS` 加 `dispatch_arms`；`skills.json` 兵部/工部 court_tools
  授权 + 前端 chip；升 `__office_grant_version`。

## 5. extractor / simulator 接口

- extractor 顶层加 `arms_changes`：总库增减（产出之外的叙事性，如缴获/炸毁/采购）
  `{"红夷大炮": +12, "火铳": -2000, "reason": "...}` → `db.apply_arms_stock_deltas`。
  **边界**：建筑稳定月产由 flows 程序化唯一变更，extractor **只抽叙事性增减**，不重复抽建筑产出
  （同 arrears「户部结算唯一变更」的纪律）。
- LLM 出未列型号 → `content.weapon_meta` 动态归 tier 注册（§1）。
- `score_extractor_military_external.md`：加武器型号映射表 + arms_changes 约束 + 动态新增说明。
- `season_simulator.md`：军械建筑造械、拨发、战损叙事点明型号与数量。

## 6. 前端展示

- HUD：四大指标旁加「军备」面板/chip，列总库各型号件数（hud-slots.json 体系，见 memory
  project-hud-slot-coords）。
- 军队抽屉：展示该军持有武器（army_arms）。
- 邸报回放：arms_logs → 「本月京营火器局造火铳 2000、拨红夷大炮 40 门予关宁军」。
- `web_app.py` state payload 加 `arms_stock`/`army_arms`；`web/src/types.ts` 加类型。

## 7. 落地顺序（本轮一次健全做全）

按已定决策（健全/只拨有的/前置科技/免费产出），本轮一把做完：

1. ✅ `weapons.json`（已落地，10 型 + requires_tech）
2. 加载器 `load_weapons()` + `GameContent.weapons` + `weapon_meta()`（含动态归 tier）
3. weapons/arms_stock/army_arms/arms_logs 四表 + seed + kv 版本化（`weapons_version`）+ `db/arms.py` Mixin
4. `db.weapon_unlocked()`（查 requires_tech vs technologies 表）
5. flows 建筑 tick 接武器产出（解锁才产，免费入总库）
6. buildings.json 给军械建筑填 `output_metric`=武器 id
7. `dispatch_arms` court tool（兵部/工部授权，硬卡只拨有的）+ `apply_arms_dispatch`（扣库/提 equipment）
8. extractor `arms_changes` 叙事性增减 + 动态型号注册 + 提示词
9. 前端：HUD 总库面板 + 军队抽屉持有武器 + payload + types.ts

→ 闭环可验证：「火器局每月造火铳入库→HUD 看得到→下旨拨 40 红夷大炮给关宁军→总库减、关宁军装备升」。

## 8. 决策已定（原待拍板问题留档）

- **Q1 army_arms**：✅ 健全——本轮就建，拨发记某军持有明细。
- **Q2 库存不足**：✅ 只拨有的（硬卡），`actual=min(请拨, 库存)`，库空则驳。
- **Q3 武器 cost**：✅ 建筑产武器免费（料钱已含建筑维护费）；cost 仅采购/外购时扣。
  另：部分型号需 `requires_tech` 解锁方可产/造（火器新法/矿冶炼法）。
- **Q4 型号集**：✅ 已补至 10 型（火铳/鸟铳/三眼铳/燧发枪/抬枪/虎蹲炮/佛郎机/火炮/子母炮/红夷大炮）。
  还要加（如鲁密铳、大将军炮、灭虏炮…）随时说，改 weapons.json 即可。
```
