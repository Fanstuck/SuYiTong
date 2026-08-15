# 速易通项目文档索引

本目录是速易通的单一规划事实源。产品、研究、架构和实施决策应先更新文档，再进入开发。

## 文档状态约定

| 状态 | 含义 |
|---|---|
| 草案 | 用于讨论，允许大幅调整 |
| 待评审 | 内容相对完整，等待项目方确认 |
| 已冻结 | 可作为开发与验收依据 |
| 已废弃 | 不再执行，仅保留历史依据 |

当前文档基线为 **v0.1**；项目已进入 P1 技术验证，尚未冻结的比赛规则和研究方向继续保留为开放问题。

## 文档地图

| 编号 | 文档 | 主要回答的问题 |
|---|---|---|
| 00 | [项目章程](00-project-charter.md) | 为什么做、做到什么程度、坚持什么原则 |
| 01 | [范围与需求基线](01-scope-and-requirements.md) | 第一阶段做什么、不做什么、如何验收 |
| 02 | [研究方向](02-research-direction.md) | 选择哪个 Agent 研究方向，论文如何形成贡献 |
| 03 | [系统架构](03-system-architecture.md) | 中台如何分层，JiuwenSwarm 位于哪里 |
| 04 | [科研工作流](04-research-workflow.md) | 从选题到论文交付每一步如何流转 |
| 05 | [Agent/Skill/工具](05-agent-skill-tool-design.md) | 智能体如何分工，哪些能力应写成确定性工具 |
| 06 | [数据/上下文/记忆](06-data-context-memory.md) | 如何保证证据、结论、实验和记忆可追溯 |
| 07 | [质量门](07-quality-gates.md) | 什么样的论文才允许交付 |
| 08 | [实验与评测](08-evaluation-plan.md) | 如何证明平台和论文方法真正有效 |
| 09 | [JiuwenSwarm 集成](09-jiuwenswarm-integration.md) | 如何二次开发且保持可升级性 |
| 10 | [开发路线](10-roadmap-and-acceptance.md) | 先做什么、后做什么、每阶段交付什么 |
| 11 | [风险与治理](11-risk-compliance-governance.md) | 如何控制幻觉、版权、隐私、成本与自演进风险 |
| 12 | [决策与开放问题](12-decisions-and-open-questions.md) | 哪些结论已定，哪些必须继续研究 |
| 13 | [资料来源](13-references.md) | 本基线依据哪些本地材料和官方文档 |
| 14 | [开发环境与启动](14-development-setup.md) | 当前代码如何安装、配置、运行和验证 |
| 15 | [PACM-SW 垂直链路](15-pacm-sw-vertical-slice.md) | 核心技术方向如何从需求澄清形成可追溯选题产物 |
| 16 | [PACM-SW 文献调研链路](16-pacm-sw-literature-review.md) | 如何从真实学术元数据形成有证据编号的综述并进入人工质量门 |
| 17 | [PACM-SW 方法设计基线](17-pacm-sw-method-design.md) | 如何把已确认文献证据转化为可实现、可证伪、可消融的方法 |
| 18 | [PACM-SW 实验验证模块](18-pacm-sw-experiment.md) | 如何预注册实验、运行工程试验并阻止代理数据进入论文结论 |
| 19 | [PACM-SW 真实检索执行器](19-pacm-sw-real-retrieval.md) | 如何运行 B2/B3/PACM-SW 并用逐查询 JSONL 完整记录结果 |
| 20 | [PACM-SW 正式基线与消融批量](20-pacm-sw-formal-benchmark.md) | 如何运行 B0/B1、盲化人工 qrels、R1–R6 和三随机种子矩阵 |

## 变更规则

1. 影响产品范围的变更，先更新 00、01 和 12。
2. 影响科研贡献的变更，先更新 02 和 08。
3. 影响系统接口或存储模型的变更，先更新 03、05 和 06。
4. 影响交付标准的变更，先更新 07 和 10。
5. 已冻结内容发生重大变化时，应在 12 中新增决策记录，不直接覆盖历史原因。
