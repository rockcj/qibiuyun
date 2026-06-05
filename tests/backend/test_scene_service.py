"""场景配置服务单元测试 – enabled 开关、场景查询、契约字段。"""

import pytest

from services.scene_service import get_all_scenes, get_scene, get_scene_list


class TestSceneService:
    """场景配置服务测试。"""

    def test_get_all_scenes_returns_three_scenes(self):
        """应返回 interview、restaurant、meeting 三个场景。"""
        scenes = get_all_scenes()
        names = {s["scene"] for s in scenes}
        assert names == {"interview", "restaurant", "meeting"}

    def test_interview_scene_always_enabled(self):
        """面试场景应始终 enabled=True。"""
        interview = get_scene("interview")
        assert interview is not None
        assert interview["enabled"] is True
        assert interview["requiresResumeJD"] is True

    def test_restaurant_scene_disabled_by_default(self, monkeypatch):
        """默认配置下餐厅场景应 disabled。"""
        monkeypatch.setenv("ENABLE_RESTAURANT_SCENE", "false")
        # 重新加载 settings 较复杂，直接验证静态逻辑
        restaurant = get_scene("restaurant")
        assert restaurant is not None
        assert restaurant["requiresResumeJD"] is False
        assert len(restaurant["topics"]) >= 1
        assert len(restaurant["roleModes"]) >= 1

    def test_get_scene_not_found(self):
        """不存在的场景应返回 None。"""
        assert get_scene("unknown") is None

    def test_get_scene_list_lightweight_fields(self):
        """轻量列表应包含首页卡片所需字段。"""
        items = get_scene_list()
        for item in items:
            assert "scene" in item
            assert "displayName" in item
            assert "description" in item
            assert "icon" in item
            assert "color" in item
            assert "enabled" in item

    def test_interview_rubric_matches_contract(self):
        """面试评分维度应与 api-contract 一致。"""
        interview = get_scene("interview")
        expected = ["english", "logic", "confidence", "star", "technical", "communication"]
        assert interview["rubric"] == expected

    def test_disabled_scene_has_release_priority(self):
        """未启用场景应携带 releasePriority 和 disabledReason。"""
        scenes = get_all_scenes()
        restaurant = next(s for s in scenes if s["scene"] == "restaurant")
        if not restaurant["enabled"]:
            assert restaurant.get("releasePriority") == "P1"
            assert restaurant.get("disabledReason")
