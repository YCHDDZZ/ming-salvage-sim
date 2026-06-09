"""军事装备：weapons 型号注册 / arms_stock 总库 / army_arms 拨发 / arms_logs 流水。

_ArmsMixin。军备实物链：建筑产械入总库（flows）→ 皇帝下旨拨发给某军（dispatch）提 equipment。
- 型号清单走 content/weapons.json，seed 灌 weapons 表，版本化走 kv_store(weapons_version)（铁律）。
- 部分型号需 requires_tech 前置科技（technologies 表已解锁）才可产/造。
- 拨发硬卡：只拨总库现有量（actual=min(请拨,库存)）。
"""

from __future__ import annotations

from typing import Dict, List, Optional

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
                INSERT INTO weapons (id, name, tier, power, cost, equip_per_unit, requires_tech, registered)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'seed')
                ON CONFLICT(id) DO UPDATE SET
                  name=excluded.name, tier=excluded.tier, power=excluded.power,
                  cost=excluded.cost, equip_per_unit=excluded.equip_per_unit,
                  requires_tech=excluded.requires_tech, registered='seed',
                  updated_at=CURRENT_TIMESTAMP
                WHERE weapons.registered='seed'
                """,
                (w["id"], w["name"], w["tier"], int(w["power"]), int(w["cost"]),
                 float(w["equip_per_unit"]), str(w.get("requires_tech") or "")),
            )
            # 总库行确保存在（不覆盖已有 qty）
            self.conn.execute(
                "INSERT OR IGNORE INTO arms_stock (weapon_id, qty) VALUES (?, 0)", (w["id"],)
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
            INSERT INTO weapons (id, name, tier, power, cost, equip_per_unit, requires_tech, registered)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'runtime')
            ON CONFLICT(id) DO NOTHING
            """,
            (meta["id"], meta["name"], meta["tier"], int(meta["power"]), int(meta["cost"]),
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
        tech = str(row["requires_tech"] or "").strip()
        if not tech:
            return True
        return self.conn.execute(
            "SELECT 1 FROM technologies WHERE name=?", (tech,)
        ).fetchone() is not None

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

    # ── 拨发到军（硬卡：只拨有的）──────────────────────────────────────
    def apply_arms_dispatch(self, state: GameState, army_id: str, weapon_name_or_id: str,
                            qty: int, reason: str = "") -> Dict[str, object]:
        """总库→某军拨发。actual=min(请拨, 总库)；扣总库、增 army_arms、提该军 equipment、写流水。
        返回 {ok, army, weapon, requested, dispatched, equipment_gain, note}。"""
        w = self._ensure_weapon_registered(weapon_name_or_id)
        if w is None:
            return {"ok": False, "note": f"未知型号：{weapon_name_or_id}"}
        wid = str(w["id"])
        army = self.conn.execute("SELECT id, name, manpower, equipment FROM armies WHERE id=?",
                                 (army_id,)).fetchone()
        if army is None:
            return {"ok": False, "note": f"未入库军队：{army_id}"}
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
        # 2) 增 army_arms
        held_row = self.conn.execute(
            "SELECT qty FROM army_arms WHERE army_id=? AND weapon_id=?", (army_id, wid)).fetchone()
        held_old = int(held_row["qty"]) if held_row else 0
        held_new = held_old + actual
        self.conn.execute(
            """
            INSERT INTO army_arms (army_id, weapon_id, qty) VALUES (?, ?, ?)
            ON CONFLICT(army_id, weapon_id) DO UPDATE SET qty=excluded.qty, updated_at=CURRENT_TIMESTAMP
            """,
            (army_id, wid, held_new),
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
            "ok": True, "army": army["name"], "weapon": w["name"],
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
        """某军持有武器明细。供军队抽屉展示。"""
        rows = self.conn.execute(
            """
            SELECT aa.weapon_id, w.name, w.tier, aa.qty
            FROM army_arms aa JOIN weapons w ON w.id = aa.weapon_id
            WHERE aa.army_id = ? AND aa.qty > 0
            ORDER BY w.tier, w.name
            """,
            (army_id,),
        ).fetchall()
        return [{"id": r["weapon_id"], "name": r["name"], "tier": r["tier"], "qty": int(r["qty"])}
                for r in rows]
