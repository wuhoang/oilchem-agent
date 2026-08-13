/**
 * 数据库管理面板。
 *
 * 通过后端 API 与 SQLite 数据库交互：
 * 实验记录、样品管理、设备台账的 CRUD。
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchDbTables,
  queryDbTable,
  insertDbRow,
  updateDbRow,
  deleteDbRow,
  type DbTableInfo,
} from "../services/api";
import { notifyError } from "./ErrorToast";

interface TableColumn {
  key: string;
  label: string;
  width?: string;
}

const TABLE_META: Record<string, { name: string; description: string; icon: string; columns: TableColumn[] }> = {
  experiments: {
    name: "实验记录",
    description: "所有实验的登记、步骤和结果",
    icon: "\u{1F9EA}",
    columns: [
      { key: "id", label: "编号", width: "90px" },
      { key: "name", label: "实验名称" },
      { key: "operator", label: "操作人", width: "100px" },
      { key: "status", label: "状态", width: "90px" },
      { key: "created_at", label: "创建时间", width: "160px" },
    ],
  },
  samples: {
    name: "样品管理",
    description: "样品登记、批次、溯源信息",
    icon: "\u{1F4E6}",
    columns: [
      { key: "code", label: "样品号", width: "130px" },
      { key: "name", label: "样品名称" },
      { key: "batch", label: "批次", width: "120px" },
      { key: "location", label: "存放位置", width: "120px" },
      { key: "status", label: "状态", width: "90px" },
    ],
  },
  devices: {
    name: "设备台账",
    description: "设备基本信息和状态",
    icon: "\u{1F527}",
    columns: [
      { key: "id", label: "设备ID", width: "110px" },
      { key: "name", label: "设备名称" },
      { key: "model", label: "型号", width: "110px" },
      { key: "status", label: "状态", width: "90px" },
      { key: "last_maintain", label: "上次维护", width: "130px" },
    ],
  },
};

const STATUS_BADGE: Record<string, string> = {
  "在线": "bg-emerald-50 text-emerald-700 border-emerald-200",
  "启用": "bg-emerald-50 text-emerald-700 border-emerald-200",
  "进行中": "bg-blue-50 text-blue-700 border-blue-200",
  "已完成": "bg-slate-50 text-slate-700 border-slate-200",
  "待开始": "bg-amber-50 text-amber-700 border-amber-200",
  "待处置": "bg-amber-50 text-amber-700 border-amber-200",
  "留样": "bg-purple-50 text-purple-700 border-purple-200",
  "在用": "bg-emerald-50 text-emerald-700 border-emerald-200",
  "离线": "bg-slate-50 text-slate-600 border-slate-200",
  "异常": "bg-red-50 text-red-700 border-red-200",
};

export function DatabasePanel() {
  const [tables, setTables] = useState<DbTableInfo[]>([]);
  const [activeKey, setActiveKey] = useState<string>("experiments");
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [search, setSearch] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingRow, setEditingRow] = useState<Record<string, unknown> | null>(null);
  const [newRowMode, setNewRowMode] = useState(false);

  // 加载表列表
  const loadTables = useCallback(async () => {
    try {
      const res = await fetchDbTables();
      setTables(res.tables);
    } catch {
      // 忽略
    }
  }, []);

  useEffect(() => {
    loadTables();
  }, [loadTables]);

  // 加载当前表数据
  const loadRows = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await queryDbTable(activeKey, search || undefined);
      if (res.success) {
        setRows(res.data);
      } else {
        setError(res.message);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [activeKey, search]);

  useEffect(() => {
    loadRows();
  }, [loadRows]);

  const active = useMemo(
    () => TABLE_META[activeKey] || TABLE_META.experiments,
    [activeKey],
  );

  const activeCount = useMemo(() => {
    const t = tables.find((tb) => tb.name === activeKey);
    return t ? t.count : rows.length;
  }, [tables, activeKey, rows.length]);

  // 新增
  const handleInsert = async (row: Record<string, unknown>) => {
    try {
      const res = await insertDbRow(activeKey, row);
      if (res.success) {
        setNewRowMode(false);
        await loadRows();
        await loadTables();
      } else {
        notifyError(res.message);
      }
    } catch (e) {
      notifyError(String(e));
    }
  };

  // 更新
  const handleUpdate = async (row: Record<string, unknown>) => {
    try {
      const res = await updateDbRow(activeKey, row);
      if (res.success) {
        setEditingRow(null);
        await loadRows();
      } else {
        notifyError(res.message);
      }
    } catch (e) {
      notifyError(String(e));
    }
  };

  // 删除
  const handleDelete = async (row: Record<string, unknown>) => {
    const pkField = active.columns[0].key;
    const pkValue = String(row[pkField] ?? "");
    if (!confirm(`确认删除 ${pkValue}？`)) return;
    try {
      const res = await deleteDbRow(activeKey, pkValue);
      if (res.success) {
        await loadRows();
        await loadTables();
      } else {
        notifyError(res.message);
      }
    } catch (e) {
      notifyError(String(e));
    }
  };

  // 导出 CSV
  const handleExport = () => {
    if (rows.length === 0) return;
    const headers = active.columns.map((c) => c.key);
    const csvLines = [headers.join(",")];
    for (const row of rows) {
      csvLines.push(headers.map((h) => {
        const v = String(row[h] ?? "");
        return v.includes(",") ? `"${v}"` : v;
      }).join(","));
    }
    const blob = new Blob(["﻿" + csvLines.join("\n")], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${activeKey}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex h-full w-full gap-4 p-4">
      {/* 表选择 */}
      <aside className="flex w-60 shrink-0 flex-col gap-1 rounded-xl border border-slate-200 bg-white p-3">
        <div className="mb-2 px-1 text-sm font-semibold text-slate-700">数据库表</div>
        {Object.entries(TABLE_META).map(([key, meta]) => {
          const t = tables.find((tb) => tb.name === key);
          return (
            <button
              key={key}
              onClick={() => {
                setActiveKey(key);
                setSearch("");
                setEditingRow(null);
                setNewRowMode(false);
              }}
              className={`flex flex-col items-start gap-0.5 rounded-lg border px-3 py-2 text-left transition ${
                activeKey === key
                  ? "border-blue-300 bg-blue-50"
                  : "border-transparent hover:border-slate-200 hover:bg-slate-50"
              }`}
            >
              <div className="flex w-full items-center gap-2">
                <span>{meta.icon}</span>
                <span className="text-sm font-medium text-slate-700">{meta.name}</span>
                <span className="ml-auto text-xs text-slate-400">{t ? t.count : "?"}</span>
              </div>
              <span className="text-xs text-slate-500">{meta.description}</span>
            </button>
          );
        })}
      </aside>

      {/* 数据区 */}
      <section className="flex min-w-0 flex-1 flex-col gap-3 overflow-hidden">
        {/* 工具栏 */}
        <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3">
          <div>
            <h2 className="text-base font-semibold text-slate-800">
              {active.icon} {active.name}
            </h2>
            <p className="text-xs text-slate-500">{active.description}</p>
          </div>
          <div className="flex items-center gap-2">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索关键字..."
              className="w-52 rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm outline-none transition focus:border-blue-300 focus:bg-white"
            />
            <button
              onClick={handleExport}
              className="rounded-md bg-blue-600 px-3 py-1.5 text-sm text-white transition hover:bg-blue-700"
            >
              导出 CSV
            </button>
            <button
              onClick={() => {
                setNewRowMode(true);
                setEditingRow(null);
              }}
              className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
            >
              + 新增
            </button>
          </div>
        </div>

        {/* 状态栏 */}
        <div className="flex items-center gap-4 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs text-slate-500">
          <span className="flex items-center gap-1.5">
            <span className={`h-2 w-2 rounded-full ${error ? "bg-red-500" : "bg-emerald-500"}`} />
            {error ? `错误: ${error}` : "数据库已连接"}
          </span>
          <span>表 <span className="font-mono text-slate-700">{activeKey}</span> · {activeCount} 行</span>
          {loading && <span className="text-blue-500">加载中...</span>}
        </div>

        {/* 新增行表单 */}
        {newRowMode && (
          <InlineForm
            columns={active.columns}
            onSave={handleInsert}
            onCancel={() => setNewRowMode(false)}
          />
        )}

        {/* 数据表格 */}
        <div className="min-h-0 flex-1 overflow-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full border-collapse text-sm">
            <thead className="sticky top-0 bg-slate-50">
              <tr>
                {active.columns.map((col) => (
                  <th
                    key={col.key}
                    style={{ width: col.width }}
                    className="border-b border-slate-200 px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500"
                  >
                    {col.label}
                  </th>
                ))}
                <th className="border-b border-slate-200 px-4 py-2.5 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                  操作
                </th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={active.columns.length + 1} className="px-4 py-12 text-center text-slate-400">
                    加载中...
                  </td>
                </tr>
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={active.columns.length + 1} className="px-4 py-12 text-center text-slate-400">
                    {search ? "无匹配数据" : "暂无数据，点击「+ 新增」添加"}
                  </td>
                </tr>
              ) : (
                rows.map((row, idx) => {
                  const pkField = active.columns[0].key;
                  const pkValue = String(row[pkField] ?? idx);
                  const isEditing = editingRow !== null && String(editingRow[pkField] ?? "") === pkValue;
                  return (
                    <tr key={pkValue} className="border-b border-slate-100 transition hover:bg-slate-50">
                      {active.columns.map((col) => {
                        const raw = row[col.key];
                        const badgeClass = STATUS_BADGE[String(raw)] || "bg-slate-50 text-slate-700 border-slate-200";
                        const isStatus = col.key === "status";
                        return (
                          <td key={col.key} className="px-4 py-2.5 text-slate-700">
                            {isEditing ? (
                              <input
                                className="w-full rounded border border-slate-300 px-2 py-1 text-sm"
                                defaultValue={String(raw ?? "")}
                                id={`edit-${pkValue}-${col.key}`}
                              />
                            ) : isStatus ? (
                              <span className={`inline-block rounded-md border px-2 py-0.5 text-xs ${badgeClass}`}>
                                {String(raw ?? "")}
                              </span>
                            ) : (
                              <span className="tabular-nums">{String(raw ?? "")}</span>
                            )}
                          </td>
                        );
                      })}
                      <td className="px-4 py-2.5 text-right">
                        {isEditing ? (
                          <>
                            <button
                              onClick={() => {
                                const updated: Record<string, unknown> = { ...row };
                                active.columns.forEach((col) => {
                                  const el = document.getElementById(`edit-${pkValue}-${col.key}`) as HTMLInputElement | null;
                                  if (el) updated[col.key] = el.value;
                                });
                                handleUpdate(updated);
                              }}
                              className="mr-2 text-xs text-emerald-600 hover:underline"
                            >
                              保存
                            </button>
                            <button
                              onClick={() => setEditingRow(null)}
                              className="text-xs text-slate-500 hover:underline"
                            >
                              取消
                            </button>
                          </>
                        ) : (
                          <>
                            <button
                              onClick={() => setEditingRow({ ...row })}
                              className="mr-2 text-xs text-blue-600 hover:underline"
                            >
                              编辑
                            </button>
                            <button
                              onClick={() => handleDelete(row)}
                              className="text-xs text-red-500 hover:underline"
                            >
                              删除
                            </button>
                          </>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

/** 新增行内联表单 */
function InlineForm({
  columns,
  onSave,
  onCancel,
}: {
  columns: TableColumn[];
  onSave: (row: Record<string, unknown>) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<Record<string, string>>({});

  const handleSave = () => onSave(form as Record<string, unknown>);

  return (
    <div className="rounded-xl border border-blue-200 bg-blue-50/50 px-4 py-3">
      <div className="mb-2 text-sm font-medium text-blue-700">新增记录</div>
      <div className="flex flex-wrap gap-3">
        {columns.map((col) => (
          <div key={col.key} className="flex items-center gap-1.5">
            <label className="text-xs text-slate-600">{col.label}</label>
            <input
              className="rounded border border-slate-300 px-2 py-1 text-sm"
              value={form[col.key] || ""}
              onChange={(e) => setForm((prev) => ({ ...prev, [col.key]: e.target.value }))}
              style={{ width: col.width || "140px" }}
            />
          </div>
        ))}
        <button onClick={handleSave} className="rounded-md bg-emerald-600 px-3 py-1 text-sm text-white hover:bg-emerald-700">
          保存
        </button>
        <button onClick={onCancel} className="rounded-md border border-slate-300 px-3 py-1 text-sm text-slate-600 hover:bg-slate-50">
          取消
        </button>
      </div>
    </div>
  );
}
