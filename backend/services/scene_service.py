"""Scene configuration service – returns scene, topic, role and rubric data."""

from typing import Optional

from config import settings

# ---------------------------------------------------------------------------
# Static scene configuration – mirrors the architecture doc's Scene Router output.
# In production this data lives in the `scene_presets` table.
# ---------------------------------------------------------------------------

SCENES_CONFIG = [
    {
        "scene": "interview",
        "displayName": "求职面试",
        "description": "模拟真实英文面试，支持简历/JD驱动、多种面试官人格和STAR分析",
        "icon": "briefcase",
        "color": "#4F46E5",
        "topics": [
            {"topic": "behavioral", "displayName": "行为面试"},
            {"topic": "technical", "displayName": "技术面试"},
            {"topic": "projectDeepDive", "displayName": "项目深挖"},
            {"topic": "systemDesign", "displayName": "系统设计"},
            {"topic": "resumeBased", "displayName": "简历问答"},
        ],
        "roleModes": [
            {"roleMode": "founder", "displayName": "Founder Mode（关注执行与业务影响）"},
            {"roleMode": "productThinker", "displayName": "Product Thinker（关注用户价值）"},
            {"roleMode": "dataDriven", "displayName": "Data Driven（关注指标与实验）"},
            {"roleMode": "engineeringLeader", "displayName": "Engineering Leader（关注架构与技术深度）"},
            {"roleMode": "stressInterview", "displayName": "Stress Interview（压力面试）"},
        ],
        "rubric": ["english", "logic", "confidence", "star", "technical", "communication"],
        "requiresResumeJD": True,
        "correctionPolicy": {
            "realtimeLightCorrection": True,
            "onlyInterruptSevereErrors": True,
        },
    },
    {
        "scene": "restaurant",
        "displayName": "餐厅点餐",
        "description": "在餐厅场景中练习点餐、预约、投诉和结账的实用英语",
        "icon": "utensils",
        "color": "#F59E0B",
        "topics": [
            {"topic": "ordering", "displayName": "点餐"},
            {"topic": "reservation", "displayName": "预约餐桌"},
            {"topic": "specialRequests", "displayName": "特殊要求（过敏/素食）"},
            {"topic": "complaint", "displayName": "投诉处理"},
            {"topic": "payment", "displayName": "结账与AA制"},
        ],
        "roleModes": [
            {"roleMode": "friendlyWaiter", "displayName": "友好的服务员"},
            {"roleMode": "busyWaiter", "displayName": "忙碌的服务员"},
            {"roleMode": "impatientWaiter", "displayName": "不耐烦的服务员"},
        ],
        "rubric": ["english", "politeness", "functionalPhrases", "taskCompletion", "pronunciationFluency"],
        "requiresResumeJD": False,
        "correctionPolicy": {
            "realtimeLightCorrection": True,
            "onlyInterruptSevereErrors": True,
        },
    },
    {
        "scene": "meeting",
        "displayName": "商务会议",
        "description": "练习英文会议中的汇报、提问、建议和总结能力",
        "icon": "presentation",
        "color": "#10B981",
        "topics": [
            {"topic": "selfIntroduction", "displayName": "会议开场自我介绍"},
            {"topic": "projectUpdate", "displayName": "项目进展汇报"},
            {"topic": "proposal", "displayName": "提出建议或质疑"},
            {"topic": "respondingQuestions", "displayName": "回应提问"},
            {"topic": "clarify", "displayName": "礼貌打断与澄清"},
            {"topic": "summary", "displayName": "总结与结束会议"},
        ],
        "roleModes": [
            {"roleMode": "meetingHost", "displayName": "会议主持人"},
            {"roleMode": "colleague", "displayName": "同事"},
            {"roleMode": "superior", "displayName": "上级"},
        ],
        "rubric": ["english", "logic", "communication", "functionalPhrases", "meetingControl"],
        "requiresResumeJD": False,
        "correctionPolicy": {
            "realtimeLightCorrection": True,
            "onlyInterruptSevereErrors": False,
        },
    },
]


def _is_scene_enabled(scene_name: str) -> bool:
    """根据环境变量判断场景是否启用。"""
    if scene_name == "interview":
        return True
    if scene_name == "restaurant":
        return settings.enable_restaurant_scene
    if scene_name == "meeting":
        return settings.enable_meeting_scene
    return False


def _scene_release_priority(scene_name: str) -> Optional[str]:
    """返回场景发布优先级标签。"""
    if scene_name == "restaurant":
        return "P1"
    if scene_name == "meeting":
        return "P2"
    return None


def _scene_disabled_reason(scene_name: str) -> Optional[str]:
    """返回场景禁用原因说明。"""
    if scene_name == "restaurant" and not settings.enable_restaurant_scene:
        return "P0 阶段先完成面试闭环"
    if scene_name == "meeting" and not settings.enable_meeting_scene:
        return "P0/P1 稳定后再接入"
    return None


def get_all_scenes() -> list[dict]:
    """Return the complete scene configuration list with enabled flags."""
    result = []
    for scene in SCENES_CONFIG:
        entry = {**scene, "enabled": _is_scene_enabled(scene["scene"])}
        if not entry["enabled"]:
            entry["releasePriority"] = _scene_release_priority(scene["scene"])
            entry["disabledReason"] = _scene_disabled_reason(scene["scene"])
        result.append(entry)
    return result


def get_scene(scene_name: str) -> Optional[dict]:
    """Return configuration for a single scene."""
    for scene in SCENES_CONFIG:
        if scene["scene"] == scene_name:
            return {**scene, "enabled": _is_scene_enabled(scene_name)}
    return None


def get_scene_list() -> list[dict]:
    """Return a lightweight scene list (for the homepage cards)."""
    items = []
    for s in SCENES_CONFIG:
        enabled = _is_scene_enabled(s["scene"])
        item = {
            "scene": s["scene"],
            "displayName": s["displayName"],
            "description": s["description"],
            "icon": s["icon"],
            "color": s["color"],
            "enabled": enabled,
        }
        if not enabled:
            item["releasePriority"] = _scene_release_priority(s["scene"])
            item["disabledReason"] = _scene_disabled_reason(s["scene"])
        items.append(item)
    return items
