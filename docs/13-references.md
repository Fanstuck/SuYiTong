# 13 资料来源

## 1. 用户提供的本地材料

### 1.1 学术写作质量门 SOP

文件：`C:\Users\10799\xwechat_files\wxid_6osleafhpejk22_c3a5\msg\file\2026-07\速易通交付标准SOP_学术写作质量门.md`

用于提取：

- 质量门的阻断/警告设计；
- 引用、术语、数据和结构检查思路；
- 机器可编码规则骨架；
- 质量门需配置化而非完全依赖模型的原则。

适用性说明：原文件主要面向经济、金融和战略专著，包含 GB/T 7714、固定十章结构、受控术语和数据截止日。上述领域规则不直接应用于 ICLR Agent 论文，而是保留为未来 `finance_book` 质量配置参考。

### 1.2 学术写作场景说明

文件：`C:\Users\10799\xwechat_files\wxid_6osleafhpejk22_c3a5\msg\file\2026-07\速易通学术写作场景说明文档.docx`

用于提取：

- 专著出海、学术论文提炼、政策报告转化三类既有场景；
- 从松散、口语化、术语不一致内容到结构化学术交付的价值；
- 可量化交付与人工信任的重要性。

说明：本次研究已结构化读取文本；当前环境缺少 LibreOffice，因此未完成 DOCX 页级渲染检查。

### 1.3 速易通产品介绍 PPT

文件：`C:\Users\10799\xwechat_files\wxid_6osleafhpejk22_c3a5\msg\file\2026-07\速易通：基于鸿蒙生态的学术写作效率平台(1).pptx`

用于提取：

- 学术写作的流程断裂、机械重复和缺乏判断三类痛点；
- 上传、AI 预处理、人工确认、交付的既有处理链路；
- 术语、结构、引用和格式四类 Agent 思路；
- 结构化重构、学术术语统一和多人协作入口；
- 现有方案与全流程自动科研之间的能力差距。

说明：本次研究已渲染并逐页检查全部 16 页。

## 2. JiuwenSwarm 与 openJiuwen 官方资料

- JiuwenSwarm 官方 AtomGit 仓库：<https://atomgit.com/openJiuwen/jiuwenswarm>
- JiuwenSwarm GitHub 组织镜像：<https://github.com/openJiuwen-ai>
- 用户指定 v0.2.2 文档入口：<https://www.openjiuwen.com/docs-page?version=jiuwenswarm-v0.2.2-zh-5g721TgP&path=%E5%AE%89%E8%A3%85%E6%8C%87%E5%8D%97>
- 官方安装指南镜像：<https://github.com/openJiuwen-ai/jiuwenswarm/blob/develop/docs/en/InstallGuide.md>
- 官方配置说明：<https://github.com/openJiuwen-ai/jiuwenswarm/blob/develop/docs/zh/%E9%85%8D%E7%BD%AE%E4%BF%A1%E6%81%AF.md>
- 官方记忆系统说明：<https://github.com/openJiuwen-ai/jiuwenswarm/blob/develop/docs/zh/%E8%AE%B0%E5%BF%86.md>
- 官方 Skill 自演进说明：<https://github.com/openJiuwen-ai/jiuwenswarm/blob/develop/docs/zh/Skill%E8%87%AA%E6%BC%94%E8%BF%9B.md>
- openJiuwen Core：<https://github.com/openJiuwen-ai/agent-core>

版本说明：上述部分页面为 `develop` 分支，其内容可能晚于 v0.2.2。当前实现以 AtomGit 标签 `JiuwenSwarm0.2.2` 和提交 `d7c2ab2f299cd2c73201afb41ebb8b9c00cc7015` 为准。

## 3. 论文模板和外部审稿

- ICLR 2026 Author Guide：<https://iclr.cc/Conferences/2026/AuthorGuide>
- ICLR Master Template：<https://github.com/ICLR/Master-Template>
- Stanford Agentic Reviewer：<https://paperreview.ai/>
- Stanford Agentic Reviewer Tech Overview：<https://paperreview.ai/tech-overview>

当前外部审稿约束记录：

- 上传 PDF；
- 最大 10MB；
- 分析前 15 页；
- 当前支持英文论文；
- 选择 ICLR 目标 venue 时显示整体评分；
- 自动审稿可能出错，只能作为辅助评价。

## 4. 文献元数据与公开研究服务

- OpenAlex API：<https://developers.openalex.org/api-reference/introduction>
- Crossref REST API：<https://www.crossref.org/documentation/retrieve-metadata/rest-api/>
- arXiv API User Manual：<https://github.com/arXiv/arxiv-docs/blob/develop/source/help/api/user-manual.md>

接入这些服务前还需核对各自最新使用条款、速率限制、鉴权和缓存要求。

## 5. 后续需补充的资料

- 比赛正式规则、评分表和交付模板；
- JiuwenSwarm v0.2.2 与后续安全更新的差异；
- 可用第三方模型、API 预算、速率限制和故障切换说明；
- Agent 研究方向的系统性相关工作；
- 任务集与数据集许可；
- ICLR Short Paper 的比赛特定页数与披露要求。
