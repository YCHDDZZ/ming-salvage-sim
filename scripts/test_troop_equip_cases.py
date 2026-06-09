"""跑通验证：兵种升级须有对应实物装备（AI 软判）。

每个 case 程序拨发特定军械（确定性）→ resolve_turn 带 cheat_directive 注入整编意图
→ 真跑 simulator/extractor LLM → 检查落库后该军的 troop_composition。

不靠 AI 崇祯自主玩（不可控），只测「AI 看 army_held_arms 定升级人数」这一环。
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ming_sim.simulation as simulation
from ming_sim.content import GameContent
from ming_sim.llm_config import load_llm_config
from ming_sim.session import GameSession

# 关闭 HITL 决策点注入，否则 simulator 每月产 2 个决策点暂停，cheat 的整编意图进不了 extractor。
simulation._load_hitl_min_decisions = lambda: 0


def _comp(session, army_id: str) -> dict:
    row = session.db.conn.execute(
        "SELECT troop_composition FROM armies WHERE id=?", (army_id,)).fetchone()
    return json.loads(row["troop_composition"] or "{}")


def _held(session, army_id: str) -> dict:
    rows = session.db.conn.execute(
        """SELECT w.name, aa.qty FROM army_arms aa JOIN weapons w ON w.id=aa.weapon_id
           WHERE aa.army_id=? AND aa.qty>0""", (army_id,)).fetchall()
    return {r["name"]: int(r["qty"]) for r in rows}


def run_case(name: str, dispatches: list, cheat: str, army_id: str, content, llm_config):
    """dispatches: [(weapon, qty), ...]；cheat: 注入 extractor 的整编意图既成事实。"""
    print(f"\n{'='*70}\n【CASE】{name}\n{'='*70}")
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    try:
        session = GameSession(tmp.name, llm_config, content=content, verify_llm=False)
        session.begin_turn()
        state = session.state
        # 1) 程序拨发军械（确定性）—— 拨给某军某兵种（军→兵种→装备）
        for troop, weapon, qty in dispatches:
            res = session.db.apply_arms_dispatch(state, army_id, troop, weapon, qty, "测试拨发")
            print(f"  拨发 {troop}/{weapon} x{qty} → ok={res.get('ok')} 实拨={res.get('dispatched')}")
        before = _comp(session, army_id)
        print(f"  整编前 composition: {before}")
        print(f"  该军实际持械 held_arms: {_held(session, army_id)}")
        # 2) resolve（真跑 LLM），cheat_directive 注入整编意图
        print(f"  注入整编意图: {cheat}")
        result = session.resolve_turn(decree="", cheat_directive=cheat)
        if result.awaiting:
            print("  [跳过] 推演产生 HITL 决策点，本 case 不深入")
            return
        after = _comp(session, army_id)
        print(f"  整编后 composition: {after}")
        print(f"  邸报节选: {(session.last_report or '')[:200]}")
    finally:
        try:
            os.unlink(tmp.name)
            os.unlink(tmp.name + ".emperor.db")
        except OSError:
            pass


def main():
    content = GameContent.load()
    llm_config = load_llm_config(
        base_url=os.environ.get("OPENAI_BASE_URL", ""),
        model=os.environ.get("OPENAI_MODEL", ""),
        timeout_seconds=float(os.environ.get("OPENAI_TIMEOUT_SECONDS", "180") or "180"),
    )
    # 用关宁军（guanning）做被试，开局是基础步骑。京营总库有火铳/虎蹲炮/佛郎机可拨。
    army = "guanning"

    # 注意：apply_arms_dispatch 硬卡 min(请拨, 总库)。开局总库火铳1200/三眼铳500/鸟铳300/
    # 虎蹲炮40/佛郎机12。故拨发量取库存内真实值。1200杆枪只够1200人换装——正好验「按件数定人数」。
    cases = [
        ("B1 够装备→按件数升级（拨1200火铳+500三眼铳=1700件给非正规步兵，整编火枪步兵）",
         [("非正规步兵", "火铳", 1200), ("非正规步兵", "三眼铳", 500)],
         "关宁军以新拨发的火铳、三眼铳整编一部非正规步兵为火枪步兵（线列步兵），按实际枪数定人数，余部仍为非正规步兵。",
         army),
        ("B2 无装备→拒升（不拨任何枪，硬整编全军为火枪步兵）",
         [],
         "关宁军全军整编为火枪步兵（线列步兵）。",
         army),
        ("B3 炮兵按门配人（拨40虎蹲炮+12佛郎机=52门给火炮队，约配2600人）",
         [("火炮队", "虎蹲炮", 40), ("火炮队", "佛郎机", 12)],
         "关宁军以新拨发的火炮整编一部为火炮队，按火炮门数定炮兵人数（炮约1门配50人）。",
         army),
    ]
    for cname, disp, cheat, aid in cases:
        try:
            run_case(cname, disp, cheat, aid, content, llm_config)
        except Exception as exc:  # noqa: BLE001
            print(f"  [ERROR] case 异常：{type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
