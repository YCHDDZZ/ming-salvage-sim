import tempfile
import unittest

from ming_sim.content import GameContent, canon_troop_name, troop_rate_for_type
from ming_sim.db import GameDB
from ming_sim.flows import apply_fixed_period_flows
from ming_sim.models import Event, GameState
import ming_sim.issues as issues


class ArmsAndTroopsTests(unittest.TestCase):
    def setUp(self):
        self.content = GameContent.load()
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db")
        self.db = GameDB(self.tmp.name, self.content)
        self.db.seed_static_data()
        self.state = self.db.load_state()

    def tearDown(self):
        self.tmp.close()

    def test_opening_arms_stock_defaults(self):
        stock = {item["id"]: item for item in self.db.arms_stock_payload()}
        self.assertEqual(stock["huochong"]["qty"], 1200)
        self.assertEqual(stock["niaochong"]["qty"], 300)
        self.assertEqual(stock["sanyan_chong"]["qty"], 500)
        self.assertEqual(stock["hudun_pao"]["qty"], 40)
        self.assertEqual(stock["folangji"]["qty"], 12)
        self.assertFalse(stock["suifa_qiang"]["unlocked"])
        self.assertEqual(stock["suifa_qiang"]["qty"], 0)

    def test_opening_monthly_arms_production(self):
        flows = apply_fixed_period_flows(self.db, self.state)
        arms_flows = {
            (item["weapon"], item["building"]): item["amount"]
            for item in flows
            if item.get("dir") == "arms"
        }
        self.assertEqual(arms_flows[("huochong", "京营火器局")], 440)
        self.assertEqual(arms_flows[("folangji", "定海卫海防炮台")], 2)
        stock = {item["id"]: item["qty"] for item in self.db.arms_stock_payload()}
        self.assertEqual(stock["huochong"], 1640)
        self.assertEqual(stock["folangji"], 14)

    def test_army_payload_has_composition_and_computed_pay(self):
        army = next(item for item in self.db.army_payload() if item["id"] == "jingying")
        self.assertEqual(army["troop_composition"], {"非正规步兵": 75000, "火炮队": 5000, "骑兵": 5000})
        self.assertEqual(army["manpower"], sum(army["troop_composition"].values()))
        self.assertEqual(army["maintenance_per_turn"], self.content.troop_maintenance_total(army["troop_composition"]))

    def test_army_held_arms_feeds_payload(self):
        # 拨发军械后，每军持械量进 army_held_arms（AI 据此判升级规模）；未拨发的军不出现。
        self.assertEqual(self.db.army_held_arms_all(), {})  # 开局各军无入库持械
        self.db.apply_arms_dispatch(self.state, "jingying", "火铳", 1200, "测试拨发")
        held = self.db.army_held_arms_all()
        self.assertIn("京营", held)
        self.assertEqual(held["京营"]["火铳"], 1200)
        # 其余军未拨发 → 不在表里
        self.assertNotIn("关宁军 / 宁锦防线", held)


class TroopRateAndCanonTests(unittest.TestCase):
    def setUp(self):
        self.content = GameContent.load()
        self.tc = self.content.troop_cost

    def test_long_name_not_eaten_by_short(self):
        # B1 bug：「骑兵」是「骠骑兵」的子串，骠骑兵单价必须取自己档而非被骑兵吃
        self.assertEqual(troop_rate_for_type("骠骑兵", self.tc), 0.2)
        self.assertEqual(troop_rate_for_type("骑兵", self.tc), 0.16)

    def test_free_text_takes_most_expensive_hit(self):
        # 自由串关键词命中多档时取最贵（红夷炮队→火炮队 0.2），不随 JSON 顺序漂移
        self.assertEqual(troop_rate_for_type("红夷炮队", self.tc), 0.2)

    def test_canon_number_and_dirty_name(self):
        # 番号/脏名归一到固定兵种闭集名
        self.assertEqual(canon_troop_name("关宁铁骑", self.tc), "骑兵")
        self.assertEqual(canon_troop_name("步卒", self.tc), "非正规步兵")
        # 精确名原样保留
        self.assertEqual(canon_troop_name("线列步兵", self.tc), "线列步兵")


class TechGateTests(unittest.TestCase):
    def setUp(self):
        self.content = GameContent.load()
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db")
        self.db = GameDB(self.tmp.name, self.content)
        self.db.seed_static_data()
        self.state = self.db.load_state()

    def tearDown(self):
        self.tmp.close()

    def test_troop_tiers_seeded(self):
        n = self.db.conn.execute("SELECT COUNT(*) FROM troop_tiers").fetchone()[0]
        self.assertEqual(n, len(self.content.troop_cost["tiers"]))

    def test_preset_troop_gate(self):
        # 预设超前兵种未研成对应科技 → 锁；基础兵种放行；AI 新兵种放行
        self.assertTrue(self.db.troop_unlocked("非正规步兵"))
        self.assertFalse(self.db.troop_unlocked("机械化步兵"))
        self.assertTrue(self.db.troop_unlocked("电磁炮兵"))  # runtime/AI 自创，不在表里
        # 研成科技后解锁
        self.db.add_technology(self.state, "内燃机甲", "科技", origin="issue")
        self.assertTrue(self.db.troop_unlocked("机械化步兵"))

    def test_building_tech_gate(self):
        rid = self.db.conn.execute("SELECT id FROM regions LIMIT 1").fetchone()["id"]
        with self.assertRaises(ValueError):
            self.db.add_building(self.state, region_id=rid, name="蒸汽厂",
                                 category="军事", requires_tech="蒸汽机")
        self.db.add_technology(self.state, "蒸汽机", "科技", origin="issue")
        bid = self.db.add_building(self.state, region_id=rid, name="蒸汽厂",
                                   category="军事", requires_tech="蒸汽机")
        self.assertTrue(bid)

    def test_weapon_gate_still_works(self):
        self.assertTrue(self.db.weapon_unlocked("huochong"))
        self.assertFalse(self.db.weapon_unlocked("suifa_qiang"))
        self.db.add_technology(self.state, "火器新法", "科技", origin="issue")
        self.assertTrue(self.db.weapon_unlocked("suifa_qiang"))

    def test_recompose_locked_troop_folds_into_default(self):
        # 端到端：改编制塞入未解锁的「机械化步兵」（内燃机甲未研），
        # 落库后 composition 不应含该兵种，兵力并入 default_tier「非正规步兵」。
        event = Event(id="t", title="整编", kind="测试", summary="", urgency=0,
                      severity=0, credibility=100, interests=[], audiences=[])
        changes = self.db.apply_army_deltas(
            self.state, event, None, "测试",
            {"guanning": {"troop_composition": {"机械化步兵": 20000, "骑兵": 10000},
                          "reason": "整编新军"}},
        )
        import json
        comp = json.loads(self.db.conn.execute(
            "SELECT troop_composition FROM armies WHERE id='guanning'").fetchone()["troop_composition"])
        self.assertNotIn("机械化步兵", comp)          # 未解锁，被门控剔除
        self.assertEqual(comp.get("骑兵"), 10000)      # 已解锁，原样保留
        self.assertEqual(comp.get("非正规步兵"), 20000)  # 锁定兵力并入 default
        # 程序代为降级的事实透出到明细 note，玩家可见
        entry = next(c for c in changes if c.get("field") == "troop_composition")
        self.assertIn("机械化步兵", entry.get("note", ""))
        self.assertIn("内燃机甲", entry.get("note", ""))

    def test_recompose_unlocked_troop_kept_after_tech(self):
        # 研成内燃机甲后，机械化步兵编制应原样落库，不再并入 default。
        self.db.add_technology(self.state, "内燃机甲", "科技", origin="issue")
        event = Event(id="t", title="整编", kind="测试", summary="", urgency=0,
                      severity=0, credibility=100, interests=[], audiences=[])
        self.db.apply_army_deltas(
            self.state, event, None, "测试",
            {"guanning": {"troop_composition": {"机械化步兵": 20000, "骑兵": 10000}}},
        )
        import json
        comp = json.loads(self.db.conn.execute(
            "SELECT troop_composition FROM armies WHERE id='guanning'").fetchone()["troop_composition"])
        self.assertEqual(comp.get("机械化步兵"), 20000)

    def test_issue_effect_building_gate_blocks_locked(self):
        # 端到端：走 issue effect 落建筑，带未研成的 requires_tech → 不落库。
        issues.bind_content(self.content)
        rid = self.db.conn.execute("SELECT id FROM regions LIMIT 1").fetchone()["id"]
        before = self.db.conn.execute("SELECT COUNT(*) FROM buildings").fetchone()[0]
        op = [{"action": "create", "region_id": rid, "name": "蒸汽兵工厂",
               "category": "军事", "requires_tech": "蒸汽机"}]
        applied = issues._apply_issue_buildings(self.db, self.state, op, issues._ISSUE_PSEUDO_EVENT, "测试结案")
        after = self.db.conn.execute("SELECT COUNT(*) FROM buildings").fetchone()[0]
        self.assertEqual(after, before)  # 门控拦截，未落库
        # 拒绝事实透出到明细
        self.assertTrue(applied and applied[0].get("rejected"))
        self.assertIn("蒸汽机", applied[0].get("note", ""))
        # 研成后再走同一 op → 落库
        self.db.add_technology(self.state, "蒸汽机", "科技", origin="issue")
        issues._apply_issue_buildings(self.db, self.state, op, issues._ISSUE_PSEUDO_EVENT, "测试结案")
        after2 = self.db.conn.execute("SELECT COUNT(*) FROM buildings").fetchone()[0]
        self.assertEqual(after2, before + 1)


class EffectBriefGateTests(unittest.TestCase):
    def test_blocked_building_surfaces_in_brief(self):
        # 建筑被门控拒绝（building_ops.rejected）→ effect_brief 透出「工程受阻」
        from ming_sim.memories import effect_brief
        applied = {"issue_summary": {"advances": [{
            "title": "蒸汽局",
            "building_ops": [{"action": "create", "name": "蒸汽兵工厂",
                              "rejected": True, "note": "前置科技「蒸汽机」未研成"}],
        }]}}
        brief = effect_brief(applied)
        self.assertIn("工程受阻", brief)
        self.assertIn("蒸汽机", brief)

    def test_gated_troop_surfaces_in_brief(self):
        from ming_sim.memories import effect_brief
        applied = {"army_changes": [{"army": "关宁军", "field": "troop_composition",
                                     "note": "机械化步兵20000兵需先研成「内燃机甲」，暂并入「非正规步兵」"}]}
        brief = effect_brief(applied)
        self.assertIn("科技未及", brief)
        self.assertIn("内燃机甲", brief)


if __name__ == "__main__":
    unittest.main()
