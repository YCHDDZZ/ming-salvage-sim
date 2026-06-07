import React from "react";
import { createPortal } from "react-dom";
import { api } from "../api";
import { formatClosedEffect, formatIssueEffect, issueTone } from "../format";
import type { ClosedIssue, Issue, PresetTreeItem, PresetTrees } from "../types";

// 八题材分类（与后端 ISSUE_THEMES 对齐）：决定手动局势走满后落成何种实体。
const ISSUE_THEMES = ["工程", "科技", "政治", "军事", "民生", "经济", "文化", "其他"] as const;

// 局势分组：长期(贯穿一朝大计) vs 近期。纯前端按 fail_condition 文案判定。
export function groupIssues(issues: Issue[]) {
  const active = issues.filter((i) => i.kind === "situation" || i.kind === "initiative");
  const bySeq = (a: Issue, b: Issue) => {
    if (a.kind !== b.kind) return a.kind === "initiative" ? -1 : 1;
    return a.id - b.id;
  };
  const isLongTerm = (i: Issue) => /甲申|贯穿一朝|倾国之大计/.test(i.fail_condition || "");
  return {
    active,
    longTerm: active.filter(isLongTerm).sort(bySeq),
    nearTerm: active.filter((i) => !isLongTerm(i)).sort(bySeq),
  };
}

export function SituationPanel({ issues, closedIssues, hasLegacies, compact = false, onOpenDrawer, onChanged }: {
  issues: Issue[];
  closedIssues: ClosedIssue[];
  hasLegacies: boolean;
  compact?: boolean;
  onOpenDrawer?: () => void;
  onChanged?: () => void | Promise<void>;
}) {
  const { active, longTerm, nearTerm } = groupIssues(issues);
  // compact 模式始终保留「局势管理」入口（即便当前无局势，也能进抽屉新建）。
  if (!active.length && !closedIssues.length && !(compact && onOpenDrawer)) return null;
  const compactLimit = 6;
  const shownClosed = compact ? closedIssues.slice(0, Math.min(2, compactLimit)) : closedIssues;
  const remainingCompactSlots = Math.max(0, compactLimit - shownClosed.length);
  const shownLongTerm = compact ? longTerm.slice(0, Math.min(2, remainingCompactSlots)) : longTerm;
  const shownNearTerm = compact ? nearTerm.slice(0, Math.max(0, remainingCompactSlots - shownLongTerm.length)) : nearTerm;
  const totalCount = active.length + closedIssues.length;
  const shownCount = shownClosed.length + shownLongTerm.length + shownNearTerm.length;
  const hiddenCount = Math.max(0, totalCount - shownCount);
  return (
    <aside
      className={`situation-panel ${hasLegacies ? "with-legacies" : ""} ${compact ? "compact" : ""}`}
      aria-label="局势进度"
    >
      {shownClosed.length ? (
        <div className="situation-closed-list">
          {shownClosed.map((ci) => (
            <div className={`situation-closed-row ${ci.status}`} key={`closed-${ci.id}`} tabIndex={0}>
              <div className="situation-closed-head">
                <span className="situation-closed-badge">{ci.status === "resolved" ? "已结案" : ci.status === "failed" ? "已崩坏" : "已撤"}</span>
                <span className="situation-closed-name">{ci.title}</span>
              </div>
              <div className="situation-closed-effect">{formatClosedEffect(ci.effect)}</div>
            </div>
          ))}
        </div>
      ) : null}
      {shownLongTerm.length ? (
        <div className="situation-group">
          <div className="situation-group-title">长期局势</div>
          <div className="situation-list">
            {shownLongTerm.map((issue) => <SituationRow key={issue.id} issue={issue} onChanged={onChanged} />)}
          </div>
        </div>
      ) : null}
      {shownNearTerm.length ? (
        <div className="situation-group">
          <div className="situation-group-title">近期局势</div>
          <div className="situation-list">
            {shownNearTerm.map((issue) => <SituationRow key={issue.id} issue={issue} onChanged={onChanged} />)}
          </div>
        </div>
      ) : null}
      {compact && onOpenDrawer ? (
        <button
          type="button"
          className="situation-more-hint"
          onClick={(e) => {
            e.stopPropagation();
            onOpenDrawer();
          }}
        >
          {hiddenCount > 0 ? `局势管理 · 余 ${hiddenCount} 条` : "局势管理"}
        </button>
      ) : null}
    </aside>
  );
}

export function SituationDrawer({ open, issues, closedIssues, onClose, maxDecreeIssues = 10, regions = [], presetTrees, onChanged }: {
  open: boolean;
  issues: Issue[];
  closedIssues: ClosedIssue[];
  onClose: () => void;
  maxDecreeIssues?: number;
  regions?: { id: string; name: string }[];
  presetTrees?: PresetTrees;
  onChanged?: () => void | Promise<void>;
}) {
  const { active, longTerm, nearTerm } = groupIssues(issues);
  const decreeIssueCount = active.filter((i) => i.origin_kind === "decree").length;
  const [editor, setEditor] = React.useState<{ mode: "create" } | { mode: "edit"; issue: Issue } | null>(null);
  return (
    <>
      <div className={`situation-drawer-scrim ${open ? "open" : ""}`} onClick={onClose} />
      <aside className={`situation-drawer ${open ? "open" : ""}`} aria-label="局势进度抽屉" aria-hidden={!open}>
        <div className="situation-drawer-head">
          <div>
            <strong>局势进度</strong>
            <span>{active.length} 条在办 · {closedIssues.length} 条本回合结案</span>
          </div>
          <button onClick={onClose} aria-label="关闭局势抽屉">×</button>
        </div>
        <div className="situation-drawer-body">
          <div className="situation-manual-bar">
            <span className="situation-manual-count">decree 局势 {decreeIssueCount} / {maxDecreeIssues}</span>
            <button
              type="button"
              className="situation-manual-add"
              disabled={decreeIssueCount >= maxDecreeIssues}
              title={decreeIssueCount >= maxDecreeIssues ? "已达上限，可在主菜单游戏设置调高" : "手动新建一条局势"}
              onClick={() => setEditor({ mode: "create" })}
            >
              ＋ 新建局势
            </button>
          </div>
          {decreeIssueCount >= maxDecreeIssues ? (
            <p className="situation-manual-hint">已达上限（{maxDecreeIssues}）。可在主菜单「游戏设置」调高，但会增加推演 token 消耗。</p>
          ) : null}
          {closedIssues.length ? (
            <section className="situation-drawer-section">
              <h3>本回合结案</h3>
              {closedIssues.map((ci) => (
                <article className={`situation-drawer-closed ${ci.status}`} key={`drawer-closed-${ci.id}`}>
                  <div className="situation-drawer-closed-head">
                    <b>{ci.status === "resolved" ? "已结案" : ci.status === "failed" ? "已崩坏" : "已撤"}</b>
                    <span>{ci.title}</span>
                  </div>
                  <p>{formatClosedEffect(ci.effect)}</p>
                </article>
              ))}
            </section>
          ) : null}
          <SituationDrawerGroup title="长期局势" issues={longTerm} onEdit={(i) => setEditor({ mode: "edit", issue: i })} onChanged={onChanged} />
          <SituationDrawerGroup title="近期局势" issues={nearTerm} onEdit={(i) => setEditor({ mode: "edit", issue: i })} onChanged={onChanged} />
        </div>
      </aside>
      {editor ? (
        <ManualIssueEditor
          editing={editor.mode === "edit" ? editor.issue : null}
          regions={regions}
          presetTrees={presetTrees}
          onClose={() => setEditor(null)}
          onSaved={async () => {
            setEditor(null);
            await onChanged?.();
          }}
        />
      ) : null}
    </>
  );
}

function SituationDrawerGroup({ title, issues, onEdit, onChanged }: {
  title: string;
  issues: Issue[];
  onEdit?: (issue: Issue) => void;
  onChanged?: () => void | Promise<void>;
}) {
  if (!issues.length) return null;
  return (
    <section className="situation-drawer-section">
      <h3>{title}</h3>
      {issues.map((issue) => (
        <SituationDrawerRow issue={issue} key={`drawer-${issue.id}`} onEdit={onEdit} onChanged={onChanged} />
      ))}
    </section>
  );
}

function SituationDrawerRow({ issue, onEdit, onChanged }: {
  issue: Issue;
  onEdit?: (issue: Issue) => void;
  onChanged?: () => void | Promise<void>;
}) {
  const [detail, setDetail] = React.useState(false);
  const onDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!window.confirm(`确定删除手动局势〔${issue.title}〕？`)) return;
    try {
      await api(`/api/issues/manual/${issue.id}`, { method: "DELETE" });
      await onChanged?.();
    } catch (err: any) {
      window.alert(err?.message || "删除失败");
    }
  };
  return (
    <>
      <article
        className={`situation-drawer-row ${issueTone(issue.bar_value)}`}
        role="button"
        tabIndex={0}
        onClick={() => setDetail(true)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            setDetail(true);
          }
        }}
      >
        <div className="situation-drawer-row-head">
          <b>{issue.title}{issue.is_manual ? <span className="situation-manual-tag">手动</span> : null}</b>
          <span>{issue.bar_value}</span>
        </div>
        <div className="situation-bar">
          <i style={{ width: `${Math.max(0, Math.min(100, issue.bar_value))}%` }} />
        </div>
        <p>{issue.stage_text}</p>
        {issue.is_manual ? (
          <div className="situation-manual-actions" onClick={(e) => e.stopPropagation()}>
            <span className="situation-manual-dur">
              {issue.duration_turns ? `持续 ${issue.duration_turns} 回合` : "无期限"}
            </span>
            <button type="button" onClick={(e) => { e.stopPropagation(); onEdit?.(issue); }}>编辑</button>
            <button type="button" className="danger" onClick={onDelete}>删除</button>
          </div>
        ) : null}
      </article>
      {detail ? <SituationDetailModal issue={issue} onClose={() => setDetail(false)} onChanged={onChanged} /> : null}
    </>
  );
}

// 手动局势新建/编辑弹窗：名称(title) + 分类(tags，仅新建) + 目标(goal) + 持续回合数。
// 目标喂给推演逐月推进；分类决定走满后落成何种实体（工程→建筑、科技→科技、政治→部门）。
// 题材 → 走满落成的实体类型。工程→建筑、科技→科技、政治→部门；其余题材无实体（只是可追踪局势）。
const THEME_ENTITY: Record<string, "building" | "technology" | "department" | ""> = {
  工程: "building", 科技: "technology", 政治: "department",
  军事: "", 民生: "", 经济: "", 文化: "", 其他: "",
};
// 建筑类别白名单（与后端 BUILDING_CATEGORIES 对齐）。
const BUILDING_CATEGORIES = ["民生", "财政", "军事", "科技", "交通", "内廷"] as const;

function presetRequirementText(item: PresetTreeItem, pool: PresetTreeItem[]) {
  if (!item.requires.length) return "根基";
  const names = item.requires.map((key) => pool.find((p) => p.key === key)?.name || key);
  return `前置：${names.join("、")}`;
}

export function ManualIssueEditor({ editing, regions = [], presetTrees, onClose, onSaved }: {
  editing: Issue | null;
  regions?: { id: string; name: string }[];
  presetTrees?: PresetTrees;
  onClose: () => void;
  onSaved: () => void | Promise<void>;
}) {
  const [title, setTitle] = React.useState(editing?.title || "");
  const [duration, setDuration] = React.useState<number>(editing?.duration_turns || 0);
  const [goal, setGoal] = React.useState(editing?.goal || "");
  const [category, setCategory] = React.useState<string>(editing?.tags?.[0] || "工程");
  // 实体固定字段（按题材展开）
  const [regionId, setRegionId] = React.useState<string>(regions[0]?.id || "");
  const [bldCategory, setBldCategory] = React.useState<string>("民生");
  const [maintenance, setMaintenance] = React.useState<number>(1);
  const [authorityScope, setAuthorityScope] = React.useState<string>("");
  const [power, setPower] = React.useState<number>(50);
  const [effectSummary, setEffectSummary] = React.useState<string>("");
  const [presetMode, setPresetMode] = React.useState<"preset" | "custom">("preset");
  const [presetKey, setPresetKey] = React.useState<string>("");
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState("");
  const entityKind = THEME_ENTITY[category] || "";
  const presetPool = entityKind === "technology"
    ? (presetTrees?.technologies || [])
    : entityKind === "department"
      ? (presetTrees?.departments || [])
      : [];
  const selectablePresets = presetPool.filter((p) => !p.unlocked);
  const selectedPreset = presetPool.find((p) => p.key === presetKey) || null;
  React.useEffect(() => {
    if (entityKind !== "technology" && entityKind !== "department") {
      setPresetKey("");
      return;
    }
    const first = selectablePresets.find((p) => p.available)?.key || selectablePresets[0]?.key || "";
    setPresetKey((cur) => (cur && selectablePresets.some((p) => p.key === cur) ? cur : first));
  }, [entityKind, selectablePresets.map((p) => `${p.key}:${p.available}:${p.unlocked}`).join("|")]);
  React.useEffect(() => {
    if (editing || presetMode !== "preset" || !selectedPreset) return;
    setTitle(selectedPreset.name);
    setGoal(selectedPreset.effect_summary || selectedPreset.name);
    if (entityKind === "department") {
      setAuthorityScope(selectedPreset.authority_scope || "");
      setPower(selectedPreset.power ?? 50);
    } else if (entityKind === "technology") {
      setEffectSummary(selectedPreset.effect_summary || "");
    }
  }, [editing, presetMode, selectedPreset?.key, entityKind]);
  const save = async () => {
    if (!title.trim()) { setErr("名称不能为空"); return; }
    setBusy(true);
    setErr("");
    try {
      if (editing) {
        // 编辑：仅名称/持续可改。goal 立项后锁定、实体固定字段不可改。
        await api(`/api/issues/manual/${editing.id}`, {
          method: "PATCH",
          body: JSON.stringify({ title: title.trim(), duration_turns: duration }),
        });
      } else {
        // 按题材组装实体固定字段，立项预埋。
        let entity: any = null;
        if (entityKind === "building") {
          if (!regionId) { setErr("请为建筑选择省份"); setBusy(false); return; }
          entity = { kind: "building", name: title.trim(), region_id: regionId, category: bldCategory, maintenance };
        } else if (entityKind === "department") {
          if (presetMode === "preset" && selectedPreset) {
            if (!selectedPreset.available) { setErr("前置衙门未设立"); setBusy(false); return; }
            entity = { kind: "department", preset_key: selectedPreset.key };
          } else {
            entity = { kind: "department", name: title.trim(), authority_scope: authorityScope.trim(), power };
          }
        } else if (entityKind === "technology") {
          if (presetMode === "preset" && selectedPreset) {
            if (!selectedPreset.available) { setErr("前置科技未完成"); setBusy(false); return; }
            entity = { kind: "technology", preset_key: selectedPreset.key };
          } else {
            entity = { kind: "technology", name: title.trim(), effect_summary: effectSummary.trim() };
          }
        }
        await api("/api/issues/manual", {
          method: "POST",
          body: JSON.stringify({ title: title.trim(), duration_turns: duration, goal: goal.trim(), tags: [category], entity }),
        });
      }
      await onSaved();
    } catch (e: any) {
      setErr(e?.message || "保存失败");
      setBusy(false);
    }
  };
  return createPortal(
    <div className="situation-detail-backdrop" onClick={onClose}>
      <div className="situation-detail manual-issue-editor" onClick={(e) => e.stopPropagation()}>
        <div className="situation-detail-head">
          <span>{editing ? "编辑手动局势" : "新建手动局势"}</span>
          <button className="situation-detail-close" onClick={onClose} aria-label="关闭">×</button>
        </div>
        <div className="manual-issue-form">
          {err ? <div className="manual-issue-err">{err}</div> : null}
          <label>
            名称
            <input
              type="text"
              value={title}
              maxLength={60}
              placeholder="如：兴办苏州玻璃制造厂"
              onChange={(e) => setTitle(e.target.value)}
            />
          </label>
          {editing ? null : (
            <label>
              分类
              <select value={category} onChange={(e) => setCategory(e.target.value)}>
                {ISSUE_THEMES.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              <small className="manual-issue-hint">工程→建筑，科技→科技，政治→新设衙门（走满即落成对应实体）；其余题材只作可追踪局势。</small>
            </label>
          )}
          {/* 实体固定字段：按题材展开，仅新建时 */}
          {!editing && entityKind === "building" ? (
            <fieldset className="manual-issue-entity">
              <legend>落成建筑（走满 100 自动建成）</legend>
              <label>所在省份
                <select value={regionId} onChange={(e) => setRegionId(e.target.value)}>
                  {!regions.length ? <option value="">（无省份数据）</option> : null}
                  {regions.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                </select>
              </label>
              <label>建筑类别
                <select value={bldCategory} onChange={(e) => setBldCategory(e.target.value)}>
                  {BUILDING_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
              <label>月维护费（万两）
                <input type="number" min={0} max={50} value={maintenance}
                  onChange={(e) => setMaintenance(Math.max(0, Number(e.target.value) || 0))} />
              </label>
            </fieldset>
          ) : null}
          {!editing && entityKind === "department" ? (
            <fieldset className="manual-issue-entity">
              <legend>新设衙门（走满 100 自动设立）</legend>
              <div className="manual-issue-mode">
                <button type="button" className={presetMode === "preset" ? "active" : ""} onClick={() => setPresetMode("preset")}>预设政治树</button>
                <button type="button" className={presetMode === "custom" ? "active" : ""} onClick={() => setPresetMode("custom")}>自定义</button>
              </div>
              {presetMode === "preset" ? (
                <div className="manual-preset-tree">
                  {selectablePresets.map((p) => (
                    <button type="button" key={p.key} className={`manual-preset-node ${presetKey === p.key ? "active" : ""} ${!p.available ? "locked" : ""}`}
                      onClick={() => setPresetKey(p.key)}>
                      <span>{p.name}</span>
                      <small>{p.unlocked ? "已设立" : p.available ? `${p.expected_months} 月 · 起步 ${p.bar_value}` : presetRequirementText(p, presetPool)}</small>
                    </button>
                  ))}
                  {!selectablePresets.length ? <small className="manual-issue-hint">预设衙门已全部设立。</small> : null}
                </div>
              ) : (
                <>
                  <label>职权范围
                    <input type="text" value={authorityScope} maxLength={40} placeholder="如：统筹中枢军政机要"
                      onChange={(e) => setAuthorityScope(e.target.value)} />
                  </label>
                  <label>权力值（0-100）
                    <input type="number" min={0} max={100} value={power}
                      onChange={(e) => setPower(Math.max(0, Math.min(100, Number(e.target.value) || 0)))} />
                  </label>
                </>
              )}
            </fieldset>
          ) : null}
          {!editing && entityKind === "technology" ? (
            <fieldset className="manual-issue-entity">
              <legend>新解锁科技（走满 100 自动解锁）</legend>
              <div className="manual-issue-mode">
                <button type="button" className={presetMode === "preset" ? "active" : ""} onClick={() => setPresetMode("preset")}>预设科技树</button>
                <button type="button" className={presetMode === "custom" ? "active" : ""} onClick={() => setPresetMode("custom")}>自定义</button>
              </div>
              {presetMode === "preset" ? (
                <div className="manual-preset-tree">
                  {selectablePresets.map((p) => (
                    <button type="button" key={p.key} className={`manual-preset-node ${presetKey === p.key ? "active" : ""} ${!p.available ? "locked" : ""}`}
                      onClick={() => setPresetKey(p.key)}>
                      <span>{p.name}</span>
                      <small>{p.unlocked ? "已研成" : p.available ? `${p.expected_months} 月 · 起步 ${p.bar_value}` : presetRequirementText(p, presetPool)}</small>
                    </button>
                  ))}
                  {!selectablePresets.length ? <small className="manual-issue-hint">预设科技已全部研成。</small> : null}
                </div>
              ) : (
                <label>效果摘要
                  <input type="text" value={effectSummary} maxLength={60} placeholder="如：仿西法烧造琉璃，开海外贸易之源"
                    onChange={(e) => setEffectSummary(e.target.value)} />
                </label>
              )}
            </fieldset>
          ) : null}
          {editing ? null : (
            <label>
              目标
              <textarea
                value={goal}
                maxLength={300}
                rows={3}
                placeholder="皇帝亲定的方向，如：在苏州招募商匠建窑、聘琉璃匠、采石英砂，逐月推进至落成烧造。"
                onChange={(e) => setGoal(e.target.value)}
              />
              <small className="manual-issue-hint">推演每月按此目标推进进度。立项后锁定，不可改。</small>
            </label>
          )}
          <label>
            持续回合数
            <input
              type="number"
              min={0}
              max={120}
              value={duration}
              onChange={(e) => setDuration(Math.max(0, Number(e.target.value) || 0))}
            />
            <small className="manual-issue-hint">0 = 无期限；&gt;0 到期自动撤销。</small>
          </label>
          <div className="manual-issue-actions">
            <button onClick={onClose} disabled={busy}>取消</button>
            <button className="primary" onClick={save} disabled={busy}>{busy ? "保存中…" : "保存"}</button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}

export function SituationRow({ issue, onChanged }: { issue: Issue; onChanged?: () => void | Promise<void> }) {
  const ref = React.useRef<HTMLDivElement>(null);
  const [tipPos, setTipPos] = React.useState<{ x: number; y: number } | null>(null);
  const [detail, setDetail] = React.useState(false);
  const suppressRef = React.useRef(false);  // 关弹窗后抑制 tip，直到鼠标移出再进
  const showTip = () => {
    if (detail || suppressRef.current) return;
    const r = ref.current?.getBoundingClientRect();
    if (r) setTipPos({ x: r.right + 12, y: r.top });
  };
  const hideTip = () => { setTipPos(null); suppressRef.current = false; };  // 鼠标移出，解抑制
  const closeDetail = () => {
    setDetail(false);
    setTipPos(null);
    suppressRef.current = true;  // 关弹窗时鼠标多半还在行上，抑制到下次移出
  };
  return (
    <div ref={ref} className={`situation-row ${issueTone(issue.bar_value)}`} tabIndex={0}
      onClick={() => {
        setDetail(true);
        setTipPos(null);
      }} role="button"
      onMouseEnter={showTip} onMouseLeave={hideTip} onFocus={showTip} onBlur={hideTip}>
      <div className="situation-row-head">
        <span className="situation-name">{issue.title}</span>
        <b>{issue.bar_value}</b>
      </div>
      <div className="situation-bar">
        <i style={{ width: `${Math.max(0, Math.min(100, issue.bar_value))}%` }} />
      </div>
      {tipPos && !detail ? <SituationTip issue={issue} pos={tipPos} /> : null}
      {detail ? <SituationDetailModal issue={issue} onClose={closeDetail} onChanged={onChanged} /> : null}
    </div>
  );
}


// 局势悬浮框（精简）：只显数值，hover 触发。详细达成/失败点击弹窗看
export function SituationTip({ issue, pos }: { issue: Issue; pos: { x: number; y: number } }) {
  const W = 280, vw = window.innerWidth, vh = window.innerHeight;
  const left = pos.x + W > vw ? Math.max(8, pos.x - W - 24) : pos.x;
  const top = Math.min(pos.y, vh - 200);
  return createPortal(
    <div className="situation-tip-float" style={{ left, top: Math.max(8, top) }}>
        <div className="situation-tip-float-head">#{issue.id} {issue.title}</div>
        <div className="situation-tip-inner">
        <div className="situation-tip-row"><span>阶段</span><b>{issue.phase}</b></div>
        <div className="situation-tip-row"><span>进度</span><b>{issue.bar_value} / 100</b></div>
        <div className="situation-tip-row">
          <span>月度推进</span>
          <b>{issue.inertia > 0 ? `+${issue.inertia}` : issue.inertia}/月</b>
        </div>
        <div className="situation-tip-row">
          <span>当前影响</span>
          <b>{issue.ongoing_text || "无"}</b>
        </div>
        <p className="situation-tip-stage">{issue.stage_text}</p>
        <div className="situation-tip-more">点击查看达成 / 失败条件</div>
        </div>
    </div>,
    document.body
  );
}


// 局势目标(goal)只读展示——goal 立项后锁定不可改。
function IssueGoalView({ issue }: { issue: Issue }) {
  if (!issue.goal) return null;
  return (
    <div className="issue-goal-box">
      <div className="issue-goal-label">目标</div>
      <p className="issue-goal-text">{issue.goal}</p>
    </div>
  );
}

// 局势详情弹窗（点击）：完整达成/失败条件 + 标签 + 目标(可改)。居中模态，Portal 脱离梯形
export function SituationDetailModal({ issue, onClose, onChanged }: {
  issue: Issue;
  onClose: () => void;
  onChanged?: () => void | Promise<void>;
}) {
  return createPortal(
    <div className="situation-detail-backdrop" onClick={onClose}>
      <div className="situation-detail" onClick={(e) => e.stopPropagation()}>
        <div className="situation-detail-head">
          <span>#{issue.id} {issue.title}</span>
          <button className="situation-detail-close" onClick={onClose} aria-label="关闭">×</button>
        </div>
        <div className="situation-tip-inner">
        <IssueGoalView issue={issue} />
        <div className="situation-tip-row"><span>阶段</span><b>{issue.phase}</b></div>
        <div className="situation-tip-row"><span>进度</span><b>{issue.bar_value} / 100</b></div>
        <div className="situation-tip-row">
          <span>月度推进</span>
          <b>{issue.inertia > 0 ? `+${issue.inertia}` : issue.inertia}/月</b>
        </div>
        <div className="situation-tip-row">
          <span>当前影响</span>
          <b>{issue.ongoing_text || "无"}</b>
        </div>
        <p className="situation-tip-stage">{issue.stage_text}</p>
        <div className="situation-tip-outcome good">
          <div className="situation-tip-outcome-head">达成（{issue.bar_good_meaning}）</div>
          {issue.resolve_condition && <p>{issue.resolve_condition}</p>}
          <div className="situation-tip-effect">{formatIssueEffect(issue.effect_on_resolve)}</div>
        </div>
        <div className="situation-tip-outcome bad">
          <div className="situation-tip-outcome-head">失败（{issue.bar_bad_meaning}）</div>
          {issue.fail_condition && <p>{issue.fail_condition}</p>}
          <div className="situation-tip-effect">{formatIssueEffect(issue.effect_on_fail)}</div>
        </div>
        {issue.tags.length ? (
          <div className="situation-tip-tags">
            {issue.tags.map((tag) => <small key={tag}>{tag}</small>)}
          </div>
        ) : null}
        </div>
      </div>
    </div>,
    document.body
  );
}

export function IssueGroup({ title, issues }: { title: string; issues: Issue[] }) {
  if (!issues.length) return null;
  return (
    <div className="issue-group">
      <h3>{title}</h3>
      <div className="issue-list">
        {issues.map((issue) => (
          <article className={`issue-line ${issueTone(issue.bar_value)}`} key={issue.id}>
            <div className="issue-head">
              <b>#{issue.id} {issue.title}</b>
              <span>{issue.phase} · {issue.bar_value}</span>
            </div>
            <div className="issue-progress" aria-label={`${issue.title}进度 ${issue.bar_value}`}>
              <span>{issue.bar_bad_meaning}</span>
              <div>
                <i style={{ width: `${Math.max(0, Math.min(100, issue.bar_value))}%` }} />
              </div>
              <span>{issue.bar_good_meaning}</span>
            </div>
            <p>{issue.stage_text}</p>
            {issue.tags.length ? (
              <div className="issue-tags">
                {issue.tags.map((tag) => <small key={tag}>{tag}</small>)}
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </div>
  );
}
