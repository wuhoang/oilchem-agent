"""
图表绘制工具。

使用 matplotlib 生成曲线图、柱状图、散点图等，
将图表编码为 base64 图片返回，供前端直接展示。
"""

from __future__ import annotations

import base64
import io
from typing import Any

from loguru import logger

from app.tools.base import BaseTool, ToolMetadata, ToolResult
from app.tools.registry import register_tool

# 中文字体配置（Windows 中文环境）
plt_configured = False


def _configure_matplotlib() -> None:
    global plt_configured
    if plt_configured:
        return
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    # 尝试设置中文字体
    import platform
    system = platform.system()
    if system == "Windows":
        plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    else:
        plt.rcParams["font.sans-serif"] = ["WenQuanYi Micro Hei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    plt_configured = True


def _fig_to_base64(fig: Any) -> str:
    """将 matplotlib Figure 转换为 base64 PNG 字符串。"""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    import matplotlib.pyplot as plt
    plt.close(fig)
    return b64


@register_tool(ToolMetadata(
    name="plot_chart",
    description=(
        "绘制数据图表并返回图片。支持曲线图(plot)、柱状图(bar)、散点图(scatter)、"
        "直方图(hist)。输入 x 和 y 数据（列表或 JSON 数组），生成图表后返回 base64 图片，"
        "前端会直接展示。当用户要求'画图'、'绘制曲线'、'生成图表'时使用此工具。"
    ),
    parameters={
        "chart_type": {
            "type": "string",
            "description": "图表类型：plot（曲线图）、bar（柱状图）、scatter（散点图）、hist（直方图）",
        },
        "x_data": {
            "type": "array",
            "description": "X 轴数据数组，如 [1,2,3,4,5] 或 ['A','B','C']",
        },
        "y_data": {
            "type": "array",
            "description": "Y 轴数据数组（多系列传嵌套数组），如 [10,20,15,30,25] 或 [[10,20],[15,30]]",
        },
        "title": {
            "type": "string",
            "description": "图表标题（可选）",
        },
        "x_label": {
            "type": "string",
            "description": "X 轴标签（可选）",
        },
        "y_label": {
            "type": "string",
            "description": "Y 轴标签（可选）",
        },
        "labels": {
            "type": "array",
            "description": "多条曲线的图例标签（可选），如 ['系列1','系列2']",
        },
        "color": {
            "type": "string",
            "description": "线条/填充颜色（可选），如 'red'、'#FF5733'，多系列用数组",
        },
    },
))
class PlotChartTool(BaseTool):
    """绘制图表并返回 base64 图片。"""

    async def execute(self, **kwargs: Any) -> ToolResult:
        _configure_matplotlib()
        import matplotlib.pyplot as plt
        import numpy as np

        chart_type = kwargs.get("chart_type", "plot").strip().lower()
        x_data = kwargs.get("x_data", [])
        y_data = kwargs.get("y_data", [])
        title = kwargs.get("title", "")
        x_label = kwargs.get("x_label", "")
        y_label = kwargs.get("y_label", "")
        labels = kwargs.get("labels", [])
        color = kwargs.get("color", None)

        if not y_data:
            return ToolResult(success=False, error="缺少 y_data 参数")

        if not isinstance(y_data, list):
            return ToolResult(
                success=False,
                error=f"y_data 必须是数组（当前是 {type(y_data).__name__}）。"
                f"如果参数来自前序步骤结果，请用 {{step_N_result.字段名}} 引用。",
            )

        try:
            # 校验数值元素（多系列取第一个子列表）
            probe = y_data[0] if isinstance(y_data[0], list) else y_data
            if not all(isinstance(v, (int, float)) for v in probe):
                return ToolResult(
                    success=False,
                    error=f"y_data 包含非数值元素: {[str(v)[:20] for v in probe[:5]]}",
                )
        except (IndexError, TypeError):
            return ToolResult(success=False, error="y_data 为空或格式无效")

        try:
            fig, ax = plt.subplots(figsize=(8, 5))

            # 多系列检测
            is_multi = (
                isinstance(y_data, list)
                and len(y_data) > 0
                and isinstance(y_data[0], list)
            )

            if chart_type == "plot":
                if is_multi:
                    for i, ys in enumerate(y_data):
                        lbl = labels[i] if i < len(labels) else f"系列{i + 1}"
                        c = color[i] if isinstance(color, list) and i < len(color) else None
                        xs = x_data if x_data else list(range(len(ys)))
                        ax.plot(xs, ys, label=lbl, color=c or None, marker="o")
                    ax.legend()
                else:
                    xs = x_data if x_data else list(range(len(y_data)))
                    ax.plot(xs, y_data, color=color or None, marker="o", linewidth=2)

            elif chart_type == "bar":
                if is_multi:
                    x_pos = np.arange(len(x_data)) if x_data else np.arange(len(y_data[0]))
                    width = 0.8 / len(y_data)
                    for i, ys in enumerate(y_data):
                        offset = (i - len(y_data) / 2 + 0.5) * width
                        lbl = labels[i] if i < len(labels) else f"系列{i + 1}"
                        c = color[i] if isinstance(color, list) and i < len(color) else None
                        ax.bar(x_pos + offset, ys, width, label=lbl, color=c or None)
                    ax.set_xticks(x_pos)
                    if x_data:
                        ax.set_xticklabels(x_data)
                    ax.legend()
                else:
                    xs = x_data if x_data else list(range(len(y_data)))
                    ax.bar(xs, y_data, color=color or None)

            elif chart_type == "scatter":
                if is_multi:
                    for i, ys in enumerate(y_data):
                        lbl = labels[i] if i < len(labels) else f"系列{i + 1}"
                        c = color[i] if isinstance(color, list) and i < len(color) else None
                        xs = x_data if x_data else list(range(len(ys)))
                        ax.scatter(xs, ys, label=lbl, color=c or None, alpha=0.7)
                    ax.legend()
                else:
                    xs = x_data if x_data else list(range(len(y_data)))
                    ax.scatter(xs, y_data, color=color or None, alpha=0.7)

            elif chart_type == "hist":
                if is_multi:
                    for i, ys in enumerate(y_data):
                        lbl = labels[i] if i < len(labels) else f"系列{i + 1}"
                        c = color[i] if isinstance(color, list) and i < len(color) else None
                        ax.hist(ys, bins=10, label=lbl, color=c or None, alpha=0.7)
                    ax.legend()
                else:
                    ax.hist(y_data, bins=10, color=color or None, alpha=0.7)

            else:
                return ToolResult(
                    success=False,
                    error=f"不支持的图表类型: {chart_type}。支持: plot, bar, scatter, hist",
                )

            if title:
                ax.set_title(title, fontsize=14)
            if x_label:
                ax.set_xlabel(x_label)
            if y_label:
                ax.set_ylabel(y_label)

            ax.grid(True, alpha=0.3)
            fig.tight_layout()

            img_b64 = _fig_to_base64(fig)

            return ToolResult(
                success=True,
                data={
                    "chart_type": chart_type,
                    "image_base64": img_b64,
                    "image_mime": "image/png",
                    "width": 800,
                    "height": 500,
                },
            )

        except Exception as exc:
            logger.bind(component="chart").error("Chart generation failed: {}", exc)
            return ToolResult(success=False, error=f"图表生成失败: {exc}")


__all__ = ["PlotChartTool"]
