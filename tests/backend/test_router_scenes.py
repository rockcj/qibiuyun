"""场景路由 API 测试 – GET /api/scenes。"""

import pytest


class TestScenesRouter:
    """场景配置接口测试。"""

    @pytest.mark.asyncio
    @pytest.mark.contract
    async def test_get_scenes_lightweight(self, app_client):
        """轻量列表应返回 scenes 数组。"""
        resp = await app_client.get("/api/scenes")
        assert resp.status_code == 200
        data = resp.json()
        assert "scenes" in data
        assert len(data["scenes"]) == 3

    @pytest.mark.asyncio
    @pytest.mark.contract
    async def test_get_scenes_full_includes_topics(self, app_client):
        """完整配置应包含 topics 和 roleModes。"""
        resp = await app_client.get("/api/scenes?full=true")
        assert resp.status_code == 200
        interview = next(s for s in resp.json()["scenes"] if s["scene"] == "interview")
        assert "topics" in interview
        assert "roleModes" in interview
        assert "rubric" in interview
        assert interview["enabled"] is True

    @pytest.mark.asyncio
    @pytest.mark.p0
    async def test_interview_scene_enabled_restaurant_disabled(self, app_client):
        """P0：面试启用，点餐默认禁用。"""
        resp = await app_client.get("/api/scenes")
        scenes = {s["scene"]: s for s in resp.json()["scenes"]}
        assert scenes["interview"]["enabled"] is True
        # 默认环境变量下 restaurant/meeting 应为 false
        assert scenes["restaurant"]["enabled"] is False
        assert scenes["restaurant"].get("releasePriority") == "P1"
