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
    troop_cost = load_troop_cost()
    armies: Dict[str, Army] = {}
    for idx, raw in enumerate(require_list(data.get("armies"), "armies.json.armies"), 1):
        item = require_dict(raw, f"armies.json.armies[{idx}]")
        army_id = str_field(item, "id", f"armies.json.armies[{idx}]")
        troop_composition = normalize_troop_composition(
            item.get("troop_composition"),
            fallback_troop_type=str(item.get("troop_type") or ""),
            fallback_manpower=int(item.get("manpower") or 0),
            troop_cost=troop_cost,
        )
        troop_type = troop_type_from_composition(troop_composition) or str_field(item, "troop_type", f"armies.json.armies[{idx}]")
        manpower = sum(troop_composition.values()) if troop_composition else int_field(item, "manpower", f"armies.json.armies[{idx}]")
        owner_power = str_field(item, "owner_power", f"armies.json.armies[{idx}]")
        armies[army_id] = Army(
            id=army_id,
            name=str_field(item, "name", f"armies.json.armies[{idx}]"),
            station=str_field(item, "station", f"armies.json.armies[{idx}]"),
            theater=str_field(item, "theater", f"armies.json.armies[{idx}]"),
            commander=str_field(item, "commander", f"armies.json.armies[{idx}]"),
            controller=str_field(item, "controller", f"armies.json.armies[{idx}]"),
            troop_type=troop_type,
            troop_composition=troop_composition,
            manpower=manpower,
            maintenance_per_turn=troop_maintenance_total(troop_composition, troop_cost)
            if troop_composition and owner_power == "ming"
            else int_field(item, "maintenance_per_turn", f"armies.json.armies[{idx}]"),
            supply=int_field(item, "supply", f"armies.json.armies[{idx}]"),
            morale=int_field(item, "morale", f"armies.json.armies[{idx}]"),
            training=int_field(item, "training", f"armies.json.armies[{idx}]"),
            equipment=int_field(item, "equipment", f"armies.json.armies[{idx}]"),
            arrears=int_field(item, "arrears", f"armies.json.armies[{idx}]"),
            mobility=int_field(item, "mobility", f"armies.json.armies[{idx}]"),
            loyalty=int_field(item, "loyalty", f"armies.json.armies[{idx}]"),
            status=str_field(item, "status", f"armies.json.armies[{idx}]"),
            owner_power=owner_power,
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
        # output_metric 可以是四大指标白名单，或某武器型号 id（建筑产械入总库）。
        if output_metric not in BUILDING_OUTPUT_METRICS and output_metric not in _weapon_id_set():
            raise SystemExit(
                f"{ctx}: output_metric '{output_metric}' 既不在指标白名单 {BUILDING_OUTPUT_METRICS}，"
                f"也不是已知武器型号 id（见 weapons.json）。"
            )
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


def load_troop_cost() -> "Dict[str, object]":
    """兵种月饷单价表（content/troop_cost.json）。无 fallback，缺字段直接 SystemExit。

    返回 {"version", "default_tier", "tiers": [{"tier","per_kilo","keywords":[...]}, ...]}。
    tiers 顺序＝匹配优先级（从贵到便宜）；扩缩军按 troop_type 串关键词命中最贵档算单价。
    """
    raw = require_dict(load_json_asset("troop_cost.json"), "troop_cost.json")
    version = int_field(raw, "version", "troop_cost.json")
    default_tier = str_field(raw, "default_tier", "troop_cost.json")
    tiers_raw = require_list(raw.get("tiers"), "troop_cost.json.tiers")
    tiers: List[Dict[str, object]] = []
    names: Set[str] = set()
    for idx, entry in enumerate(tiers_raw):
        path = f"troop_cost.json.tiers[{idx}]"
        item = require_dict(entry, path)
        tier = str_field(item, "tier", path)
        if tier in names:
            raise SystemExit(f"{path}: tier 重复：{tier}")
        names.add(tier)
        if "per_kilo" not in item:
            raise SystemExit(f"{path}: 缺 per_kilo")
        try:
            per_kilo = float(item["per_kilo"])
        except (TypeError, ValueError):
            raise SystemExit(f"{path}: per_kilo 非数值：{item['per_kilo']!r}")
        if per_kilo < 0:
            raise SystemExit(f"{path}: per_kilo 不可为负：{per_kilo}")
        keywords = string_list(item.get("keywords"), f"{path}.keywords")
        if not keywords:
            raise SystemExit(f"{path}: keywords 不可为空")
        tiers.append({
            "tier": tier,
            "per_kilo": per_kilo,
            "keywords": keywords,
            "requires_tech": str(item.get("requires_tech") or ""),
            "category": str(item.get("category") or ""),
            "upgrades": list(item.get("upgrades") or []),
        })
    if default_tier not in names:
        raise SystemExit(f"troop_cost.json: default_tier '{default_tier}' 不在 tiers 中")
    return {"version": version, "default_tier": default_tier, "tiers": tiers}


def _match_troop_tier(name: str, troop_cost: Dict[str, object]) -> Optional[Dict[str, object]]:
    """据兵种名/自由文本找命中的 tier 档（不兜底 default）。
    ① 先按 tier 名**精确**命中——composition 的 key 已是规范名，这条几乎总中，且杜绝
       「骑兵」吃「骠骑兵」这类短名吃长名（精确名优先于子串关键词）。
    ② 都不精确命中（传入是 LLM 自由串/番号）→ 收集**所有**关键词子串命中的档，取 per_kilo
       **最贵**的一档（兑现「军内取最贵兵种」契约，不再随 tiers 的 JSON 顺序漂移）。
    返回命中的 tier dict，或 None（无任何命中，由调用方决定兜底）。"""
    text = str(name or "")
    tiers = troop_cost.get("tiers") or []
    for tier in tiers:
        if text == str(tier.get("tier") or ""):
            return tier
    hits = [tier for tier in tiers
            if any(kw and kw in text for kw in tier.get("keywords", []))]
    if hits:
        return max(hits, key=lambda t: float(t.get("per_kilo") or 0.0))
    return None


def canon_troop_name(name: str, troop_cost: Dict[str, object]) -> str:
    """把任意兵种名/番号/自由串归一成固定兵种名（troop_cost 闭集里的 tier 名）。
    命中走 _match_troop_tier（精确优先、关键词取最贵）；无命中兜底 default_tier。
    归一与算饷（troop_rate_for_type）共用同一匹配内核，杜绝两套逻辑错配。"""
    tier = _match_troop_tier(name, troop_cost)
    if tier is not None:
        return str(tier.get("tier") or "")
    return str(troop_cost.get("default_tier") or "非正规步兵")


def normalize_troop_composition(
    value: object,
    *,
    fallback_troop_type: str = "",
    fallback_manpower: int = 0,
    troop_cost: Dict[str, object] | None = None,
) -> Dict[str, int]:
    spec = troop_cost or {}
    if isinstance(value, dict):
        out: Dict[str, int] = {}
        for key, raw_amount in value.items():
            troop = canon_troop_name(str(key).strip(), spec)
            try:
                amount = int(raw_amount)
            except (TypeError, ValueError):
                amount = 0
            if troop and amount > 0:
                out[troop] = out.get(troop, 0) + amount
        return out
    text = str(fallback_troop_type or "").strip()
    if text and fallback_manpower > 0:
        return {canon_troop_name(text, spec): int(fallback_manpower)}
    return {}


def troop_type_from_composition(composition: Dict[str, int]) -> str:
    return "、".join(k for k, v in composition.items() if int(v) > 0)


def troop_rate_for_type(troop_type: str, troop_cost: Dict[str, object]) -> float:
    """据兵种名/自由文本返回月饷单价（万两/千人）。精确名优先、关键词取最贵命中、兜底 default_tier。"""
    tier = _match_troop_tier(troop_type, troop_cost)
    if tier is not None:
        return float(tier["per_kilo"])
    default_tier = troop_cost.get("default_tier")
    for tier in troop_cost.get("tiers") or []:
        if tier.get("tier") == default_tier:
            return float(tier["per_kilo"])
    return 0.0


def troop_maintenance_total(composition: Dict[str, int], troop_cost: Dict[str, object]) -> int:
    total = 0.0
    for troop_type, manpower in composition.items():
        total += troop_rate_for_type(troop_type, troop_cost) * int(manpower) / 1000.0
    return round(total)


def _slug_weapon_id(name: str) -> str:
    """LLM 新出型号无英文 id 时，由名生成安全 id。ASCII 直接小写连字符，
    中文则退化成 `weapon_<hex>`（稳定可复现，同名同 id，供 arms 表主键去重）。"""
    import re as _re, hashlib as _hashlib
    ascii_slug = _re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")
    if ascii_slug:
        return ascii_slug
    return "weapon_" + _hashlib.md5(str(name).strip().encode("utf-8")).hexdigest()[:8]


def _float_field(data: Dict[str, object], key: str, path: str) -> float:
    if key not in data:
        raise SystemExit(f"{path}: 缺 {key}")
    try:
        return float(data[key])  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise SystemExit(f"{path}: {key} 非数值：{data[key]!r}")


def _weapon_id_set() -> "Set[str]":
    """weapons.json 里所有预设武器 id 集合，供 buildings.json 的 output_metric 校验放行。
    轻量直读（不经 GameContent），与 load_weapons 同源。"""
    raw = require_dict(load_json_asset("weapons.json"), "weapons.json")
    return {str(w.get("id")) for w in require_list(raw.get("weapons"), "weapons.json.weapons")
            if isinstance(w, dict) and w.get("id")}


def load_weapons() -> "Dict[str, object]":
    """军事装备型号表（content/weapons.json）。无 fallback，缺字段直接 SystemExit。

    返回 {"version", "default_tier", "tiers": {名: {power,cost,equip_per_unit,keywords}},
          "weapons": [{id,name,tier,power,cost,equip_per_unit,requires_tech}, ...]}。
    建筑按 output_metric=武器id 产械入总库；拨发给某军按 equip_per_unit 提 equipment。
    requires_tech＝前置科技中文名（须在 technologies 表已解锁，空＝无门槛）。
    LLM 推演新出未列型号→按 tiers[*].keywords 归档、给默认属性动态注册（见 weapon_meta）。
    """
    raw = require_dict(load_json_asset("weapons.json"), "weapons.json")
    version = int_field(raw, "version", "weapons.json")
    default_tier = str_field(raw, "default_tier", "weapons.json")
    tiers_raw = require_dict(raw.get("tiers"), "weapons.json.tiers")
    tiers: Dict[str, Dict[str, object]] = {}
    for tier_name, tier_val in tiers_raw.items():
        tpath = f"weapons.json.tiers[{tier_name}]"
        tdict = require_dict(tier_val, tpath)
        tiers[str(tier_name)] = {
            "cost": int_field(tdict, "cost", tpath),
            "equip_per_unit": _float_field(tdict, "equip_per_unit", tpath),
            "keywords": string_list(tdict.get("keywords"), f"{tpath}.keywords"),
        }
    if default_tier not in tiers:
        raise SystemExit(f"weapons.json: default_tier '{default_tier}' 不在 tiers 中")
    weapons_raw = require_list(raw.get("weapons"), "weapons.json.weapons")
    weapons: List[Dict[str, object]] = []
    seen_ids: Set[str] = set()
    seen_names: Set[str] = set()
    for idx, entry in enumerate(weapons_raw):
        path = f"weapons.json.weapons[{idx}]"
        item = require_dict(entry, path)
        wid = str_field(item, "id", path)
        name = str_field(item, "name", path)
        tier = str_field(item, "tier", path)
        if wid in seen_ids:
            raise SystemExit(f"{path}: 武器 id 重复：{wid}")
        if name in seen_names:
            raise SystemExit(f"{path}: 武器名重复：{name}")
        if tier not in tiers:
            raise SystemExit(f"{path}: tier '{tier}' 不在 tiers 中")
        seen_ids.add(wid)
        seen_names.add(name)
        weapons.append({
            "id": wid,
            "name": name,
            "tier": tier,
            "cost": int_field(item, "cost", path),
            "equip_per_unit": _float_field(item, "equip_per_unit", path),
            "requires_tech": str(item.get("requires_tech") or ""),
            "opening_stock": max(0, int(item.get("opening_stock") or 0)),
        })
    return {"version": version, "default_tier": default_tier, "tiers": tiers, "weapons": weapons}


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
    scenario_gen_characters_prompt: str = ""
    scenario_gen_events_prompt: str = ""
    scenario_gen_seed_events_prompt: str = ""
    scenario_editor_prompt: str = ""

    fiscal_items: List[Dict[str, object]] = field(default_factory=list)
    troop_cost: Dict[str, object] = field(default_factory=dict)
    weapons: Dict[str, object] = field(default_factory=dict)

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
            troop_cost=load_troop_cost(),
            weapons=load_weapons(),
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
            scenario_gen_characters_prompt=load_text_asset("prompts/scenario_gen_characters.md"),
            scenario_gen_events_prompt=load_text_asset("prompts/scenario_gen_events.md"),
            scenario_gen_seed_events_prompt=load_text_asset("prompts/scenario_gen_seed_events.md"),
            scenario_editor_prompt=load_text_asset("prompts/scenario_editor.md"),
        )

    def troop_cost_per_kilo(self, troop_type: str) -> float:
        """据 troop_type 自由组合串匹配兵种档，返回每千人月饷单价（万两）。
        tiers 按从贵到便宜排序，命中第一档即返回（即取军内最贵兵种）；都不命中走 default_tier。
        """
        return troop_rate_for_type(troop_type, self.troop_cost)

    def troop_maintenance_delta(self, troop_type: str, manpower_delta: int) -> int:
        """扩缩军兵力增量 → 军费增量（万两，四舍五入）。单价＝troop_cost_per_kilo，
        manpower 单位＝人，单价单位＝万两/千人，故 ÷1000。"""
        rate = self.troop_cost_per_kilo(troop_type)
        return round(rate * manpower_delta / 1000.0)

    def troop_maintenance_total(self, composition: Dict[str, int]) -> int:
        return troop_maintenance_total(composition, self.troop_cost)

    def weapon_meta(self, name_or_id: str) -> Dict[str, object]:
        """据武器 id 或中文名解析型号元数据。命中预设→返回其条目；
        未列型号（LLM 新出）→按 tiers[*].keywords 归 tier（从重到轻顺序匹配），
        取该 tier 默认属性、requires_tech 默认空、id 由名生成，registered='runtime'。
        返回 {id,name,tier,power,cost,equip_per_unit,requires_tech,registered}。"""
        key = str(name_or_id or "").strip()
        for w in self.weapons.get("weapons", []):
            if key == w["id"] or key == w["name"]:
                return {**w, "registered": "seed"}
        # 动态归 tier：tiers dict 保留 JSON 顺序（重炮…轻火器），命中第一档即归
        tiers: Dict[str, object] = self.weapons.get("tiers", {})  # type: ignore[assignment]
        chosen = self.weapons.get("default_tier", "")
        for tier_name, tdef in tiers.items():
            for kw in tdef.get("keywords", []):  # type: ignore[union-attr]
                if kw and kw in key:
                    chosen = tier_name
                    break
            else:
                continue
            break
        tdef = tiers.get(chosen, {})  # type: ignore[assignment]
        return {
            "id": _slug_weapon_id(key),
            "name": key,
            "tier": chosen,
            "cost": int(tdef.get("cost", 1)),  # type: ignore[union-attr]
            "equip_per_unit": float(tdef.get("equip_per_unit", 0.4)),
            "requires_tech": "",
            "registered": "runtime",
        }

    # office_court_grants 仅作 DB seed 源（db.init_office_grants 灌进 offices.court_grant_json）；
    # 运行时 court tool 挂载 / agno skill 注入 / 前端 chip 全读 DB（db.get_office_court_grant），不读 content。
