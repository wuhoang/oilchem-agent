/**
 * 实验中心面板（M5 三视角）。
 *
 * 集成看板、方案库、实验工作台：
 * - 看板：实验列表 + 状态统计
 * - 方案库：浏览实验方案
 * - 工作台：选择方案 → 一键开始实验 → 查看进度 + 数据
 */

import { useCallback, useEffect, useState } from "react";
import {
  fetchProtocols,
  fetchExperiments,
  createExperiment,
  startExperiment,
  abortExperiment,
  approveExperiment,
  rejectExperiment,
  fetchExperimentDetail,
  fetchExperimentMeasurements,
  fetchDashboard,
  fetchExperimenters,
  fetchReviewers,
  fetchExperimentReport,
  type Protocol,
  type Experiment,
  type ExperimentStep,
  type Measurement,
  type Experimenter,
  type AuditEvent,
  getToken,
} from "../services/api";
import { notifyError } from "./ErrorToast";

const STATUS_COLOR: Record<string, string> = {
  草稿: "bg-slate-100 text-slate-600",
  待执行: "bg-blue-100 text-blue-700",
  执行中: "bg-amber-100 text-amber-700",
  待审核: "bg-violet-100 text-violet-700",
  已完成: "bg-emerald-100 text-emerald-700",
  已驳回: "bg-orange-100 text-orange-700",
  异常: "bg-red-100 text-red-700",
  中止: "bg-slate-200 text-slate-600",
};

export function ExperimentCenter() {
  const [protocols, setProtocols] = useState<Protocol[]>([]);
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [experimenters, setExperimenters] = useState<Experimenter[]>([]);
  const [reviewers, setReviewers] = useState<Experimenter[]>([]);
  const [selectedProtocol, setSelectedProtocol] = useState<string>("");
  const [selectedExperiment, setSelectedExperiment] = useState<string>("");
  const [selectedOperator, setSelectedOperator] = useState<string>("");
  const [selectedReviewer, setSelectedReviewer] = useState<string>("");
  const [sampleCode, setSampleCode] = useState<string>("");
  const [detail, setDetail] = useState<{ experiment: Experiment; steps: ExperimentStep[]; audits?: AuditEvent[] } | null>(null);
  const [measurements, setMeasurements] = useState<Measurement[]>([]);
  const [stats, setStats] = useState<{ total_experiments: number; status_count: Record<string, number> }>({
    total_experiments: 0,
    status_count: {},
  });

  const loadAll = useCallback(async () => {
    try {
      const [p, e, d, ex, rv] = await Promise.all([fetchProtocols(), fetchExperiments(), fetchDashboard(), fetchExperimenters(), fetchReviewers()]);
      setProtocols(p.protocols);
      setExperiments(e.experiments);
      setStats(d);
      setExperimenters(ex.experimenters);
      setReviewers(rv.reviewers);
      if (!selectedOperator && ex.experimenters.length > 0) {
        setSelectedOperator(ex.experimenters[0].id);
      }
    } catch (err) {
      notifyError(String(err));
    }
  }, [selectedOperator]);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const [resultChart, setResultChart] = useState<{ image_base64: string; image_mime: string; chart_type: string } | null>(null);
  const [resultSummary, setResultSummary] = useState<Record<string, unknown> | null>(null);

  const refreshDetail = useCallback(async () => {
    if (!selectedExperiment) return;
    try {
      const [det, meas] = await Promise.all([
        fetchExperimentDetail(selectedExperiment),
        fetchExperimentMeasurements(selectedExperiment),
      ]);
      setDetail(det);
      setMeasurements(meas.measurements);
      // 解析 result 里的图表和摘要
      if (det.experiment.result) {
        try {
          const parsed = JSON.parse(det.experiment.result);
          if (parsed.chart?.image_base64) {
            setResultChart({
              image_base64: parsed.chart.image_base64,
              image_mime: parsed.chart.image_mime || "image/png",
              chart_type: parsed.chart.chart_type || "plot",
            });
          }
          if (parsed.summary) setResultSummary(parsed.summary);
        } catch {
          // result 解析失败忽略
        }
      }
    } catch (err) {
      // 测量数据可能为空
    }
  }, [selectedExperiment]);

  useEffect(() => {
    if (selectedExperiment) {
      refreshDetail();
      // SSE 订阅实验事件，实时更新（替换轮询）
      const token = getToken();
      const es = new EventSource(
        token
          ? `/api/v1/experiments/events?token=${encodeURIComponent(token)}`
          : "/api/v1/experiments/events",
      );
      es.onmessage = (e) => {
        try {
          const ev = JSON.parse(e.data);
          if (ev.type === "experiment_status" || ev.type === "step_status" || ev.type === "measurement") {
            if (ev.experiment_id === selectedExperiment) {
              refreshDetail();
            }
          }
        } catch {
          // 忽略非 JSON
        }
      };
      return () => es.close();
    }
  }, [selectedExperiment, refreshDetail]);

  const handleCreateAndStart = async () => {
    if (!selectedProtocol) {
      notifyError("请先选择一个实验方案");
      return;
    }
    if (!selectedOperator) {
      notifyError("请选择操作员");
      return;
    }
    try {
      const exp = await createExperiment({
        name: `实验 ${selectedProtocol}`,
        protocol_id: selectedProtocol,
        operator_id: selectedOperator,
        sample_code: sampleCode || undefined,
      });
      await startExperiment(exp.id);
      setSelectedExperiment(exp.id);
      await loadAll();
    } catch (err) {
      notifyError(String(err));
    }
  };

  const handleDownloadReport = async () => {
    if (!selectedExperiment) return;
    try {
      const r = await fetchExperimentReport(selectedExperiment);
      notifyError(`报告已生成：Word=${r.word_path}`);
    } catch (err) {
      notifyError(String(err));
    }
  };

  const handleAbort = async () => {
    if (!selectedExperiment) return;
    try {
      await abortExperiment(selectedExperiment);
      await loadAll();
      await refreshDetail();
    } catch (err) {
      notifyError(String(err));
    }
  };

  const reviewerId = selectedReviewer || selectedOperator;

  const handleApprove = async () => {
    if (!selectedExperiment) return;
    if (!reviewerId) {
      notifyError("请选择审核人");
      return;
    }
    try {
      await approveExperiment(selectedExperiment, reviewerId, "");
      await loadAll();
      await refreshDetail();
    } catch (err) {
      notifyError(String(err));
    }
  };

  const handleReject = async () => {
    if (!selectedExperiment) return;
    if (!reviewerId) {
      notifyError("请选择审核人");
      return;
    }
    const comment = window.prompt("请输入驳回意见：");
    if (comment === null) return;
    try {
      await rejectExperiment(selectedExperiment, reviewerId, comment);
      await loadAll();
      await refreshDetail();
    } catch (err) {
      notifyError(String(err));
    }
  };

  return (
    <div className="flex h-full w-full gap-4 p-4">
      {/* 左栏：方案库 */}
      <aside className="flex w-64 shrink-0 flex-col gap-2 rounded-xl border border-slate-200 bg-white p-3">
        <div className="mb-1 px-1 text-sm font-semibold text-slate-700">实验方案</div>
        {protocols.map((p) => (
          <button
            key={p.id}
            onClick={() => setSelectedProtocol(p.id)}
            className={`rounded-lg border px-3 py-2 text-left transition ${
              selectedProtocol === p.id
                ? "border-blue-300 bg-blue-50"
                : "border-transparent hover:border-slate-200 hover:bg-slate-50"
            }`}
          >
            <div className="text-sm font-medium text-slate-700">{p.name}</div>
            <div className="text-xs text-slate-500 line-clamp-2">{p.description}</div>
          </button>
        ))}
        <div className="mt-2 flex flex-col gap-2 border-t border-slate-100 pt-2">
          <label className="text-xs text-slate-500">
            操作员
            <select
              value={selectedOperator}
              onChange={(e) => setSelectedOperator(e.target.value)}
              className="mt-1 w-full rounded-md border border-slate-200 px-2 py-1 text-sm"
            >
              {experimenters.map((ex) => (
                <option key={ex.id} value={ex.id}>{ex.name}（{ex.role}）</option>
              ))}
            </select>
          </label>
          <label className="text-xs text-slate-500">
            样品号（可空）
            <input
              value={sampleCode}
              onChange={(e) => setSampleCode(e.target.value)}
              placeholder="如 S-2026-0801"
              className="mt-1 w-full rounded-md border border-slate-200 px-2 py-1 text-sm"
            />
          </label>
        </div>
        <button
          onClick={handleCreateAndStart}
          disabled={!selectedProtocol || !selectedOperator}
          className="mt-2 rounded-lg bg-blue-600 px-3 py-2 text-sm text-white transition hover:bg-blue-700 disabled:opacity-40"
        >
          一键开始实验
        </button>
      </aside>

      {/* 中栏：实验列表 + 看板统计 */}
      <section className="flex w-72 shrink-0 flex-col gap-2 rounded-xl border border-slate-200 bg-white p-3">
        <div className="flex items-center justify-between px-1">
          <span className="text-sm font-semibold text-slate-700">实验列表</span>
          <span className="text-xs text-slate-400">{stats.total_experiments} 个</span>
        </div>
        <div className="flex flex-wrap gap-1 px-1 pb-1">
          {Object.entries(stats.status_count).map(([k, v]) => (
            <span key={k} className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
              {k}: {v}
            </span>
          ))}
        </div>
        <div className="flex-1 overflow-auto">
          {experiments.map((e) => (
            <button
              key={e.id}
              onClick={() => setSelectedExperiment(e.id)}
              className={`mb-1 w-full rounded-lg border px-3 py-2 text-left transition ${
                selectedExperiment === e.id
                  ? "border-blue-300 bg-blue-50"
                  : "border-transparent hover:bg-slate-50"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-700 truncate">{e.name}</span>
                <span className={`ml-2 shrink-0 rounded px-1.5 py-0.5 text-xs ${STATUS_COLOR[e.status] || "bg-slate-100 text-slate-600"}`}>
                  {e.status}
                </span>
              </div>
              <div className="text-xs text-slate-400">{e.id}</div>
            </button>
          ))}
        </div>
      </section>

      {/* 右栏：实验详情 + 数据 */}
      <section className="flex min-w-0 flex-1 flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4">
        {selectedExperiment ? (
          <>
            <div className="flex items-center justify-between">
              <h2 className="text-base font-semibold text-slate-800">实验 {selectedExperiment}</h2>
              <div className="flex items-center gap-2">
                {detail?.experiment?.status === "待审核" && (
                  <>
                    <label className="flex items-center gap-1 text-xs text-slate-500">
                      审核人
                      <select
                        value={selectedReviewer || selectedOperator}
                        onChange={(e) => setSelectedReviewer(e.target.value)}
                        className="rounded-md border border-slate-200 px-2 py-1.5 text-sm text-slate-700"
                      >
                        {reviewers.map((rv) => (
                          <option key={rv.id} value={rv.id}>{rv.name}（{rv.role}）</option>
                        ))}
                      </select>
                    </label>
                    <button
                      onClick={handleApprove}
                      className="rounded-md border border-emerald-200 px-3 py-1.5 text-sm text-emerald-600 hover:bg-emerald-50"
                    >
                      审核通过
                    </button>
                    <button
                      onClick={handleReject}
                      className="rounded-md border border-orange-200 px-3 py-1.5 text-sm text-orange-600 hover:bg-orange-50"
                    >
                      审核驳回
                    </button>
                  </>
                )}
                {(detail?.experiment?.status === "待审核" || detail?.experiment?.status === "已完成") && (
                  <button
                    onClick={handleDownloadReport}
                    className="rounded-md border border-emerald-200 px-3 py-1.5 text-sm text-emerald-600 hover:bg-emerald-50"
                  >
                    生成/下载报告
                  </button>
                )}
                <button
                  onClick={handleAbort}
                  className="rounded-md border border-red-200 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50"
                >
                  中止实验
                </button>
              </div>
            </div>

            {/* 步骤进度 */}
            <div className="space-y-2">
              <div className="text-sm font-medium text-slate-600">执行步骤</div>
              {detail?.steps.map((s) => (
                <div key={s.step_order} className="flex items-center gap-3 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
                  <span className="text-xs text-slate-400">#{s.step_order}</span>
                  <span className="text-sm font-mono text-slate-700">{s.action}</span>
                  <span className="text-xs text-slate-400">{s.device_id}</span>
                  <span className={`ml-auto rounded px-2 py-0.5 text-xs ${STATUS_COLOR[s.status] || "bg-slate-100"}`}>
                    {s.status}
                  </span>
                  {s.error && <span className="text-xs text-red-500">{s.error}</span>}
                </div>
              ))}
              {(!detail || detail.steps.length === 0) && (
                <div className="text-sm text-slate-400">暂无步骤数据</div>
              )}
            </div>

            {/* 执行记录时间线 */}
            {detail?.audits && detail.audits.length > 0 && (
              <div className="space-y-1 rounded-lg border border-slate-100 bg-slate-50 p-3">
                <div className="mb-1 text-sm font-medium text-slate-600">执行记录</div>
                {detail.audits.map((a, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs">
                    <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-400" />
                    <span className="text-slate-400">{a.created_at?.replace("T", " ").slice(0, 19)}</span>
                    <span className="font-medium text-slate-600">{a.event_type}</span>
                    <span className="text-slate-500">{a.detail}</span>
                  </div>
                ))}
              </div>
            )}

            {/* 实验结果图表 */}
            {resultChart && (
              <div className="rounded-lg border border-slate-200 bg-white p-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm font-medium text-slate-600">实验结果</span>
                  {resultSummary && (
                    <span className="text-xs text-slate-400">
                      峰值 {String(resultSummary.max)} · 终值 {String(resultSummary.final)}
                    </span>
                  )}
                </div>
                <img
                  src={`data:${resultChart.image_mime};base64,${resultChart.image_base64}`}
                  alt="实验结果曲线"
                  className="max-h-64 rounded"
                />
              </div>
            )}

            {/* 测量数据 */}
            <div className="mt-2 flex-1 overflow-auto">
              <div className="mb-2 text-sm font-medium text-slate-600">测量数据（{measurements.length} 点）</div>
              {measurements.length > 0 ? (
                <div className="space-y-1">
                  {measurements.slice(-20).map((m, i) => (
                    <div key={i} className="flex items-center gap-3 text-sm">
                      <span className="text-slate-500">{m.metric_name}</span>
                      <span className="font-mono text-slate-700">{m.value}</span>
                      <span className="text-xs text-slate-400">{m.unit}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-sm text-slate-400">暂无测量数据</div>
              )}
            </div>
          </>
        ) : (
          <div className="flex h-full items-center justify-center text-slate-400">
            从左侧选择一个实验查看详情
          </div>
        )}
      </section>
    </div>
  );
}
