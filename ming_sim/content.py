"""设定加载：把 content/*.json 与 content/prompts/*.md 收进 GameContent。L2。

GameContent.load() 显式调用——模块导入本身不读盘、无副作用。
设定文件是唯一来源（CLAUDE.md），代码不硬编码副本。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from ming_sim.assets import (
    int_field,
    load_json_asset,
    load_text_asset,
    require_dict,
    require_list,
    str_field,
    string_list,
    validate_gate_expr,
)
from ming_sim.constants import BUILDING_CATEGORIES, BUILDING_OUTPUT_METRICS
from ming_sim.models import (
    Army,
    Building,
    Character,
    Event,
    Faction,
    OpeningLegacy,
    Power,
    PresetDepartment,
    PresetTechnology,
    Region,
    SocialClass,
)


# --- 单项加载器（保留原签名，便于复用与单测）---

def load_character_content() -> Tuple[Dict[str, Faction], Dict[str, Character]]:
    data = require_dict(load_json_asset("characters.json"), "characters.json")
    factions: Dict[str, Faction] = {}
    for idx, raw in enumerate(require_list(data.get("factions"), "characters.json.factions"), 1):
        item = require_dict(raw, f"characters.json.factions[{idx}]")
        name = str_field(item, "name", f"characters.json.factions[{idx}]")
        factions[name] = Faction(
            name=name,
            satisfaction=int_field(item, "satisfaction", f"characters.json.factions[{idx}]"),
            leverage=int_field(item, "leverage", f"characters.json.factions[{idx}]"),
            agenda=str_field(item, "agenda", f"characters.json.factions[{idx}]"),
        )

    characters: Dict[str, Character] = {}
    for idx, raw in enumerate(require_list(data.get("characters"), "characters.json.characters"), 1):
        item = require_dict(raw, f"characters.json.characters[{idx}]")
        name = str_field(item, "name", f"characters.json.characters[{idx}]")
        characters[name] = Character(
            name=name,
            office=str_field(item, "office", f"characters.json.characters[{idx}]"),
            office_type=str_field(item, "office_type", f"characters.json.characters[{idx}]"),
            faction=str_field(item, "faction", f"characters.json.characters[{idx}]"),
            aliases=string_list(item.get("aliases", []), f"characters.json.characters[{idx}].aliases"),
            personal_skills=string_list(item.get("personal_skills"), f"characters.json.characters[{idx}].personal_skills"),
            loyalty=int_field(item, "loyalty", f"characters.json.characters[{idx}]"),
            ability=int_field(item, "ability", f"characters.json.characters[{idx}]"),
            integrity=int_field(item, "integrity", f"characters.json.characters[{idx}]"),
            courage=int_field(item, "courage", f"characters.json.characters[{idx}]"),
            style=str_field(item, "style", f"characters.json.characters[{idx}]"),
            power_id=str_field(item, "power_id", f"characters.json.characters[{idx}]"),
            diplomacy=int(item.get("diplomacy", item.get("ability", 50)) or 50),
            martial=int(item.get("martial", item.get("military", item.get("ability", 50))) or 50),
            stewardship=int(item.get("stewardship", item.get("administration", item.get("ability", 50))) or 50),
            intrigue=int(item.get("intrigue", item.get("ability", 50)) or 50),
            learning=int(item.get("learning", item.get("ability", 50)) or 50),
            location=str(item.get("location") or "").strip(),
            birth_year=int(item.get("birth_year") or 0),
            historical_death_year=int(item.get("historical_death_year") or 0),
            historical_death_month=int(item.get("historical_death_month") or 0),
            debut_year=int(item.get("debut_year") or 0),
            debut_month=int(item.get("debut_month") or 0),
            status=str(item.get("status") or "active"),
            summary=str(item.get("summary") or ""),
            portrait_id=str(item.get("portrait_id") or ""),
        )

    if not factions or not characters:
        raise SystemExit("characters.json 必须至少定义一个派系和一个人物。")
    return factions, characters


def load_event_content(filename: str = "events.json") -> List[Event]:
    events: List[Event] = []
    for idx, raw in enumerate(require_list(load_json_asset(filename), filename), 1):
        item = require_dict(raw, f"{filename}[{idx}]")
        event_type = str(item.get("event_type") or "situation")
        if event_type not in ("situation", "node", "ending"):
            raise SystemExit(
                f"{filename}[{idx}] event_type 非法：{event_type!r}（仅 situation/node/ending）。"
            )
        # trigger_gate（seed 候选门槛）与 require（历史 node 可证伪前提）共用 gate DSL 校验。
        # key 形式与布尔树结构见 gating.evaluate_gate；id/field 存在性由 runtime 求值器校验。
        trigger_gate = validate_gate_expr(item.get("trigger_gate") or {}, f"{filename}[{idx}].trigger_gate")
        require = validate_gate_expr(item.get("require") or {}, f"{filename}[{idx}].require")
        ev_trigger_year = int(item.get("trigger_year") or 0)
        # is_historical：JSON 显式声明优先；未填则缺省 = trigger_year>0（沿用旧推断）。
        if "is_historical" in item:
            if not isinstance(item["is_historical"], bool):
                raise SystemExit(f"{filename}[{idx}].is_historical 应为布尔值 true/false（得到 {item['is_historical']!r}）。")
            ev_is_historical = item["is_historical"]
        else:
            ev_is_historical = ev_trigger_year > 0
        events.append(
            Event(
                id=str_field(item, "id", f"{filename}[{idx}]"),
                title=str_field(item, "title", f"{filename}[{idx}]"),
                kind=str_field(item, "kind", f"{filename}[{idx}]"),
                summary=str_field(item, "summary", f"{filename}[{idx}]"),
                urgency=int_field(item, "urgency", f"{filename}[{idx}]"),
                severity=int_field(item, "severity", f"{filename}[{idx}]"),
                credibility=int_field(item, "credibility", f"{filename}[{idx}]"),
                interests=string_list(item.get("interests"), f"{filename}[{idx}].interests"),
                audiences=string_list(item.get("audiences"), f"{filename}[{idx}].audiences"),
                resolve_condition=str(item.get("resolve_condition") or ""),
                fail_condition=str(item.get("fail_condition") or ""),
                trigger_year=ev_trigger_year,
                trigger_month=int(item.get("trigger_month") or 0),
                is_historical=ev_is_historical,
                trigger_end_year=int(item.get("trigger_end_year") or 0),
                trigger_end_month=int(item.get("trigger_end_month") or 0),
                precondition=str(item.get("precondition") or ""),
                require=require,
                event_type=event_type,
                trigger_gate=trigger_gate,
                auto_trigger=bool(item.get("auto_trigger") or False),
                bar_value=int(item.get("bar_value") or 0),
                bar_good_meaning=str(item.get("bar_good_meaning") or ""),
                bar_bad_meaning=str(item.get("bar_bad_meaning") or ""),
                issue_inertia=int(item.get("inertia") or 0),
                stage_text=str(item.get("stage_text") or ""),
                region_hint=str(item.get("region_hint") or ""),
                issue_tags=string_list(item.get("tags"), f"{filename}[{idx}].tags") if item.get("tags") else [],
                ongoing_effects=dict(item.get("ongoing_effects") or {}),
                effect_on_resolve=dict(item.get("effect_on_resolve") or {}),
                effect_on_fail=dict(item.get("effect_on_fail") or {}),
            )
        )
    if not events:
        raise SystemExit(f"{filename} 必须至少定义一个事件。")
    return events


def load_region_content() -> Dict[str, Region]:
    data = require_dict(load_json_asset("regions.json"), "regions.json")
    regions: Dict[str, Region] = {}
    for idx, raw in enumerate(require_list(data.get("regions"), "regions.json.regions"), 1):
        item = require_dict(raw, f"regions.json.regions[{idx}]")
        region_id = str_field(item, "id", f"regions.json.regions[{idx}]")
        ctx = f"regions.json.regions[{idx}]"
        fiscal_raw = item.get("fiscal")
        if not isinstance(fiscal_raw, dict):
            raise SystemExit(f"{ctx}.fiscal 必须是 JSON 对象，实际为 {type(fiscal_raw).__name__}。")
        regions[region_id] = Region(
            id=region_id,
            name=str_field(item, "name", ctx),
            kind=str_field(item, "kind", ctx),
            population=int_field(item, "population", ctx),
            public_support=int_field(item, "public_support", ctx),
            unrest=int_field(item, "unrest", ctx),
            natural_disaster=str_field(item, "natural_disaster", ctx),
            human_disaster=str_field(item, "human_disaster", ctx),
            registered_land=int_field(item, "registered_land", ctx),
            hidden_land=int_field(item, "hidden_land", ctx),
            tax_per_turn=int_field(item, "tax_per_turn", ctx),
            gentry_resistance=int_field(item, "gentry_resistance", ctx),
            military_pressure=int_field(item, "military_pressure", ctx),
            status=str_field(item, "status", ctx),
            controlled_by=str_field(item, "controlled_by", ctx),
            fiscal=dict(fiscal_raw),
            on_restore=dict(item.get("on_restore") or {}),
        )
    if not regions:
        raise SystemExit("regions.json 必须至少定义一个地区。")
    return regions


def load_army_content() -> Dict[str, Army]:
    data = require_dict(load_json_asset("armies.json"), "armies.json")
    armies: Dict[str, Army] = {}
    for idx, raw in enumerate(require_list(data.get("armies"), "armies.json.armies"), 1):
        item = require_dict(raw, f"armies.json.armies[{idx}]")
        army_id = str_field(item, "id", f"armies.json.armies[{idx}]")
        armies[army_id] = Army(
            id=army_id,
            name=str_field(item, "name", f"armies.json.armies[{idx}]"),
            station=str_field(item, "station", f"armies.json.armies[{idx}]"),
            theater=str_field(item, "theater", f"armies.json.armies[{idx}]"),
            commander=str_field(item, "commander", f"armies.json.armies[{idx}]"),
            controller=str_field(item, "controller", f"armies.json.armies[{idx}]"),
            troop_type=str_field(item, "troop_type", f"armies.json.armies[{idx}]"),
            manpower=int_field(item, "manpower", f"armies.json.armies[{idx}]"),
            maintenance_per_turn=int_field(item, "maintenance_per_turn", f"armies.json.armies[{idx}]"),
            supply=int_field(item, "supply", f"armies.json.armies[{idx}]"),
            morale=int_field(item, "morale", f"armies.json.armies[{idx}]"),
            training=int_field(item, "training", f"armies.json.armies[{idx}]"),
            equipment=int_field(item, "equipment", f"armies.json.armies[{idx}]"),
            arrears=int_field(item, "arrears", f"armies.json.armies[{idx}]"),
            mobility=int_field(item, "mobility", f"armies.json.armies[{idx}]"),
            loyalty=int_field(item, "loyalty", f"armies.json.armies[{idx}]"),
            status=str_field(item, "status", f"armies.json.armies[{idx}]"),
            owner_power=str_field(item, "owner_power", f"armies.json.armies[{idx}]"),
        )
    if not armies:
        raise SystemExit("armies.json 必须至少定义一支军队。")
    return armies


def load_building_content() -> Dict[str, Building]:
    data = require_dict(load_json_asset("buildings.json"), "buildings.json")
    buildings: Dict[str, Building] = {}
    for idx, raw in enumerate(require_list(data.get("buildings"), "buildings.json.buildings"), 1):
        item = require_dict(raw, f"buildings.json.buildings[{idx}]")
        ctx = f"buildings.json.buildings[{idx}]"
        building_id = str_field(item, "id", ctx)
        category = str_field(item, "category", ctx)
        if category not in BUILDING_CATEGORIES:
            raise SystemExit(f"{ctx}: category '{category}' 不在白名单 {BUILDING_CATEGORIES}。")
        output_metric = str(item.get("output_metric") or "")
        if output_metric not in BUILDING_OUTPUT_METRICS:
            raise SystemExit(f"{ctx}: output_metric '{output_metric}' 不在白名单 {BUILDING_OUTPUT_METRICS}。")
        buildings[building_id] = Building(
            id=building_id,
            region_id=str_field(item, "region_id", ctx),
            name=str_field(item, "name", ctx),
            category=category,
            level=int_field(item, "level", ctx),
            condition=int_field(item, "condition", ctx),
            maintenance=int_field(item, "maintenance", ctx),
            risk=int_field(item, "risk", ctx),
            output_metric=output_metric,
            output_amount=int_field(item, "output_amount", ctx),
            status=str_field(item, "status", ctx),
        )
    if not buildings:
        raise SystemExit("buildings.json 必须至少定义一座建筑。")
    return buildings


def load_class_content() -> Dict[str, SocialClass]:
    """阶级人口设定。key = "name@region_id"（region_id 为空则 key="name"）。"""
    data = require_dict(load_json_asset("classes.json"), "classes.json")
    classes: Dict[str, SocialClass] = {}
    for idx, raw in enumerate(require_list(data.get("classes"), "classes.json.classes"), 1):
        item = require_dict(raw, f"classes.json.classes[{idx}]")
        name = str_field(item, "name", f"classes.json.classes[{idx}]")
        region_id = str(item.get("region_id") or "").strip()
        key = f"{name}@{region_id}" if region_id else name
        if key in classes:
            raise SystemExit(f"classes.json 重复条目：{key}")
        classes[key] = SocialClass(
            name=name,
            region_id=region_id,
            population=int_field(item, "population", f"classes.json.classes[{idx}]"),
            satisfaction=int_field(item, "satisfaction", f"classes.json.classes[{idx}]"),
            leverage=int_field(item, "leverage", f"classes.json.classes[{idx}]"),
            agenda=str_field(item, "agenda", f"classes.json.classes[{idx}]"),
        )
    if not classes:
        raise SystemExit("classes.json 必须至少定义一个阶级条目。")
    return classes


def load_powers() -> Dict[str, Power]:
    data = load_json_asset("powers.json")
    raw = require_dict(data, "powers.json")
    powers_raw = require_list(raw.get("powers"), "powers.json::powers")
    powers: Dict[str, Power] = {}
    for item in powers_raw:
        entry = require_dict(item, "powers.json::powers[item]")
        pid = str_field(entry, "id", "powers.json::powers[item].id")
        powers[pid] = Power(
            id=pid,
            name=str_field(entry, "name", "powers.json::powers[item].name"),
            kind=str_field(entry, "kind", "powers.json::powers[item].kind"),
            leader=str_field(entry, "leader", "powers.json::powers[item].leader"),
            stance=str_field(entry, "stance", "powers.json::powers[item].stance"),
            leverage=int_field(entry, "leverage", "powers.json::powers[item].leverage"),
            satisfaction=int_field(entry, "satisfaction", "powers.json::powers[item].satisfaction"),
            military_strength=int_field(entry, "military_strength", "powers.json::powers[item].military_strength"),
            cohesion=int_field(entry, "cohesion", "powers.json::powers[item].cohesion"),
            supply=int_field(entry, "supply", "powers.json::powers[item].supply"),
            agenda=str_field(entry, "agenda", "powers.json::powers[item].agenda"),
            status=str_field(entry, "status", "powers.json::powers[item].status"),
            last_action=str(entry.get("last_action") or "尚无新动").strip() or "尚无新动",
            aliases="，".join(string_list(entry.get("aliases", []), "powers.json::powers[item].aliases")),
        )
    return powers


def load_opening_legacies() -> List[OpeningLegacy]:
    """开局负面帝国修正：content/opening_legacies.json。无 fallback，缺字段直接 SystemExit。"""
    raw = require_dict(load_json_asset("opening_legacies.json"), "opening_legacies.json")
    items = require_list(raw.get("legacies"), "opening_legacies.json::legacies")
    out: List[OpeningLegacy] = []
    for idx, item in enumerate(items, 1):
        path = f"opening_legacies.json::legacies[{idx}]"
        entry = require_dict(item, path)
        modifiers = require_dict(entry.get("modifiers"), f"{path}.modifiers")
        # clear_gate 走 gate DSL 校验（支持布尔树/扁平 dict/char/event 叶子）；仍必须非空。
        clear_gate = validate_gate_expr(entry.get("clear_gate") or {}, f"{path}.clear_gate")
        if not clear_gate:
            raise SystemExit(f"{path}.clear_gate 不能为空（开局负面修正必须有程序判定的消除条件）。")
        out.append(OpeningLegacy(
            key=str_field(entry, "key", path),
            name=str_field(entry, "name", path),
            modifiers=modifiers,
            narrative_hint=str_field(entry, "narrative_hint", path),
            clear_gate=clear_gate,
            clear_narrative=str(entry.get("clear_narrative") or "").strip(),
        ))
    if not out:
        raise SystemExit("opening_legacies.json 必须至少定义一条开局负面修正。")
    return out


def load_preset_departments() -> Dict[str, PresetDepartment]:
    """可设衙门预设池：content/preset_departments.json。缺字段直接 SystemExit。"""
    raw = require_dict(load_json_asset("preset_departments.json"), "preset_departments.json")
    items = require_list(raw.get("departments"), "preset_departments.json::departments")
    out: Dict[str, PresetDepartment] = {}
    for idx, item in enumerate(items, 1):
        path = f"preset_departments.json::departments[{idx}]"
        entry = require_dict(item, path)
        key = str_field(entry, "key", path)
        out[key] = PresetDepartment(
            key=key,
            name=str_field(entry, "name", path),
            category=str_field(entry, "category", path),
            authority_scope=str_field(entry, "authority_scope", path),
            power=int_field(entry, "power", path),
            responsibility=int_field(entry, "responsibility", path),
            corruption_risk=int_field(entry, "corruption_risk", path),
            effect_summary=str_field(entry, "effect_summary", path),
            modifiers=require_dict(entry.get("modifiers"), f"{path}.modifiers"),
            theme=str_field(entry, "题材", path),
            expected_months=int_field(entry, "预计月数", path),
            bar_value=int_field(entry, "起步进度", path),
            stage_text=str_field(entry, "stage_text", path),
            resolve_condition=str_field(entry, "resolve_condition", path),
            fail_condition=str_field(entry, "fail_condition", path),
            effect_on_resolve=require_dict(entry.get("effect_on_resolve"), f"{path}.effect_on_resolve"),
            effect_on_fail=require_dict(entry.get("effect_on_fail"), f"{path}.effect_on_fail"),
            requires=string_list(entry.get("requires", []), f"{path}.requires"),
        )
    if not out:
        raise SystemExit("preset_departments.json 必须至少定义一项预设衙门。")
    return out


def load_preset_technologies() -> Dict[str, PresetTechnology]:
    """可推科技预设池：content/preset_technologies.json。缺字段直接 SystemExit。"""
    raw = require_dict(load_json_asset("preset_technologies.json"), "preset_technologies.json")
    items = require_list(raw.get("technologies"), "preset_technologies.json::technologies")
    out: Dict[str, PresetTechnology] = {}
    for idx, item in enumerate(items, 1):
        path = f"preset_technologies.json::technologies[{idx}]"
        entry = require_dict(item, path)
        key = str_field(entry, "key", path)
        out[key] = PresetTechnology(
            key=key,
            name=str_field(entry, "name", path),
            category=str_field(entry, "category", path),
            effect_summary=str_field(entry, "effect_summary", path),
            modifiers=require_dict(entry.get("modifiers"), f"{path}.modifiers"),
            theme=str_field(entry, "题材", path),
            expected_months=int_field(entry, "预计月数", path),
            bar_value=int_field(entry, "起步进度", path),
            stage_text=str_field(entry, "stage_text", path),
            resolve_condition=str_field(entry, "resolve_condition", path),
            fail_condition=str_field(entry, "fail_condition", path),
            effect_on_resolve=require_dict(entry.get("effect_on_resolve"), f"{path}.effect_on_resolve"),
            effect_on_fail=require_dict(entry.get("effect_on_fail"), f"{path}.effect_on_fail"),
            requires=string_list(entry.get("requires", []), f"{path}.requires"),
            default_unlocked=bool(entry.get("default_unlocked", False)),
        )
    if not out:
        raise SystemExit("preset_technologies.json 必须至少定义一项预设科技。")
    return out


def dict_of_string_lists(value: object, path: str) -> Dict[str, List[str]]:
    data = require_dict(value, path)
    return {str(key): string_list(item, f"{path}.{key}") for key, item in data.items()}


def dict_of_strings(value: object, path: str) -> Dict[str, str]:
    data = require_dict(value, path)
    output: Dict[str, str] = {}
    for key, item in data.items():
        if not isinstance(item, str):
            raise SystemExit(f"设定字段应为字符串：{path}.{key}")
        output[str(key)] = item
    return output


def load_skill_content() -> Tuple[Dict[str, Dict[str, object]], int, Dict[str, Dict[str, object]]]:
    data = require_dict(load_json_asset("skills.json"), "skills.json")
    # office_default_skills 的 value 是运行时授权 json：{court_tools, agno_skills, chips}。
    # court_tools/agno_skills/chips 抽进 office_court_grants（court tool 挂载/agno skill 注入/前端 chip 授权）。
    # 加新 office = 只在 skills.json 这一张表加一项，三处代码自动读到，不必改 Python。
    office_grant_version = int(data.get("__office_grant_version") or 1)
    office_court_grants: Dict[str, Dict[str, object]] = {}
    for office_type, raw in require_dict(data.get("office_default_skills"), "skills.json.office_default_skills").items():
        grant = require_dict(raw, f"skills.json.office_default_skills.{office_type}")
        ot = str(office_type)
        office_court_grants[ot] = {
            "court_tools": string_list(grant.get("court_tools"), f"skills.json.office_default_skills.{ot}.court_tools"),
            "agno_skills": string_list(grant.get("agno_skills"), f"skills.json.office_default_skills.{ot}.agno_skills"),
            "chips": list(grant.get("chips") or []),
        }

    office_definitions: Dict[str, Dict[str, object]] = {}
    for office_type, raw in require_dict(data.get("office_definitions"), "skills.json.office_definitions").items():
        item = require_dict(raw, f"skills.json.office_definitions.{office_type}")
        office_definitions[str(office_type)] = {
            "skills": [],
            "tools": string_list(item.get("tools"), f"skills.json.office_definitions.{office_type}.tools"),
            "authority_scope": str_field(item, "authority_scope", f"skills.json.office_definitions.{office_type}"),
            "power": int_field(item, "power", f"skills.json.office_definitions.{office_type}"),
            "responsibility": int_field(item, "responsibility", f"skills.json.office_definitions.{office_type}"),
            "corruption_risk": int_field(item, "corruption_risk", f"skills.json.office_definitions.{office_type}"),
        }

    return (
        office_court_grants,
        office_grant_version,
        office_definitions,
    )


def load_fiscal_config() -> "List[Dict[str, object]]":
    """财政科目目录（content/fiscal_config.json）。无 fallback，缺字段直接 SystemExit。

    每项必含 key/value/kind/budget_role/note。`budget_role=fixed` 的 base 项额外必含
    account/direction/display（供 flows 生成预算行）。rate 项与 dynamic 项不强制这三字段。
    返回有序 list（保留 JSON 顺序），db.init_fiscal_config 据此 seed。
    """
    raw = require_dict(load_json_asset("fiscal_config.json"), "fiscal_config.json")
    items_raw = require_list(raw.get("items"), "fiscal_config.json.items")
    schema_version = int_field(raw, "schema_version", "fiscal_config.json")
    items: List[Dict[str, object]] = []
    seen: Set[str] = set()
    for idx, entry in enumerate(items_raw):
        path = f"fiscal_config.json.items[{idx}]"
        item = require_dict(entry, path)
        key = str_field(item, "key", path)
        if key in seen:
            raise SystemExit(f"{path}: fiscal key 重复：{key}")
        seen.add(key)
        kind = str_field(item, "kind", path)
        role = str_field(item, "budget_role", path)
        if role not in ("fixed", "dynamic"):
            raise SystemExit(f"{path}: budget_role 必须是 fixed/dynamic，得到 {role}")
        record: Dict[str, object] = {
            "key": key,
            "value": int_field(item, "value", path),
            "kind": kind,
            "budget_role": role,
            "note": str_field(item, "note", path),
            "order": int(item["order"]) if "order" in item else 9999,
            "formula": str(item.get("formula") or ""),
            "basis": str(item.get("basis") or ""),
            "rate_unit": str(item.get("rate_unit") or ""),
        }
        # fixed 的 base 项必须给 account/direction/display；flows 据此生成预算行。
        if role == "fixed" and kind == "base":
            account = str_field(item, "account", path)
            direction = str_field(item, "direction", path)
            if account not in ("国库", "内库"):
                raise SystemExit(f"{path}: account 必须是 国库/内库，得到 {account}")
            if direction not in ("income", "expense"):
                raise SystemExit(f"{path}: direction 必须是 income/expense，得到 {direction}")
            record["account"] = account
            record["direction"] = direction
            record["display"] = str_field(item, "display", path)
        items.append(record)
    return [{"__schema_version": schema_version}, *items]


@dataclass
class GameContent:
    """游戏全部静态设定。GameContent.load() 一次性读盘填充。

    替代原 main.py 的模块级全局量（FACTIONS/CHARACTERS/EVENTS/...），
    根治 `import main` 即读盘的副作用。
    """

    factions: Dict[str, Faction] = field(default_factory=dict)
    characters: Dict[str, Character] = field(default_factory=dict)
    events: List[Event] = field(default_factory=list)
    seed_events: List[Event] = field(default_factory=list)
    opening_legacies: List[OpeningLegacy] = field(default_factory=list)
    preset_departments: Dict[str, PresetDepartment] = field(default_factory=dict)
    preset_technologies: Dict[str, PresetTechnology] = field(default_factory=dict)
    event_by_id: Dict[str, Event] = field(default_factory=dict)
    regions: Dict[str, Region] = field(default_factory=dict)
    armies: Dict[str, Army] = field(default_factory=dict)
    buildings: Dict[str, Building] = field(default_factory=dict)
    faction_metrics: Tuple[str, ...] = ()
    powers: Dict[str, Power] = field(default_factory=dict)
    classes: Dict[str, SocialClass] = field(default_factory=dict)

    # runtime office grants
    # office_type → {court_tools:[...], agno_skills:[...], chips:[{...}]}：court 授权唯一来源。
    office_court_grants: Dict[str, Dict[str, object]] = field(default_factory=dict)
    # 授权表大版本号；老档 < 此值才重 seed 授权（玩家运行时改过的授权在 >= 时神圣不动）。
    office_grant_version: int = 1
    office_definitions: Dict[str, Dict[str, object]] = field(default_factory=dict)
    skill_tool_templates: Dict[str, str] = field(default_factory=dict)

    # 提示词
    game_world_prompt: str = ""
    minister_agent_prompt: str = ""
    consort_agent_prompt: str = ""
    court_chat_agent_prompt: str = ""

    decree_writer_prompt: str = ""
    season_simulator_prompt: str = ""
    score_extractor_shared_prompt: str = ""
    score_extractor_module_prompts: Dict[str, str] = field(default_factory=dict)
    chapter_memory_prompt: str = ""
    minister_recap_prompt: str = ""
    ending_summary_prompt: str = ""

    fiscal_items: List[Dict[str, object]] = field(default_factory=list)

    @classmethod
    def load(cls) -> "GameContent":
        factions, characters = load_character_content()
        events = load_event_content("events.json")
        seed_events = load_event_content("seed_events.json")
        opening_legacies = load_opening_legacies()
        preset_departments = load_preset_departments()
        preset_technologies = load_preset_technologies()
        regions = load_region_content()
        armies = load_army_content()
        buildings = load_building_content()
        powers = load_powers()
        classes = load_class_content()
        (
            office_court_grants,
            office_grant_version,
            office_definitions,
        ) = load_skill_content()
        return cls(
            factions=factions,
            characters=characters,
            events=events,
            seed_events=seed_events,
            opening_legacies=opening_legacies,
            preset_departments=preset_departments,
            preset_technologies=preset_technologies,
            event_by_id={ev.id: ev for ev in (*events, *seed_events)},
            regions=regions,
            armies=armies,
            buildings=buildings,
            faction_metrics=tuple(factions.keys()),
            powers=powers,
            classes=classes,
            office_court_grants=office_court_grants,
            office_grant_version=office_grant_version,
            office_definitions=office_definitions,
            fiscal_items=load_fiscal_config(),
            skill_tool_templates=dict_of_strings(load_json_asset("skill_tools.json"), "skill_tools.json"),
            game_world_prompt=load_text_asset("prompts/game_world.md"),
            minister_agent_prompt=load_text_asset("prompts/minister_agent.md"),
            consort_agent_prompt=load_text_asset("prompts/consort_agent.md"),
            court_chat_agent_prompt=load_text_asset("prompts/court_chat_agent.md"),
            decree_writer_prompt=load_text_asset("prompts/decree_writer.md"),
            season_simulator_prompt=load_text_asset("prompts/season_simulator.md"),
            score_extractor_shared_prompt=load_text_asset("prompts/score_extractor_shared.md"),
            score_extractor_module_prompts={
                "internal": load_text_asset("prompts/score_extractor_internal.md"),
                "military_external": load_text_asset("prompts/score_extractor_military_external.md"),
                "issues": load_text_asset("prompts/score_extractor_issues.md"),
                "personnel_secret": load_text_asset("prompts/score_extractor_personnel_secret.md"),
            },
            chapter_memory_prompt=load_text_asset("prompts/chapter_memory.md"),
            minister_recap_prompt=load_text_asset("prompts/minister_recap.md"),
            ending_summary_prompt=load_text_asset("prompts/ending_summary.md"),
        )

    # office_court_grants 仅作 DB seed 源（db.init_office_grants 灌进 offices.court_grant_json）；
    # 运行时 court tool 挂载 / agno skill 注入 / 前端 chip 全读 DB（db.get_office_court_grant），不读 content。
