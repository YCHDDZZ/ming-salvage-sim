"""GameDB：所有 SQLite 持久化。L3。

原单文件 db.py 已按域拆成本包各 Mixin（方法体逐字未改），此处多继承聚合回 GameDB。
对外 API 与旧 `ming_sim.db` 完全一致：`from ming_sim.db import GameDB, normalize_office,
infer_office_type_from_office` 不变。各 Mixin 共享 self.conn / self.content（由 _BaseMixin.__init__ 建）。

init_schema 建表，seed_static_data 从 GameContent 初始化静态盘面。
"""

from __future__ import annotations

from ming_sim.db._helpers import (
    normalize_office,
    infer_office_type_from_office,
    COURT_OFFICE_TYPES,
    MINISTRY_OFFICE_TYPES,
)
from ming_sim.db.base import _BaseMixin
from ming_sim.db.schema import _SchemaMixin
from ming_sim.db.seed import _SeedMixin
from ming_sim.db.state import _StateMixin
from ming_sim.db.fiscal import _FiscalMixin
from ming_sim.db.characters import _CharactersMixin
from ming_sim.db.factions import _FactionsMixin
from ming_sim.db.powers import _PowersMixin
from ming_sim.db.regions import _RegionsMixin
from ming_sim.db.armies import _ArmiesMixin
from ming_sim.db.arms import _ArmsMixin
from ming_sim.db.buildings import _BuildingsMixin
from ming_sim.db.issues import _IssuesMixin
from ming_sim.db.memories import _MemoriesMixin
from ming_sim.db.turns import _TurnsMixin
from ming_sim.db.chat import _ChatMixin
from ming_sim.db.secret_orders import _SecretOrdersMixin
from ming_sim.db.kv import _KvMixin
from ming_sim.db.admin import _AdminMixin


class GameDB(
    _SchemaMixin,
    _SeedMixin,
    _StateMixin,
    _FiscalMixin,
    _CharactersMixin,
    _FactionsMixin,
    _PowersMixin,
    _RegionsMixin,
    _ArmiesMixin,
    _ArmsMixin,
    _BuildingsMixin,
    _IssuesMixin,
    _MemoriesMixin,
    _TurnsMixin,
    _ChatMixin,
    _SecretOrdersMixin,
    _KvMixin,
    _AdminMixin,
    _BaseMixin,
):
    """GameDB 公共 API 不变；行为=各 Mixin 之和。__init__ 在 _BaseMixin。"""


__all__ = [
    "GameDB",
    "normalize_office",
    "infer_office_type_from_office",
    "COURT_OFFICE_TYPES",
    "MINISTRY_OFFICE_TYPES",
]
