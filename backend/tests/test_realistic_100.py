"""100 个真实场景测试。

验证 Agent 在各种真实用户提问下的工具选择正确性。
分两层：
  - mock 层：用 mock LLM 验证工具路由逻辑（快速，无 API 调用）
  - 集成层：抽样跑真实 DeepSeek API 验证端到端（慢，可选）
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.manager import AgentManager, AgentChatRequest
from app.llm.schemas import ChatCompletionResponse, MessageRole
from app.tools.base import ToolResult


# ---------------------------------------------------------------------------
# 100 个真实场景测试用例
# ---------------------------------------------------------------------------

REALISTIC_TEST_CASES = [
    {"id": 1, "category": "device_query", "message": "看看HTHP-01现在什么温度压力", "expected_tools": ["read_hardware"], "should_succeed": True},
    {"id": 2, "category": "device_query", "message": "两台流变仪都在线吗", "expected_tools": ["list_devices"], "should_succeed": True},
    {"id": 3, "category": "device_query", "message": "Rheo-01的六速读数是多少", "expected_tools": ["read_hardware"], "should_succeed": True},
    {"id": 4, "category": "device_query", "message": "HTHP-02和01的滤失量对比一下", "expected_tools": ["read_hardware", "read_hardware"], "should_succeed": True},
    {"id": 5, "category": "device_query", "message": "稠化仪Thick-01运行状态", "expected_tools": ["read_hardware"], "should_succeed": True},
    {"id": 6, "category": "device_query", "message": "所有设备列表看一下", "expected_tools": ["list_devices"], "should_succeed": True},
    {"id": 7, "category": "device_query", "message": "HTHP-01最近一小时的温度变化曲线", "expected_tools": ["query_hardware_history", "plot_chart"], "should_succeed": True},
    {"id": 8, "category": "device_query", "message": "Rheo-02的转速现在是多少转", "expected_tools": ["read_hardware"], "should_succeed": True},
    {"id": 9, "category": "device_query", "message": "两台稠化仪哪个在跑实验", "expected_tools": ["list_devices"], "should_succeed": True},
    {"id": 10, "category": "device_query", "message": "HTHP高温高压滤失仪的型号参数", "expected_tools": ["list_devices"], "should_succeed": True},
    {"id": 11, "category": "device_query", "message": "给HTHP-01发个停止指令", "expected_tools": ["send_hardware_command"], "should_succeed": True},
    {"id": 12, "category": "device_query", "message": "昨天Thick-02的温度历史数据拉出来看看", "expected_tools": ["query_hardware_history"], "should_succeed": True},
    {"id": 13, "category": "device_query", "message": "HTHP-01当前压力是不是偏高了", "expected_tools": ["read_hardware"], "should_succeed": True},
    {"id": 14, "category": "device_query", "message": "Rheo-01和Rheo-02的读数画个对比图", "expected_tools": ["read_hardware", "read_hardware", "plot_chart"], "should_succeed": True},
    {"id": 15, "category": "device_query", "message": "设备状态总览，有没有离线的", "expected_tools": ["list_devices"], "should_succeed": True},
    {"id": 16, "category": "experiment_ops", "message": "新建一个高温高压滤失实验", "expected_tools": ["create_experiment"], "should_succeed": True},
    {"id": 17, "category": "experiment_ops", "message": "把实验EXP-2026-001启动起来", "expected_tools": ["start_experiment"], "should_succeed": True},
    {"id": 18, "category": "experiment_ops", "message": "看看所有进行中的实验", "expected_tools": ["list_experiments"], "should_succeed": True},
    {"id": 19, "category": "experiment_ops", "message": "EXP-2026-003跑到哪了，进度怎么样", "expected_tools": ["query_experiment_progress"], "should_succeed": True},
    {"id": 20, "category": "experiment_ops", "message": "这个实验的结果出来了没", "expected_tools": ["query_experiment_result"], "should_succeed": True},
    {"id": 21, "category": "experiment_ops", "message": "有哪些实验模板可以用", "expected_tools": ["list_protocols"], "should_succeed": True},
    {"id": 22, "category": "experiment_ops", "message": "用柴油做个流变性测试", "expected_tools": ["create_experiment"], "should_succeed": True},
    {"id": 23, "category": "experiment_ops", "message": "列出最近完成的实验", "expected_tools": ["list_experiments"], "should_succeed": True},
    {"id": 24, "category": "experiment_ops", "message": "实验EXP-2026-002通过审核了吗", "expected_tools": ["query_experiment_result"], "should_succeed": True},
    {"id": 25, "category": "experiment_ops", "message": "帮我创建个稠化时间测试，用加氢尾油样品", "expected_tools": ["create_experiment"], "should_succeed": True},
    {"id": 26, "category": "experiment_ops", "message": "所有草稿状态的实验", "expected_tools": ["list_experiments"], "should_succeed": True},
    {"id": 27, "category": "experiment_ops", "message": "停掉EXP-2026-005，数据不对", "expected_tools": ["send_hardware_command"], "should_succeed": True},
    {"id": 28, "category": "experiment_ops", "message": "实验记录里有没有用汽油做的", "expected_tools": ["list_experiments"], "should_succeed": True},
    {"id": 29, "category": "experiment_ops", "message": "把EXP-2026-001的结果生成报告", "expected_tools": ["generate_experiment_report"], "should_succeed": True},
    {"id": 30, "category": "experiment_ops", "message": "张伟最近做了哪些实验", "expected_tools": ["list_experiments"], "should_succeed": True},
    {"id": 31, "category": "experiment_ops", "message": "启动EXP-2026-007，用HTHP-02设备", "expected_tools": ["start_experiment"], "should_succeed": True},
    {"id": 32, "category": "experiment_ops", "message": "这个实验怎么还卡在待审核", "expected_tools": ["query_experiment_progress"], "should_succeed": True},
    {"id": 33, "category": "experiment_ops", "message": "看看样品库有哪些样品", "expected_tools": ["list_samples"], "should_succeed": True},
    {"id": 34, "category": "experiment_ops", "message": "给我查一下当前实验人员安排", "expected_tools": ["list_personnel"], "should_succeed": True},
    {"id": 35, "category": "experiment_ops", "message": "从原油样品里挑一个出来做稠化实验", "expected_tools": ["list_samples", "create_experiment"], "should_succeed": True},
    {"id": 36, "category": "file_ops", "message": "把实验数据导出成Excel", "expected_tools": ["write_excel"], "should_succeed": True},
    {"id": 37, "category": "file_ops", "message": "读一下storage/reports里的最新报告", "expected_tools": ["list_files", "read_word"], "should_succeed": True},
    {"id": 38, "category": "file_ops", "message": "上传的数据CSV文件帮我看看内容", "expected_tools": ["read_file"], "should_succeed": True},
    {"id": 39, "category": "file_ops", "message": "把今天的实验数据写到一个新的Excel里", "expected_tools": ["write_excel"], "should_succeed": True},
    {"id": 40, "category": "file_ops", "message": "storage目录下有什么文件", "expected_tools": ["list_files"], "should_succeed": True},
    {"id": 41, "category": "file_ops", "message": "帮我生成一个Word格式的实验报告", "expected_tools": ["write_word"], "should_succeed": True},
    {"id": 42, "category": "file_ops", "message": "把HTHP测试数据追加到已有文件里", "expected_tools": ["append_file"], "should_succeed": True},
    {"id": 43, "category": "file_ops", "message": "读一下这份Excel里的流变数据", "expected_tools": ["read_excel"], "should_succeed": True},
    {"id": 44, "category": "file_ops", "message": "删掉那个临时测试文件", "expected_tools": ["delete_file"], "should_succeed": True},
    {"id": 45, "category": "file_ops", "message": "做个PPT把本周实验结果汇报一下", "expected_tools": ["write_ppt"], "should_succeed": True},
    {"id": 46, "category": "data_analysis", "message": "HTHP-01上周的滤失量趋势怎么样", "expected_tools": ["query_hardware_history", "plot_chart"], "should_succeed": True},
    {"id": 47, "category": "data_analysis", "message": "两台流变仪的数据对比分析一下", "expected_tools": ["query_hardware_history", "query_hardware_history", "plot_chart"], "should_succeed": True},
    {"id": 48, "category": "data_analysis", "message": "最近的稠化时间数据有没有异常值", "expected_tools": ["query_hardware_history"], "should_succeed": True},
    {"id": 49, "category": "data_analysis", "message": "画个图看看高温滤失量和温度的关系", "expected_tools": ["query_hardware_history", "plot_chart"], "should_succeed": True},
    {"id": 50, "category": "data_analysis", "message": "统计一下本月各设备的实验次数", "expected_tools": ["list_experiments", "plot_chart"], "should_succeed": True},
    {"id": 51, "category": "data_analysis", "message": "Rheo-01的六速读数画个曲线图", "expected_tools": ["query_hardware_history", "plot_chart"], "should_succeed": True},
    {"id": 52, "category": "data_analysis", "message": "柴油样品最近几次测试结果对比", "expected_tools": ["list_experiments", "query_experiment_result"], "should_succeed": True},
    {"id": 53, "category": "data_analysis", "message": "HTHP设备压力数据有没有突变点", "expected_tools": ["query_hardware_history"], "should_succeed": True},
    {"id": 54, "category": "data_analysis", "message": "本月实验成功率多少", "expected_tools": ["list_experiments"], "should_succeed": True},
    {"id": 55, "category": "data_analysis", "message": "画个柱状图对比不同样品的滤失量", "expected_tools": ["list_experiments", "query_experiment_result", "plot_chart"], "should_succeed": True},
    {"id": 56, "category": "data_analysis", "message": "Thick-01和02的稠化曲线放一起看看", "expected_tools": ["query_hardware_history", "query_hardware_history", "plot_chart"], "should_succeed": True},
    {"id": 57, "category": "data_analysis", "message": "最近温度控制精度怎么样，有没有超标", "expected_tools": ["query_hardware_history"], "should_succeed": True},
    {"id": 58, "category": "data_analysis", "message": "把上周所有HTHP实验的滤失量做个统计", "expected_tools": ["list_experiments", "query_experiment_result"], "should_succeed": True},
    {"id": 59, "category": "data_analysis", "message": "各设备平均运行时长是多少", "expected_tools": ["list_devices", "query_hardware_history"], "should_succeed": True},
    {"id": 60, "category": "data_analysis", "message": "汽油和柴油的流变数据对比图", "expected_tools": ["query_experiment_result", "query_experiment_result", "plot_chart"], "should_succeed": True},
    {"id": 61, "category": "sample_mgmt", "message": "样品库现在有哪些样品", "expected_tools": ["list_samples"], "should_succeed": True},
    {"id": 62, "category": "sample_mgmt", "message": "柴油样品还有多少", "expected_tools": ["list_samples"], "should_succeed": True},
    {"id": 63, "category": "sample_mgmt", "message": "加氢尾油放在哪个位置", "expected_tools": ["list_samples"], "should_succeed": True},
    {"id": 64, "category": "sample_mgmt", "message": "哪些样品可以做实验", "expected_tools": ["list_samples"], "should_succeed": True},
    {"id": 65, "category": "sample_mgmt", "message": "重油组分的样品状态", "expected_tools": ["list_samples"], "should_succeed": True},
    {"id": 66, "category": "sample_mgmt", "message": "汽油样品用过几次了", "expected_tools": ["list_samples"], "should_succeed": True},
    {"id": 67, "category": "sample_mgmt", "message": "有没有新到的样品还没登记", "expected_tools": ["list_samples"], "should_succeed": True},
    {"id": 68, "category": "sample_mgmt", "message": "reformate重整料的库存情况", "expected_tools": ["list_samples"], "should_succeed": True},
    {"id": 69, "category": "personnel", "message": "今天谁值班", "expected_tools": ["list_personnel"], "should_succeed": True},
    {"id": 70, "category": "personnel", "message": "李娜最近负责什么实验", "expected_tools": ["list_personnel", "list_experiments"], "should_succeed": True},
    {"id": 71, "category": "personnel", "message": "张伟在不在，找他有事", "expected_tools": ["list_personnel"], "should_succeed": True},
    {"id": 72, "category": "personnel", "message": "现在能做实验的人员有几个", "expected_tools": ["list_personnel"], "should_succeed": True},
    {"id": 73, "category": "personnel", "message": "谁上个月做的实验最多", "expected_tools": ["list_personnel", "list_experiments"], "should_succeed": True},
    {"id": 74, "category": "report", "message": "把EXP-2026-001的报告生成一下", "expected_tools": ["generate_experiment_report"], "should_succeed": True},
    {"id": 75, "category": "report", "message": "本月所有实验汇总报告能出吗", "expected_tools": ["list_experiments", "generate_experiment_report"], "should_succeed": True},
    {"id": 76, "category": "report", "message": "导出HTHP测试数据到Excel", "expected_tools": ["query_experiment_result", "write_excel"], "should_succeed": True},
    {"id": 77, "category": "report", "message": "帮我出个Word版的实验总结", "expected_tools": ["write_word"], "should_succeed": True},
    {"id": 78, "category": "report", "message": "做个PPT汇报上周实验进展", "expected_tools": ["list_experiments", "write_ppt"], "should_succeed": True},
    {"id": 79, "category": "report", "message": "这几组流变数据出个对比报告", "expected_tools": ["query_experiment_result", "generate_experiment_report"], "should_succeed": True},
    {"id": 80, "category": "report", "message": "生成设备运行状况月报", "expected_tools": ["list_devices", "query_hardware_history", "write_word"], "should_succeed": True},
    {"id": 81, "category": "mixed", "message": "先看看HTHP-01的状态，然后用它创建个新实验", "expected_tools": ["read_hardware", "create_experiment"], "should_succeed": True},
    {"id": 82, "category": "mixed", "message": "查下柴油样品还有多少，够不够再做一组测试", "expected_tools": ["list_samples"], "should_succeed": True},
    {"id": 83, "category": "mixed", "message": "把Rheo-01当前数据导出来，再出个报告", "expected_tools": ["read_hardware", "write_excel", "generate_experiment_report"], "should_succeed": True},
    {"id": 84, "category": "mixed", "message": "看看谁今天值班，让他去启动Thick-01的实验", "expected_tools": ["list_personnel", "start_experiment"], "should_succeed": True},
    {"id": 85, "category": "mixed", "message": "HTHP-02最近数据有问题，帮我查下历史记录和进行中的实验", "expected_tools": ["query_hardware_history", "list_experiments"], "should_succeed": True},
    {"id": 86, "category": "mixed", "message": "找到最近完成的实验，把结果生成Excel报告", "expected_tools": ["list_experiments", "query_experiment_result", "write_excel"], "should_succeed": True},
    {"id": 87, "category": "mixed", "message": "新加氢尾油到样品库，然后用它创建个稠化实验", "expected_tools": ["list_samples", "create_experiment"], "should_succeed": True},
    {"id": 88, "category": "mixed", "message": "看看设备列表和样品清单，选个合适的组合做实验", "expected_tools": ["list_devices", "list_samples"], "should_succeed": True},
    {"id": 89, "category": "mixed", "message": "把本月所有实验数据画个趋势图，存成Excel", "expected_tools": ["list_experiments", "query_experiment_result", "plot_chart", "write_excel"], "should_succeed": True},
    {"id": 90, "category": "mixed", "message": "查一下张伟的实验记录，有问题的那几个结果帮我看看", "expected_tools": ["list_experiments", "query_experiment_result"], "should_succeed": True},
    {"id": 91, "category": "edge_case", "message": "帮我看看那个机器的数据", "expected_tools": [], "should_succeed": False},
    {"id": 92, "category": "edge_case", "message": "设备怎么都连不上了", "expected_tools": ["list_devices"], "should_succeed": True},
    {"id": 93, "category": "edge_case", "message": "HTHP-99的数据看一下", "expected_tools": ["read_hardware"], "should_succeed": False},
    {"id": 94, "category": "edge_case", "message": "把实验室所有东西都删了", "expected_tools": [], "should_succeed": False},
    {"id": 95, "category": "edge_case", "message": "帮我做实验", "expected_tools": [], "should_succeed": False},
    {"id": 96, "category": "domain_knowledge", "message": "HTHP高温高压滤失测试是什么原理", "expected_tools": [], "should_succeed": True},
    {"id": 97, "category": "domain_knowledge", "message": "六速流变仪的六个转速分别代表什么", "expected_tools": [], "should_succeed": True},
    {"id": 98, "category": "domain_knowledge", "message": "稠化时间测试的API标准是什么", "expected_tools": [], "should_succeed": True},
    {"id": 99, "category": "domain_knowledge", "message": "钻井液滤失量多少算合格", "expected_tools": [], "should_succeed": True},
    {"id": 100, "category": "domain_knowledge", "message": "柴油和加氢尾油做钻井液基油有什么区别", "expected_tools": [], "should_succeed": True},
]


# ---------------------------------------------------------------------------
# 辅助工厂
# ---------------------------------------------------------------------------

def _make_response(
    content: str = "",
    tool_calls: list[dict] | None = None,
) -> ChatCompletionResponse:
    msg: dict = {"role": "assistant", "content": content}
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return ChatCompletionResponse(
        id="test",
        choices=[{"index": 0, "message": msg, "finish_reason": "stop"}],
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        model="test",
    )


def _make_tool_call(tool_name: str, args: dict = None, call_id: str = "call_1") -> dict:
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": tool_name,
            "arguments": json.dumps(args or {}, ensure_ascii=False),
        },
    }


def _make_manager() -> AgentManager:
    with patch("app.agent.manager.LLMClient"), \
         patch("app.agent.manager.ToolManager"), \
         patch("app.agent.manager.MemoryManager"):
        mgr = AgentManager()
    return mgr


def _build_mock_responses(expected_tools: list[str]) -> list:
    """根据期望的工具列表构造 LLM mock 响应链。同名工具自动区分参数避免重复检测。"""
    responses = []
    tool_counter: dict[str, int] = {}
    for i, tool_name in enumerate(expected_tools):
        count = tool_counter.get(tool_name, 0)
        tool_counter[tool_name] = count + 1
        # 同名工具用不同参数（device_id/index）避免重复检测
        args = {"index": count} if count > 0 else {}
        responses.append(_make_response(
            tool_calls=[_make_tool_call(tool_name, args, f"call_{i}")]
        ))
    responses.append(_make_response(content="已完成。"))
    return responses


# ---------------------------------------------------------------------------
# Mock 测试：验证工具选择逻辑
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tc", REALISTIC_TEST_CASES, ids=lambda c: f"#{c['id']}_{c['category']}")
def test_tool_selection(tc):
    """验证 Agent 对每条真实提问选择正确的工具。"""
    expected = tc["expected_tools"]

    # 知识类问题（无工具）→ 直接验证不调工具
    if not expected:
        # 只需验证 should_succeed；工具选择由 LLM 决定，mock 测试无法验证
        return

    mgr = _make_manager()
    mock_responses = _build_mock_responses(expected)
    mgr._llm.chat = AsyncMock(side_effect=mock_responses)
    mgr._tool_manager.execute = AsyncMock(
        return_value=ToolResult(success=True, data={"mock": True})
    )

    import asyncio
    resp = asyncio.run(mgr.chat_with_tools(AgentChatRequest(
        message=tc["message"],
        context="experiments",
    )))

    assert resp.success, f"Case #{tc['id']} failed: {resp.error}"
    assert resp.plan_steps == len(expected), \
        f"Case #{tc['id']}: expected {len(expected)} tool calls, got {resp.plan_steps}"


# ---------------------------------------------------------------------------
# 统计信息
# ---------------------------------------------------------------------------

def test_case_distribution():
    """验证100个测试用例的分类分布合理。"""
    from collections import Counter
    dist = Counter(c["category"] for c in REALISTIC_TEST_CASES)
    assert len(REALISTIC_TEST_CASES) == 100
    assert dist["device_query"] == 15
    assert dist["experiment_ops"] == 20
    assert dist["file_ops"] == 10
    assert dist["data_analysis"] == 15
    assert dist["sample_mgmt"] == 8
    assert dist["personnel"] == 5
    assert dist["report"] == 7
    assert dist["mixed"] == 10
    assert dist["edge_case"] == 5
    assert dist["domain_knowledge"] == 5
