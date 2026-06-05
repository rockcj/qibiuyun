"""对话服务 – 流式 LLM 对话 + 场景 System Prompt + 上下文管理。

负责：
- 构建场景驱动的 System Prompt
- 调用 DeepSeek Anthropic 兼容 API 做流式对话
- 管理最近 5 轮对话历史
- 轻纠正检测（语法错误 → correction.light 事件）
"""

import json
import re
from typing import Any, AsyncGenerator, Optional

import httpx

from config import settings


# 会话级对话历史最大轮数
_MAX_HISTORY_TURNS = 5


# 通用对话 System Prompt 模板
_CONVERSATION_SYSTEM_PROMPT = """You are an AI role-play partner for OfferGPT, an English speaking practice platform.

Your role: {role_description}

Scene: {scene_name} — {topic_name}

Rules:
1. Stay in character at all times. You are {role_name}, not an AI assistant.
2. Speak naturally in English, keep responses concise (2-4 sentences).
3. Drive the conversation forward — ask follow-up questions, react to what the user says.
4. If the user makes a serious grammar mistake that affects understanding, briefly correct it
   in a natural way (one short tip), then continue the conversation. Format your correction as:
   [CORRECTION: original phrase → corrected phrase]
5. If the user's response is vague or too short, ask a concrete follow-up question.
6. Never break character to explain grammar rules at length.
7. Keep spoken responses under 20 seconds when read aloud.

Current conversation goal: {goal}"""


# 面试场景专用追问策略
_INTERVIEW_FOLLOWUP_RULES = """
Additional interview rules:
- Ask only ONE question at a time.
- If the candidate mentions a metric without explaining how they achieved it, ask "What specific actions did you take?"
- If the candidate uses "we" instead of "I", ask "What was your personal contribution?"
- If the candidate describes a process without a result, ask "What was the measurable outcome?"
- If the candidate goes off-topic, gently redirect: "That's interesting, but let's focus on..."
"""


class ConversationService:
    """流式对话服务。"""

    def __init__(self):
        self._api_key: str = settings.deepseek_api_key or settings.llm_api_key
        self._base_url: str = settings.llm_api_base_url.rstrip("/")
        self._model: str = settings.llm_model

    # ------------------------------------------------------------------
    # System Prompt 构建
    # ------------------------------------------------------------------
    def build_system_prompt(self, scene_config: dict) -> str:
        """根据场景配置生成 System Prompt。"""
        scene = scene_config.get("scene", "interview")
        topic = scene_config.get("topic", "general")
        role_mode = scene_config.get("roleMode", "friendly")
        persona_mode = scene_config.get("personaMode", role_mode)

        # 构建角色描述
        role_descriptions = {
            "founder": "a startup founder interviewing a candidate. You care deeply about ownership, execution speed, and measurable business impact. You are direct and push for specifics.",
            "engineeringLeader": "a senior engineering leader evaluating technical depth. You ask about architecture trade-offs, system design decisions, and technical challenges.",
            "productThinker": "a product leader who cares about user value and product judgment. You ask about user problems, prioritization, and success metrics.",
            "dataDriven": "a data-driven manager who focuses on metrics, experiments, and causal reasoning. You ask about A/B tests, data pipelines, and analytical methods.",
            "stressInterview": "an interviewer conducting a high-pressure interview. You challenge answers respectfully but firmly. You never insult or discriminate.",
            "friendlyWaiter": "a friendly waiter at a restaurant. You are helpful, patient, and polite.",
            "busyWaiter": "a busy waiter at a crowded restaurant. You are efficient, speak quickly, and keep interactions brief.",
            "impatientWaiter": "an impatient waiter who wants to take orders quickly. You are slightly rushed but still professional.",
            "meetingHost": "a meeting host facilitating a business discussion. You keep the agenda moving and invite participation.",
            "colleague": "a supportive colleague in a business meeting. You collaborate and build on ideas.",
            "superior": "a senior manager in a business meeting. You ask clarifying questions and expect concise updates.",
        }

        role_desc = role_descriptions.get(role_mode, f"a {role_mode} in a {scene} scenario")

        # 构建对话目标
        goals = {
            ("interview", "behavioral"): "Evaluate the candidate's past behavior and STAR-structured responses.",
            ("interview", "technical"): "Assess the candidate's technical knowledge and problem-solving approach.",
            ("restaurant", "ordering"): "Help the customer complete their food order with any special requests.",
            ("restaurant", "reservation"): "Handle the customer's table reservation request.",
            ("restaurant", "complaint"): "Address the customer's complaint about their meal or service.",
            ("meeting", "projectUpdate"): "Discuss project progress, risks, and next steps.",
            ("meeting", "selfIntroduction"): "Guide the participant through a professional self-introduction.",
        }
        goal = goals.get((scene, topic), f"Have a natural {scene} conversation about {topic}.")

        prompt = _CONVERSATION_SYSTEM_PROMPT.format(
            role_description=role_desc,
            scene_name=scene,
            topic_name=topic,
            role_name=role_mode,
            goal=goal,
        )

        # 面试场景追加追问策略
        if scene == "interview":
            prompt += _INTERVIEW_FOLLOWUP_RULES

        return prompt

    # ------------------------------------------------------------------
    # 流式对话
    # ------------------------------------------------------------------
    async def stream_chat(
        self,
        system_prompt: str,
        user_message: str,
        history: Optional[list[dict]] = None,
    ) -> AsyncGenerator[dict, None]:
        """流式调用 LLM，逐 token 产出。

        Yields:
            {"type": "text", "content": "token_text"}  — 文本增量
            {"type": "correction", "original": "...", "corrected": "..."}  — 轻纠正
            {"type": "done"}  — 完成
            {"type": "error", "message": "..."}  — 错误
        """
        if not self._api_key:
            yield {"type": "error", "message": "LLM API Key not configured"}
            return

        # 构建消息列表
        messages: list[dict] = [{"role": "system", "content": system_prompt}]

        if history:
            for turn in history[-_MAX_HISTORY_TURNS * 2:]:  # N 轮 = 2N 条消息
                messages.append(turn)

        messages.append({"role": "user", "content": user_message})

        url = f"{self._base_url}/v1/messages"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        payload = {
            "model": self._model,
            "max_tokens": 512,
            "messages": messages,
            "stream": True,
            "temperature": 0.8,
        }

        full_text = ""

        try:
            # 设置较长的超时时间：连接 10s，读取 60s（推理模型思考阶段可能较长）
            timeout = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)
            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        yield {"type": "error", "message": f"LLM API error ({resp.status_code}): {body[:200]}"}
                        return

                    async for line in resp.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                        except json.JSONDecodeError:
                            continue

                        # Anthropic 兼容流式格式
                        delta = None
                        if "delta" in data:
                            # OpenAI 兼容格式
                            delta = data["delta"]
                        elif "content_block" in data and data["content_block"].get("type") == "text":
                            # Anthropic 原生格式
                            delta = {"text": data["content_block"].get("text", "")}
                        elif "type" in data and data["type"] == "content_block_delta":
                            delta_data = data.get("delta", {})
                            if isinstance(delta_data, dict):
                                delta = {"text": delta_data.get("text", "")}

                        if delta and delta.get("text"):
                            token = delta["text"]
                            full_text += token
                            yield {"type": "text", "content": token}

        except httpx.TimeoutException:
            yield {"type": "error", "message": "LLM request timeout"}
        except Exception as exc:
            yield {"type": "error", "message": f"LLM error: {str(exc)}"}

        # 解析 [CORRECTION: ...] 模式
        correction_match = re.search(
            r"\[CORRECTION:\s*([^\]]+?)\s*→\s*([^\]]+?)\]", full_text
        )
        if correction_match:
            original = correction_match.group(1).strip()
            corrected = correction_match.group(2).strip()
            # 移除文本中的 CORRECTION 标记
            clean_text = re.sub(r"\[CORRECTION:\s*[^\]]+?\]", "", full_text).strip()
            yield {"type": "correction", "original": original, "corrected": corrected, "cleanText": clean_text}

        yield {"type": "done"}


# 全局单例
conversation_service = ConversationService()
