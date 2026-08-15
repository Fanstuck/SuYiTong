# 05 Agent、Skill 与工具设计

## 1. 设计原则

- Agent 数量由职责隔离和评测需要决定，不以数量作为先进性证明。
- Agent 之间通过结构化产物交接，不以无限聊天作为主要协作方式。
- 一个 Agent 对一个阶段负主要责任，但必须接受独立质量检查。
- 稳定流程写入 Skill；确定性原子能力实现为 Tool；阶段流转由状态机控制。
- Agent 输出必须符合 JSON Schema 或受控文档模板。

## 2. 核心 Agent 团队

### 2.1 Research Lead

职责：

- 理解项目约束；
- 分解阶段任务；
- 选择需要的专业 Agent；
- 汇总冲突并请求决策；
- 检查阶段交付契约；
- 维护研究目标与范围一致性。

不得：绕过审批、直接修改实验结果、把团队共识当作证据。

### 2.2 Literature Scout

职责：

- 生成多粒度查询；
- 检索与初筛文献；
- 建立主题、方法、数据集与基线分类；
- 提取可定位证据；
- 报告反证和未覆盖区域。

不得：创建不存在的文献、将搜索摘要当作已验证全文结论。

### 2.3 Methodologist

职责：

- 将研究空白转化为可证伪假设；
- 设计方法、基线和消融；
- 定义数据、指标、重复次数和停止条件；
- 识别混杂变量、泄漏和不可验证主张。

不得：在结果产生后静默修改主要指标或假设。

### 2.4 Experimenter

职责：

- 把实验计划转化为代码与配置；
- 使用工具运行测试和实验；
- 保存环境、日志、资源和原始指标；
- 诊断失败但不伪造结果；
- 生成机器可读实验摘要。

不得：在未审批时扩大资源、联网或安装不受信依赖。

### 2.5 Paper Writer

职责：

- 根据 Claim Ledger 和论文模板组织叙事；
- 正确引用已验证文献；
- 从真实指标生成表格与分析；
- 区分事实、结果、推断和限制；
- 控制页数和表达清晰度。

不得：自由补充数字、虚构对照实验、扩大结论范围。

### 2.6 Reviewer

职责：

- 以独立视角审查新颖性、方法、实验和写作；
- 检查 Claim 是否得到 Evidence/Experiment 支撑；
- 发现缺失基线、消融和限制；
- 将意见转化为可执行修订任务；
- 给出置信度和无法判断的部分。

Reviewer 不负责直接重写论文，以保持“发现问题”和“修改问题”的角色分离。

## 3. 临时评审角色

内部评审阶段可以为同一 Reviewer 配置不同 persona，但不需要长期运行多个常驻 Agent：

- Novelty Reviewer；
- Method Reviewer；
- Empirical Reviewer；
- Reproducibility Reviewer；
- Clarity Reviewer。

最终评审应聚合不同意见和分歧，不应通过简单多数投票掩盖关键阻断问题。

## 4. 职责矩阵

| 产物 | Lead | Literature | Method | Experiment | Writer | Reviewer |
|---|---|---|---|---|---|---|
| Research Brief | A/R | C | C | I | I | I |
| Evidence Ledger | A | R | C | I | C | C |
| Gap Analysis | A | R | R | I | I | C |
| Experiment Plan | A | C | R | C | I | C |
| Experiment Runs | I | I | A | R | I | C |
| Claim Ledger | A | C | C | C | R | C |
| Paper Draft | A | C | C | C | R | C |
| Review Report | I | I | I | I | C | A/R |

说明：R=负责，A=最终负责，C=参与，I=知会。

## 5. 首期 Skill 目录

```text
skills/
├── research-intake/
├── topic-ideation/
├── literature-search/
├── evidence-extraction/
├── gap-analysis/
├── experiment-design/
├── experiment-implementation/
├── result-audit/
├── claim-synthesis/
├── iclr-writing/
├── internal-review/
├── revision-planning/
└── delivery-audit/
```

每个 Skill 至少包含：

- 适用条件和不适用条件；
- 必需输入；
- 执行步骤；
- 可用工具；
- 输出 schema；
- 质量检查；
- 失败与升级路径；
- 正例和反例；
- 版本和回放测试集。

## 6. 工具能力清单

### 6.1 文献工具

- `search_openalex`
- `search_arxiv`
- `lookup_crossref_doi`
- `normalize_bibliographic_record`
- `deduplicate_works`
- `fetch_allowed_fulltext`
- `extract_evidence_span`
- `build_bibtex`
- `check_retraction_or_update`

### 6.2 文件与解析工具

- `read_project_artifact`
- `write_versioned_artifact`
- `parse_pdf`
- `parse_markdown`
- `parse_latex`
- `parse_docx`
- `compute_file_hash`
- `diff_artifact_versions`

### 6.3 实验工具

- `create_experiment_workspace`
- `run_unit_tests`
- `build_container`
- `run_experiment`
- `cancel_experiment`
- `collect_metrics`
- `validate_result_schema`
- `compute_statistics`
- `build_chart_data`

### 6.4 论文与质量工具

- `compile_latex`
- `check_bibtex`
- `check_citations`
- `check_claim_support`
- `check_anonymity`
- `check_page_budget`
- `check_pdf_size`
- `check_template_integrity`
- `build_delivery_manifest`

## 7. 工具权限分级

| 级别 | 示例 | 默认动作 |
|---|---|---|
| 只读低风险 | 搜索元数据、读取项目文件 | allow |
| 可逆写入 | 创建版本化产物、写实验工作区 | allow/record |
| 外部网络 | 下载全文、调用外部 API | ask 或按白名单 allow |
| 环境变更 | 安装依赖、构建镜像 | ask |
| 高成本执行 | GPU、长时间任务、大模型批量调用 | ask |
| 破坏性操作 | 删除数据、覆盖已批准产物 | deny 或严格审批 |
| 外部发布 | 投稿、发送邮件、公开上传 | deny（首期） |

## 8. Agent 输出契约

所有阶段 Agent 输出使用统一包装：

```json
{
  "stage": "method_design",
  "status": "proposed",
  "summary": "...",
  "artifacts": [],
  "evidence_used": [],
  "assumptions": [],
  "uncertainties": [],
  "blocking_questions": [],
  "quality_self_check": [],
  "next_action_proposal": "request_approval"
}
```

状态机只接受通过 schema 验证的结果。`summary` 不作为事实数据，核心内容必须存在于对应 artifact 中。

## 9. Agent 间通信规则

- 交接信息必须关联 `project_id`、`stage_run_id` 和 artifact version。
- 结论通过 Claim/Decision 记录传递，不通过未经整理的长聊天转发。
- Agent 发现冲突时生成 `conflict_record`，不得自行删除其中一方。
- 只有 Lead 可以调整团队任务，但不能修改已批准研究事实。
- Reviewer 的阻断意见必须被显式解决、驳回或升级给人工。

## 10. 反模式

项目应主动避免：

- 一个 Agent 完成所有工作，其他 Agent 只重复润色；
- 为了表现 Swarm 而把确定性任务拆给多个模型；
- Agent 互相引用对方的自然语言作为证据；
- 把检索摘要、搜索片段或自动审稿意见当作论文事实；
- 失败后无限重试直到得到想要的结果；
- 让 Writer 在缺失实验时“合理补全”；
- 让 Reviewer 直接改稿导致审改角色合一；
- 允许自演进无评测地修改所有团队共享 Skill。

