const STAGES = [
  ["intake", "需求澄清", "INTAKE"],
  ["topic_framing", "选题拆解", "TOPIC"],
  ["literature_review", "文献调研", "REVIEW"],
  ["method_design", "方法设计", "METHOD"],
  ["experiment", "实验验证", "EXPERIMENT"],
  ["writing", "论文撰写", "WRITING"],
  ["quality_review", "质量审查", "QUALITY"],
  ["delivered", "论文交付", "DELIVERED"],
];

const ENDPOINTS = [
  ["GET", "/health", "中台服务健康检查"],
  ["GET", "/api/v1/system/capabilities", "运行时与系统能力快照"],
  ["GET", "/api/v1/system/environment", "读取脱敏后的模型环境"],
  ["PUT", "/api/v1/system/environment", "保存模型与检索服务配置"],
  ["POST", "/api/v1/system/model/test", "检测模型服务连通性"],
  ["POST", "/api/v1/system/embedding/test", "检测 Embedding 服务与向量维度"],
  ["POST", "/api/v1/system/openalex/test", "检测 OpenAlex 认证检索与限额"],
  ["POST", "/api/v1/projects", "创建科研论文项目"],
  ["GET", "/api/v1/projects", "列出全部科研项目"],
  ["GET", "/api/v1/projects/{project_id}", "获取项目状态与元数据"],
  ["POST", "/api/v1/projects/{project_id}/topic-framing/runs", "运行 PACM-SW 选题拆解智能体"],
  ["GET", "/api/v1/projects/{project_id}/topic-framing/runs/latest", "读取最新选题产物与执行轨迹"],
  ["POST", "/api/v1/projects/{project_id}/topic-framing/confirm", "确认选题质量门并进入文献调研"],
  ["POST", "/api/v1/projects/{project_id}/literature-review/runs", "检索真实文献并生成证据综述"],
  ["GET", "/api/v1/projects/{project_id}/literature-review/runs/latest", "读取文献记录、综述与审计轨迹"],
  ["POST", "/api/v1/projects/{project_id}/literature-review/confirm", "确认文献质量门并进入方法设计"],
  ["POST", "/api/v1/projects/{project_id}/method-design/runs", "生成 PACM-SW 方法、公式与实验设计"],
  ["GET", "/api/v1/projects/{project_id}/method-design/runs/latest", "读取方法产物、证据继承与执行轨迹"],
  ["POST", "/api/v1/projects/{project_id}/method-design/confirm", "确认方法质量门并进入实验验证"],
  ["POST", "/api/v1/projects/{project_id}/experiments/runs", "生成预注册协议并运行检索 harness smoke test"],
  ["GET", "/api/v1/projects/{project_id}/experiments/runs/latest", "读取实验协议、预检、pilot 与阻断项"],
  ["POST", "/api/v1/projects/{project_id}/experiments/confirm", "正式结果审计通过后进入论文写作"],
  ["POST", "/api/v1/projects/{project_id}/experiments/retrieval-runs", "执行真实 B2/B3/PACM-SW 检索"],
  ["GET", "/api/v1/projects/{project_id}/experiments/retrieval-runs/latest", "读取真实检索运行与 JSONL manifest"],
  ["GET", "/api/v1/projects/{project_id}/experiments/retrieval-runs/{run_id}/log", "下载逐查询 JSONL 审计日志"],
  ["POST", "/api/v1/projects/{project_id}/experiments/qrels", "创建盲化人工 qrels 候选池"],
  ["PUT", "/api/v1/projects/{project_id}/experiments/qrels/{qrels_id}/judgments", "保存人工相关性标注"],
  ["POST", "/api/v1/projects/{project_id}/experiments/qrels/{qrels_id}/freeze", "完整性检查并冻结 qrels SHA"],
  ["POST", "/api/v1/projects/{project_id}/experiments/generation-runs", "执行 B0/B1 多任务多种子生成批量"],
  ["GET", "/api/v1/projects/{project_id}/experiments/generation-runs/{run_id}/log", "下载 B0/B1 逐智能体 JSONL"],
  ["POST", "/api/v1/projects/{project_id}/transitions", "推进至下一质量阶段"],
];

const state = { capabilities: null, environment: null, projects: [], selectedId: null, modelConnection: null, embeddingConnection: null, embeddingConnectionResult: null, openAlexConnection: null, openAlexConnectionResult: null, topicRuns: {}, topicLoading: false, literatureRuns: {}, literatureLoading: false, methodRuns: {}, methodLoading: false, experimentRuns: {}, experimentLoading: false, retrievalRuns: {}, retrievalLoading: false, qrelsSets: {}, qrelsLoading: false, qrelsActiveQuery: {}, generationRuns: {}, generationLoading: false };
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

async function request(path, options = {}) {
  const response = await fetch(path, { headers: { "Content-Type": "application/json", ...(options.headers || {}) }, ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    const message = typeof detail === "string" ? detail : detail?.message || detail?.[0]?.msg || `请求失败（${response.status}）`;
    throw new Error(message);
  }
  return data;
}

function toast(message, type = "success") {
  const item = document.createElement("div");
  item.className = `toast ${type}`;
  item.textContent = message;
  $("#toastStack").append(item);
  setTimeout(() => item.remove(), 3600);
}

function navigate(view) {
  $$(".view").forEach((node) => node.classList.toggle("active", node.id === `view-${view}`));
  $$(".nav-item").forEach((node) => node.classList.toggle("active", node.dataset.view === view));
  const titles = { dashboard: "科研工作台", projects: "论文项目", environment: "环境配置", api: "接口能力" };
  $("#pageTitle").textContent = titles[view];
  $(".sidebar").classList.remove("open");
  history.replaceState(null, "", `#${view}`);
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function renderWorkflow(root, currentStage = "intake") {
  const current = STAGES.findIndex(([key]) => key === currentStage);
  root.innerHTML = STAGES.map(([key, name, code], index) => {
    const status = index < current ? "done" : index === current ? "active" : "";
    const marker = index < current ? "✓" : String(index + 1).padStart(2, "0");
    return `<div class="stage ${status}"><div class="stage-dot">${marker}</div><b>${name}</b><small>${code}</small></div>`;
  }).join("");
}

function renderCapabilities() {
  const cap = state.capabilities;
  if (!cap) return;
  const ports = cap.jiuwenswarm.ports || {};
  const online = Object.values(ports).filter(Boolean).length;
  const allOnline = online === Object.keys(ports).length && online > 0;
  $("#metricApi").textContent = "运行正常";
  $("#metricSwarm").textContent = allOnline ? "全部在线" : `${online} 项在线`;
  $("#metricSwarmSub").textContent = `${online} / ${Object.keys(ports).length} 服务在线`;
  const environment = state.environment || {};
  $("#metricModel").textContent = cap.jiuwenswarm.model_configured ? (environment.model_name || "已配置") : "待配置";
  $("#metricModelSub").textContent = state.modelConnection === true
    ? `连接正常 · ${environment.model_provider || "兼容接口"}`
    : state.modelConnection === false
      ? "连接异常 · 请检查配置"
      : `${environment.model_provider || "OpenAI"} 兼容接口`;
  $("#liteMode").textContent = cap.jiuwenswarm.lite_mode ? "已启用" : "未启用";
  $("#sidebarStatus").textContent = allOnline ? "运行正常" : "部分服务离线";
  $("#sidebarPulse").classList.toggle("online", allOnline);
  $("#serviceList").innerHTML = Object.entries(ports).map(([port, ok]) => {
    const labels = { "5173": ["Jiuwen Web", "可视化控制台"], "18092": ["Agent Server", "智能体调度服务"], "19000": ["Gateway", "运行时网关"], "19001": ["Core Service", "核心能力服务"] };
    const [name, desc] = labels[port] || ["Runtime Service", "JiuwenSwarm 服务"];
    return `<div class="service-row"><span class="status-dot ${ok ? "on" : ""}"></span><div><strong>${name}</strong><small>${desc}</small></div><code>:${port}</code></div>`;
  }).join("");
  $("#capabilityJson").textContent = JSON.stringify(cap, null, 2);
  updateChecklist();
}

function renderProjects() {
  const projects = state.projects;
  $("#metricProjects").textContent = `${projects.length} 个`;
  $("#metricProjectSub").textContent = projects.length ? "科研工作流持续推进中" : "等待创建首个项目";
  $("#projectCountLabel").textContent = `共 ${projects.length} 个项目`;
  const list = $("#projectList");
  if (!projects.length) {
    list.innerHTML = `<div class="empty-state"><span>◇</span><h4>还没有论文项目</h4><p>创建第一个研究任务，开始搭建论文流程。</p></div>`;
    $("#projectDetail").innerHTML = `<div class="empty-detail"><span>↖</span><h3>选择一个项目</h3><p>这里会展示当前阶段、完整流程和下一步动作。</p></div>`;
    return;
  }
  if (!state.selectedId || !projects.some((p) => p.id === state.selectedId)) state.selectedId = projects[0].id;
  list.innerHTML = projects.map((project, index) => {
    const stage = STAGES.find(([key]) => key === project.stage)?.[1] || project.stage;
    return `<button class="project-card ${project.id === state.selectedId ? "active" : ""}" data-project="${project.id}"><span class="project-index">${String(index + 1).padStart(2, "0")}</span><div><h4>${escapeHtml(project.title)}</h4><p>${escapeHtml(project.research_direction)} · ${project.mode === "full" ? "全流程" : "半流程"}</p></div><span class="stage-tag">${stage}</span></button>`;
  }).join("");
  $$('[data-project]').forEach((node) => node.addEventListener("click", async () => { state.selectedId = node.dataset.project; renderProjects(); await Promise.all([loadTopicRun(node.dataset.project), loadLiteratureRun(node.dataset.project), loadMethodRun(node.dataset.project), loadExperimentRun(node.dataset.project), loadRetrievalRun(node.dataset.project), loadQrels(node.dataset.project), loadGenerationRun(node.dataset.project)]); }));
  renderProjectDetail(projects.find((p) => p.id === state.selectedId));
}

function renderProjectDetail(project) {
  const index = STAGES.findIndex(([key]) => key === project.stage);
  const current = STAGES[index];
  const updated = new Date(project.updated_at).toLocaleString("zh-CN", { month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  const topicRun = state.topicRuns[project.id];
  const literatureRun = state.literatureRuns[project.id];
  const methodRun = state.methodRuns[project.id];
  const experimentRun = state.experimentRuns[project.id];
  const retrievalRun = state.retrievalRuns[project.id];
  const qrels = state.qrelsSets[project.id];
  const generationRun = state.generationRuns[project.id];
  $("#projectDetail").innerHTML = `<div class="detail-head"><div><h3>${escapeHtml(project.title)}</h3><span class="stage-tag">${current?.[1] || project.stage}</span></div><div class="detail-meta"><span>${escapeHtml(project.research_direction)}</span><span>${project.mode === "full" ? "全流程模式" : "半流程模式"}</span><span>更新于 ${updated}</span></div></div><div class="detail-stage"><h4>项目质量门</h4><div class="workflow" id="detailWorkflow"></div></div>${topicWorkbench(project, topicRun)}${literatureWorkbench(project, topicRun, literatureRun)}${methodWorkbench(project, literatureRun, methodRun)}${experimentWorkbench(project, methodRun, experimentRun)}${retrievalWorkbench(project, experimentRun, retrievalRun)}${formalBenchmarkWorkbench(project, retrievalRun, qrels, generationRun)}`;
  renderWorkflow($("#detailWorkflow"), project.stage);
  $("#runTopicFraming")?.addEventListener("click", () => runTopicFraming(project));
  $("#confirmTopicFraming")?.addEventListener("click", () => confirmTopicFraming(project, topicRun));
  $("#runLiteratureReview")?.addEventListener("click", () => runLiteratureReview(project));
  $("#confirmLiteratureReview")?.addEventListener("click", () => confirmLiteratureReview(project, literatureRun));
  $("#runMethodDesign")?.addEventListener("click", () => runMethodDesign(project));
  $("#confirmMethodDesign")?.addEventListener("click", () => confirmMethodDesign(project, methodRun));
  $("#runExperiment")?.addEventListener("click", () => runExperiment(project));
  $("#runRealRetrieval")?.addEventListener("click", () => runRealRetrieval(project));
  $("#createQrels")?.addEventListener("click", () => createQrels(project));
  $("#saveQrelsPage")?.addEventListener("click", () => saveQrelsPage(project, qrels));
  $("#freezeQrels")?.addEventListener("click", () => freezeQrels(project, qrels));
  $("#runAblationBatch")?.addEventListener("click", () => runAblationBatch(project));
  $("#runGenerationSample")?.addEventListener("click", () => runGenerationBatch(project, false));
  $("#runGenerationBatch")?.addEventListener("click", () => runGenerationBatch(project, true));
  $("#qrelsQuerySelect")?.addEventListener("change", (event) => { state.qrelsActiveQuery[project.id] = event.target.value; renderProjectDetail(project); });
}

function topicWorkbench(project, run) {
  if (state.topicLoading) {
    return `<div class="research-workbench running"><div class="run-spinner"></div><div><span>PACM-SW AGENT RUNNING</span><h4>正在执行需求澄清与选题拆解</h4><p>JiuwenSwarm 正在汇集可追溯上下文、调用模型并校验结构化产物，请勿关闭页面。</p></div></div>`;
  }
  if (run === undefined) {
    return `<div class="research-workbench"><span>PACM-SW VERTICAL SLICE</span><h4>正在读取最新科研产物</h4></div>`;
  }
  if (!run || run.status === "failed") {
    const error = run?.error ? `<div class="run-error">上次运行失败：${escapeHtml(run.error)}</div>` : "";
    const legacy = project.stage === "delivered" ? "该项目的阶段来自旧版演示推进，本次运行会建立第一份真实科研产物。" : "本阶段不会直接推进状态，必须先生成并确认选题产物。";
    return `<div class="research-workbench start"><span>PACM-SW · TRACEABLE RESEARCH</span><h4>运行需求澄清与选题拆解智能体</h4><p>${legacy}</p>${error}<ul><li>汇集项目输入与 PACM-SW 核心上下文</li><li>生成研究问题、贡献假设、关键词与检索式</li><li>记录来源映射，标记待文献验证的结论</li></ul><button class="primary" id="runTopicFraming">${run ? "重新运行选题拆解" : "开始真实推理 →"}</button></div>`;
  }
  const result = run.result;
  if (run.confirmed_at) {
    const selected = result.candidate_titles[run.decision?.selected_candidate_index || 0];
    return `<div class="completed-slice"><span>✓</span><div><small>选题拆解 · 已通过</small><b>${escapeHtml(selected.title_cn)}</b><em>${escapeHtml(selected.title_en)}</em></div><code>${escapeHtml(run.prompt_version)}</code></div>`;
  }
  const candidates = result.candidate_titles.map((item, index) => `<label class="topic-candidate"><input type="radio" name="topic_candidate" value="${index}" ${index === (run.decision?.selected_candidate_index ?? 0) ? "checked" : ""} ${run.confirmed_at ? "disabled" : ""}><span><b>${escapeHtml(item.title_cn)}</b><em>${escapeHtml(item.title_en)}</em><small>${escapeHtml(item.focus)}</small></span></label>`).join("");
  const questions = result.research_questions.map((item, index) => `<li><i>RQ${index + 1}</i>${escapeHtml(item)}</li>`).join("");
  const contributions = result.proposed_contributions.map((item, index) => `<li><i>C${index + 1}</i>${escapeHtml(item)}</li>`).join("");
  const keywords = [...result.keywords_cn, ...result.keywords_en].map((item) => `<span>${escapeHtml(item)}</span>`).join("");
  const provenance = result.provenance_map.slice(0, 6).map((item) => `<div class="provenance-row"><div><b>${escapeHtml(item.statement)}</b><small>${escapeHtml(item.verification_status)}</small></div><code>${item.context_ids.map(escapeHtml).join(" · ")}</code></div>`).join("");
  const trace = run.execution_trace.map((item) => `<li class="${item.status}"><span>${item.status === "completed" ? "✓" : "!"}</span><div><b>${escapeHtml(item.step)}</b><small>${escapeHtml(item.detail)}</small></div></li>`).join("");
  const gate = run.confirmed_at
    ? `<div class="gate-confirmed"><span>✓</span><div><b>选题质量门已确认</b><small>项目已进入文献调研阶段，选题决定与审核意见已保存。</small></div></div>`
    : `<label class="review-note"><span>人工审核意见（可选）</span><textarea id="topicReviewNotes" maxlength="2000" placeholder="记录选择理由、需要保留的边界或下一阶段注意事项"></textarea></label><button class="primary full" id="confirmTopicFraming">接受所选方案并进入文献调研 →</button>`;
  return `<div class="research-workbench result"><div class="workbench-head"><div><span>PACM-SW TOPIC ARTIFACT</span><h4>选题拆解产物</h4></div><div class="run-meta"><b>${escapeHtml(run.model_name)}</b><small>${escapeHtml(run.prompt_version)}</small></div></div><div class="result-block"><h5>需求澄清</h5><p>${escapeHtml(result.requirements_summary)}</p><div class="boundary-note">证据边界：${escapeHtml(result.evidence_boundary.join("；") || "尚未进入文献验证")}</div></div><div class="result-block"><h5>候选研究题目</h5><div class="topic-candidates">${candidates}</div></div><div class="result-columns"><div class="result-block"><h5>研究问题</h5><ol class="research-list">${questions}</ol></div><div class="result-block"><h5>预期贡献（待验证）</h5><ol class="research-list">${contributions}</ol></div></div><div class="result-block"><h5>方法定位</h5><p>${escapeHtml(result.method_positioning)}</p><div class="keyword-list">${keywords}</div></div><details class="audit-details"><summary>查看来源映射与执行轨迹</summary><div class="audit-grid"><div><h5>来源映射</h5>${provenance}</div><div><h5>可审计执行轨迹</h5><ul class="trace-list">${trace}</ul></div></div></details><div class="gate-area">${gate}</div></div>`;
}

function literatureWorkbench(project, topicRun, run) {
  if (!topicRun?.confirmed_at) return `<div class="locked-slice"><span>02</span><div><b>文献调研</b><small>完成并确认选题拆解后解锁</small></div></div>`;
  if (state.literatureLoading) return `<div class="research-workbench running literature-running"><div class="run-spinner"></div><div><span>LITERATURE AGENT RUNNING</span><h4>正在检索并分析真实学术记录</h4><p>依次执行 OpenAlex/Crossref 检索、DOI/标题去重、元数据保存和受 PAPER id 约束的证据综述。</p></div></div>`;
  if (run === undefined) return `<div class="research-workbench"><span>LITERATURE REVIEW</span><h4>正在读取最新文献调研产物</h4></div>`;
  if (!run || run.status === "failed") {
    const error = run?.error ? `<div class="run-error">上次运行失败：${escapeHtml(run.error)}</div>` : "";
    return `<div class="research-workbench start literature-start"><span>PACM-SW · EVIDENCE RETRIEVAL</span><h4>运行可追溯文献调研</h4><p>使用已确认选题生成的检索式，从公开学术元数据源获取真实题录，再生成受证据约束的相关工作分析。</p>${error}<ul><li>OpenAlex + Crossref 双源检索（OpenAlex ${state.environment?.has_openalex_api_key ? "认证密钥已启用" : "当前为匿名访问"}）</li><li>按 DOI 和规范化标题去重</li><li>研究空白与结论必须引用 PAPER id</li><li>摘要缺失与检索覆盖不足会明确标记</li></ul><button class="primary" id="runLiteratureReview">${run ? "重新运行文献调研" : "开始真实文献调研 →"}</button></div>`;
  }
  if (run.confirmed_at) {
    return `<div class="completed-slice literature-complete"><span>✓</span><div><small>文献调研 · 已通过</small><b>${run.papers.length} 篇去重学术记录已形成证据综述</b><em>项目已进入方法设计阶段</em></div><code>${escapeHtml(run.prompt_version)}</code></div>`;
  }
  const result = run.result;
  const doiCount = run.papers.filter((paper) => paper.doi).length;
  const abstractCount = run.papers.filter((paper) => paper.abstract).length;
  const sourceCount = new Set(run.papers.flatMap((paper) => paper.source.split("+"))).size;
  const themes = result.themes.map((theme) => `<div class="theme-card"><b>${escapeHtml(theme.name)}</b><p>${escapeHtml(theme.description)}</p><small>${theme.paper_ids.map(escapeHtml).join(" · ") || "证据不足"}</small></div>`).join("");
  const gaps = result.validated_gap_hypotheses.map((item) => `<div class="evidence-claim"><div><span>${escapeHtml(item.verification_status)}</span><em>${escapeHtml(item.confidence)}</em></div><p>${escapeHtml(item.claim)}</p><small>${item.paper_ids.map(escapeHtml).join(" · ") || "暂无有效证据"}</small></div>`).join("");
  const papers = run.papers.slice(0, 20).map((paper) => `<article class="paper-record"><div class="paper-id">${escapeHtml(paper.id)}</div><div><h6>${escapeHtml(paper.title)}</h6><p>${escapeHtml(paper.authors.slice(0, 4).join(", ") || "作者信息缺失")} · ${paper.year || "年份缺失"} · ${escapeHtml(paper.venue || paper.source)}</p><small>${paper.doi ? `DOI ${escapeHtml(paper.doi)}` : "无 DOI"} · 引用 ${paper.cited_by_count} · ${escapeHtml(paper.source)}</small></div>${safeUrl(paper.url) ? `<a href="${escapeHtml(paper.url)}" target="_blank" rel="noreferrer">↗</a>` : ""}</article>`).join("");
  const traces = run.execution_trace.map((item) => `<li class="${item.status}"><span>${item.status === "completed" ? "✓" : "!"}</span><div><b>${escapeHtml(item.step)}</b><small>${escapeHtml(item.detail)}</small></div></li>`).join("");
  const limitations = result.search_limitations.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  return `<div class="literature-workbench"><div class="literature-head"><div><span>PACM-SW LITERATURE ARTIFACT</span><h4>可追溯文献调研产物</h4><small class="source-auth-note">OpenAlex · ${state.environment?.has_openalex_api_key ? "认证检索已配置" : "匿名检索"} / Crossref · 公共元数据</small></div><div><b>${escapeHtml(run.model_name)}</b><small>${escapeHtml(run.prompt_version)}</small></div></div><div class="literature-metrics"><div><strong>${run.papers.length}</strong><span>去重记录</span></div><div><strong>${doiCount}</strong><span>包含 DOI</span></div><div><strong>${abstractCount}</strong><span>包含摘要</span></div><div><strong>${sourceCount}</strong><span>元数据源</span></div></div><section class="literature-section"><h5>综述摘要</h5><p>${escapeHtml(result.executive_summary)}</p><div class="query-chips">${run.queries.map((query) => `<span>${escapeHtml(query)}</span>`).join("")}</div></section><section class="literature-section"><h5>相关工作主题</h5><div class="theme-grid">${themes}</div></section><section class="literature-section"><h5>研究空白验证</h5><div class="evidence-grid">${gaps || "<p>本轮没有形成可验证的研究空白。</p>"}</div></section><details class="paper-browser" open><summary>真实文献记录 <span>显示前 ${Math.min(run.papers.length, 20)} / ${run.papers.length} 篇</span></summary><div class="paper-list">${papers}</div></details><section class="literature-section related-draft"><h5>相关工作草稿</h5><p>${escapeHtml(result.related_work_draft)}</p></section><details class="audit-details"><summary>查看检索限制与执行轨迹</summary><div class="audit-grid"><div><h5>检索限制</h5><ul class="limitation-list">${limitations}</ul></div><div><h5>可审计执行轨迹</h5><ul class="trace-list">${traces}</ul></div></div></details><div class="gate-area"><label class="review-note"><span>文献质量门审核意见（可选）</span><textarea id="literatureReviewNotes" maxlength="3000" placeholder="记录需要补查的文献、范围边界或方法设计阶段必须遵守的证据约束"></textarea></label><button class="primary full" id="confirmLiteratureReview">确认文献质量门并进入方法设计 →</button></div></div>`;
}

function methodWorkbench(project, literatureRun, run) {
  if (!literatureRun?.confirmed_at) return `<div class="locked-slice"><span>03</span><div><b>方法设计</b><small>完成并确认文献调研后解锁</small></div></div>`;
  if (state.methodLoading) return `<div class="research-workbench running method-running"><div class="run-spinner"></div><div><span>METHOD AGENT RUNNING</span><h4>正在形成 PACM-SW 可实现方法</h4><p>继承已确认文献证据，生成架构组件、分层记忆、溯源契约、检索公式和可证伪实验设计。</p></div></div>`;
  if (run === undefined) return `<div class="research-workbench"><span>PACM-SW METHOD</span><h4>正在读取最新方法设计产物</h4></div>`;
  if (!run || run.status === "failed") {
    const error = run?.error ? `<div class="run-error">上次运行失败：${escapeHtml(run.error)}</div>` : "";
    return `<div class="research-workbench start method-start"><span>PACM-SW · METHOD DESIGN</span><h4>生成论文方法设计</h4><p>把已确认的文献缺口转化为可实现、可证伪、可消融的方法，而不是直接假定方法有效。</p>${error}<ul><li>冻结并继承 ${literatureRun.papers.length} 个 PAPER 证据编号</li><li>定义分层记忆、provenance contract 与组合检索目标</li><li>设计 B0–B3 基线、公平控制、主指标和证伪条件</li><li>H3 继续保持证据不足，不包装为既定创新</li></ul><button class="primary" id="runMethodDesign">${run ? "重新生成方法设计" : "开始 METHOD 推理 →"}</button></div>`;
  }
  if (run.confirmed_at) {
    return `<div class="completed-slice method-complete"><span>✓</span><div><small>方法设计 · 已通过</small><b>${escapeHtml(run.result.method_name)} 方法与实验契约已冻结</b><em>项目已进入实验验证阶段</em></div><code>${escapeHtml(run.prompt_version)}</code></div>`;
  }
  const result = run.result;
  const components = result.components.map((item) => `<article class="method-component"><div><span>${escapeHtml(item.id)}</span><b>${escapeHtml(item.name)}</b></div><p>${escapeHtml(item.purpose)}</p><ol>${item.algorithm_steps.map((step) => `<li>${escapeHtml(step)}</li>`).join("")}</ol><small>${item.evidence_ids.map(escapeHtml).join(" · ") || "工程约束 / 无直接论文证据"}</small></article>`).join("");
  const layers = result.memory_layers.map((item, index) => `<article class="memory-layer"><span>L${index + 1}</span><div><b>${escapeHtml(item.name)}</b><p>${escapeHtml(item.content_types.join(" · "))}</p><small>写入：${escapeHtml(item.write_policy)}<br>检索：${escapeHtml(item.retrieval_role)}</small></div><em>${item.provenance_required ? "PROVENANCE REQUIRED" : "OPTIONAL"}</em></article>`).join("");
  const scoreTerms = result.retrieval_objective.terms.map((term) => `<div class="score-term"><code>${escapeHtml(term.symbol)}</code><div><b>${escapeHtml(term.name)}</b><p>${escapeHtml(term.definition)}</p><small>${escapeHtml(term.optimization_note)}</small></div></div>`).join("");
  const experiments = result.experiment_designs.map((item) => `<article class="experiment-card"><div><span>${escapeHtml(item.id)}</span><b>${escapeHtml(item.research_question)}</b></div><p>${escapeHtml(item.falsifiable_hypothesis)}</p><small><strong>主指标</strong> ${escapeHtml(item.primary_metrics.join(" · "))}</small><small><strong>证伪</strong> ${escapeHtml(item.falsification_condition)}</small><div>${item.baselines.map((base) => `<i>${escapeHtml(base)}</i>`).join("")}</div></article>`).join("");
  const evidenceLinks = result.evidence_design_links.map((item) => `<div class="design-evidence"><div><b>${escapeHtml(item.design_claim)}</b><span>${escapeHtml(item.confidence)}</span></div><p>${escapeHtml(item.rationale)}</p><code>${item.paper_ids.map(escapeHtml).join(" · ") || "暂无直接证据"}</code></div>`).join("");
  const traces = run.execution_trace.map((item) => `<li class="${item.status}"><span>${item.status === "completed" ? "✓" : "!"}</span><div><b>${escapeHtml(item.step)}</b><small>${escapeHtml(item.detail)}</small></div></li>`).join("");
  return `<div class="method-workbench"><header class="method-head"><div><span>PACM-SW METHOD ARTIFACT</span><h4>${escapeHtml(result.method_name)}</h4><small>Provenance-Aware Context Memory for Scientific Writing</small></div><div><b>${escapeHtml(run.model_name)}</b><small>${escapeHtml(run.prompt_version)}</small></div></header><div class="method-metrics"><div><strong>${result.components.length}</strong><span>架构组件</span></div><div><strong>${result.memory_layers.length}</strong><span>记忆层级</span></div><div><strong>${result.experiment_designs.length}</strong><span>可证伪实验</span></div><div><strong>${result.ablations.length}</strong><span>单变量消融</span></div></div><section class="method-section method-overview"><h5>方法摘要</h5><p>${escapeHtml(result.method_summary)}</p><div class="method-boundary"><b>问题定义</b>${escapeHtml(result.problem_formulation)}</div><div class="method-boundary caution"><b>新颖性边界</b>${escapeHtml(result.novelty_boundary)}</div></section><section class="method-section"><h5>系统组件与算法步骤</h5><div class="method-component-grid">${components}</div></section><section class="method-section"><h5>分层记忆结构</h5><div class="memory-stack">${layers}</div></section><section class="method-section retrieval-design"><h5>组合检索目标</h5><pre>${escapeHtml(result.retrieval_objective.formula)}</pre><div class="score-grid">${scoreTerms}</div><p><b>候选召回：</b>${escapeHtml(result.retrieval_objective.candidate_generation.join(" → "))}</p><p><b>预算策略：</b>${escapeHtml(result.retrieval_objective.budget_policy)}</p><p><b>同分策略：</b>${escapeHtml(result.retrieval_objective.tie_break_policy)}</p></section><section class="method-section provenance-contract"><h5>Provenance Contract</h5><div class="contract-grid"><div><b>实体</b><p>${escapeHtml(result.provenance_contract.entities.join(" · "))}</p></div><div><b>关系</b><p>${escapeHtml(result.provenance_contract.relations.join(" · "))}</p></div><div><b>必填字段</b><p>${escapeHtml(result.provenance_contract.required_fields.join(" · "))}</p></div><div><b>不变量</b><p>${escapeHtml(result.provenance_contract.invariants.join("；"))}</p></div></div></section><section class="method-section"><h5>实验与证伪矩阵</h5><div class="experiment-grid">${experiments}</div></section><details class="method-details" open><summary>证据—设计映射 <span>${run.inherited_paper_ids.length} 个继承 PAPER id</span></summary><div class="design-evidence-list">${evidenceLinks}</div></details><details class="method-details"><summary>消融、风险与执行轨迹</summary><div class="method-audit"><div><h5>单变量消融</h5><ol>${result.ablations.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ol><h5>风险与限制</h5><ul>${result.risks_and_limitations.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div><div><h5>可审计执行轨迹</h5><ul class="trace-list">${traces}</ul><h5>实现契约</h5><ul>${result.implementation_contracts.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div></div></details><div class="gate-area"><label class="review-note"><span>方法质量门审核意见（可选）</span><textarea id="methodReviewNotes" maxlength="3000" placeholder="记录公式、数据结构、基线公平性或实验阶段必须遵守的约束"></textarea></label><button class="primary full" id="confirmMethodDesign">确认方法质量门并进入实验验证 →</button></div></div>`;
}

function experimentWorkbench(project, methodRun, run) {
  if (!methodRun?.confirmed_at) return `<div class="locked-slice"><span>04</span><div><b>实验验证</b><small>完成并确认方法设计后解锁</small></div></div>`;
  if (state.experimentLoading) return `<div class="research-workbench running experiment-running"><div class="run-spinner"></div><div><span>EXPERIMENT AGENT RUNNING</span><h4>正在生成预注册协议并运行 smoke test</h4><p>冻结方法与文献快照，生成 B0–B3/Ours 配置，然后执行确定性预检和检索 harness。</p></div></div>`;
  if (run === undefined) return `<div class="research-workbench"><span>PACM-SW EXPERIMENT</span><h4>正在读取最新实验产物</h4></div>`;
  if (!run || run.status === "failed") {
    const error = run?.error ? `<div class="run-error">上次运行失败：${escapeHtml(run.error)}</div>` : "";
    return `<div class="research-workbench start experiment-start"><span>PACM-SW · EXPERIMENT PROTOCOL</span><h4>生成实验协议并运行 harness smoke test</h4><p>首轮验证实验数据链路、配置公平性、指标契约与结果阻断，不会生成或猜测 PACM-SW 的正式效果结论。</p>${error}<ul><li>固定 B0、B1、B2、B3 与 Ours 五个系统</li><li>冻结任务、种子、重复次数、指标与资源预算</li><li>运行 DOI、PAPER 白名单与检索 proxy 技术预检</li><li>正式基线和消融未完成前禁止进入论文写作</li></ul><button class="primary" id="runExperiment">${run ? "重新生成实验协议" : "开始 EXPERIMENT →"}</button></div>`;
  }
  const result = run.result;
  const protocol = result.protocol;
  const passCount = result.preflight_checks.filter((item) => item.status === "pass").length;
  const blockCount = result.preflight_checks.filter((item) => item.status === "block").length;
  const systems = protocol.systems.map((item) => `<article class="system-config ${item.id === "Ours" ? "ours" : ""}"><div><span>${escapeHtml(item.id)}</span><b>${escapeHtml(item.name)}</b></div><p>${escapeHtml(item.description)}</p><small>Memory · ${escapeHtml(item.memory_strategy)}</small><small>Retrieval · ${escapeHtml(item.retrieval_strategy)}</small><div class="system-flags"><i class="${item.provenance_enforced ? "on" : ""}">PROV</i><i class="${item.role_aware ? "on" : ""}">ROLE</i><i class="${item.graph_enabled ? "on" : ""}">GRAPH</i><i class="${item.conflict_detection ? "on" : ""}">CONFLICT</i></div></article>`).join("");
  const tasks = protocol.tasks.map((item) => `<article class="protocol-task"><div><span>${escapeHtml(item.id)}</span><b>${escapeHtml(item.name)}</b><em>${escapeHtml(item.task_type)}</em></div><p>${escapeHtml(item.input_contract)}</p><small>产物：${escapeHtml(item.expected_artifact)}</small><code>${item.required_evidence_ids.map(escapeHtml).join(" · ") || "运行时分配证据"}</code></article>`).join("");
  const checks = result.preflight_checks.map((item) => `<div class="preflight-check ${escapeHtml(item.status)}"><span>${item.status === "pass" ? "✓" : item.status === "warn" ? "!" : "×"}</span><div><b>${escapeHtml(item.id)} · ${escapeHtml(item.name)}</b><p>${escapeHtml(item.detail)}</p></div><em>${escapeHtml(item.status)}</em></div>`).join("");
  const pilots = result.pilot_results.map((item) => `<article class="pilot-card"><div><span>${escapeHtml(item.system_id)}</span><b>${escapeHtml(item.system_name)}</b></div><small>${escapeHtml(item.implementation_level)}</small><div class="pilot-numbers"><div><strong>${item.mean_recall_at_5.toFixed(3)}</strong><span>Recall@5</span></div><div><strong>${item.mean_mrr_at_5.toFixed(3)}</strong><span>MRR@5</span></div><div><strong>${item.mean_provenance_coverage_at_5.toFixed(3)}</strong><span>Prov@5</span></div><div><strong>${item.mean_token_proxy.toFixed(0)}</strong><span>Token proxy</span></div></div></article>`).join("");
  const metrics = protocol.metrics.map((item) => `<div class="metric-contract"><div><b>${escapeHtml(item.name)}</b><span>${item.deterministic ? "DETERMINISTIC" : "REVIEW REQUIRED"}</span></div><p>${escapeHtml(item.formula_or_procedure)}</p><small>${escapeHtml(item.direction)} · ${escapeHtml(item.required_inputs.join(" · "))}</small></div>`).join("");
  const traces = run.execution_trace.map((item) => `<li class="${item.status}"><span>${item.status === "completed" ? "✓" : "!"}</span><div><b>${escapeHtml(item.step)}</b><small>${escapeHtml(item.detail)}</small></div></li>`).join("");
  const blockers = result.blockers.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const limitations = result.pilot_limitations.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  return `<div class="experiment-workbench"><header class="experiment-head"><div><span>PACM-SW EXPERIMENT ARTIFACT</span><h4>实验协议与 Harness Pilot</h4><small>${escapeHtml(result.validation_level)}</small></div><div><b>${result.efficacy_claim_allowed ? "RESULTS AUDITED" : "NO EFFICACY CLAIM"}</b><small>${escapeHtml(result.benchmark_status)}</small></div></header><div class="experiment-metrics"><div><strong>${protocol.systems.length}</strong><span>系统配置</span></div><div><strong>${protocol.tasks.length}</strong><span>实验任务</span></div><div><strong>${passCount}</strong><span>预检通过</span></div><div class="blocked"><strong>${blockCount}</strong><span>阻断项</span></div></div><section class="experiment-section"><h5>预注册目标与范围</h5><p>${escapeHtml(protocol.objective)}</p><div class="experiment-scope">${escapeHtml(protocol.validation_scope)}</div><div class="seed-strip"><span>SEEDS ${protocol.seeds.join(" · ")}</span><span>REPETITIONS ${protocol.repetitions}</span><span>BUDGET ${protocol.systems[0]?.context_budget_tokens || "-"} TOKENS</span></div></section><section class="experiment-section"><h5>B0–B3 / Ours 冻结配置</h5><div class="system-grid">${systems}</div></section><section class="experiment-section"><h5>任务注册表</h5><div class="protocol-task-list">${tasks}</div></section><section class="experiment-section"><h5>指标契约</h5><div class="metric-contract-grid">${metrics}</div></section><section class="experiment-section"><h5>确定性预检</h5><div class="preflight-list">${checks}</div></section><section class="experiment-section pilot-section"><div class="section-line"><h5>检索 Harness Smoke Test</h5><span>仅验证执行链路，不是论文结果</span></div><div class="pilot-grid">${pilots}</div><div class="experiment-warning"><b>解释边界</b><ul>${limitations}</ul></div></section><details class="experiment-details"><summary>执行顺序、资源、统计与复现</summary><div class="experiment-audit"><div><h5>执行顺序</h5><ol>${protocol.execution_order.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ol><h5>资源预算</h5><ul>${protocol.resource_budget.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul><h5>停止条件</h5><ul>${protocol.stop_conditions.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div><div><h5>统计方案</h5><ul>${protocol.statistics_plan.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul><h5>复现清单</h5><ul>${protocol.reproducibility_manifest.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul><h5>执行轨迹</h5><ul class="trace-list">${traces}</ul></div></div></details><div class="experiment-gate blocked"><span>QUALITY GATE BLOCKED</span><h5>正式效果实验尚未完成</h5><ul>${blockers}</ul><p>下方独立运行真实检索执行器；完成后仍需 B0/B1、独立 qrels、六组消融和统计审计，才能进入论文写作。</p><button class="primary full" disabled>暂不能进入论文写作</button></div></div>`;
}

function retrievalWorkbench(project, experimentRun, run) {
  if (!experimentRun?.result) return `<div class="locked-slice"><span>05A</span><div><b>真实检索执行器</b><small>生成实验协议后解锁</small></div></div>`;
  if (state.retrievalLoading) return `<div class="research-workbench running retrieval-running"><div class="run-spinner"></div><div><span>REAL RETRIEVAL RUNNING</span><h4>正在执行 B2 / B3 / PACM-SW</h4><p>调用外部 Embedding，构建四层记忆，逐查询记录候选分数并封存 JSONL 与 SHA-256。</p></div></div>`;
  const embeddingReady = Boolean(state.environment?.embed_api_base && state.environment?.embed_model && state.environment?.has_embed_api_key);
  if (run === undefined) return `<div class="research-workbench"><span>REAL RETRIEVAL</span><h4>正在读取真实检索运行</h4></div>`;
  if (!run || run.status === "failed") {
    const error = run?.error ? `<div class="run-error">上次运行失败：${escapeHtml(run.error)}</div>` : "";
    return `<div class="retrieval-workbench retrieval-start"><header><div><span>PACM-SW · REAL RETRIEVAL</span><h4>执行真实 B2 / B3 / PACM-SW 检索</h4></div><em class="${embeddingReady ? "ready" : "blocked"}">${embeddingReady ? "EMBEDDING READY" : "EMBEDDING NOT READY"}</em></header><p>该运行不会再次生成实验协议；它固定当前 METHOD、文献和协议版本，调用真实 Embedding API，并为每个系统和查询保存完整候选评分。</p>${error}<div class="retrieval-config"><label><span>检索角色</span><select id="retrievalRole"><option value="researcher">Researcher</option><option value="planner">Planner</option><option value="writer">Writer</option><option value="reviewer">Reviewer</option></select></label><label><span>Top K</span><input id="retrievalTopK" type="number" min="1" max="20" value="5"></label><label><span>上下文预算</span><input id="retrievalBudget" type="number" min="256" max="50000" value="6000"></label></div><ul><li>B2：真实 dense cosine 检索</li><li>B3：BM25 与 dense rank 的 RRF 融合</li><li>PACM-SW：四层记忆、provenance、角色、图连接、冲突、冗余与预算评分</li><li>逐查询 JSONL + SHA-256 完整性封存</li></ul><button class="primary" id="runRealRetrieval" ${embeddingReady ? "" : "disabled"}>${run ? "重新执行真实检索" : "开始真实检索 →"}</button>${embeddingReady ? "" : `<small>请先在环境配置中完成并检测 Embedding API。</small>`}</div>`;
  }
  const result = run.result;
  const systems = result.systems.map((item) => `<article class="real-system-card ${item.system_id === "Ours" ? "ours" : ""}"><div><span>${escapeHtml(item.system_id)}</span><b>${escapeHtml(item.system_name)}</b></div><small>${escapeHtml(item.implementation_level)}</small><div class="real-system-metrics"><div><strong>${item.mean_recall_at_k.toFixed(3)}</strong><span>Recall@K</span></div><div><strong>${item.mean_mrr_at_k.toFixed(3)}</strong><span>MRR@K</span></div><div><strong>${item.mean_provenance_coverage_at_k.toFixed(3)}</strong><span>Prov@K</span></div><div><strong>${item.mean_context_tokens.toFixed(0)}</strong><span>Tokens</span></div><div><strong>${item.mean_latency_ms.toFixed(1)}</strong><span>ms/query</span></div></div></article>`).join("");
  const checks = result.engine_checks.map((item) => `<div class="retrieval-check ${escapeHtml(item.status)}"><span>${item.status === "pass" ? "✓" : "×"}</span><div><b>${escapeHtml(item.id)} · ${escapeHtml(item.name)}</b><small>${escapeHtml(item.detail)}</small></div><em>${escapeHtml(item.status)}</em></div>`).join("");
  const limitations = result.limitations.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const manifest = result.log_manifest;
  const logUrl = `/api/v1/projects/${encodeURIComponent(project.id)}/experiments/retrieval-runs/${encodeURIComponent(run.id)}/log`;
  return `<div class="retrieval-workbench retrieval-result"><header><div><span>REAL RETRIEVAL ARTIFACT</span><h4>B2 / B3 / PACM-SW 检索执行结果</h4><small>${escapeHtml(result.validation_level)}</small></div><div class="retrieval-status"><b>ENGINEERING VALIDATED</b><small>${escapeHtml(result.benchmark_status)}</small></div></header><div class="retrieval-summary"><div><strong>${result.systems.length}</strong><span>真实执行器</span></div><div><strong>${result.systems.reduce((sum, item) => sum + item.query_results.length, 0)}</strong><span>逐查询运行</span></div><div><strong>${manifest.embedding_dimension}</strong><span>向量维度</span></div><div><strong>${manifest.record_count}</strong><span>JSONL 记录</span></div></div><section><div class="section-line"><h5>真实执行器对比</h5><span>工程 qrels，不是论文结论</span></div><div class="real-system-grid">${systems}</div></section><section><h5>执行器质量检查</h5><div class="retrieval-checks">${checks}</div></section><section class="jsonl-manifest"><div><span>IMMUTABLE RUN LOG</span><h5>逐运行 JSONL Manifest</h5><code>${escapeHtml(manifest.relative_path)}</code><small>SHA-256 · ${escapeHtml(manifest.sha256)}</small><small>${escapeHtml(manifest.embedding_model)} · ${manifest.embedding_dimension} dims · corpus ${manifest.corpus_size}</small></div><a class="primary" href="${logUrl}" download>下载 JSONL</a></section><details class="experiment-details"><summary>解释边界与执行轨迹</summary><div class="experiment-audit"><div><h5>限制</h5><ul>${limitations}</ul></div><div><h5>执行轨迹</h5><ul class="trace-list">${run.execution_trace.map((item) => `<li class="${escapeHtml(item.status)}"><span>${item.status === "completed" ? "✓" : "!"}</span><div><b>${escapeHtml(item.step)}</b><small>${escapeHtml(item.detail)}</small></div></li>`).join("")}</ul></div></div></details><div class="experiment-gate blocked"><span>QUALITY GATE STILL BLOCKED</span><h5>真实检索层已完成，正式论文效果实验仍未完成</h5><p>${escapeHtml(result.blockers.join("；"))}</p><button class="primary full" id="runRealRetrieval">使用相同冻结输入重新运行</button></div></div>`;
}

function formalBenchmarkWorkbench(project, retrievalRun, qrels, generationRun) {
  if (!retrievalRun?.result) return `<div class="locked-slice"><span>05B</span><div><b>Gold Qrels 与批量基线</b><small>完成真实检索后解锁</small></div></div>`;
  if (state.qrelsLoading || state.generationLoading) return `<div class="research-workbench running"><div class="run-spinner"></div><div><span>FORMAL BENCHMARK WORKING</span><h4>${state.qrelsLoading ? "正在保存人工标注" : "正在执行 B0/B1 生成批量"}</h4><p>运行记录会逐步写入 JSONL；失败单元不会被删除或替换。</p></div></div>`;
  let qrelsSection = "";
  if (qrels === undefined) {
    qrelsSection = `<section><h5>正在读取 qrels 状态…</h5></section>`;
  } else if (!qrels) {
    qrelsSection = `<section class="qrels-create"><div class="section-line"><h5>01 · 创建盲化人工 Qrels</h5><span>禁止模型自动标注</span></div><p>系统会合并各检索器候选并打乱顺序，页面不显示候选来自哪个系统。相关性等级：0 不相关、1 弱相关、2 相关、3 高度相关。</p><div class="qrels-create-form"><label><span>人工标注者 ID</span><input id="qrelsAssessor" placeholder="例如 reviewer-a"></label><label><span>每系统 Pool Depth</span><input id="qrelsPoolDepth" type="number" min="5" max="30" value="10"></label><button class="primary" id="createQrels">生成盲化候选池</button></div></section>`;
  } else if (qrels.status === "draft") {
    const queries = [...new Set(qrels.items.map((item) => item.query))];
    const active = state.qrelsActiveQuery[project.id] && queries.includes(state.qrelsActiveQuery[project.id]) ? state.qrelsActiveQuery[project.id] : queries[0];
    state.qrelsActiveQuery[project.id] = active;
    const queryItems = qrels.items.filter((item) => item.query === active);
    const cards = queryItems.map((item, index) => `<article class="qrel-item" data-query="${escapeHtml(item.query)}" data-paper="${escapeHtml(item.paper_id)}"><div><span>${escapeHtml(item.paper_id)}</span><b>${escapeHtml(item.title)}</b><em>${item.year || "—"}</em></div><p>${escapeHtml(item.abstract || "摘要缺失；请根据题名谨慎判断")}</p><small>${item.doi ? `DOI ${escapeHtml(item.doi)}` : "无 DOI"}</small><fieldset><legend>人工相关性</legend>${[0,1,2,3].map((grade) => `<label><input type="radio" name="qrel_${index}" value="${grade}" ${item.judgment?.relevance === grade ? "checked" : ""}><span>${grade}</span></label>`).join("")}</fieldset><input class="qrel-rationale" maxlength="1000" placeholder="判断依据（建议填写）" value="${escapeHtml(item.judgment?.rationale || "")}"></article>`).join("");
    const complete = qrels.judgment_count === qrels.items.length;
    qrelsSection = `<section class="qrels-annotator"><div class="section-line"><h5>01 · 盲化人工 Qrels 标注</h5><span>${qrels.judgment_count} / ${qrels.items.length} 已标注</span></div><div class="qrels-progress"><i style="width:${Math.round(qrels.judgment_count / qrels.items.length * 100)}%"></i></div><div class="qrels-toolbar"><select id="qrelsQuerySelect">${queries.map((query, index) => `<option value="${escapeHtml(query)}" ${query === active ? "selected" : ""}>Q${index + 1} · ${escapeHtml(query)}</option>`).join("")}</select><span>当前 ${queryItems.length} 个盲化候选</span></div><div class="qrels-items">${cards}</div><div class="qrels-actions"><button class="secondary" id="saveQrelsPage">保存当前查询标注</button><button class="primary" id="freezeQrels" ${complete ? "" : "disabled"}>完整检查并冻结 Qrels</button></div><small>${escapeHtml(qrels.instructions)}</small></section>`;
  } else {
    qrelsSection = `<section class="qrels-frozen"><div><span>GOLD QRELS FROZEN</span><h5>独立人工相关性集合已冻结</h5><p>${qrels.query_count} 条查询 · ${qrels.judgment_count} 个人工判断 · assessor ${escapeHtml(qrels.assessor_id)}</p><code>SHA-256 ${escapeHtml(qrels.frozen_sha256)}</code></div><b>✓</b></section>`;
  }
  const frozen = qrels?.status === "frozen";
  const ablationReady = retrievalRun.request?.evaluation_mode === "formal" && retrievalRun.request?.include_ablations && (retrievalRun.request?.seeds?.length || 0) >= 3;
  const retrievalBatch = `<section class="formal-run-control"><div><span>02 · RETRIEVAL MATRIX</span><h5>R1–R6 × Seeds 13/37/73</h5><p>B2、B3、Ours 和六组单变量消融，共 9 配置 × 查询 × 3 seeds。检索是确定性的，seed 只控制同分排序。</p></div><div><em class="${ablationReady ? "ready" : ""}">${ablationReady ? "BATCH COMPLETE" : frozen ? "READY" : "WAITING QRELS"}</em><button class="primary" id="runAblationBatch" ${frozen ? "" : "disabled"}>运行正式检索矩阵</button></div></section>`;
  let generationSection = `<section class="generation-control"><div class="section-line"><h5>03 · B0/B1 生成基线</h5><span>第三方模型调用</span></div><p>B0 每任务每 seed 调用 1 次；B1 Planner/Writer/Reviewer 每任务每 seed 调用 3 次。完整 4 任务 × 3 seeds 共 48 次模型调用。</p><div class="generation-actions"><button class="secondary" id="runGenerationSample">工程抽样：1 任务 × 1 seed</button><button class="primary" id="runGenerationBatch" ${frozen ? "" : "disabled"}>正式批量：4 任务 × 3 seeds</button></div></section>`;
  if (generationRun?.result) {
    const genCards = generationRun.result.systems.map((item) => `<article><div><span>${escapeHtml(item.system_id)}</span><b>${escapeHtml(item.system_name)}</b></div><strong>${item.completed_cells}/${item.cells}</strong><small>完成单元</small><p>Valid refs ${item.mean_valid_citation_rate.toFixed(3)} · Fabricated ${item.mean_fabricated_reference_rate.toFixed(3)} · Required evidence ${item.mean_required_evidence_coverage.toFixed(3)}</p></article>`).join("");
    const failedCells = generationRun.result.cells.filter((item) => item.status === "failed");
    const failurePanel = failedCells.length ? `<details class="generation-failures" open><summary>${failedCells.length} 个实验单元失败 · 已原样写入 JSONL</summary>${failedCells.map((item) => `<div><b>${escapeHtml(item.system_id)} · ${escapeHtml(item.task_id)} · seed ${item.seed}</b><span>实际调用 ${item.model_calls} 次</span><p>${escapeHtml(item.error || "未返回错误详情")}</p></div>`).join("")}</details>` : `<div class="generation-success">✓ 当前批次所有生成单元均已完成</div>`;
    const logUrl = `/api/v1/projects/${encodeURIComponent(project.id)}/experiments/generation-runs/${encodeURIComponent(generationRun.id)}/log`;
    generationSection += `<section class="generation-result"><div class="generation-run-state ${failedCells.length ? "failed" : "completed"}"><b>${escapeHtml(generationRun.result.benchmark_status)}</b><span>${generationRun.request?.mode === "formal" ? "FORMAL" : "ENGINEERING"} · ${escapeHtml(generationRun.model_name || "model unknown")}</span></div><div class="generation-cards">${genCards}</div>${failurePanel}<div class="generation-manifest"><code>${escapeHtml(generationRun.result.log_manifest.sha256)}</code><span>${generationRun.result.log_manifest.record_count} JSONL records · provider seed enforced: ${generationRun.result.provider_seed_enforced ? "yes" : "no"}</span><a href="${logUrl}" download>下载生成 JSONL</a></div></section>`;
  }
  return `<div class="formal-benchmark-workbench"><header><div><span>PACM-SW FORMAL BENCHMARK PREPARATION</span><h4>人工 Gold、消融与生成基线</h4></div><em>${frozen ? "QRELS FROZEN" : "HUMAN LABELS REQUIRED"}</em></header>${qrelsSection}${retrievalBatch}${generationSection}<footer><b>论文效果门仍受控</b><p>只有检索矩阵、生成矩阵、人工写作质量评审与统计重建全部完成后，才允许形成论文结果主张。</p></footer></div>`;
}

async function loadTopicRun(projectId) {
  try {
    state.topicRuns[projectId] = await request(`/api/v1/projects/${projectId}/topic-framing/runs/latest`);
    if (state.selectedId === projectId) renderProjectDetail(state.projects.find((item) => item.id === projectId));
  } catch (error) { state.topicRuns[projectId] = null; toast(error.message, "error"); }
}

async function runTopicFraming(project) {
  state.topicLoading = true; renderProjectDetail(project);
  try {
    const run = await request(`/api/v1/projects/${project.id}/topic-framing/runs`, { method: "POST" });
    state.topicRuns[project.id] = run;
    toast("真实选题拆解已经完成，请审阅候选方案");
  } catch (error) { toast(error.message, "error"); await loadTopicRun(project.id); }
  finally { state.topicLoading = false; renderProjectDetail(project); }
}

async function confirmTopicFraming(project, run) {
  const selected = Number($("input[name='topic_candidate']:checked")?.value || 0);
  const reviewNotes = $("#topicReviewNotes")?.value || "";
  try {
    const confirmation = await request(`/api/v1/projects/${project.id}/topic-framing/confirm`, { method: "POST", body: JSON.stringify({ selected_candidate_index: selected, review_notes: reviewNotes }) });
    state.projects = state.projects.map((item) => item.id === confirmation.project.id ? confirmation.project : item);
    state.topicRuns[project.id] = confirmation.run;
    renderProjects();
    toast("选题质量门已确认，项目进入文献调研阶段");
  } catch (error) { toast(error.message, "error"); }
}

async function loadLiteratureRun(projectId) {
  try {
    state.literatureRuns[projectId] = await request(`/api/v1/projects/${projectId}/literature-review/runs/latest`);
    if (state.selectedId === projectId) renderProjectDetail(state.projects.find((item) => item.id === projectId));
  } catch (error) { state.literatureRuns[projectId] = null; toast(error.message, "error"); }
}

async function runLiteratureReview(project) {
  state.literatureLoading = true; renderProjectDetail(project);
  try {
    const run = await request(`/api/v1/projects/${project.id}/literature-review/runs`, { method: "POST" });
    state.literatureRuns[project.id] = run;
    toast(`文献调研完成：已保存 ${run.papers.length} 篇去重学术记录`);
  } catch (error) { toast(error.message, "error"); await loadLiteratureRun(project.id); }
  finally { state.literatureLoading = false; renderProjectDetail(project); }
}

async function confirmLiteratureReview(project, run) {
  const reviewNotes = $("#literatureReviewNotes")?.value || "";
  try {
    const confirmation = await request(`/api/v1/projects/${project.id}/literature-review/confirm`, { method: "POST", body: JSON.stringify({ review_notes: reviewNotes }) });
    state.projects = state.projects.map((item) => item.id === confirmation.project.id ? confirmation.project : item);
    state.literatureRuns[project.id] = confirmation.run;
    renderProjects();
    toast("文献质量门已确认，项目进入方法设计阶段");
  } catch (error) { toast(error.message, "error"); }
}

async function loadMethodRun(projectId) {
  try {
    state.methodRuns[projectId] = await request(`/api/v1/projects/${projectId}/method-design/runs/latest`);
    if (state.selectedId === projectId) renderProjectDetail(state.projects.find((item) => item.id === projectId));
  } catch (error) { state.methodRuns[projectId] = null; toast(error.message, "error"); }
}

async function runMethodDesign(project) {
  state.methodLoading = true; renderProjectDetail(project);
  try {
    const run = await request(`/api/v1/projects/${project.id}/method-design/runs`, { method: "POST" });
    state.methodRuns[project.id] = run;
    toast(`方法设计完成：${run.result.components.length} 个组件，${run.result.experiment_designs.length} 个实验设计`);
  } catch (error) { toast(error.message, "error"); await loadMethodRun(project.id); }
  finally { state.methodLoading = false; renderProjectDetail(project); }
}

async function confirmMethodDesign(project, run) {
  const reviewNotes = $("#methodReviewNotes")?.value || "";
  try {
    const confirmation = await request(`/api/v1/projects/${project.id}/method-design/confirm`, { method: "POST", body: JSON.stringify({ review_notes: reviewNotes }) });
    state.projects = state.projects.map((item) => item.id === confirmation.project.id ? confirmation.project : item);
    state.methodRuns[project.id] = confirmation.run;
    renderProjects();
    toast("方法质量门已确认，项目进入实验验证阶段");
  } catch (error) { toast(error.message, "error"); }
}

async function loadExperimentRun(projectId) {
  try {
    state.experimentRuns[projectId] = await request(`/api/v1/projects/${projectId}/experiments/runs/latest`);
    if (state.selectedId === projectId) renderProjectDetail(state.projects.find((item) => item.id === projectId));
  } catch (error) { state.experimentRuns[projectId] = null; toast(error.message, "error"); }
}

async function runExperiment(project) {
  state.experimentLoading = true; renderProjectDetail(project);
  try {
    const run = await request(`/api/v1/projects/${project.id}/experiments/runs`, { method: "POST" });
    state.experimentRuns[project.id] = run;
    toast(`实验协议完成：${run.result.protocol.systems.length} 个配置，${run.result.pilot_results.length} 个 proxy pilot`);
  } catch (error) { toast(error.message, "error"); await loadExperimentRun(project.id); }
  finally { state.experimentLoading = false; renderProjectDetail(project); }
}

async function loadRetrievalRun(projectId) {
  try {
    state.retrievalRuns[projectId] = await request(`/api/v1/projects/${projectId}/experiments/retrieval-runs/latest`);
    if (state.selectedId === projectId) renderProjectDetail(state.projects.find((item) => item.id === projectId));
  } catch (error) { state.retrievalRuns[projectId] = null; toast(error.message, "error"); }
}

async function runRealRetrieval(project) {
  const body = {
    role: $("#retrievalRole")?.value || state.retrievalRuns[project.id]?.request?.role || "researcher",
    top_k: Number($("#retrievalTopK")?.value || state.retrievalRuns[project.id]?.request?.top_k || 5),
    context_budget_tokens: Number($("#retrievalBudget")?.value || state.retrievalRuns[project.id]?.request?.context_budget_tokens || 6000),
  };
  state.retrievalLoading = true; renderProjectDetail(project);
  try {
    const run = await request(`/api/v1/projects/${project.id}/experiments/retrieval-runs`, { method: "POST", body: JSON.stringify(body) });
    state.retrievalRuns[project.id] = run;
    toast(`真实检索完成：${run.result.systems.length} 个执行器，${run.result.log_manifest.record_count} 条 JSONL 记录`);
  } catch (error) { toast(error.message, "error"); await loadRetrievalRun(project.id); }
  finally { state.retrievalLoading = false; renderProjectDetail(project); }
}

async function loadQrels(projectId) {
  try {
    state.qrelsSets[projectId] = await request(`/api/v1/projects/${projectId}/experiments/qrels/latest`);
    if (state.selectedId === projectId) renderProjectDetail(state.projects.find((item) => item.id === projectId));
  } catch (error) { state.qrelsSets[projectId] = null; toast(error.message, "error"); }
}

async function createQrels(project) {
  const assessorId = $("#qrelsAssessor")?.value?.trim();
  if (!assessorId) { toast("请填写人工标注者 ID", "error"); return; }
  state.qrelsLoading = true; renderProjectDetail(project);
  try {
    state.qrelsSets[project.id] = await request(`/api/v1/projects/${project.id}/experiments/qrels`, {
      method: "POST",
      body: JSON.stringify({ assessor_id: assessorId, pool_depth: Number($("#qrelsPoolDepth")?.value || 10) }),
    });
    toast("盲化 qrels 候选池已创建，系统来源与排名已隐藏");
  } catch (error) { toast(error.message, "error"); }
  finally { state.qrelsLoading = false; renderProjectDetail(project); }
}

async function saveQrelsPage(project, qrels) {
  const judgments = $$(".qrel-item").flatMap((item) => {
    const selected = item.querySelector('input[type="radio"]:checked');
    if (!selected) return [];
    return [{ query: item.dataset.query, paper_id: item.dataset.paper, relevance: Number(selected.value), rationale: item.querySelector(".qrel-rationale")?.value || "" }];
  });
  if (!judgments.length) { toast("当前查询尚未选择任何相关性等级", "error"); return; }
  state.qrelsLoading = true;
  try {
    state.qrelsSets[project.id] = await request(`/api/v1/projects/${project.id}/experiments/qrels/${qrels.id}/judgments`, {
      method: "PUT", body: JSON.stringify({ assessor_id: qrels.assessor_id, judgments }),
    });
    toast(`已保存 ${judgments.length} 条人工判断`);
  } catch (error) { toast(error.message, "error"); }
  finally { state.qrelsLoading = false; renderProjectDetail(project); }
}

async function freezeQrels(project, qrels) {
  state.qrelsLoading = true;
  try {
    state.qrelsSets[project.id] = await request(`/api/v1/projects/${project.id}/experiments/qrels/${qrels.id}/freeze`, { method: "POST" });
    toast("人工 qrels 已完成完整性检查并冻结 SHA-256");
  } catch (error) { toast(error.message, "error"); }
  finally { state.qrelsLoading = false; renderProjectDetail(project); }
}

async function runAblationBatch(project) {
  state.retrievalLoading = true; renderProjectDetail(project);
  try {
    const run = await request(`/api/v1/projects/${project.id}/experiments/retrieval-runs`, {
      method: "POST",
      body: JSON.stringify({ role: "researcher", top_k: 5, context_budget_tokens: 6000, seeds: [13, 37, 73], include_ablations: true, evaluation_mode: "formal" }),
    });
    state.retrievalRuns[project.id] = run;
    toast(`正式检索矩阵完成：${run.result.systems.length} 个配置，${run.result.log_manifest.record_count} 条记录`);
  } catch (error) { toast(error.message, "error"); await loadRetrievalRun(project.id); }
  finally { state.retrievalLoading = false; renderProjectDetail(project); }
}

async function loadGenerationRun(projectId) {
  try {
    state.generationRuns[projectId] = await request(`/api/v1/projects/${projectId}/experiments/generation-runs/latest`);
    if (state.selectedId === projectId) renderProjectDetail(state.projects.find((item) => item.id === projectId));
  } catch (error) { state.generationRuns[projectId] = null; toast(error.message, "error"); }
}

async function runGenerationBatch(project, formal) {
  state.generationLoading = true; renderProjectDetail(project);
  try {
    const run = await request(`/api/v1/projects/${project.id}/experiments/generation-runs`, {
      method: "POST",
      body: JSON.stringify({ seeds: formal ? [13, 37, 73] : [13], task_limit: formal ? 4 : 1, context_budget_tokens: 6000, mode: formal ? "formal" : "engineering" }),
    });
    state.generationRuns[project.id] = run;
    toast(`B0/B1 批量完成：${run.result.cells.filter((item) => item.status === "completed").length}/${run.result.cells.length} 个单元成功`);
  } catch (error) { toast(error.message, "error"); await loadGenerationRun(project.id); }
  finally { state.generationLoading = false; renderProjectDetail(project); }
}

function renderEnvironment() {
  const env = state.environment;
  if (!env) return;
  const form = $("#environmentForm");
  ["api_base", "model_name", "model_provider", "custom_headers", "embed_api_base", "embed_model"].forEach((key) => {
    if (form.elements[key]) form.elements[key].value = env[key] || "";
  });
  const ready = env.has_api_key && env.api_base && env.model_name;
  $("#modelConfigBadge").textContent = state.modelConnection === true ? "连接正常" : ready ? "已配置" : "未完成";
  $("#modelConfigBadge").classList.toggle("ready", Boolean(ready));
  const openAlexReady = Boolean(env.has_openalex_api_key);
  $("#openAlexConfigBadge").textContent = state.openAlexConnection === true ? "连接正常" : openAlexReady ? "已配置" : "未配置";
  $("#openAlexConfigBadge").classList.toggle("ready", openAlexReady && state.openAlexConnection !== false);
  const openAlexDetail = state.openAlexConnectionResult;
  $("#openAlexConnectionDetail").textContent = openAlexDetail?.remaining != null
    ? `认证成功 · 今日剩余 ${openAlexDetail.remaining} / ${openAlexDetail.daily_limit ?? "?"}`
    : state.openAlexConnection === false
      ? (openAlexDetail?.message || "连接失败，请检查密钥")
      : openAlexReady ? "密钥已安全保存，可执行认证检测" : "保存密钥后可检测认证检索与剩余额度";
  const embeddingReady = Boolean(env.embed_api_base && env.embed_model && env.has_embed_api_key);
  const embeddingDetail = state.embeddingConnectionResult;
  const embeddingNode = $("#embeddingConnectionDetail");
  if (embeddingNode) embeddingNode.textContent = state.embeddingConnection === true
    ? `${embeddingDetail.model} · ${embeddingDetail.dimension} 维 · ${embeddingDetail.latency_ms} ms`
    : state.embeddingConnection === false
      ? (embeddingDetail?.message || "连接失败，请检查配置")
      : embeddingReady ? "配置已保存，可执行真实向量检测" : "完成 Base、模型与 Key 后启用真实检索";
  const keyStates = { apiKeyState: env.has_api_key, openAlexKeyState: env.has_openalex_api_key, embedKeyState: env.has_embed_api_key, jinaKeyState: env.has_jina_api_key, serperKeyState: env.has_serper_api_key, perplexityKeyState: env.has_perplexity_api_key };
  Object.entries(keyStates).forEach(([id, configured]) => { $(`#${id}`).textContent = configured ? "· 已安全保存" : "· 未配置"; });
  updateChecklist();
}

function updateChecklist() {
  const env = state.environment || {};
  const checks = { checkBase: Boolean(env.api_base), checkKey: Boolean(env.has_api_key), checkModel: Boolean(env.model_name), checkConnection: state.modelConnection === true, checkEmbedding: Boolean(env.embed_api_base && env.embed_model && env.has_embed_api_key), checkEmbeddingConnection: state.embeddingConnection === true, checkOpenAlexKey: Boolean(env.has_openalex_api_key), checkOpenAlexConnection: state.openAlexConnection === true, checkRuntime: Boolean(state.capabilities?.jiuwenswarm?.initialized) };
  Object.entries(checks).forEach(([id, ok]) => { const node = $(`#${id}`); if (!node) return; node.textContent = ok ? "✓" : "○"; node.classList.toggle("ok", ok); });
}

function renderEndpoints() {
  $("#endpointList").innerHTML = ENDPOINTS.map(([method, path, description]) => `<div class="endpoint"><span class="method ${method.toLowerCase()}">${method}</span><div><code>${path}</code><p>${description}</p></div><span class="auth">LOCAL API</span></div>`).join("");
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[char]);
}

function safeUrl(value) {
  try { const url = new URL(value); return ["http:", "https:"].includes(url.protocol) ? url.href : ""; }
  catch { return ""; }
}

async function loadCapabilities(showToast = false) {
  try {
    state.capabilities = await request("/api/v1/system/capabilities");
    renderCapabilities();
    $("#syncTime").textContent = `刚刚同步 · ${new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`;
    if (showToast) toast("运行状态已刷新");
  } catch (error) { $("#metricApi").textContent = "连接异常"; toast(error.message, "error"); }
}

async function loadModelHealth(showToast = false) {
  try {
    const result = await request("/api/v1/system/model/test", { method: "POST" });
    state.modelConnection = true;
    if (showToast) toast(result.message);
  } catch (error) {
    state.modelConnection = false;
    if (showToast) toast(error.message, "error");
  }
  renderCapabilities();
  renderEnvironment();
}

async function loadOpenAlexHealth(showToast = false) {
  try {
    const result = await request("/api/v1/system/openalex/test", { method: "POST" });
    state.openAlexConnection = true;
    state.openAlexConnectionResult = result;
    if (showToast) toast(result.remaining != null ? `${result.message}，今日剩余 ${result.remaining}` : result.message);
  } catch (error) {
    state.openAlexConnection = false;
    state.openAlexConnectionResult = { message: error.message };
    if (showToast) toast(error.message, "error");
  }
  renderEnvironment();
}

async function loadEmbeddingHealth(showToast = false) {
  try {
    const result = await request("/api/v1/system/embedding/test", { method: "POST" });
    state.embeddingConnection = true;
    state.embeddingConnectionResult = result;
    if (showToast) toast(`${result.message}：${result.model} / ${result.dimension} 维`);
  } catch (error) {
    state.embeddingConnection = false;
    state.embeddingConnectionResult = { message: error.message };
    if (showToast) toast(error.message, "error");
  }
  renderEnvironment();
}

async function loadAll() {
  document.body.classList.add("loading");
  try {
    const [capabilities, projects, environment] = await Promise.all([
      request("/api/v1/system/capabilities"), request("/api/v1/projects"), request("/api/v1/system/environment")
    ]);
    state.capabilities = capabilities; state.projects = projects; state.environment = environment;
    renderCapabilities(); renderProjects(); renderEnvironment();
    if (state.selectedId) await Promise.all([loadTopicRun(state.selectedId), loadLiteratureRun(state.selectedId), loadMethodRun(state.selectedId), loadExperimentRun(state.selectedId), loadRetrievalRun(state.selectedId), loadQrels(state.selectedId), loadGenerationRun(state.selectedId)]);
    if (capabilities.jiuwenswarm.model_configured) await loadModelHealth(false);
    if (environment.has_openalex_api_key) await loadOpenAlexHealth(false);
    if (environment.embed_api_base && environment.embed_model && environment.has_embed_api_key) await loadEmbeddingHealth(false);
    $("#syncTime").textContent = `刚刚同步 · ${new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}`;
  } catch (error) { toast(`初始化失败：${error.message}`, "error"); }
  finally { document.body.classList.remove("loading"); }
}

$("#projectForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  try {
    const project = await request("/api/v1/projects", { method: "POST", body: JSON.stringify(data) });
    state.projects.unshift(project); state.selectedId = project.id; renderProjects();
    form.reset(); $("#createPanel").classList.remove("open");
    toast("论文项目创建成功");
  } catch (error) { toast(error.message, "error"); }
});

$("#environmentForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = event.currentTarget;
  const data = Object.fromEntries(new FormData(form));
  ["api_key", "openalex_api_key", "embed_api_key", "jina_api_key", "serper_api_key", "perplexity_api_key"].forEach((key) => { if (!data[key]) data[key] = null; });
  try {
    state.environment = await request("/api/v1/system/environment", { method: "PUT", body: JSON.stringify(data) });
    ["api_key", "openalex_api_key", "embed_api_key", "jina_api_key", "serper_api_key", "perplexity_api_key"].forEach((key) => { form.elements[key].value = ""; });
    state.openAlexConnection = null; state.openAlexConnectionResult = null;
    state.embeddingConnection = null; state.embeddingConnectionResult = null;
    renderEnvironment(); await loadCapabilities(); toast(state.environment.message || "环境配置已保存");
  } catch (error) { toast(error.message, "error"); }
});

$("#testModel").addEventListener("click", async () => {
  const button = $("#testModel"); const old = button.textContent; button.textContent = "检测中…"; button.disabled = true;
  try { await loadModelHealth(true); }
  finally { button.textContent = old; button.disabled = false; }
});

$("#testOpenAlex").addEventListener("click", async () => {
  const button = $("#testOpenAlex"); const old = button.textContent; button.textContent = "检测中…"; button.disabled = true;
  try { await loadOpenAlexHealth(true); }
  finally { button.textContent = old; button.disabled = false; }
});

$("#testEmbedding")?.addEventListener("click", async () => {
  const button = $("#testEmbedding"); const old = button.textContent; button.textContent = "检测中…"; button.disabled = true;
  try { await loadEmbeddingHealth(true); }
  finally { button.textContent = old; button.disabled = false; }
});

$$('[data-reveal]').forEach((button) => button.addEventListener("click", () => {
  const input = $("#environmentForm").elements[button.dataset.reveal];
  input.type = input.type === "password" ? "text" : "password";
  button.textContent = input.type === "password" ? "显示" : "隐藏";
}));

$$('.nav-item').forEach((item) => item.addEventListener("click", () => navigate(item.dataset.view)));
$$('[data-go]').forEach((item) => item.addEventListener("click", () => { navigate(item.dataset.go); if (item.dataset.go === "projects") $("#createPanel").classList.add("open"); }));
$("#toggleCreate").addEventListener("click", () => $("#createPanel").classList.toggle("open"));
$("#cancelCreate").addEventListener("click", () => $("#createPanel").classList.remove("open"));
$("#menuButton").addEventListener("click", () => $(".sidebar").classList.toggle("open"));
$("#refreshButton").addEventListener("click", () => loadAll());
$("#serviceRefresh").addEventListener("click", () => loadCapabilities(true));
$("#runCapability").addEventListener("click", () => loadCapabilities(true));
$("#copyResponse").addEventListener("click", async () => { await navigator.clipboard.writeText($("#capabilityJson").textContent); toast("响应内容已复制"); });

renderWorkflow($("#workflowOverview"));
renderEndpoints();
navigate(location.hash.slice(1) || "dashboard");
loadAll();
setInterval(() => loadCapabilities(false), 20000);
