import unittest

from ming_sim.content import GameContent
from ming_sim.db import GameDB
from ming_sim.models import Event, GameState


class ArmyDeltaSemanticsTests(unittest.TestCase):
    def setUp(self):
        self.content = GameContent.load()
        self.db = GameDB(":memory:", self.content)
        self.db.seed_static_data()
        self.state = GameState()
        self.event = Event(
            id="test",
            title="军队增减测试",
            kind="测试",
            summary="",
            urgency=0,
            severity=0,
            credibility=100,
            interests=[],
            audiences=[],
        )

    def test_existing_army_manpower_is_delta_only(self):
        before = self.db.conn.execute(
            "SELECT manpower FROM armies WHERE id = 'guanning'"
        ).fetchone()["manpower"]

        self.db.apply_army_deltas(
            self.state,
            self.event,
            None,
            "测试",
            {"guanning": {"manpower": 8000, "reason": "补兵八千"}},
        )

        after = self.db.conn.execute(
            "SELECT manpower FROM armies WHERE id = 'guanning'"
        ).fetchone()["manpower"]
        log = self.db.conn.execute(
            """
            SELECT old_value, new_value, delta
            FROM army_logs
            WHERE army_id = 'guanning' AND field = 'manpower'
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

        self.assertEqual(after, before + 8000)
        self.assertEqual(int(log["old_value"]), before)
        self.assertEqual(int(log["new_value"]), before + 8000)
        self.assertEqual(log["delta"], 8000)

    def test_existing_army_maintenance_is_delta_only(self):
        before = self.db.conn.execute(
            "SELECT maintenance_per_turn FROM armies WHERE id = 'guanning'"
        ).fetchone()["maintenance_per_turn"]

        self.db.apply_army_deltas(
            self.state,
            self.event,
            None,
            "测试",
            {"guanning": {"maintenance_per_turn": 5, "reason": "月饷增五万"}},
        )

        after = self.db.conn.execute(
            "SELECT maintenance_per_turn FROM armies WHERE id = 'guanning'"
        ).fetchone()["maintenance_per_turn"]

        self.assertEqual(after, before + 5)

    def test_duplicate_new_army_does_not_merge_into_existing_army(self):
        before = self.db.conn.execute(
            "SELECT manpower FROM armies WHERE id = 'guanning'"
        ).fetchone()["manpower"]

        created = self.db.create_armies_from_extraction(
            self.state,
            [
                {
                    "id": "guanning",
                    "name": "关宁军 / 宁锦防线",
                    "owner_power": "ming",
                    "station": "辽东 / 宁远锦州",
                    "commander": "袁崇焕",
                    "troop_type": "边军、骑兵、火器兵、炮兵",
                    "manpower": before,
                    "maintenance_per_turn": 15,
                    "supply": 38,
                    "morale": 52,
                    "training": 68,
                    "equipment": 62,
                    "mobility": 48,
                    "loyalty": 55,
                    "status": "重复抽成新建军队",
                }
            ],
        )

        after = self.db.conn.execute(
            "SELECT manpower FROM armies WHERE id = 'guanning'"
        ).fetchone()["manpower"]
        log_count = self.db.conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM army_logs
            WHERE army_id = 'guanning' AND field = 'manpower'
            """
        ).fetchone()["count"]

        self.assertEqual(created, [])
        self.assertEqual(after, before)
        self.assertEqual(log_count, 0)


if __name__ == "__main__":
    unittest.main()
