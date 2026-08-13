"""
LLM 管理端点。

提供 LLM 连通性测试、模型信息查询等端点。
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.llm import LLMClient

router = APIRouter(tags=["llm"])


# ---------------------------------------------------------------------------
# 响应模型
# ---------------------------------------------------------------------------

class LLMTestResponse(BaseModel):
    """LLM 连通性测试响应。"""

    success: bool = Field(..., description="连接是否成功")
    message: str = Field(..., description="测试结果描述")
    latency_ms: int = Field(..., description="响应延迟（毫秒）")
    model: str = Field(default="", description="实际使用的模型名称")


class LLMInfoResponse(BaseModel):
    """LLM 配置信息响应。"""

    provider: str = Field(..., description="提供商类型")
    base_url: str = Field(..., description="API 基础 URL")
    model_name: str = Field(..., description="默认模型名称")
    timeout: float = Field(..., description="请求超时（秒）")


# ---------------------------------------------------------------------------
# 端点
# ---------------------------------------------------------------------------

@router.get("/llm/test", response_model=LLMTestResponse)
async def test_llm_connection() -> LLMTestResponse:
    """测试 LLM 连通性。

    发送一条简短消息，验证 LLM 是否可正常调用。
    """
    try:
        client = LLMClient.from_settings()
        result = await client.test_connection()
        await client.close()
        return LLMTestResponse(**result)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"LLM connection test failed: {exc}",
        )


@router.get("/llm/info", response_model=LLMInfoResponse)
async def get_llm_info() -> LLMInfoResponse:
    """获取当前 LLM 配置信息（不含敏感字段）。"""
    from app.core.config import settings

    return LLMInfoResponse(
        provider=settings.llm_provider,
        base_url=settings.openai_base_url,
        model_name=settings.model_name,
        timeout=settings.llm_timeout,
    )
