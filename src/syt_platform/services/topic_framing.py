"""PACM-SW 需求澄清与选题拆解垂直链路。"""

from __future__ import annotations

import hashlib
import json

from pydantic import ValidationError

from syt_platform.domain.project import ResearchProject
from syt_platform.domain.topic_framing import (
    ContextItem,
    ExecutionStep,
    ProvenanceRecord,
    TopicFramingResult,
    TopicFramingRun,
)
from syt_platform.repositories.topic_runs import TopicRunRepository
from syt_platform.services.model_gateway import JiuwenModelGateway, ModelGatewayError


PROMPT_VERSION = "pacm-sw-topic-framing-v1"
PACM_SW_CORE = (
    "推荐将‘可溯源上下文记忆’作为主方向，把上下文工程和记忆引擎结合起来，"
    "自演进作为平台扩展能力而非首篇论文的主要结论。系统工作名为 "
    "Provenance-Aware Context Memory for Multi-Agent Scientific Writing，中文名为"
    "‘面向多智能体科研写作的可溯源上下文记忆方法’，暂定方法名 PACM-SW。"
    "方法名尚未冻结，必须在相关工作检索后检查重名和新颖性。"
)


class TopicFramingError(RuntimeError):
    pass


def _context_item(
    item_id: str,
    source_type: str,
    source_label: str,
    content: str,
) -> ContextItem:
    checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
    return ContextItem(
        id=item_id,
        source_type=source_type,
        source_label=source_label,
        content=content,
        checksum=checksum,
    )


class TopicFramingService:
    def __init__(
        self,
        repository: TopicRunRepository,
        model_gateway: JiuwenModelGateway,
    ) -> None:
        self.repository = repository
        self.model_gateway = model_gateway

    @staticmethod
    def contexts(project: ResearchProject) -> list[ContextItem]:
        return [
            _context_item("CTX-PROJECT-001", "project", "用户暂定题目", project.title),
            _context_item(
                "CTX-PROJECT-002",
                "project",
                "用户研究方向",
                project.research_direction,
            ),
            _context_item("CTX-CORE-001", "product_core", "PACM-SW 核心技术方向", PACM_SW_CORE),
            _context_item(
                "CTX-RULE-001",
                "quality_rule",
                "证据与新颖性边界",
                "当前阶段尚未完成外部文献检索。不得虚构论文、作者、实验结果或引用；"
                "所有研究空白与新颖性判断只能写成待验证假设。",
            ),
            _context_item(
                "CTX-DELIVERY-001",
                "delivery_constraint",
                "比赛交付约束",
                "目标为 Agent 方向科研 Short Paper，建议采用 ICLR 模板，并接受自动化评审。",
            ),
        ]

    @staticmethod
    def _system_prompt() -> str:
        schema = json.dumps(TopicFramingResult.model_json_schema(), ensure_ascii=False)
        return (
            "你是 PACM-SW 科研选题架构智能体。你的任务是完成需求澄清和选题拆解，"
            "不是撰写整篇论文。必须严格区分用户输入、平台核心假设和待文献验证结论。"
            "禁止捏造文献、作者、数据、实验结果或已证实的 SOTA 结论。"
            "每个关键陈述都应在 provenance_map 中引用给定 context id；"
            "涉及现有工作、新颖性或效果的陈述必须标记 pending_literature_verification。"
            "给出 3 个聚焦但有区分度的中英文候选题目。只输出一个 JSON 对象，不要 Markdown。"
            f"输出必须符合以下 JSON Schema：{schema}"
        )

    @staticmethod
    def _user_prompt(project: ResearchProject, contexts: list[ContextItem]) -> str:
        payload = {
            "project": project.model_dump(mode="json"),
            "traceable_context": [item.model_dump(mode="json") for item in contexts],
            "instructions": [
                "以可溯源上下文记忆为核心，统一上下文工程与记忆引擎",
                "自演进只作为未来扩展，不作为首篇论文主要结论",
                "研究问题应可以通过后续实验验证",
                "贡献点不得提前声称已验证有效",
                "为下一阶段给出可直接用于检索的中英文查询词",
            ],
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @staticmethod
    def _normalize_provenance(
        result: TopicFramingResult,
        contexts: list[ContextItem],
    ) -> TopicFramingResult:
        known = {item.id for item in contexts}
        normalized: list[ProvenanceRecord] = []
        for record in result.provenance_map:
            context_ids = [item for item in record.context_ids if item in known]
            if not context_ids:
                context_ids = ["CTX-CORE-001"]
            normalized.append(record.model_copy(update={"context_ids": context_ids}))
        if not normalized:
            normalized.append(
                ProvenanceRecord(
                    statement=result.method_positioning,
                    context_ids=["CTX-CORE-001", "CTX-RULE-001"],
                    verification_status="context_supported",
                )
            )
        return result.model_copy(update={"provenance_map": normalized})

    async def run(self, project: ResearchProject) -> TopicFramingRun:
        contexts = self.contexts(project)
        trace = [
            ExecutionStep(
                step="context_assembly",
                status="completed",
                detail=f"已汇集 {len(contexts)} 条带校验摘要的来源上下文",
            ),
            ExecutionStep(
                step="model_generation",
                status="running",
                detail="正在通过 JiuwenSwarm 模型栈执行结构化选题拆解",
            ),
        ]
        try:
            model_name = self.model_gateway.model_name
        except ModelGatewayError as exc:
            raise TopicFramingError(str(exc)) from exc
        run = self.repository.create(
            project.id,
            model_name,
            PROMPT_VERSION,
            contexts,
            trace,
        )
        try:
            generated = await self.model_gateway.generate_json(
                system_prompt=self._system_prompt(),
                user_prompt=self._user_prompt(project, contexts),
                operation="pacm_sw_topic_framing",
            )
            result = TopicFramingResult.model_validate(generated.data)
            result = self._normalize_provenance(result, contexts)
            usage_total = generated.usage.get("total", {})
            trace[1] = ExecutionStep(
                step="model_generation",
                status="completed",
                detail=(
                    f"{generated.model_name} 已返回结构化结果；"
                    f"token={usage_total.get('total_tokens', 0)}"
                ),
            )
            trace.extend(
                [
                    ExecutionStep(
                        step="schema_validation",
                        status="completed",
                        detail="产物已通过 TopicFramingResult 结构校验",
                    ),
                    ExecutionStep(
                        step="provenance_validation",
                        status="completed",
                        detail="来源引用已限制在本次输入上下文集合内",
                    ),
                ]
            )
            return self.repository.complete(run.id, result, trace)
        except (ModelGatewayError, ValidationError, ValueError) as exc:
            trace[1] = ExecutionStep(
                step="model_generation",
                status="failed",
                detail="模型生成或结构校验失败",
            )
            self.repository.fail(run.id, str(exc), trace)
            raise TopicFramingError(str(exc)) from exc
