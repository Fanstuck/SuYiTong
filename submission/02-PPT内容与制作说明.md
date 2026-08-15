# 速易通方案 PPT 内容与制作说明

## 一、PPT 的沟通目标

评委看完后应形成一个明确判断：速易通不是“一键代写”界面，而是一套把 Agent 科研过程变成可追溯、可审批、可实验、可复现工程流程的中台；PACM-SW 是其区别于普通 Chat/RAG 的核心技术。

建议采用 **14 页、16:9、7–9 分钟讲解**。视觉沿用产品的深绿、米白与低饱和薄荷绿；一页只表达一个结论，产品截图优先于概念插画。HarmonyOS 不进入当前主叙事，只在路线图中作为未来多端入口。

## 二、逐页内容

### 第 1 页｜封面

**标题：** 速易通 SuYiTong  
**副标题：** 基于 JiuwenSwarm 的可追溯科研 Agent 中台  
**一句话：** 让科研短论文从研究意图走向有证据、有实验、有边界的可复现交付。

视觉建议：使用 `screenshots/01-dashboard.png` 做右侧或下方大图，左侧保留标题、团队名和比赛赛题。

### 第 2 页｜场景来源：科研写作卡在“流程和判断”

**页面主张：** 真正耗时的不只是写字，而是跨工具协作、证据核验和质量判断。

可见内容：

- 流程断裂：选题、检索、写作、实验、排版分散在不同工具；
- 重复劳动：术语、引用、版本和格式反复调整；
- 缺乏判断：不知道论点是否有证据、实验是否足以支撑结论；
- 长流程失忆：Agent 交接时容易丢失决策原因和限制条件。

说明：前三项来自早期专著重构、论文提炼和政策报告转化材料；第四项来自当前 Agent 科研任务的技术问题。

### 第 3 页｜目标用户与核心任务

**页面主张：** 同一平台服务三类角色，但保留研究责任在人。

- 高校学生/青年科研人员：需要清晰流程、文献证据和写作规范；
- 课题组/研发团队：需要多 Agent 协作、项目状态和实验复现；
- 质量审阅者：需要检查证据链、运行日志和结论边界。

右侧用一句任务定义：输入研究方向、已有计划或中间产物，输出可继续编辑和复现的 Short Paper 研究包。

### 第 4 页｜解决方案：把科研变成受控状态机

**页面主张：** 速易通把一次性对话升级为可恢复、可回放的科研工作流。

流程：

```text
选题拆解 → 文献调研 → 方法设计 → 实验验证 → 结果分析 → 论文写作 → 内部评审 → 交付
             ↑人工审批↑        ↑成本/结果审批↑              ↑最终审批↑
```

强调全流程与半流程两种入口；每个阶段都有输入、产物、状态、失败原因和质量门。配图使用 `screenshots/02-project-workbench-overview.png`。

### 第 5 页｜系统架构：JiuwenSwarm 负责协作，中台负责事实

**页面主张：** 对话不是项目事实源，结构化产物才是。

架构层次：

```text
Web 工作台
  ↓
FastAPI Control API / 项目状态机 / 人工审批
  ↓
JiuwenSwarm Adapter / Planner-Researcher-Writer-Reviewer
  ↓
OpenAlex、Crossref、模型 API、Embedding API、确定性校验工具
  ↓
SQLite 项目库、Evidence/Experiment Ledger、逐运行 JSONL
```

页脚写明：第三方 API 路线，无需本地 GPU；模型、检索源和 Embedding 可替换。

### 第 6 页｜Agent 能力：不是 Agent 越多越好，而是职责可验证

**页面主张：** 每个智能体只对一个可验收产物负责。

- Planner：拆解目标、任务和输出契约；
- Researcher：检索、去重并建立 PAPER 白名单；
- Method Agent：把文献空白转成可实现、可证伪方法；
- Experiment Agent：冻结基线、指标、种子和预算；
- Writer：只基于批准证据和实验结果写作；
- Reviewer：检查引用、结论边界和交付规范。

交接携带 task、approved decisions、evidence bundle、conflicts、version 和 acceptance criteria。

### 第 7 页｜核心创新：PACM-SW 可溯源上下文记忆

**页面主张：** 普通相似度检索回答“像不像”，PACM-SW 还回答“从哪里来、是否适合当前角色、是否冲突”。

四层记忆：

- K 约束层：任务要求、质量规则、禁止事项；
- P 程序层：方法步骤、实验协议和分析流程；
- E 情节层：运行、结果、失败与版本变化；
- S 语义层：论文、概念、Claim 与 Evidence。

排序信号：Relevance + Provenance + Freshness + RoleMatch + GraphConnection - Conflict - Redundancy，并按 Token 预算装配。配图使用 `screenshots/05-method-design.png`，裁取“四层记忆/评分目标”区域。

### 第 8 页｜工具、数据与模型如何协同

**页面主张：** 大模型负责需要判断的部分，确定性工具负责必须准确的部分。

- 模型：OpenAI-compatible 第三方 API，经 JiuwenSwarm 调度；
- 学术数据：OpenAlex + Crossref，DOI 与规范化标题去重；
- 检索：B2 dense cosine、B3 BM25+dense RRF、PACM-SW；
- 向量：用户可配置 Embedding API，本地 SHA-256 缓存；
- 审计：PAPER 白名单、JSONL、SQLite、SHA-256 Manifest；
- 配置：API Key 仅写入本地 `.env`，读取接口只返回是否已配置。

配图使用 `screenshots/09-environment-demo.png`，确保密码框始终为空或掩码。

### 第 9 页｜真实产品：从选题到方法设计

**页面主张：** 已经形成可运行垂直链路，而非静态原型图。

三张截图横排或递进：

1. `screenshots/03-topic-framing.png`：手动输入研究方向，输出候选题、研究问题和证据边界；
2. `screenshots/04-literature-review.png`：双源检索、PAPER 编号、研究空白和检索限制；
3. `screenshots/05-method-design.png`：PACM-SW 组件、记忆层、溯源契约和实验设计。

页面只保留三条图注，不要把完整 UI 缩到不可读。

### 第 10 页｜实验验证：工程结果与论文结论严格分开

**页面主张：** 平台宁可阻断，也不把代理数据写成论文结论。

冻结配置：B0、B1、B2、B3、Ours；三种子 13/37/73；R1-R6 单变量消融。

已完成的工程验证：

- 9 个检索配置 × 6 条查询 × 3 seeds；
- 164 条逐运行 JSONL；
- 1024 维 Embedding；
- 相同输入复跑命中 106/106 缓存。

必须标注：上述是 engineering validation，不是 PACM-SW 效果结论。配图使用 `screenshots/06-experiment-demo.png` 与 `screenshots/07-retrieval-demo.png`。

### 第 11 页｜人工 Gold 与质量门

**页面主张：** 独立人工 qrels 未冻结时，正式实验无法启动。

- 合并各检索器候选并隐藏系统来源、排名和分数；
- 人工按 0–3 标注相关性；
- 全部完成且每条查询至少一个相关项后才能冻结；
- formal 检索与 formal 生成在 qrels 未冻结时返回 HTTP 409；
- 模型连接失败和实验失败原样写入 JSONL，不删除、不补造。

配图使用 `screenshots/08-formal-benchmark-demo.png`。这页是可信度亮点，不要弱化“QUALITY GATE BLOCKED”。

### 第 12 页｜开放与复用价值

**页面主张：** 速易通不仅能演示，还能作为科研 Agent 的实验底座复用。

- JiuwenSwarm 通过适配层接入，减少对上游核心 Fork；
- 模型、Embedding、文献源和审稿器可替换；
- API、数据模型、运行日志与质量门规则可独立复用；
- 示例配置不含密钥，公开仓库可按脚本重建；
- PACM-SW 可迁移到政策研究、技术报告和团队知识生产。

配图使用 `screenshots/10-api-demo.png`，右下角放 GitHub 仓库地址。

### 第 13 页｜当前进展与后续落地

**页面主张：** 核心科研基础设施已贯通，下一阶段是完成正式评测和论文交付。

已完成：JiuwenSwarm 二开、本地 Web、项目状态机、选题、文献、方法、实验协议、真实检索、qrels 界面、消融与 B0/B1 调度、12 项自动测试。

下一步：

1. 完成独立人工 qrels 并冻结；
2. 修复/确认正式生成模型端点；
3. 运行五系统、六消融、三种子完整矩阵；
4. 统计重建与人工写作质量评审；
5. 输出 ICLR 风格 LaTeX、PDF、BibTeX 和复现包。

HarmonyOS 多端入口放在“长期扩展”小字中即可。

### 第 14 页｜结束页

**标题：** 让 Agent 生成的不只是论文，而是可被检查的科研过程  
**副文案：** 速易通 · Provenance-Aware Scientific Writing  
**行动入口：** Demo 视频 / GitHub 仓库 / 联系方式二维码

背景建议用 `screenshots/01-dashboard.png` 模糊化处理，不再使用泛化 AI 插画。

## 三、制作注意事项

- 每页正文不超过 5 个要点；技术细节放讲解或附录。
- 工程指标必须带 `ENGINEERING` 或“非论文结论”标签。
- 不展示 API Key、Authorization Header、`.env`、本地用户目录和完整运行日志正文。
- 截图至少保留 1440px 宽；长页面只裁切当前叙事区域。
- 不再宣称“鸿蒙端侧 NPU、本地模型、离线推理已经实现”。
- 不宣称已生成完整 ICLR 论文或已通过 Stanford Agentic Reviewer；这些属于后续目标。
