/**
 * 文件浏览器组件。
 *
 * 左侧文件树（目录浏览）+ 右侧文件内容查看器。
 * 支持导航目录、查看/编辑文本文件、预览 Office 文件。
 */

import { useCallback, useEffect, useState } from "react";
import type { FileEntry, FilePreviewResponse } from "../types";
import { listFiles, previewFile } from "../services/api";

interface FileBrowserProps {
  onFileOpen?: (path: string, content: string) => void;
}

const OFFICE_EXTENSIONS = [".xlsx", ".xls", ".docx", ".doc", ".pptx", ".ppt"];
const CODE_EXTENSIONS = [".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".css", ".html", ".md", ".yaml", ".yml", ".sh", ".sql"];

export function FileBrowser({ onFileOpen }: FileBrowserProps) {
  const [currentPath, setCurrentPath] = useState<string>("");
  const [entries, setEntries] = useState<FileEntry[]>([]);
  const [selectedFile, setSelectedFile] = useState<FileEntry | null>(null);
  const [previewData, setPreviewData] = useState<FilePreviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingFile, setLoadingFile] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDirectory = useCallback(async (path: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await listFiles(path, false);
      setEntries(res.entries);
      setCurrentPath(res.path);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载目录失败");
      setEntries([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadFile = useCallback(async (entry: FileEntry) => {
    if (!entry.is_dir) {
      setSelectedFile(entry);
      setLoadingFile(true);
      setError(null);
      try {
        const res = await previewFile(entry.path);
        setPreviewData(res);
        if (res.success && res.file_type === "text" && onFileOpen) {
          const content = res.content?.content || "";
          onFileOpen(entry.path, content);
        }
      } catch (e) {
        setPreviewData(null);
        setError(e instanceof Error ? e.message : "读取文件失败");
      } finally {
        setLoadingFile(false);
      }
    }
  }, [onFileOpen]);

  const navigateUp = useCallback(() => {
    const path = currentPath.replace(/\\/g, "/");
    const parent = path.substring(0, path.lastIndexOf("/"));
    if (parent && parent !== currentPath) {
      loadDirectory(parent.replace(/\//g, "\\"));
    }
  }, [currentPath, loadDirectory]);

  const navigateTo = useCallback((entry: FileEntry) => {
    if (entry.is_dir) {
      loadDirectory(entry.path);
      setSelectedFile(null);
      setPreviewData(null);
    }
  }, [loadDirectory]);

  useEffect(() => {
    loadDirectory(currentPath);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  const formatTime = (timestamp: number) => {
    if (!timestamp) return "-";
    return new Date(timestamp * 1000).toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  const getFileIcon = (entry: FileEntry) => {
    if (entry.is_dir) {
      return (
        <svg className="h-4 w-4 shrink-0 text-amber-500" fill="currentColor" viewBox="0 0 24 24">
          <path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" />
        </svg>
      );
    }
    const ext = entry.name.split(".").pop()?.toLowerCase() || "";
    const isOffice = OFFICE_EXTENSIONS.includes(`.${ext}`);
    const isCode = CODE_EXTENSIONS.includes(`.${ext}`);
    const isImage = ["png", "jpg", "jpeg", "gif", "svg", "bmp", "webp"].includes(ext);
    const color = isOffice ? "text-emerald-500" : isCode ? "text-blue-500" : isImage ? "text-purple-500" : "text-slate-400";
    return (
      <svg className={`h-4 w-4 shrink-0 ${color}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
      </svg>
    );
  };

  const renderPreview = () => {
    if (loadingFile) {
      return (
        <div className="flex items-center justify-center py-12 text-sm text-slate-400">
          <span className="mr-2 h-3 w-3 animate-spin rounded-full border-2 border-slate-600 border-t-blue-400" />
          读取中...
        </div>
      );
    }

    if (!previewData || !previewData.success) {
      if (error) {
        return (
          <div className="flex items-center justify-center py-12 text-sm text-red-400">
            {error}
          </div>
        );
      }
      return (
        <div className="flex flex-col items-center justify-center py-12 text-slate-400">
          <svg className="h-12 w-12 mb-3 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 7.5l-.625 10.632a2.25 2.25 0 01-2.247 2.118H6.622a2.25 2.25 0 01-2.247-2.118L3.75 7.5M10 11.25h4M3.375 7.5h17.25c.621 0 1.125-.504 1.125-1.125v-1.5c0-.621-.504-1.125-1.125-1.125H3.375c-.621 0-1.125.504-1.125 1.125v1.5c0 .621.504 1.125 1.125 1.125z" />
          </svg>
          <p className="text-sm">无法预览此文件</p>
        </div>
      );
    }

    const { file_type, content } = previewData;

    if (file_type === "text") {
      const text = content?.content || "";
      return (
        <pre className="p-4 text-sm leading-relaxed text-slate-100 font-mono whitespace-pre-wrap break-words overflow-auto">
          {text}
        </pre>
      );
    }

    if (file_type === "excel") {
      return <ExcelPreview data={content} />;
    }

    if (file_type === "word") {
      return <WordPreview data={content} />;
    }

    if (file_type === "ppt") {
      return <PPPPreview data={content} />;
    }

    return (
      <pre className="p-4 text-sm text-slate-300 overflow-auto">
        {JSON.stringify(content, null, 2)}
      </pre>
    );
  };

  return (
    <div className="flex h-full flex-col bg-slate-50">
      {/* 工具栏 */}
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-2.5">
        <div className="flex items-center gap-2">
          <button
            onClick={navigateUp}
            disabled={loading}
            className="flex h-7 w-7 items-center justify-center rounded-md text-slate-500 transition hover:bg-slate-100 disabled:opacity-50"
            title="上级目录"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div className="flex items-center gap-1.5 rounded-md bg-slate-100 px-2.5 py-1 text-xs">
            <svg className="h-3.5 w-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
            <span className="font-mono text-slate-600 max-w-xs truncate">{currentPath}</span>
          </div>
        </div>
        <div className="text-xs text-slate-400">
          {entries.length} 个项目
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        {/* 文件树 */}
        <div className="w-64 shrink-0 overflow-y-auto border-r border-slate-200 bg-white">
          {loading ? (
            <div className="flex items-center justify-center py-8 text-sm text-slate-400">
              <span className="mr-2 h-3 w-3 animate-spin rounded-full border-2 border-slate-300 border-t-blue-500" />
              加载中...
            </div>
          ) : error ? (
            <div className="p-4 text-sm text-red-500">{error}</div>
          ) : (
            <ul className="py-1">
              {entries.map((entry) => (
                <li key={entry.path}>
                  <button
                    onClick={() => entry.is_dir ? navigateTo(entry) : loadFile(entry)}
                    className={`group flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm transition ${
                      selectedFile?.path === entry.path
                        ? "bg-blue-50 text-blue-700"
                        : "text-slate-700 hover:bg-slate-50"
                    }`}
                  >
                    {getFileIcon(entry)}
                    <span className="truncate flex-1">{entry.name}</span>
                    {!entry.is_dir && (
                      <span className="text-xs text-slate-400 group-hover:text-slate-500">
                        {formatSize(entry.size_bytes)}
                      </span>
                    )}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* 文件内容查看器 */}
        <div className="flex min-w-0 flex-1 flex-col">
          {selectedFile ? (
            <>
              {/* 文件信息 */}
              <div className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-slate-700">
                    {selectedFile.name}
                  </span>
                  {previewData && (
                    <span className={`rounded px-2 py-0.5 text-xs ${
                      previewData.file_type === "excel" ? "bg-emerald-100 text-emerald-700" :
                      previewData.file_type === "word" ? "bg-blue-100 text-blue-700" :
                      previewData.file_type === "ppt" ? "bg-orange-100 text-orange-700" :
                      previewData.file_type === "text" ? "bg-slate-100 text-slate-700" :
                      "bg-slate-100 text-slate-600"
                    }`}>
                      {previewData.file_type === "excel" ? "Excel" :
                       previewData.file_type === "word" ? "Word" :
                       previewData.file_type === "ppt" ? "PPT" :
                       previewData.file_type === "text" ? "文本" :
                       previewData.file_type}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-4 text-xs text-slate-400">
                  <span>{formatSize(selectedFile.size_bytes)}</span>
                  <span>{formatTime(selectedFile.modified)}</span>
                </div>
              </div>

              {/* 文件内容 */}
              <div className={`min-h-0 flex-1 overflow-auto ${
                previewData?.file_type === "text" ? "bg-slate-900" : "bg-white"
              }`}>
                {renderPreview()}
              </div>
            </>
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center text-slate-400">
              <svg className="h-16 w-16 mb-4 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              <p className="text-sm">选择左侧文件查看内容</p>
              <p className="mt-1 text-xs">支持预览 Excel、Word、PPT 等文件</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Office Preview Components
// ---------------------------------------------------------------------------

function ExcelPreview({ data }: { data: any }) {
  if (!data) return null;
  const sheets: string[] = data.sheets || [];
  const currentSheet = data.sheet || "";
  const headers: string[] = data.headers || [];
  const rows: any[] = data.data || [];

  return (
    <div className="p-4">
      <div className="mb-3 flex items-center gap-2 text-xs text-slate-500">
        <span className="rounded bg-emerald-100 px-2 py-0.5 font-medium text-emerald-700">
          📊 Excel
        </span>
        <span>工作表: {currentSheet}</span>
        <span>共 {rows.length} 行 × {headers.length} 列</span>
      </div>
      {sheets.length > 1 && (
        <div className="mb-2 flex gap-1">
          {sheets.map((s: string) => (
            <span key={s} className={`rounded px-2 py-0.5 text-xs ${s === currentSheet ? "bg-emerald-600 text-white" : "bg-slate-100 text-slate-600"}`}>
              {s}
            </span>
          ))}
        </div>
      )}
      {headers.length > 0 && (
        <div className="overflow-auto rounded-lg border border-slate-200">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-slate-100">
                {headers.map((h, i) => (
                  <th key={i} className="border border-slate-200 px-3 py-2 text-left font-semibold text-slate-700 whitespace-nowrap">
                    {String(h)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row, ri) => (
                <tr key={ri} className={ri % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                  {headers.map((h, ci) => (
                    <td key={ci} className="border border-slate-200 px-3 py-2 text-slate-700 whitespace-nowrap">
                      {row[h] !== undefined && row[h] !== null ? String(row[h]) : ""}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function WordPreview({ data }: { data: any }) {
  if (!data) return null;
  const paragraphs: any[] = data.paragraphs || [];
  const tables: any[] = data.tables || [];
  const headings: any[] = data.headings || [];

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <div className="mb-3 flex items-center gap-2 text-xs text-slate-500">
        <span className="rounded bg-blue-100 px-2 py-0.5 font-medium text-blue-700">
          📝 Word
        </span>
        <span>{data.total_paragraphs || 0} 段落 · {tables.length} 表格</span>
      </div>

      {headings.length > 0 && (
        <div className="mb-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
          <div className="text-xs font-semibold text-slate-500 mb-1">目录</div>
          {headings.map((h, i) => (
            <div key={i} className="text-xs text-slate-600 py-0.5">
              {h.text}
            </div>
          ))}
        </div>
      )}

      {paragraphs.map((p, i) => {
        const style = p.style || "Normal";
        if (style.startsWith("Heading")) {
          return (
            <h2 key={i} className={`mb-3 mt-4 font-semibold ${
              style.includes("1") ? "text-2xl" :
              style.includes("2") ? "text-xl" :
              style.includes("3") ? "text-lg" : "text-base"
            } text-slate-800`}>
              {p.text}
            </h2>
          );
        }
        return (
          <p key={i} className="mb-2 text-sm leading-relaxed text-slate-700">
            {p.text}
          </p>
        );
      })}

      {(tables as Array<{ data?: unknown[][] }>).map((table, ti) => {
        const rows = (table.data || []) as unknown[][];
        if (rows.length === 0) return null;
        const cols = rows[0]?.length || 0;
        return (
          <div key={ti} className="my-4 overflow-auto rounded-lg border border-slate-200">
            <table className="w-full text-xs">
              <tbody>
                {rows.map((row: unknown[], ri) => (
                  <tr key={ri} className={ri === 0 ? "bg-slate-100 font-semibold" : ri % 2 === 0 ? "bg-white" : "bg-slate-50"}>
                    {Array.from({ length: cols }).map((_, ci) => (
                      <td key={ci} className="border border-slate-200 px-3 py-2 text-slate-700">
                        {row[ci] !== undefined ? String(row[ci]) : ""}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}

function PPPPreview({ data }: { data: any }) {
  if (!data) return null;
  const slides = (data.slides || []) as Array<{
    text_content?: string[];
    tables?: string[][][];
    notes?: string;
  }>;

  return (
    <div className="p-4">
      <div className="mb-3 flex items-center gap-2 text-xs text-slate-500">
        <span className="rounded bg-orange-100 px-2 py-0.5 font-medium text-orange-700">
          📊 PPT
        </span>
        <span>共 {data.total_slides || slides.length} 页幻灯片</span>
      </div>
      <div className="space-y-3">
        {slides.map((slide, i) => (
          <div key={i} className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div className="mb-2 flex items-center gap-2 text-xs text-slate-500">
              <span className="rounded bg-slate-200 px-2 py-0.5 font-medium">第 {i + 1} 页</span>
            </div>
            {slide.text_content && slide.text_content.length > 0 && (
              <div className="mb-2">
                <div className="text-sm font-semibold text-slate-800 mb-1">
                  {slide.text_content[0]}
                </div>
                {slide.text_content.length > 1 && (
                  <ul className="ml-4 list-disc space-y-0.5">
                    {slide.text_content.slice(1).map((t: string, ti) => (
                      <li key={ti} className="text-xs text-slate-600">{t}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
            {slide.tables && slide.tables.length > 0 && slide.tables.map((table, ti) => (
              <div key={ti} className="overflow-auto rounded border border-slate-200 bg-white mt-2">
                <table className="w-full text-xs">
                  <tbody>
                    {table.map((row: string[], ri) => (
                      <tr key={ri} className={ri === 0 ? "bg-slate-100 font-semibold" : ""}>
                        {row.map((cell: string, ci) => (
                          <td key={ci} className="border border-slate-200 px-2 py-1 text-slate-700">
                            {String(cell)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
            {slide.notes && (
              <div className="mt-2 text-xs text-slate-500 italic border-t border-slate-200 pt-2">
                💭 备注: {slide.notes}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
