# 07 质量门与论文交付规范

## 1. 目标

质量门将“可以交付”转化为可执行规则。任何阻断级检查失败，论文不得进入最终交付。

原有速易通 G1—G4 规则作为经济金融专著领域配置保留；本项目新增通用科研与 ICLR Short Paper 配置，不能把固定十章、GB/T 7714 或经济数据基线应用到 Agent 论文。

## 2. 严重级别

| 级别 | 行为 |
|---|---|
| BLOCK | 阻止阶段或交付，必须修复或正式终止项目 |
| WARN | 允许继续，但必须由人工确认并记录理由 |
| INFO | 提供改进建议，不影响交付 |

模型辅助判断默认不能单独产生 BLOCK，除非有确定性证据或人工确认。

## 3. ICLR Short Paper 质量门

### Q0 研究完整性

- **Q0.1 BLOCK**：出现捏造文献、实验、数据、作者或审稿结果。
- **Q0.2 BLOCK**：论文数字无法追溯到 Experiment Ledger 或合法数据源。
- **Q0.3 BLOCK**：隐藏失败实验以造成误导性结论。
- **Q0.4 BLOCK**：超出数据许可、隐私或伦理允许范围。
- **Q0.5 WARN/BLOCK**：重大 LLM 使用未按目标规则披露。

### Q1 文献与来源

- **Q1.1 BLOCK**：参考文献不存在或核心元数据无法验证。
- **Q1.2 BLOCK**：正文引用与 BibTeX 条目不一致。
- **Q1.3 BLOCK**：把搜索结果片段或模型总结表述为直接原文证据。
- **Q1.4 WARN**：关键相关工作只有摘要级证据。
- **Q1.5 WARN**：相关工作覆盖存在明显时间或方法空白。
- **Q1.6 BLOCK**：引用撤稿文献而未标注其状态。

### Q2 Claim-Evidence 一致性

- **Q2.1 BLOCK**：核心 Claim 没有 Evidence 或 Experiment 支撑。
- **Q2.2 BLOCK**：实验只证明相关性，论文却表述为因果或普遍结论。
- **Q2.3 WARN**：支持证据置信度低或仅来自单一二手来源。
- **Q2.4 BLOCK**：论文段落中的数值与关联实验指标不一致。
- **Q2.5 WARN**：存在未讨论的反证或冲突证据。

### Q3 方法与实验设计

- **Q3.1 BLOCK**：缺少能够检验主要假设的基线。
- **Q3.2 BLOCK**：方法贡献无法与额外 Token、模型能力或 Agent 数量区分。
- **Q3.3 BLOCK**：存在数据泄漏或测试集调参。
- **Q3.4 WARN**：消融不足以定位主要组件贡献。
- **Q3.5 WARN**：重复次数或样本规模不足，且未说明限制。
- **Q3.6 BLOCK**：实验计划与实际运行不一致且未记录变更。

### Q4 结果与统计

- **Q4.1 BLOCK**：表格或图中的值无法从机器可读结果重建。
- **Q4.2 BLOCK**：错误使用统计检验或显著性结论。
- **Q4.3 WARN**：只报告平均值，未报告方差、区间或重复性信息。
- **Q4.4 WARN**：负面结果、失败情况或边界条件未讨论。
- **Q4.5 BLOCK**：图表标签、单位或样本数与结果文件不一致。

### Q5 论文结构与写作

必需内容：

- Abstract；
- Introduction；
- Related Work；
- Method；
- Experiments；
- Results/Analysis；
- Limitations；
- References；
- 按目标规则需要的 Ethics/LLM Usage/Reproducibility 内容。

检查：

- **Q5.1 BLOCK**：摘要或贡献声明包含正文未验证结果。
- **Q5.2 WARN**：贡献与相关工作差异不清晰。
- **Q5.3 WARN**：方法缺少足够实现细节。
- **Q5.4 WARN**：术语、缩写或符号前后不一致。
- **Q5.5 BLOCK**：章节、图表或公式引用断裂。

### Q6 模板、匿名化与 PDF

- **Q6.1 BLOCK**：LaTeX 编译失败或存在 unresolved references/citations。
- **Q6.2 BLOCK**：匿名稿泄露作者、机构、仓库账户或文件元数据。
- **Q6.3 BLOCK**：修改模板页边距、字号或核心样式以规避页数限制。
- **Q6.4 BLOCK**：正文页数超过项目 `page_budget`。
- **Q6.5 BLOCK**：供 Stanford Agentic Reviewer 使用的 PDF 超过 10MB。
- **Q6.6 WARN**：核心方法和结果未出现在前 15 页内。
- **Q6.7 BLOCK**：供当前 Stanford Reviewer 使用的稿件不是英文。

说明：正式 ICLR 2026 投稿正文上限为 9 页，但比赛 Short Paper 页数应由比赛规则配置，不能硬编码为 9 页。

### Q7 可复现与交付

- **Q7.1 BLOCK**：缺少核心实验代码或执行说明，且未说明不可提供原因。
- **Q7.2 BLOCK**：关键运行缺少代码、环境、数据或模型配置版本。
- **Q7.3 BLOCK**：delivery manifest 中的文件哈希与实际文件不一致。
- **Q7.4 WARN**：第三方依赖或数据源可能不可长期获取。
- **Q7.5 WARN**：从干净环境复现未完成或存在非阻断差异。

## 4. 确定性与模型辅助规则

### 4.1 确定性规则

- 文件存在、哈希和大小；
- LaTeX 编译和页数；
- 引用键、BibTeX 和 DOI 验证；
- 数值与 metrics 映射；
- Artifact 版本和审批状态；
- 匿名化关键词与元数据扫描；
- 代码测试、退出码和复现检查。

### 4.2 模型辅助规则

- Claim 是否过度表述；
- 相关工作是否充分；
- 方法和实验是否存在逻辑缺口；
- 写作清晰度；
- 限制是否完整。

模型辅助规则应提供证据位置、置信度和复核建议，不只输出分数。

## 5. 规则配置示例

```yaml
profile: iclr_short_paper
version: 0.1
language: en
page_budget: 6
pdf_max_mb: 10
core_content_max_page: 15
anonymous: true
gates:
  citation_integrity:
    severity: BLOCK
    checks:
      - body_keys_equal_bib_keys
      - identifiers_verified
  claim_support:
    severity: BLOCK
    checks:
      - all_core_claims_have_support
      - numeric_claims_match_metrics
  reproducibility:
    severity: BLOCK
    checks:
      - run_provenance_complete
      - manifest_hashes_match
```

## 6. 验收逻辑

```text
DeliverableAccepted =
  no BLOCK failures
  AND all required approvals granted
  AND all WARN items acknowledged
  AND artifact versions match gate input versions
  AND manifest verification passes
```

质量门通过后若论文或实验产物发生变化，原质量报告自动失效，必须重新执行。

## 7. 防止评测投机

- 不以重复提交外部审稿器选择最高分版本作为主要方法。
- 不针对外部审稿器提示词反向优化论文措辞。
- 不删除低分运行或只报告最有利随机种子。
- 内部评测开发集与最终测试集分离。
- 所有指标定义在看最终结果前冻结。
- 外部自动审稿只作为多个评价视角之一。

