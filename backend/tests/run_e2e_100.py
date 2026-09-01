"""
100 个真实场景 E2E 测试 —— 对 DeepSeek API 端到端验证。

用法：
    cd backend
    .venv/Scripts/python.exe tests/run_e2e_100.py

输出：
    - 实时打印进度（每完成一个用例）
    - 最终结果写入 tests/e2e_100_results.json
    - 控制台打印汇总统计

预计耗时：5-15 分钟（取决于 DeepSeek API 响应速度）
预计 token：约 10-20 万 tokens（DeepSeek-chat 价格很低）
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# 确保能导入 app 模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agent.manager import AgentManager, AgentChatRequest


# ---------------------------------------------------------------------------
# 100 个测试用例
# ---------------------------------------------------------------------------

CASES = [
    # === 设备查询 (15) ===
    {"id": 1, "cat": "device", "msg": "看看HTHP-01现在什么温度压力", "expect": "tool"},
    {"id": 2, "cat": "device", "msg": "两台流变仪都在线吗", "expect": "tool"},
    {"id": 3, "cat": "device", "msg": "Rheo-01的六速读数是多少", "expect": "tool"},
    {"id": 4, "cat": "device", "msg": "HTHP-02和01的滤失量对比一下", "expect": "tool"},
    {"id": 5, "cat": "device", "msg": "稠化仪Thick-01运行状态", "expect": "tool"},
    {"id": 6, "cat": "device", "msg": "所有设备列表看一下", "expect": "tool"},
    {"id": 7, "cat": "device", "msg": "HTHP-01最近一小时的温度变化曲线", "expect": "tool"},
    {"id": 8, "cat": "device", "msg": "Rheo-02的转速现在是多少转", "expect": "tool"},
    {"id": 9, "cat": "device", "msg": "两台稠化仪哪个在跑实验", "expect": "tool"},
    {"id": 10, "cat": "device", "msg": "HTHP高温高压滤失仪的型号参数", "expect": "tool"},
    {"id": 11, "cat": "device", "msg": "给HTHP-01发个停止指令", "expect": "tool"},
    {"id": 12, "cat": "device", "msg": "昨天Thick-02的温度历史数据拉出来看看", "expect": "tool"},
    {"id": 13, "cat": "device", "msg": "HTHP-01当前压力是不是偏高了", "expect": "tool"},
    {"id": 14, "cat": "device", "msg": "Rheo-01和Rheo-02的读数画个对比图", "expect": "tool"},
    {"id": 15, "cat": "device", "msg": "设备状态总览，有没有离线的", "expect": "tool"},
    # === 实验操作 (20) ===
    {"id": 16, "cat": "experiment", "msg": "新建一个高温高压滤失实验", "expect": "tool"},
    {"id": 17, "cat": "experiment", "msg": "把实验EXP-2026-001启动起来", "expect": "tool"},
    {"id": 18, "cat": "experiment", "msg": "看看所有进行中的实验", "expect": "tool"},
    {"id": 19, "cat": "experiment", "msg": "EXP-2026-003跑到哪了，进度怎么样", "expect": "tool"},
    {"id": 20, "cat": "experiment", "msg": "最新实验的结果出来了没", "expect": "tool"},
    {"id": 21, "cat": "experiment", "msg": "有哪些实验模板可以用", "expect": "tool"},
    {"id": 22, "cat": "experiment", "msg": "用柴油做个流变性测试", "expect": "tool"},
    {"id": 23, "cat": "experiment", "msg": "列出最近完成的实验", "expect": "tool"},
    {"id": 24, "cat": "experiment", "msg": "实验EXP-2026-002通过审核了吗", "expect": "tool"},
    {"id": 25, "cat": "experiment", "msg": "帮我创建个稠化时间测试，用加氢尾油样品", "expect": "tool"},
    {"id": 26, "cat": "experiment", "msg": "所有草稿状态的实验", "expect": "tool"},
    {"id": 27, "cat": "experiment", "msg": "停掉EXP-2026-005，数据不对", "expect": "tool"},
    {"id": 28, "cat": "experiment", "msg": "实验记录里有没有用汽油做的", "expect": "tool"},
    {"id": 29, "cat": "experiment", "msg": "把EXP-2026-001的结果生成报告", "expect": "tool"},
    {"id": 30, "cat": "experiment", "msg": "张伟最近做了哪些实验", "expect": "tool"},
    {"id": 31, "cat": "experiment", "msg": "启动EXP-2026-007，用HTHP-02设备", "expect": "tool"},
    {"id": 32, "cat": "experiment", "msg": "这个实验怎么还卡在待审核", "expect": "tool"},
    {"id": 33, "cat": "experiment", "msg": "看看样品库有哪些样品", "expect": "tool"},
    {"id": 34, "cat": "experiment", "msg": "给我查一下当前实验人员安排", "expect": "tool"},
    {"id": 35, "cat": "experiment", "msg": "从原油样品里挑一个出来做稠化实验", "expect": "tool"},
    # === 文件操作 (10) ===
    {"id": 36, "cat": "file", "msg": "把实验数据导出成Excel", "expect": "tool"},
    {"id": 37, "cat": "file", "msg": "读一下storage/reports里的最新报告", "expect": "tool"},
    {"id": 38, "cat": "file", "msg": "上传的数据CSV文件帮我看看内容", "expect": "tool"},
    {"id": 39, "cat": "file", "msg": "把今天的实验数据写到一个新的Excel里", "expect": "tool"},
    {"id": 40, "cat": "file", "msg": "storage目录下有什么文件", "expect": "tool"},
    {"id": 41, "cat": "file", "msg": "帮我生成一个Word格式的实验报告", "expect": "tool"},
    {"id": 42, "cat": "file", "msg": "把HTHP测试数据追加到已有文件里", "expect": "tool"},
    {"id": 43, "cat": "file", "msg": "读一下这份Excel里的流变数据", "expect": "tool"},
    {"id": 44, "cat": "file", "msg": "删掉那个临时测试文件", "expect": "tool"},
    {"id": 45, "cat": "file", "msg": "做个PPT把本周实验结果汇报一下", "expect": "tool"},
    # === 数据分析 (15) ===
    {"id": 46, "cat": "analysis", "msg": "HTHP-01上周的滤失量趋势怎么样", "expect": "tool"},
    {"id": 47, "cat": "analysis", "msg": "两台流变仪的数据对比分析一下", "expect": "tool"},
    {"id": 48, "cat": "analysis", "msg": "最近的稠化时间数据有没有异常值", "expect": "tool"},
    {"id": 49, "cat": "analysis", "msg": "画个图看看高温滤失量和温度的关系", "expect": "tool"},
    {"id": 50, "cat": "analysis", "msg": "统计一下本月各设备的实验次数", "expect": "tool"},
    {"id": 51, "cat": "analysis", "msg": "Rheo-01的六速读数画个曲线图", "expect": "tool"},
    {"id": 52, "cat": "analysis", "msg": "柴油样品最近几次测试结果对比", "expect": "tool"},
    {"id": 53, "cat": "analysis", "msg": "HTHP设备压力数据有没有突变点", "expect": "tool"},
    {"id": 54, "cat": "analysis", "msg": "本月实验成功率多少", "expect": "tool"},
    {"id": 55, "cat": "analysis", "msg": "画个柱状图对比不同样品的滤失量", "expect": "tool"},
    {"id": 56, "cat": "analysis", "msg": "Thick-01和02的稠化曲线放一起看看", "expect": "tool"},
    {"id": 57, "cat": "analysis", "msg": "最近温度控制精度怎么样，有没有超标", "expect": "tool"},
    {"id": 58, "cat": "analysis", "msg": "把上周所有HTHP实验的滤失量做个统计", "expect": "tool"},
    {"id": 59, "cat": "analysis", "msg": "各设备平均运行时长是多少", "expect": "tool"},
    {"id": 60, "cat": "analysis", "msg": "汽油和柴油的流变数据对比图", "expect": "tool"},
    # === 样品管理 (8) ===
    {"id": 61, "cat": "sample", "msg": "样品库现在有哪些样品", "expect": "tool"},
    {"id": 62, "cat": "sample", "msg": "柴油样品还有多少", "expect": "tool"},
    {"id": 63, "cat": "sample", "msg": "加氢尾油放在哪个位置", "expect": "tool"},
    {"id": 64, "cat": "sample", "msg": "哪些样品可以做实验", "expect": "tool"},
    {"id": 65, "cat": "sample", "msg": "重油组分的样品状态", "expect": "tool"},
    {"id": 66, "cat": "sample", "msg": "汽油样品用过几次了", "expect": "tool"},
    {"id": 67, "cat": "sample", "msg": "有没有新到的样品还没登记", "expect": "tool"},
    {"id": 68, "cat": "sample", "msg": "reformate重整料的库存情况", "expect": "tool"},
    # === 人员 (5) ===
    {"id": 69, "cat": "personnel", "msg": "今天谁值班", "expect": "tool"},
    {"id": 70, "cat": "personnel", "msg": "李娜最近负责什么实验", "expect": "tool"},
    {"id": 71, "cat": "personnel", "msg": "张伟在不在，找他有事", "expect": "tool"},
    {"id": 72, "cat": "personnel", "msg": "现在能做实验的人员有几个", "expect": "tool"},
    {"id": 73, "cat": "personnel", "msg": "谁上个月做的实验最多", "expect": "tool"},
    # === 报告 (7) ===
    {"id": 74, "cat": "report", "msg": "把EXP-2026-001的报告生成一下", "expect": "tool"},
    {"id": 75, "cat": "report", "msg": "本月所有实验汇总报告能出吗", "expect": "tool"},
    {"id": 76, "cat": "report", "msg": "导出HTHP测试数据到Excel", "expect": "tool"},
    {"id": 77, "cat": "report", "msg": "帮我出个Word版的实验总结", "expect": "tool"},
    {"id": 78, "cat": "report", "msg": "做个PPT汇报上周实验进展", "expect": "tool"},
    {"id": 79, "cat": "report", "msg": "这几组流变数据出个对比报告", "expect": "tool"},
    {"id": 80, "cat": "report", "msg": "生成设备运行状况月报", "expect": "tool"},
    # === 混合 (10) ===
    {"id": 81, "cat": "mixed", "msg": "先看看HTHP-01的状态，然后用它创建个新实验", "expect": "tool"},
    {"id": 82, "cat": "mixed", "msg": "查下柴油样品还有多少，够不够再做一组测试", "expect": "tool"},
    {"id": 83, "cat": "mixed", "msg": "把Rheo-01当前数据导出来，再出个报告", "expect": "tool"},
    {"id": 84, "cat": "mixed", "msg": "看看谁今天值班，让他去启动Thick-01的实验", "expect": "tool"},
    {"id": 85, "cat": "mixed", "msg": "HTHP-02最近数据有问题，帮我查下历史记录和进行中的实验", "expect": "tool"},
    {"id": 86, "cat": "mixed", "msg": "找到最近完成的实验，把结果生成Excel报告", "expect": "tool"},
    {"id": 87, "cat": "mixed", "msg": "新加氢尾油到样品库，然后用它创建个稠化实验", "expect": "tool"},
    {"id": 88, "cat": "mixed", "msg": "看看设备列表和样品清单，选个合适的组合做实验", "expect": "tool"},
    {"id": 89, "cat": "mixed", "msg": "把本月所有实验数据画个趋势图，存成Excel", "expect": "tool"},
    {"id": 90, "cat": "mixed", "msg": "查一下张伟的实验记录，有问题的那几个结果帮我看看", "expect": "tool"},
    # === 边界 (5) ===
    {"id": 91, "cat": "edge", "msg": "帮我看看那个机器的数据", "expect": "ambiguous"},
    {"id": 92, "cat": "edge", "msg": "设备怎么都连不上了", "expect": "tool"},
    {"id": 93, "cat": "edge", "msg": "HTHP-99的数据看一下", "expect": "tool"},
    {"id": 94, "cat": "edge", "msg": "把实验室所有东西都删了", "expect": "refuse"},
    {"id": 95, "cat": "edge", "msg": "帮我做实验", "expect": "ambiguous"},
    # === 领域知识 (5) ===
    {"id": 96, "cat": "knowledge", "msg": "HTHP高温高压滤失测试是什么原理", "expect": "no_tool"},
    {"id": 97, "cat": "knowledge", "msg": "六速流变仪的六个转速分别代表什么", "expect": "no_tool"},
    {"id": 98, "cat": "knowledge", "msg": "稠化时间测试的API标准是什么", "expect": "no_tool"},
    {"id": 99, "cat": "knowledge", "msg": "钻井液滤失量多少算合格", "expect": "no_tool"},
    {"id": 100, "cat": "knowledge", "msg": "柴油和加氢尾油做钻井液基油有什么区别", "expect": "no_tool"},
]


# ---------------------------------------------------------------------------
# 运行器
# ---------------------------------------------------------------------------

async def run_single(mgr: AgentManager, case: dict) -> dict:
    """运行单个测试用例，返回结果。"""
    t0 = time.monotonic()
    try:
        resp = await mgr.chat_with_tools(AgentChatRequest(
            message=case["msg"],
            context="experiments",
        ))
        elapsed = time.monotonic() - t0

        used_tool = resp.plan_used
        expect = case["expect"]

        # 判定逻辑
        if expect == "tool":
            ok = used_tool and resp.success
        elif expect == "no_tool":
            ok = not used_tool and resp.success
        elif expect == "refuse":
            ok = resp.success  # Agent 应该正常回答（拒绝或警告）
        else:  # ambiguous
            ok = resp.success  # 只要不崩就算过

        return {
            "id": case["id"],
            "cat": case["cat"],
            "msg": case["msg"],
            "expect": expect,
            "used_tool": used_tool,
            "steps": resp.plan_steps,
            "ms": int(elapsed * 1000),
            "ok": ok,
            "resp_preview": resp.response[:150] if resp.response else "",
            "error": resp.error,
        }
    except Exception as exc:
        elapsed = time.monotonic() - t0
        return {
            "id": case["id"],
            "cat": case["cat"],
            "msg": case["msg"],
            "expect": case["expect"],
            "used_tool": False,
            "steps": 0,
            "ms": int(elapsed * 1000),
            "ok": False,
            "resp_preview": "",
            "error": str(exc),
        }


async def main():
    print(f"=== OilChem Agent E2E 100 测试 ===")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"用例数: {len(CASES)}")
    print()

    mgr = AgentManager()
    results = []
    pass_count = 0
    fail_count = 0
    total_ms = 0

    for i, case in enumerate(CASES):
        result = await run_single(mgr, case)
        results.append(result)

        status = "PASS" if result["ok"] else "FAIL"
        if result["ok"]:
            pass_count += 1
        else:
            fail_count += 1
        total_ms += result["ms"]

        # 实时输出
        steps_str = f"{result['steps']}步" if result["used_tool"] else "直接答"
        print(
            f"[{i+1:3d}/100] {status} #{result['id']:3d} "
            f"{result['cat']:10s} {result['ms']:5d}ms {steps_str:5s} "
            f"{result['msg'][:35]}"
        )

    # 汇总
    print()
    print(f"=== 汇总 ===")
    print(f"通过: {pass_count}/100")
    print(f"失败: {fail_count}/100")
    print(f"总耗时: {total_ms/1000:.1f}s ({total_ms/60000:.1f}min)")
    print(f"平均: {total_ms/len(CASES):.0f}ms/条")

    # 按类别统计
    from collections import Counter
    cat_total = Counter(r["cat"] for r in results)
    cat_pass = Counter(r["cat"] for r in results if r["ok"])
    print()
    print(f"{'类别':12s} {'通过':>4s} / {'总数':>4s}  {'通过率':>6s}")
    print("-" * 35)
    for cat in cat_total:
        p = cat_pass.get(cat, 0)
        t = cat_total[cat]
        print(f"{cat:12s} {p:4d} / {t:4d}  {p/t*100:5.1f}%")

    # 失败详情
    fails = [r for r in results if not r["ok"]]
    if fails:
        print()
        print(f"=== 失败详情 ({len(fails)}个) ===")
        for r in fails:
            print(f"  #{r['id']} [{r['cat']}] {r['msg'][:40]}")
            print(f"    expect={r['expect']} used_tool={r['used_tool']} steps={r['steps']}")
            if r["error"]:
                print(f"    error: {r['error'][:80]}")

    # 保存结果
    output_path = Path(__file__).parent / "e2e_100_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total": len(CASES),
                "pass": pass_count,
                "fail": fail_count,
                "total_ms": total_ms,
                "avg_ms": total_ms // len(CASES),
            },
            "by_category": {
                cat: {"pass": cat_pass.get(cat, 0), "total": cat_total[cat]}
                for cat in cat_total
            },
            "failures": fails,
            "results": results,
        }, f, ensure_ascii=False, indent=2)

    print()
    print(f"结果已保存: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
