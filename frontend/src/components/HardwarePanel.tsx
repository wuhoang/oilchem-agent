/**
 * 硬件设备面板。
 *
 * 展示实验室硬件设备列表、实时传感器数据、
 * 支持下发简单控制指令（预留真实硬件接口）。
 */

import { useEffect, useState } from "react";

interface DeviceMetric {
  name: string;
  value: number;
  unit: string;
  min?: number;
  max?: number;
}

interface Device {
  id: string;
  name: string;
  type: "reactor" | "chromatograph" | "balance" | "ph_meter" | "pump";
  status: "online" | "offline" | "error";
  metrics: DeviceMetric[];
  lastUpdate: number;
}

const TYPE_ICONS: Record<Device["type"], string> = {
  reactor: "⚗️",
  chromatograph: "🧪",
  balance: "⚖️",
  ph_meter: "📊",
  pump: "💧",
};

const TYPE_LABELS: Record<Device["type"], string> = {
  reactor: "反应器",
  chromatograph: "色谱仪",
  balance: "天平",
  ph_meter: "pH计",
  pump: "蠕动泵",
};

const STATUS_COLORS: Record<Device["status"], string> = {
  online: "bg-emerald-500",
  offline: "bg-slate-400",
  error: "bg-red-500",
};

const STATUS_LABELS: Record<Device["status"], string> = {
  online: "在线",
  offline: "离线",
  error: "异常",
};

function seedDevices(): Device[] {
  return [
    {
      id: "rct-01",
      name: "加氢反应器 R-101",
      type: "reactor",
      status: "online",
      metrics: [
        { name: "温度", value: 185.3, unit: "°C", min: 0, max: 300 },
        { name: "压力", value: 4.2, unit: "MPa", min: 0, max: 10 },
        { name: "液位", value: 62, unit: "%", min: 0, max: 100 },
      ],
      lastUpdate: Date.now(),
    },
    {
      id: "gc-01",
      name: "气相色谱仪 GC-2030",
      type: "chromatograph",
      status: "online",
      metrics: [
        { name: "柱温", value: 220, unit: "°C" },
        { name: "载气压力", value: 0.45, unit: "MPa" },
      ],
      lastUpdate: Date.now(),
    },
    {
      id: "bal-01",
      name: "分析天平 XS205",
      type: "balance",
      status: "online",
      metrics: [{ name: "当前重量", value: 12.548, unit: "g" }],
      lastUpdate: Date.now(),
    },
    {
      id: "ph-01",
      name: "pH计 FE28",
      type: "ph_meter",
      status: "online",
      metrics: [
        { name: "pH", value: 7.42, unit: "", min: 0, max: 14 },
        { name: "温度", value: 25.3, unit: "°C" },
      ],
      lastUpdate: Date.now(),
    },
    {
      id: "pump-01",
      name: "蠕动泵 RP-100",
      type: "pump",
      status: "offline",
      metrics: [{ name: "流速", value: 0, unit: "mL/min" }],
      lastUpdate: Date.now() - 60000,
    },
  ];
}

export function HardwarePanel() {
  const [devices, setDevices] = useState<Device[]>(seedDevices);
  const [selectedId, setSelectedId] = useState<string>("rct-01");
  const [log, setLog] = useState<string[]>([
    "系统已启动硬件数据采集服务",
    "已自动扫描到 5 台设备",
  ]);

  // 模拟实时数据更新
  useEffect(() => {
    const timer = setInterval(() => {
      setDevices((prev) =>
        prev.map((d) => {
          if (d.status !== "online") return d;
          return {
            ...d,
            lastUpdate: Date.now(),
            metrics: d.metrics.map((m) => {
              const drift = (Math.random() - 0.5) * Math.abs(m.value || 1) * 0.02;
              let next = m.value + drift;
              if (m.min !== undefined) next = Math.max(m.min, next);
              if (m.max !== undefined) next = Math.min(m.max, next);
              return { ...m, value: Number(next.toFixed(3)) };
            }),
          };
        })
      );
    }, 1500);
    return () => clearInterval(timer);
  }, []);

  const selected = devices.find((d) => d.id === selectedId);

  const appendLog = (line: string) => {
    const time = new Date().toLocaleTimeString("zh-CN", { hour12: false });
    setLog((prev) => [`[${time}] ${line}`, ...prev].slice(0, 80));
  };

  const handleCommand = (deviceId: string, cmd: string) => {
    appendLog(`→ 下发指令 ${cmd} 到设备 ${deviceId}（接口预留）`);
    appendLog("← 指令已入队，等待硬件网关处理");
  };

  return (
    <div className="flex h-full w-full gap-4 p-4">
      {/* 设备列表 */}
      <aside className="flex w-72 shrink-0 flex-col gap-2 overflow-y-auto rounded-xl border border-slate-200 bg-white p-3">
        <div className="mb-2 flex items-center justify-between px-1">
          <h3 className="text-sm font-semibold text-slate-700">设备列表</h3>
          <button
            onClick={() => appendLog("触发设备重新扫描（接口预留）")}
            className="rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600 transition hover:bg-slate-200"
          >
            重新扫描
          </button>
        </div>
        {devices.map((d) => (
          <button
            key={d.id}
            onClick={() => setSelectedId(d.id)}
            className={`flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left transition ${
              selectedId === d.id
                ? "border-blue-300 bg-blue-50"
                : "border-slate-200 hover:border-slate-300"
            }`}
          >
            <span className="text-xl">{TYPE_ICONS[d.type]}</span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-slate-700">
                {d.name}
              </p>
              <p className="text-xs text-slate-400">
                {TYPE_LABELS[d.type]} · {d.id}
              </p>
            </div>
            <span
              className={`h-2.5 w-2.5 shrink-0 rounded-full ${STATUS_COLORS[d.status]}`}
              title={STATUS_LABELS[d.status]}
            />
          </button>
        ))}
      </aside>

      {/* 设备详情 */}
      <section className="flex min-w-0 flex-1 flex-col gap-4 overflow-y-auto">
        {selected ? (
          <>
            {/* 头部 */}
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-4">
                  <span className="text-4xl">{TYPE_ICONS[selected.type]}</span>
                  <div>
                    <h2 className="text-lg font-semibold text-slate-800">
                      {selected.name}
                    </h2>
                    <p className="text-sm text-slate-500">
                      {TYPE_LABELS[selected.type]} · 设备 ID:{" "}
                      <span className="font-mono">{selected.id}</span>
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 rounded-full bg-slate-50 px-3 py-1">
                  <span
                    className={`h-2 w-2 rounded-full ${STATUS_COLORS[selected.status]}`}
                  />
                  <span className="text-sm text-slate-600">
                    {STATUS_LABELS[selected.status]}
                  </span>
                  <span className="text-xs text-slate-400">
                    · 更新于 {new Date(selected.lastUpdate).toLocaleTimeString("zh-CN")}
                  </span>
                </div>
              </div>

              {/* 指标卡片 */}
              <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {selected.metrics.map((m) => {
                  const pct =
                    m.min !== undefined && m.max !== undefined
                      ? Math.max(
                          0,
                          Math.min(100, ((m.value - m.min) / (m.max - m.min)) * 100)
                        )
                      : null;
                  return (
                    <div
                      key={m.name}
                      className="rounded-lg border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-4"
                    >
                      <p className="text-xs text-slate-500">{m.name}</p>
                      <p className="mt-1 text-2xl font-semibold text-slate-800 tabular-nums">
                        {m.value.toFixed(2)}
                        {m.unit && (
                          <span className="ml-1 text-base text-slate-400">
                            {m.unit}
                          </span>
                        )}
                      </p>
                      {pct !== null && (
                        <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-200">
                          <div
                            className="h-full bg-gradient-to-r from-emerald-400 to-teal-500 transition-all"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 指令下发 */}
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <h3 className="mb-3 text-sm font-semibold text-slate-700">
                指令下发（接口预留）
              </h3>
              <div className="flex flex-wrap gap-2">
                {["启动", "停止", "复位", "校准", "读取参数", "设置目标值"].map(
                  (cmd) => (
                    <button
                      key={cmd}
                      disabled={selected.status !== "online"}
                      onClick={() => handleCommand(selected.id, cmd)}
                      className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-700 transition hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {cmd}
                    </button>
                  )
                )}
              </div>
              <p className="mt-3 text-xs text-slate-400">
                注：指令通过硬件网关下发（RS232/USB/GPIB/MQTT），当前为界面演示。
              </p>
            </div>

            {/* 日志 */}
            <div className="rounded-xl border border-slate-200 bg-slate-900 p-4">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-slate-200">
                  通讯日志
                </h3>
                <button
                  onClick={() => setLog([])}
                  className="text-xs text-slate-400 hover:text-slate-200"
                >
                  清空
                </button>
              </div>
              <div className="max-h-56 overflow-y-auto font-mono text-xs leading-relaxed text-emerald-300">
                {log.length === 0 ? (
                  <p className="text-slate-500">暂无日志</p>
                ) : (
                  log.map((line, i) => <div key={i}>{line}</div>)
                )}
              </div>
            </div>
          </>
        ) : (
          <div className="flex flex-1 items-center justify-center text-slate-400">
            选择左侧设备查看详情
          </div>
        )}
      </section>
    </div>
  );
}
