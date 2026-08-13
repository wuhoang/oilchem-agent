"""
网页操作端点。

提供网页浏览、智能填表、内容提取的 REST API。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.tools.manager import ToolManager

router = APIRouter(tags=["web"])

_tool_manager = ToolManager()


class BrowseWebRequest(BaseModel):
    url: str = Field(..., description="Target page URL")
    timeout: int = Field(default=30000, description="Timeout in ms")


class SmartFillFormRequest(BaseModel):
    url: str = Field(..., description="Target page URL")
    username: str | None = Field(default=None, description="Username for login")
    password: str | None = Field(default=None, description="Password for login")
    field_mapping: dict[str, str] = Field(
        default_factory=dict,
        description="Field mapping {field_name: value}, field name can be Chinese or English",
    )
    auto_submit: bool = Field(default=True, description="Auto submit after filling")
    timeout: int = Field(default=30000, description="Timeout in ms")


class FillFormRequest(BaseModel):
    url: str = Field(..., description="Target page URL")
    username: str | None = Field(default=None)
    password: str | None = Field(default=None)
    form_data: dict[str, str] = Field(default_factory=dict, description="{index: value}")
    submit: bool = Field(default=True)
    timeout: int = Field(default=30000)


class ExtractTextRequest(BaseModel):
    url: str = Field(..., description="Target page URL")
    selector: str | None = Field(default=None, description="CSS selector")
    timeout: int = Field(default=30000)


class WebToolResponse(BaseModel):
    success: bool
    data: Any = None
    error: str | None = None


@router.post("/web/browse", response_model=WebToolResponse)
async def browse_web(req: BrowseWebRequest) -> WebToolResponse:
    result = await _tool_manager.execute(
        "browse_webpage", url=req.url, timeout=req.timeout
    )
    if result.success:
        return WebToolResponse(success=True, data=result.data)
    return WebToolResponse(success=False, error=result.error)


@router.post("/web/smart-fill", response_model=WebToolResponse)
async def smart_fill_form(req: SmartFillFormRequest) -> WebToolResponse:
    kwargs: dict[str, Any] = {
        "url": req.url,
        "timeout": req.timeout,
        "auto_submit": req.auto_submit,
    }
    if req.username:
        kwargs["username"] = req.username
    if req.password:
        kwargs["password"] = req.password
    if req.field_mapping:
        kwargs["field_mapping"] = req.field_mapping

    result = await _tool_manager.execute("smart_fill_form", **kwargs)
    if result.success:
        return WebToolResponse(success=True, data=result.data)
    return WebToolResponse(success=False, error=result.error)


@router.post("/web/fill-form", response_model=WebToolResponse)
async def fill_web_form(req: FillFormRequest) -> WebToolResponse:
    kwargs: dict[str, Any] = {"url": req.url, "timeout": req.timeout, "submit": req.submit}
    if req.username:
        kwargs["username"] = req.username
    if req.password:
        kwargs["password"] = req.password
    if req.form_data:
        kwargs["form_data"] = req.form_data

    result = await _tool_manager.execute("fill_webform", **kwargs)
    if result.success:
        return WebToolResponse(success=True, data=result.data)
    return WebToolResponse(success=False, error=result.error)


@router.post("/web/extract-text", response_model=WebToolResponse)
async def extract_web_text(req: ExtractTextRequest) -> WebToolResponse:
    result = await _tool_manager.execute(
        "extract_webpage_text", url=req.url, selector=req.selector, timeout=req.timeout
    )
    if result.success:
        return WebToolResponse(success=True, data=result.data)
    return WebToolResponse(success=False, error=result.error)


__all__ = ["router"]