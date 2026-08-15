/**
 * 硬件设备面板。
 *
 * 从后端统一设备源（DriverRegistry）读取设备列表与实时遥测。
 */

import { useCallback, useEffect, useState } from "react";
import { fetchHardwareDevices, type HardwareDevice } from "../services/api";
import { notifyError } from "./ErrorToast";

const TYPE_ICONS: Record<string, string> = {
  reactor: "⚗️",
  chromatograph: "🧪",
  balance: "⚖️",
  ph_meter: "📊",
  pump: "💧",
  hthp: "🌡️",
  rheometer: "🌀",
  thickener: "⏳",
};

const TYPE_LABELS: Record<string, string> = {
  reactor: "反应器",
  chromatograph: "色谱仪",
  balance: "天平",
  ph_meter: "pH计",
  pump: "蠕动泵",
  hthp: "失水仪",
  rheometer: "流变仪",
  thickener: "稠化仪",
};

const STATUS_COLORS: Record<string, string> = {
  online: "bg-emerald-500",
  busy: "bg-amber-500",
  offline: "bg-slate-400",
  error: "bg-red-500",
};

const STATUS_LABELS: Record<string, string> = {
  online: "在线",
  busy: "忙碌",
  offline: "离线",
  error: "异常",
};

export function HardwarePanel() {
  const [devices, setDevices] = useState<HardwareDevice[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [loading, setLoading] = useState(true);

  const loadDevices = useCallback(async () => {
    try {
      const res = await fetchHardwareDevices();
      setDevices(res.devices);
      if (!selectedId && res.devices.length > 0) {
        setSelectedId(res.devices[0].id);
      }
    } catch (err) {
      notifyError(String(err));
    } finally {
      setLoading(false);
    }
  }, [selectedId]);

  useEffect(() => {
    loadDevices();
    const timer = setInterval(loadDevices, 2000);
    return () => clearInterval(timer);
  }, [loadDevices]);

  const selected = devices.find((d) => d.id === selectedId);

  return (
    <div className="flex h-full w-full gap-4 p-4">
      {/* 设备列表 */}
      <aside className="flex w-72 shrink-0 flex-col gap-2 overflow-y-auto rounded-xl border border-slate-200 bg-white p-3">
        <div className="mb-2 flex items-center justify-between px-1">
          <h3 className="text-sm font-semibold text-slate-700">设备列表</h3>
          <span className="text-xs text-slate-400">{devices.length} 台</span>
        </div>
        {loading ? (
          <div className="p-4 text-center text-sm text-slate-400">加载中...</div>
        ) : (
          devices.map((d) => (
            <button
              key={d.id}
              onClick={() => setSelectedId(d.id)}
              className={`flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left transition ${
                selectedId === d.id
                  ? "border-blue-300 bg-blue-50"
                  : "border-slate-200 hover:border-slate-300"
              }`}
            >
              <span className="text-xl">{TYPE_ICONS[d.type] || "🔌"}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-slate-700">{d.name}</p>
                <p className="text-xs text-slate-400">
                  {TYPE_LABELS[d.type] || d.type} · {d.id}
                </p>
              </div>
              <span
                className={`h-2.5 w-2.5 shrink-0 rounded-full ${STATUS_COLORS[d.status] || "bg-slate-400"}`}
                title={STATUS_LABELS[d.status]}
              />
            </button>
          ))
        )}
      </aside>

      {/* 设备详情 */}
      <section className="flex min-w-0 flex-1 flex-col gap-4 overflow-y-auto">
        {selected ? (
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-4">
                <span className="text-4xl">{TYPE_ICONS[selected.type] || "🔌"}</span>
                <div>
                  <h2 className="text-lg font-semibold text-slate-800">{selected.name}</h2>
                  <p className="text-sm text-slate-500">
                    {TYPE_LABELS[selected.type] || selected.type} · 设备 ID:{" "}
                    <span className="font-mono">{selected.id}</span>
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 rounded-full bg-slate-50 px-3 py-1">
                <span className={`h-2 w-2 rounded-full ${STATUS_COLORS[selected.status] || "bg-slate-400"}`} />
                <span className="text-sm text-slate-600">{STATUS_LABELS[selected.status]}</span>
              </div>
            </div>

            {/* 指标卡片 */}
            <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {selected.metrics.map((m) => (
                <div
                  key={m.name}
                  className="rounded-lg border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-4"
                >
                  <p className="text-xs text-slate-500">{m.name}</p>
                  <p className="mt-1 text-2xl font-semibold text-slate-800 tabular-nums">
                    {m.value.toFixed(2)}
                    {m.unit && (
                      <span className="ml-1 text-base text-slate-400">{m.unit}</span>
                    )}
                  </p>
                </div>
              ))}
              {selected.metrics.length === 0 && (
                <p className="text-sm text-slate-400">暂无遥测数据</p>
              )}
            </div>

            {selected.error && (
              <p className="mt-3 text-xs text-red-500">{selected.error}</p>
            )}
          </div>
        ) : (
          <div className="flex flex-1 items-center justify-center text-slate-400">
            选择左侧设备查看详情
          </div>
        )}
      </section>
    </div>
  );
}
