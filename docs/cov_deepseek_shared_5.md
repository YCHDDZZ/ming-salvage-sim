# Extractor 全字段覆盖测试报告

- 跑 case：**5**　PASS **5** / FAIL **0** / ERROR **0**
- 顶层字段总数：**23**
- 耗时：571s

## 一、字段遗漏校验

⚠️ **无任何 case 验证的字段（21）**：国势变化、财政制度变化、新立月度收支、裁撤月度收支、派系变化、阶级变化、局势推进、新立局势、撤销局势、结案局势、军队变化、新建军队、势力变化、四方动向、人事变更、人物状态变化、人物易主、后宫册封、密令副作用、密令结案、崇祯结局

❌ **有 case 期望但实测从未抽到的字段（12）**：财政制度变化、新立月度收支、裁撤月度收支、撤销局势、结案局势、新建军队、人事变更、人物易主、后宫册封、密令副作用、密令结案、崇祯结局　← 需排查 prompt 或 case

## 二、字段覆盖矩阵

| 顶层字段 | 期望次数 | 实测命中次数 | 命中 case |
|---|---|---|---|
| ✅ 国势变化 | 0 | 5 | c001_chaojia_neiku、c002_chaojia_guoku、c003_zhenzai_chuzhang、c004_bushang_guanning、c005_lianglib_huboge |
| ✅ 钱粮收支 | 5 | 5 | c001_chaojia_neiku、c002_chaojia_guoku、c003_zhenzai_chuzhang、c004_bushang_guanning、c005_lianglib_huboge |
| — 财政制度变化 | 0 | 0 |  |
| — 新立月度收支 | 0 | 0 |  |
| — 裁撤月度收支 | 0 | 0 |  |
| ✅ 派系变化 | 0 | 3 | c001_chaojia_neiku、c002_chaojia_guoku、c004_bushang_guanning |
| ✅ 阶级变化 | 0 | 3 | c001_chaojia_neiku、c002_chaojia_guoku、c004_bushang_guanning |
| ✅ 地区变化 | 1 | 4 | c001_chaojia_neiku、c002_chaojia_guoku、c003_zhenzai_chuzhang、c004_bushang_guanning |
| ✅ 局势推进 | 0 | 5 | c001_chaojia_neiku、c002_chaojia_guoku、c003_zhenzai_chuzhang、c004_bushang_guanning、c005_lianglib_huboge |
| ✅ 新立局势 | 0 | 1 | c005_lianglib_huboge |
| — 撤销局势 | 0 | 0 |  |
| — 结案局势 | 0 | 0 |  |
| ✅ 军队变化 | 0 | 5 | c001_chaojia_neiku、c002_chaojia_guoku、c003_zhenzai_chuzhang、c004_bushang_guanning、c005_lianglib_huboge |
| — 新建军队 | 0 | 0 |  |
| ✅ 势力变化 | 0 | 2 | c002_chaojia_guoku、c003_zhenzai_chuzhang |
| ✅ 四方动向 | 0 | 5 | c001_chaojia_neiku、c002_chaojia_guoku、c003_zhenzai_chuzhang、c004_bushang_guanning、c005_lianglib_huboge |
| — 人事变更 | 0 | 0 |  |
| ✅ 人物状态变化 | 0 | 1 | c005_lianglib_huboge |
| — 人物易主 | 0 | 0 |  |
| — 后宫册封 | 0 | 0 |  |
| — 密令副作用 | 0 | 0 |  |
| — 密令结案 | 0 | 0 |  |
| — 崇祯结局 | 0 | 0 |  |

## 三、逐 case 明细

| case | 状态 | 期望 | 实测命中 | 缺失 | 多余 | 备注 |
|---|---|---|---|---|---|---|
| c001_chaojia_neiku | ✅ | 钱粮收支 | 军队变化、四方动向、国势变化、地区变化、局势推进、派系变化、钱粮收支、阶级变化 | — | 军队变化、四方动向、国势变化、地区变化、局势推进、派系变化、阶级变化 |  |
| c002_chaojia_guoku | ✅ | 钱粮收支 | 军队变化、势力变化、四方动向、国势变化、地区变化、局势推进、派系变化、钱粮收支、阶级变化 | — | 军队变化、势力变化、四方动向、国势变化、地区变化、局势推进、派系变化、阶级变化 |  |
| c003_zhenzai_chuzhang | ✅ | 钱粮收支、地区变化 | 军队变化、势力变化、四方动向、国势变化、地区变化、局势推进、钱粮收支 | — | 军队变化、势力变化、四方动向、国势变化、局势推进 |  |
| c004_bushang_guanning | ✅ | 钱粮收支 | 军队变化、四方动向、国势变化、地区变化、局势推进、派系变化、钱粮收支、阶级变化 | — | 军队变化、四方动向、国势变化、地区变化、局势推进、派系变化、阶级变化 |  |
| c005_lianglib_huboge | ✅ | 钱粮收支 | 人物状态变化、军队变化、四方动向、国势变化、局势推进、新立局势、钱粮收支 | — | 人物状态变化、军队变化、四方动向、国势变化、局势推进、新立局势 |  |
