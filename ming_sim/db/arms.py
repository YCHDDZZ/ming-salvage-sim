"""军事装备：weapons 型号注册 / arms_stock 总库 / army_arms 拨发 / arms_logs 流水。

_ArmsMixin。军备实物链：建筑产械入总库（flows）→ 皇帝下旨拨发给某军（dispatch）提 equipment。
- 型号清单走 content/weapons.json，seed 灌 weapons 表，版本化走 kv_store(weapons_version)（铁律）。
- 部分型号需 requires_tech 前置科技（technologies 表已解锁）才可产/造。
- 拨发硬卡：只拨总库现有量（actual=min(请拨,库存)）。
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ming_sim.content import canon_troop_name
from ming_sim.models import GameState


class _ArmsMixin:
    # ── seed / 版本化 ────────────────────────────────────────────────
    def init_weapons(self) -> None:
        """据 weapons.json seed/迁移 weapons 表。版本化走 kv_store(weapons_version)：
        cur < target 才整体刷型号结构（registered='seed' 的预设行），玩家运行时改过的
        arms_stock.qty / runtime 注册型号神圣不动。"""
        spec = self.content.weapons or {}
        target = int(spec.get("version", 1))
        cur_raw = self.kv_get("weapons_version")
        cur = int(cur_raw) if cur_raw is not None and cur_raw.isdigit() else 0
        if cur >= target:
            return
        for w in spec.get("weapons", []):
            self.conn.execute(
                """
                INSERT INTO weapons (id, name, tier, cost, equip_per_unit, requires_tech, registered)
                VALUES (?, ?, ?, ?, ?, ?, 'seed')
                ON CONFLICT(id) DO UPDATE SET
                  name=excluded.name, tier=excluded.tier,
                  cost=excluded.cost, equip_per_unit=excluded.equip_per_unit,
                  requires_tech=excluded.requires_tech, registered='seed',
                  updated_at=CURRENT_TIMESTAMP
                WHERE weapons.registered='seed'
                """,
                (w["id"], w["name"], w["tier"], int(w["cost"]),
                 float(w["equip_per_unit"]), str(w.get("requires_tech") or "")),
            )
            # 总库行：INSERT OR IGNORE 只在首次建行时写开局库存，已存在的库存量神圣不动。
            opening_stock = max(0, int(w.get("opening_stock") or 0))
            self.conn.execute(
                "INSERT OR IGNORE INTO arms_stock (weapon_id, qty) VALUES (?, ?)", (w["id"], opening_stock)
            )
        self.kv_set("weapons_version", str(target))

    # ── 型号解析 / 解锁判定 ───────────────────────────────────────────
    def _ensure_weapon_registered(self, name_or_id: str) -> Optional[Dict[str, object]]:
        """据 id/名找 weapons 表行；缺则用 content.weapon_meta 动态注册（runtime）。
        返回该型号 dict（含 id/requires_tech/equip_per_unit），无法解析返回 None。"""
        key = str(name_or_id or "").strip()
        if not key:
            return None
        row = self.conn.execute(
            "SELECT * FROM weapons WHERE id=? OR name=?", (key, key)
        ).fetchone()
        if row is not None:
            return dict(row)
        meta = self.content.weapon_meta(key)
        self.conn.execute(
            """
            INSERT INTO weapons (id, name, tier, cost, equip_per_unit, requires_tech, registered)
            VALUES (?, ?, ?, ?, ?, ?, 'runtime')
            ON CONFLICT(id) DO NOTHING
            """,
            (meta["id"], meta["name"], meta["tier"], int(meta["cost"]),
             float(meta["equip_per_unit"]), str(meta.get("requires_tech") or "")),
        )
        self.conn.execute(
            "INSERT OR IGNORE INTO arms_stock (weapon_id, qty) VALUES (?, 0)", (meta["id"],)
        )
        row = self.conn.execute("SELECT * FROM weapons WHERE id=?", (meta["id"],)).fetchone()
        return dict(row) if row else None

    def weapon_unlocked(self, weapon_id: str) -> bool:
        """该型号是否可产/造：requires_tech 空→True；否则 technologies 表按 name 命中。"""
        row = self.conn.execute("SELECT requires_tech FROM weapons WHERE id=?", (weapon_id,)).fetchone()
        if row is None:
            return False
        return self.tech_unlocked(str(row["requires_tech"] or ""))

    # ── 兵种档 seed / 解锁判定 ────────────────────────────────────────
    def init_troop_tiers(self) -> None:
        """据 troop_cost.json seed/迁移 troop_tiers 表。版本化走 kv_store(troop_tiers_version)：
        cur < target 才整体刷预设档（registered='seed'），runtime 注册的兵种神圣不动。"""
        spec = self.content.troop_cost or {}
        target = int(spec.get("version", 1))
        cur_raw = self.kv_get("troop_tiers_version")
        cur = int(cur_raw) if cur_raw is not None and cur_raw.isdigit() else 0
        if cur >= target:
            return
        for tier in spec.get("tiers", []):
            self.conn.execute(
                """
                INSERT INTO troop_tiers (name, category, per_kilo, requires_tech, registered)
                VALUES (?, ?, ?, ?, 'seed')
                ON CONFLICT(name) DO UPDATE SET
                  category=excluded.category, per_kilo=excluded.per_kilo,
                  requires_tech=excluded.requires_tech, registered='seed',
                  updated_at=CURRENT_TIMESTAMP
                WHERE troop_tiers.registered='seed'
                """,
                (str(tier.get("tier") or ""), str(tier.get("category") or ""),
                 float(tier.get("per_kilo") or 0.0), str(tier.get("requires_tech") or "")),
            )
        self.kv_set("troop_tiers_version", str(target))

    def troop_unlocked(self, tier_name: str) -> bool:
        """该兵种是否可编：未注册（runtime/AI 新发明，不在表里）→True（默认放行）；
        已注册则 requires_tech 空→True，否则 technologies 表按 name 命中。"""
        row = self.conn.execute(
            "SELECT requires_tech FROM troop_tiers WHERE name=?", (str(tier_name or ""),)).fetchone()
        if row is None:
            return True  # AI 现场发明的兵种不在预设表里，不门控
        return self.tech_unlocked(str(row["requires_tech"] or ""))

    # ── 总库增减 ─────────────────────────────────────────────────────
    def _log_arms(self, state: GameState, weapon_id: str, army_id: Optional[str],
                  old: int, new: int, reason: str, source: str) -> None:
        self.conn.execute(
            """
            INSERT INTO arms_logs
            (turn, year, period, weapon_id, army_id, old_value, new_value, delta, reason, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (state.turn, state.year, state.period, weapon_id, army_id,
             old, new, new - old, reason[:120], source),
        )

    def add_arms_stock(self, state: GameState, weapon_name_or_id: str, delta: int,
                       source: str = "issue", reason: str = "") -> int:
        """总库某型号增减（delta 带符号，钳 ≥0）。返回实际变更后总量。未解析型号→动态注册。"""
        w = self._ensure_weapon_registered(weapon_name_or_id)
        if w is None:
            print(f"[WARN] add_arms_stock 无法解析型号 '{weapon_name_or_id}' → 跳过")
            return 0
        wid = str(w["id"])
        old = int((self.conn.execute(
            "SELECT qty FROM arms_stock WHERE weapon_id=?", (wid,)).fetchone() or {"qty": 0})["qty"])
        new = max(0, old + int(delta))
        if new == old:
            return old
        self.conn.execute(
            "UPDATE arms_stock SET qty=?, updated_at=CURRENT_TIMESTAMP WHERE weapon_id=?", (new, wid)
        )
        self._log_arms(state, wid, None, old, new, reason or "军备增减", source)
        return new

    def apply_arms_stock_deltas(self, state: GameState, arms_changes: Dict[str, object]) -> List[Dict[str, object]]:
        """extractor arms_changes 落库：{型号: 增量, "reason": ...}。建筑稳定月产由 flows 唯一变更，
        此处只落叙事性增减（缴获/炸毁/采购）。返回变更清单。"""
        reason = str(arms_changes.get("reason") or arms_changes.get("原因") or "军备变动")
        changes: List[Dict[str, object]] = []
        for key, val in arms_changes.items():
            if key in ("reason", "原因"):
                continue
            try:
                delta = int(val)
            except (TypeError, ValueError):
                print(f"[WARN] arms_changes '{key}' 增量非整数 → 跳过")
                continue
            if delta == 0:
                continue
            w = self._ensure_weapon_registered(str(key))
            if w is None:
                continue
            new = self.add_arms_stock(state, str(w["id"]), delta, source="issue", reason=reason)
            changes.append({"weapon": w["name"], "delta": delta, "new": new, "reason": reason})
        return changes

    # ── 拨发到军某兵种（硬卡：只拨有的）────────────────────────────────
    def apply_arms_dispatch(self, state: GameState, army_id: str, troop_type: str,
                            weapon_name_or_id: str, qty: int, reason: str = "") -> Dict[str, object]:
        """总库→某军「某兵种」拨发（军→兵种→装备）。actual=min(请拨, 总库)；扣总库、增该兵种
        army_arms、提该军 equipment、写流水。troop_type 须在该军 troop_composition 里（归一后比对），
        空则兜底到该军主力兵种（人数最大）。返回 {ok, army, troop_type, weapon, requested, dispatched, ...}。"""
        w = self._ensure_weapon_registered(weapon_name_or_id)
        if w is None:
            return {"ok": False, "note": f"未知型号：{weapon_name_or_id}"}
        wid = str(w["id"])
        army = self.conn.execute(
            "SELECT id, name, manpower, equipment, troop_type, troop_composition FROM armies WHERE id=?",
            (army_id,)).fetchone()
        if army is None:
            return {"ok": False, "note": f"未入库军队：{army_id}"}
        # 校验/兜底兵种：须在该军编制内（归一闭集名比对）。
        composition = self._army_troop_composition(army)
        if not composition:
            return {"ok": False, "army": army["name"], "note": f"{army['name']}无编制兵种，无法拨发"}
        troop = canon_troop_name(str(troop_type or "").strip(), self.content.troop_cost) if troop_type else ""
        if not troop:
            # 空兜底到主力兵种（人数最大）
            troop = max(composition.items(), key=lambda kv: kv[1])[0]
        elif troop not in composition:
            return {"ok": False, "army": army["name"], "weapon": w["name"],
                    "note": f"{army['name']}无「{troop}」兵种（现有：{'、'.join(composition.keys())}）"}
        try:
            req = max(0, int(qty))
        except (TypeError, ValueError):
            return {"ok": False, "note": f"拨发量非整数：{qty}"}
        stock = int((self.conn.execute(
            "SELECT qty FROM arms_stock WHERE weapon_id=?", (wid,)).fetchone() or {"qty": 0})["qty"])
        actual = min(req, stock)
        if actual <= 0:
            return {"ok": False, "army": army["name"], "weapon": w["name"],
                    "requested": req, "dispatched": 0, "note": f"库无「{w['name']}」可拨（现存{stock}）"}
        rsn = (reason or f"拨发{w['name']}予{army['name']}")[:120]
        # 1) 扣总库
        new_stock = stock - actual
        self.conn.execute("UPDATE arms_stock SET qty=?, updated_at=CURRENT_TIMESTAMP WHERE weapon_id=?",
                          (new_stock, wid))
        self._log_arms(state, wid, None, stock, new_stock, rsn, "dispatch")
        # 2) 增该军「该兵种」的 army_arms（军→兵种→装备三级）
        held_row = self.conn.execute(
            "SELECT qty FROM army_arms WHERE army_id=? AND troop_type=? AND weapon_id=?",
            (army_id, troop, wid)).fetchone()
        held_old = int(held_row["qty"]) if held_row else 0
        held_new = held_old + actual
        self.conn.execute(
            """
            INSERT INTO army_arms (army_id, troop_type, weapon_id, qty) VALUES (?, ?, ?, ?)
            ON CONFLICT(army_id, troop_type, weapon_id)
              DO UPDATE SET qty=excluded.qty, updated_at=CURRENT_TIMESTAMP
            """,
            (army_id, troop, wid, held_new),
        )
        self._log_arms(state, wid, army_id, held_old, held_new, rsn, "dispatch")
        # 3) 提该军 equipment：拨发量×equip_per_unit，按军规模折算（每万兵的装备增益），钳 0-100
        manpower = max(1, int(army["manpower"]))
        raw_gain = actual * float(w["equip_per_unit"]) / (manpower / 10000.0)
        eq_old = int(army["equipment"])
        eq_new = max(0, min(100, eq_old + round(raw_gain)))
        if eq_new != eq_old:
            self.conn.execute(
                "UPDATE armies SET equipment=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (eq_new, army_id))
        self.conn.commit()
        return {
            "ok": True, "army": army["name"], "troop_type": troop, "weapon": w["name"],
            "requested": req, "dispatched": actual, "equipment_gain": eq_new - eq_old,
            "note": (f"实拨{actual}（请{req}，库存仅{stock}，照发）" if actual < req
                     else f"拨发{actual}"),
        }

    # ── 展示 payload ─────────────────────────────────────────────────
    def arms_stock_payload(self) -> List[Dict[str, object]]:
        """总库各型号件数（含 0），按 weapons 表 tier/name 排序。供 HUD / state payload。"""
        rows = self.conn.execute(
            """
            SELECT w.id, w.name, w.tier, w.requires_tech, COALESCE(s.qty, 0) AS qty
            FROM weapons w LEFT JOIN arms_stock s ON s.weapon_id = w.id
            ORDER BY w.tier, w.name
            """
        ).fetchall()
        out: List[Dict[str, object]] = []
        for r in rows:
            out.append({
                "id": r["id"], "name": r["name"], "tier": r["tier"],
                "qty": int(r["qty"]),
                "unlocked": self.weapon_unlocked(str(r["id"])),
                "requires_tech": str(r["requires_tech"] or ""),
            })
        return out

    def army_arms_payload(self, army_id: str) -> List[Dict[str, object]]:
        """某军持有武器明细（带 troop_type，军→兵种→装备三级）。供军队抽屉按兵种分组展示。"""
        rows = self.conn.execute(
            """
            SELECT aa.troop_type, aa.weapon_id, w.name, w.tier, aa.qty
            FROM army_arms aa JOIN weapons w ON w.id = aa.weapon_id
            WHERE aa.army_id = ? AND aa.qty > 0
            ORDER BY aa.troop_type, w.tier, w.name
            """,
            (army_id,),
        ).fetchall()
        return [{"troop_type": str(r["troop_type"] or ""), "id": r["weapon_id"],
                 "name": r["name"], "tier": r["tier"], "qty": int(r["qty"])}
                for r in rows]

    def army_held_arms_all(self) -> Dict[str, Dict[str, Dict[str, int]]]:
        """所有在役军队每兵种的持械量 {军名: {兵种名: {武器名: 件数}}}（军→兵种→装备三级）。
        供 simulator/extractor payload——AI 据此判「哪个兵种有多少枪炮、够装备多少人升级」。
        只列 qty>0 的型号；无持械的军/兵种不出现。"""
        rows = self.conn.execute(
            """
            SELECT a.name AS army_name, aa.troop_type, w.name AS weapon_name, aa.qty
            FROM army_arms aa
            JOIN armies a ON a.id = aa.army_id
            JOIN weapons w ON w.id = aa.weapon_id
            WHERE aa.qty > 0 AND a.active = 1
            ORDER BY a.id, aa.troop_type, w.tier, w.name
            """
        ).fetchall()
        out: Dict[str, Dict[str, Dict[str, int]]] = {}
        for r in rows:
            troop = str(r["troop_type"] or "（未分兵种）")
            army_bucket = out.setdefault(str(r["army_name"]), {})
            army_bucket.setdefault(troop, {})[str(r["weapon_name"])] = int(r["qty"])
        return out
