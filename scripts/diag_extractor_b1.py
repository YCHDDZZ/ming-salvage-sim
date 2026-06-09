"""诊断 B1：跑完整 resolve_turn（关 HITL），从 turn_extractions 读 extractor 的 raw 输出，
看它在「整编+持械量」下抽出什么 troop_composition，以及落库后 composition 是否变化。"""
from __future__ import annotations
import os, sys, tempfile, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ming_sim.simulation as simulation
simulation._load_hitl_min_decisions = lambda: 0
from ming_sim.content import GameContent
from ming_sim.llm_config import load_llm_config
from ming_sim.session import GameSession

content = GameContent.load()
llm = load_llm_config(base_url=os.environ.get("OPENAI_BASE_URL",""),
                      model=os.environ.get("OPENAI_MODEL",""), timeout_seconds=180.0)
tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
sess = GameSession(tmp.name, llm, content=content, verify_llm=False)
sess.begin_turn()
st = sess.state
sess.db.apply_arms_dispatch(st, "guanning", "非正规步兵", "火铳", 1200, "测试")
sess.db.apply_arms_dispatch(st, "guanning", "非正规步兵", "三眼铳", 500, "测试")

before = json.loads(sess.db.conn.execute(
    "SELECT troop_composition FROM armies WHERE id='guanning'").fetchone()["troop_composition"])
print("整编前:", before)

cheat = ("关宁军以新拨发的1200杆火铳、500支三眼铳整编一部非正规步兵为火枪步兵"
         "（线列步兵），按实际枪数共约1700人，余部仍为非正规步兵。")
res = sess.resolve_turn(decree="", cheat_directive=cheat)
print("awaiting:", res.awaiting)

after = json.loads(sess.db.conn.execute(
    "SELECT troop_composition FROM armies WHERE id='guanning'").fetchone()["troop_composition"])
print("整编后:", after)

# 读 extractor 的 raw 输出（turn_extractions 留痕）
row = sess.db.conn.execute(
    "SELECT extractor_output FROM turn_extractions ORDER BY turn DESC LIMIT 1").fetchone()
print("\n=== extractor RAW 输出 ===")
print((row["extractor_output"] if row else "(无留痕)")[:3000])

# 验新建军队是否落库（unlink 前查）
print("\n=== 新军是否落库 ===")
rows = sess.db.conn.execute(
    "SELECT id,name,troop_type,troop_composition,manpower FROM armies WHERE id LIKE '%musket%' OR name LIKE '%火枪%'").fetchall()
for r in rows:
    print(dict(r))

os.unlink(tmp.name)
try: os.unlink(tmp.name + ".emperor.db")
except OSError: pass
