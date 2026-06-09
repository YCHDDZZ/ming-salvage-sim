# 数据库表清单与模块对应

SQLite 持久化全在 `ming_sim/db/` 包。原单文件 `db.py` 按域拆成 Mixin，
`GameDB` 多继承聚合，对外 API 不变（`from ming_sim.db import GameDB, normalize_office,
infer_office_type_from_office` 照旧）。各 Mixin 共享 `self.conn` / `self.content`（`_BaseMixin.__init__` 建）。

共 **36 张表**，建表全在 `db/schema.py:init_schema`（含旧库 `ensure_column` 补列迁移）。

> 本文按表归到**主要读写它的 Mixin 模块**。部分表被多模块跨用（如 `economy_ledger`
> 被 fiscal 写、issues 也写），列「主属模块」+ 备注。

## 包结构（Mixin → 文件）

| 文件 | Mixin | 职责 |
|---|---|---|
| `base.py` | `_BaseMixin` | `__init__`、`ensure_column`/`table_has_rows`、JSON 行编解码、行快照/恢复、`close`/`backup_to` |
| `schema.py` | `_SchemaMixin` | `init_schema`：全部 41 表 DDL + 补列迁移 |
| `seed.py` | `_SeedMixin` | `seed_static_data` 从 GameContent 灌静态盘面；开局账本/邸报/危机；欠饷单位迁移 |
| `state.py` | `_StateMixin` | `game_state`/`metrics` 读写、上回合摘要 |
| `fiscal.py` | `_FiscalMixin` | 财政预算目录 + 账目 |
| `characters.py` | `_CharactersMixin` | 身份/任免/史实登离场/调教/技能授权 |
| `factions.py` | `_FactionsMixin` | 朝堂派系 |
| `powers.py` | `_PowersMixin` | 外部势力盘面 |
| `regions.py` | `_RegionsMixin` | 两京十三省 + 阶级 |
| `armies.py` | `_ArmiesMixin` | 军队盘面/名册 |
| `buildings.py` | `_BuildingsMixin` | 建筑/科技/衙门 |
| `issues.py` | `_IssuesMixin` | 事项/进度/触发/帝国修正符 |
| `memories.py` | `_MemoriesMixin` | 事件记忆 + 章节记忆 |
| `turns.py` | `_TurnsMixin` | 回合产物 + 诏书草案 |
| `chat.py` | `_ChatMixin` | 召对对话存档（撤回机制已废） |
| `secret_orders.py` | `_SecretOrdersMixin` | 密令系统 |
| `kv.py` | `_KvMixin` | 通用 key-value 元数据 |
| `admin.py` | `_AdminMixin` | 调试用通用表 CRUD |
| `_helpers.py` | — | 模块级纯函数：`normalize_office` / `infer_office_type_from_office` / `_normalize_power_id` 等 |

## 41 张表

### state.py — 国家全局状态
| 表 | 作用 | 关键字段 |
|---|---|---|
| `game_state` | 当前年月/回合/阶段/结局（单行 id=1） | `year, period, turn, turn_phase, ended, ending_status` |
| `metrics` | 四项全局指标 KV | `key`(国库/内库/民心/皇威), `value` |

### fiscal.py — 财政
| 表 | 作用 | 关键字段 |
|---|---|---|
| `fiscal_config` | 数据驱动预算目录：各科目月额 base + 预算行元数据 | `key, value, kind, budget_role, account, direction, display, sort_order` |
| `economy_accounts` | 资金账户（对应 metric 国库/内库），存余额 | `account, metric_key, balance, note` |
| `economy_ledger` | 收支流水账（每笔一行） | `turn, account, delta, balance_after, category, reason, purpose, target_kind, target_id`；purpose/target_* 仅 extractor 抽出的 economy_moves 填，flows 月固定支出留 NULL。也被 issues 写（`record_issue_economy_move`） |

### characters.py — 人物与任免
| 表 | 作用 | 关键字段 |
|---|---|---|
| `characters` | 人物全档（大臣/后宫，含史实生卒/登场）。**任职活数据在此**（office/office_type 列），游戏逻辑全读这里 | `name(PK), office, office_type, faction, loyalty/ability/integrity/courage, status, power_id, location, portrait_id, court_role` |
| `character_offices` | 任职**备档/审计表**（纯写，无 SELECT 读）。抄家/贬黜时 characters.office 清空，此表留旧职可回溯；在 chat 撤回白名单内 | `character_name(PK), office_title, office_type, source` |
| `offices` | 职位定义 + **职位级** court 授权 blob | `office_type(PK), power/responsibility/corruption_risk, court_grant_json, origin`；`court_grant_json`＝该**职位**（非人）配的 court tool/agno skill/前端 chip（铁律：运行时读 DB 此列），换人顶职授权跟职位走 |
| `skill_grants` | **个人级**授权：皇帝单独给**某一个人**临时多开一个技能（与职位无关）。skills.py 读它拼技能清单+打「皇帝授权」标 | `character_name, skill_id, granted_by, active`（软删=active 置 0） |
| `consort_traits` | 后宫调教记录（永久记忆） | `name(PK), extra_skills, extra_traits, updated_turn` |

### factions.py
| 表 | 作用 | 关键字段 |
|---|---|---|
| `factions` | 朝堂派系满意度/影响力 | `name(PK), satisfaction, leverage, agenda` |

### powers.py — 外部势力
| 表 | 作用 | 关键字段 |
|---|---|---|
| `powers` | 外部/内部势力盘面（含明自身 id=ming） | `id(PK), name, kind, stance, leverage, satisfaction, military_strength, cohesion, supply, status, aliases` |
| `power_logs` | 势力字段变更留痕 | `turn, power_id, field, old_value, new_value, delta, reason` |
| `power_name_logs` | 势力改名留痕 | `turn, power_id, old_name, new_name, old_aliases, new_aliases, reason` |

### regions.py — 地区与阶级
| 表 | 作用 | 关键字段 |
|---|---|---|
| `regions` | 两京十三省盘面 | `id(PK), name, population, public_support, unrest, registered_land, hidden_land, tax_per_turn, gentry_resistance, military_pressure, controlled_by, fiscal(json; grain_output=粮食年产, grain_stock=存粮)` |
| `region_logs` | 地区字段变更留痕 | `turn, region_id, field, old/new_value, delta, reason, event_id, edict_id, actor` |
| `classes` | 阶级（key=name@region_id） | `name+region_id(PK), population, satisfaction, leverage, agenda` |

### armies.py — 军队
| 表 | 作用 | 关键字段 |
|---|---|---|
| `armies` | 军队盘面 | `id(PK), name, station, commander, troop_type, manpower, maintenance_per_turn, supply, morale, training, equipment, arrears, loyalty, owner_power`（`maintenance/tax_per_turn` 实为月值） |
| `army_logs` | 军队字段变更留痕 | `turn, army_id, field, old/new_value, delta, reason, event_id, edict_id, actor` |

### arms.py — 军事装备库存
| 表 | 作用 | 关键字段 |
|---|---|---|
| `weapons` | 武器型号注册（weapons.json 打底 + 运行时 LLM 新增） | `id(PK), name, tier, power, cost, equip_per_unit, requires_tech, registered(seed/runtime)` |
| `arms_stock` | 国家军备总库（一行一型号） | `weapon_id(PK→weapons), qty` |
| `army_arms` | 拨发到军（某军持有某型号几件） | `(army_id, weapon_id) PK, qty` |
| `arms_logs` | 军备变更流水（`army_id` NULL=总库变更） | `turn, weapon_id, army_id, old/new_value, delta, reason, source(building/issue/dispatch/war)` |

> 版本化走 `kv_store(weapons_version)`；建筑产械入总库（flows 建筑 tick）、皇帝下旨 `dispatch_arms`
> 拨发给某军提 `equipment`（硬卡只拨有的）。`requires_tech` 须 `technologies` 表已解锁方可产/造。

### buildings.py — 建筑/科技/衙门
| 表 | 作用 | 关键字段 |
|---|---|---|
| `buildings` | 建筑盘面 | `id(PK), region_id, category, level, condition, maintenance, risk, output_metric, output_amount, origin` |
| `building_logs` | 建筑字段变更留痕 | `turn, building_id, field, old/new_value, delta, reason` |
| `technologies` | 已解锁科技清单（无月度产出，研发进度由 issue bar 承载） | `id(PK), name, category, effect_summary, status, origin` |

> 衙门/部门复用 `offices` 表插行（`add_department`），非独立表。

### issues.py — 事项与帝国修正
| 表 | 作用 | 关键字段 |
|---|---|---|
| `issues` | 可追踪事项（改革/危机），双向进度条 | `id(PK), kind, title, bar_value, bar_good/bad_meaning, phase, status, severity, ongoing_effects, effect_on_resolve/fail, resolve/fail_condition` |
| `issue_advances` | 事项每次推进流水 | `issue_id, turn, trigger_kind, delta_bar, from/to_value, narrative, metric_delta` |
| `events` | 事件定义（可触发事项的剧本） | `id(PK), title, kind, summary, urgency, severity, credibility, interests, audiences` |
| `event_triggers` | 事件已触发记录（去重） | `event_id(PK), turn, source` |
| `legacies` | 帝国长期百分比修正符（结案/开局产生） | `id(PK), name, modifiers(json), start_month, duration_months(-1=永久), status, clear_gate, legacy_key` |

### memories.py — 记忆
| 表 | 作用 | 关键字段 |
|---|---|---|
| `event_memories` | 主体（人物/地区/势力…）事件记忆，含 chapter_summary 章节记忆 | `id(PK), subject_type, subject_id, turn, event_type, title, cause/process/outcome, sentiment, importance, source_kind, source_id, body, expires_turn`；UNIQUE(subject_type,subject_id,event_type,source_kind,source_id) |
| `event_memory_sources` | 记忆的来源出处（多源） | `memory_id, source_kind, source_id, excerpt, locator`；FK ON DELETE CASCADE |

### turns.py — 回合产物与诏书
| 表 | 作用 | 关键字段 |
|---|---|---|
| `turn_reports` | 月末邸报（每回合一行，**玩家可见的正式回奏正源**，`previous_turn_summary` 优先读它） | `turn(PK), year, period, report` |
| `turn_extractions` | 推演链各 agent 原始输入输出留痕。**非纯审计**：`memories.py` 读 extractor_output 回填章节记忆、`list_archived_turns` 点徽标、web 前端展示 | `turn(PK), decree_text, narrative, extractor_input, extractor_output` |
| `ending_summary` | 结局总结（每局触发时一条） | `turn(PK), ending_status, summary, timeline` |
| `turn_directives` | 诏书草案/已颁诏 | `id(PK), turn, event_id, actor, skill_id, text, source, status(draft/...), notes` |

> HITL 决策点（原 `pending_decisions` / `pending_resolve_context`）已改走 GameSession 进程内存
> （`_pending_decisions` / `_pending_resolve_ctx`），不落库——决策暂停期间进程重启即丢，按重跑推演处理。

### chat.py — 召对存档
| 表 | 作用 | 关键字段 |
|---|---|---|
| `chat_messages` | 召对聊天逐条持久化（答完整轮一起落 user+minister；中途退出＝前端中断不落库）。进程重启恢复内存缓存 | `id(PK), minister_name, turn, role, content` |

> 原撤回机制（`chat_turns` / `chat_turn_rollback_items` + agno runs 裁剪）已废：召对流式
> 中途退出由前端中断线程，整轮不落库（副作用循环在流式跑完后才执行，中断即无副作用），无需事后回滚。

### secret_orders.py
| 表 | 作用 | 关键字段 |
|---|---|---|
| `secret_orders` | 密令（立项→进展→催办→到期核议） | `id(PK), turn_issued, due_turn, minister_name, title, content, tags, importance, status(active/...), result, sim_note, turn_closed` |

### kv.py
| 表 | 作用 | 关键字段 |
|---|---|---|
| `kv_store` | 通用 key-value 元数据（schema/迁移版本号铁律走这里） | `key(PK), value` |

### admin.py
> 不建专表。`ADMIN_TABLES` 白名单暴露 `game_state/metrics/regions/armies/characters/buildings` 给调试 CRUD。

## 维护提示
- 加表：写进 `schema.py:init_schema`，对应 Mixin 加读写方法，本文补一行。
- 加列（旧库迁移）：`schema.py` 末尾 `ensure_column`，遵循「无 fallback、版本号走 `kv_store`」铁律。
- Mixin 间互调（如 regions 调 `self.power_display_name`）天然可用——多继承后全在同一实例。
