import { useState } from "react";
import { browseWeb, fillWebForm, smartFillForm, extractWebText } from "../services/api";

type Step = "idle" | "browsing" | "filling" | "smart" | "done" | "error";
type TabType = "smart" | "browse" | "fill" | "extract";

interface FormElement {
  index: number;
  type: string;
  name: string;
  id: string;
  placeholder: string;
  visible: boolean;
}

interface BrowseResult {
  url: string;
  title: string;
  text_content: string;
  form_elements: {
    inputs: FormElement[];
    buttons: { index: number; tag: string; text: string; id: string; class: string; visible: boolean }[];
  };
  screenshot_base64: string;
  screenshot_mime: string;
  width: number;
  height: number;
}

interface FillResult {
  url: string;
  title: string;
  fields_filled: number;
  submitted: boolean;
  screenshot_base64: string;
  screenshot_mime: string;
  message: string;
}

interface SmartFillResult extends FillResult {
  filled_fields: { field: string; matched_to: string; value: string }[];
  failed_fields: { field: string; reason: string }[];
}

export function WebFormPanel() {
  const [url, setUrl] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [formFields, setFormFields] = useState<Record<string, string>>({});
  const [step, setStep] = useState<Step>("idle");
  const [browseResult, setBrowseResult] = useState<BrowseResult | null>(null);
  const [fillResult, setFillResult] = useState<FillResult | null>(null);
  const [smartResult, setSmartResult] = useState<SmartFillResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>("smart");
  const [extractSelector, setExtractSelector] = useState("");
  const [extractResult, setExtractResult] = useState<any>(null);

  // Smart fill specific
  const [smartFieldDefs, setSmartFieldDefs] = useState<{ key: string; value: string }[]>([
    { key: "", value: "" },
  ]);
  const [smartAutoSubmit, setSmartAutoSubmit] = useState(true);

  const handleBrowse = async () => {
    if (!url.trim()) {
      setError("Please enter a URL");
      return;
    }
    setStep("browsing");
    setError(null);
    setBrowseResult(null);
    setFillResult(null);
    setSmartResult(null);
    try {
      const res = await browseWeb(url.trim());
      if (res.success && res.data) {
        setBrowseResult(res.data as BrowseResult);
        setStep("done");
      } else {
        setError(res.error || "Failed to browse page");
        setStep("error");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
      setStep("error");
    }
  };

  const handleFillForm = async () => {
    if (!url.trim()) {
      setError("Please enter a URL");
      return;
    }
    setStep("filling");
    setError(null);
    setFillResult(null);
    try {
      const res = await fillWebForm(url.trim(), {
        username: username || undefined,
        password: password || undefined,
        formData: Object.keys(formFields).length > 0 ? formFields : undefined,
        submit: true,
      });
      if (res.success && res.data) {
        setFillResult(res.data as FillResult);
        setStep("done");
      } else {
        setError(res.error || "Failed to fill form");
        setStep("error");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
      setStep("error");
    }
  };

  const handleSmartFill = async () => {
    if (!url.trim()) {
      setError("Please enter a URL");
      return;
    }

    // Build field mapping from dynamic inputs
    const fieldMapping: Record<string, string> = {};
    smartFieldDefs.forEach((f) => {
      if (f.key.trim() && f.value.trim()) {
        fieldMapping[f.key.trim()] = f.value.trim();
      }
    });

    if (!username && !password && Object.keys(fieldMapping).length === 0) {
      setError("Please enter login credentials or field mapping");
      return;
    }

    setStep("smart");
    setError(null);
    setSmartResult(null);
    try {
      const res = await smartFillForm(url.trim(), {
        username: username || undefined,
        password: password || undefined,
        fieldMapping: Object.keys(fieldMapping).length > 0 ? fieldMapping : undefined,
        autoSubmit: smartAutoSubmit,
      });
      if (res.success && res.data) {
        setSmartResult(res.data as SmartFillResult);
        setStep("done");
      } else {
        setError(res.error || "Smart fill failed");
        setStep("error");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
      setStep("error");
    }
  };

  const handleExtract = async () => {
    if (!url.trim()) {
      setError("Please enter a URL");
      return;
    }
    setError(null);
    setExtractResult(null);
    try {
      const res = await extractWebText(url.trim(), extractSelector || undefined);
      if (res.success && res.data) {
        setExtractResult(res.data);
      } else {
        setError(res.error || "Failed to extract text");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    }
  };

  const updateFormField = (index: string, value: string) => {
    setFormFields((prev) => ({ ...prev, [index]: value }));
  };

  const updateSmartField = (i: number, key: string, value: string) => {
    setSmartFieldDefs((prev) => {
      const next = [...prev];
      next[i] = { key, value };
      return next;
    });
  };

  const addSmartField = () => {
    setSmartFieldDefs((prev) => [...prev, { key: "", value: "" }]);
  };

  const removeSmartField = (i: number) => {
    setSmartFieldDefs((prev) => prev.filter((_, idx) => idx !== i));
  };

  const isLoading = step === "browsing" || step === "filling" || step === "smart";

  const tabs: { key: TabType; label: string; badge?: string }[] = [
    { key: "smart", label: "AI Smart Fill", badge: "AI" },
    { key: "browse", label: "Browse" },
    { key: "fill", label: "Fill Form" },
    { key: "extract", label: "Extract" },
  ];

  return (
    <div className="flex h-full flex-col bg-slate-50">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-purple-100">
            <svg className="h-4 w-4 text-purple-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </div>
          <div>
            <h2 className="text-sm font-semibold text-slate-700">Web Automation</h2>
            <p className="text-xs text-slate-400">Browse, fill forms, extract data</p>
          </div>
        </div>
        {isLoading && (
          <span className="flex items-center gap-1 rounded-full bg-purple-100 px-3 py-0.5 text-xs text-purple-600">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-purple-500" />
            {step === "browsing" ? "Browsing..." : step === "smart" ? "AI filling..." : "Filling..."}
          </span>
        )}
      </header>

      <div className="border-b border-slate-200 bg-white px-4">
        <div className="flex gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => { setActiveTab(tab.key); setError(null); }}
              className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium transition border-b-2 ${
                activeTab === tab.key
                  ? "border-purple-600 text-purple-600"
                  : "border-transparent text-slate-500 hover:text-slate-700"
              }`}
            >
              {tab.label}
              {tab.badge && (
                <span className="rounded bg-gradient-to-r from-purple-500 to-pink-500 px-1.5 py-0.5 text-[10px] font-bold text-white">
                  {tab.badge}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      <div className="flex min-h-0 flex-1 gap-4 p-4 overflow-hidden">
        {/* Left Panel */}
        <div className="w-96 shrink-0 overflow-y-auto rounded-lg border border-slate-200 bg-white p-4">
          <div className="mb-4">
            <label className="mb-1.5 block text-xs font-medium text-slate-600">URL</label>
            <input
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/login"
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
            />
          </div>

          {/* AI Smart Fill Tab */}
          {activeTab === "smart" && (
            <>
              <div className="mb-4 rounded-md bg-gradient-to-br from-purple-50 to-pink-50 p-3">
                <div className="mb-3 text-xs font-semibold text-purple-700">Login (optional)</div>
                <div className="space-y-2">
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="Username"
                    className="w-full rounded-md border border-purple-200 bg-white px-3 py-1.5 text-sm focus:border-purple-500 focus:outline-none"
                  />
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Password"
                    className="w-full rounded-md border border-purple-200 bg-white px-3 py-1.5 text-sm focus:border-purple-500 focus:outline-none"
                  />
                </div>
              </div>

              <div className="mb-4 rounded-md bg-amber-50 p-3">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs font-semibold text-amber-700">Field Mapping</span>
                  <button
                    onClick={addSmartField}
                    className="rounded bg-amber-200 px-2 py-0.5 text-xs text-amber-800 hover:bg-amber-300"
                  >
                    + Add
                  </button>
                </div>
                <div className="space-y-2">
                  {smartFieldDefs.map((field, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <input
                        type="text"
                        value={field.key}
                        onChange={(e) => updateSmartField(i, e.target.value, field.value)}
                        placeholder="Field name (e.g. temperature)"
                        className="w-32 rounded border border-amber-200 bg-white px-2 py-1 text-xs focus:border-amber-500 focus:outline-none"
                      />
                      <input
                        type="text"
                        value={field.value}
                        onChange={(e) => updateSmartField(i, field.key, e.target.value)}
                        placeholder="Value"
                        className="flex-1 rounded border border-amber-200 bg-white px-2 py-1 text-xs focus:border-amber-500 focus:outline-none"
                      />
                      {smartFieldDefs.length > 1 && (
                        <button
                          onClick={() => removeSmartField(i)}
                          className="text-xs text-red-400 hover:text-red-600"
                        >
                          ✕
                        </button>
                      )}
                    </div>
                  ))}
                </div>
                <p className="mt-2 text-xs text-amber-600">
                  Field names support Chinese & English. AI auto-matches to page elements.
                </p>
              </div>

              <div className="mb-4 flex items-center gap-2">
                <input
                  type="checkbox"
                  id="autoSubmit"
                  checked={smartAutoSubmit}
                  onChange={(e) => setSmartAutoSubmit(e.target.checked)}
                  className="rounded border-slate-300"
                />
                <label htmlFor="autoSubmit" className="text-xs text-slate-600">
                  Auto submit after filling
                </label>
              </div>

              <button
                onClick={handleSmartFill}
                disabled={isLoading}
                className="w-full rounded-md bg-gradient-to-r from-purple-600 to-pink-600 px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50"
              >
                {isLoading ? "AI Filling..." : "AI Smart Fill & Submit"}
              </button>

              {smartResult && (
                <div className="mt-3 rounded-md bg-slate-50 p-3 text-xs">
                  <div className="mb-1 font-medium text-slate-700">
                    Result: {smartResult.fields_filled} fields filled
                    {smartResult.failed_fields.length > 0 && (
                      <span className="text-red-500"> ({smartResult.failed_fields.length} failed)</span>
                    )}
                  </div>
                  {smartResult.filled_fields.length > 0 && (
                    <div className="space-y-0.5">
                      {smartResult.filled_fields.map((f, i) => (
                        <div key={i} className="text-green-700">
                          ✓ {f.field} → {f.matched_to}: {f.value}
                        </div>
                      ))}
                    </div>
                  )}
                  {smartResult.failed_fields.length > 0 && (
                    <div className="mt-1 space-y-0.5">
                      {smartResult.failed_fields.map((f, i) => (
                        <div key={i} className="text-red-600">
                          ✗ {f.field}: {f.reason}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {/* Browse Tab */}
          {activeTab === "browse" && (
            <>
              <button
                onClick={handleBrowse}
                disabled={isLoading}
                className="mb-4 w-full rounded-md bg-purple-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-purple-700 disabled:opacity-50"
              >
                {isLoading ? "Browsing..." : "Analyze Page Structure"}
              </button>

              {browseResult && (
                <div className="rounded-md bg-slate-50 p-3">
                  <div className="mb-2 text-xs font-medium text-slate-600">Page Info</div>
                  <div className="mb-1 text-xs text-slate-500">Title: {browseResult.title}</div>
                  <div className="mb-2 text-xs text-slate-500 truncate">URL: {browseResult.url}</div>
                  <div className="mb-2 rounded bg-white p-2 text-xs text-slate-600 max-h-32 overflow-auto">
                    {browseResult.text_content?.slice(0, 500)}
                    {browseResult.text_content?.length > 500 ? "..." : ""}
                  </div>
                  <div className="flex gap-4 text-xs text-slate-500">
                    <span>Inputs: {browseResult.form_elements?.inputs?.length || 0}</span>
                    <span>Buttons: {browseResult.form_elements?.buttons?.length || 0}</span>
                  </div>
                </div>
              )}
            </>
          )}

          {/* Fill Form Tab */}
          {activeTab === "fill" && (
            <>
              <div className="mb-4 space-y-3">
                <div className="rounded-md bg-blue-50 p-3">
                  <div className="mb-2 text-xs font-medium text-blue-700">Login (optional)</div>
                  <div className="space-y-2">
                    <input
                      type="text"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      placeholder="Username"
                      className="w-full rounded-md border border-blue-200 bg-white px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
                    />
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Password"
                      className="w-full rounded-md border border-blue-200 bg-white px-3 py-1.5 text-sm focus:border-blue-500 focus:outline-none"
                    />
                  </div>
                </div>

                {browseResult?.form_elements?.inputs && (
                  <div className="rounded-md bg-amber-50 p-3">
                    <div className="mb-2 text-xs font-medium text-amber-700">Field Mapping</div>
                    <div className="space-y-2 max-h-48 overflow-auto">
                      {browseResult.form_elements.inputs
                        .filter((el: FormElement) => el.visible)
                        .map((el: FormElement) => (
                          <div key={el.index} className="flex items-center gap-2">
                            <span className="w-20 shrink-0 text-xs text-slate-500 truncate">
                              {el.name || el.id || `Field${el.index}`}
                            </span>
                            <input
                              type="text"
                              value={formFields[String(el.index)] || ""}
                              onChange={(e) => updateFormField(String(el.index), e.target.value)}
                              placeholder={el.placeholder || "Value"}
                              className="flex-1 rounded border border-amber-200 bg-white px-2 py-1 text-xs focus:border-amber-500 focus:outline-none"
                            />
                          </div>
                        ))}
                    </div>
                  </div>
                )}
              </div>

              <button
                onClick={handleFillForm}
                disabled={isLoading}
                className="w-full rounded-md bg-purple-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-purple-700 disabled:opacity-50"
              >
                {isLoading ? "Filling..." : "Fill & Submit"}
              </button>
            </>
          )}

          {/* Extract Tab */}
          {activeTab === "extract" && (
            <>
              <div className="mb-4">
                <label className="mb-1.5 block text-xs font-medium text-slate-600">CSS Selector (optional)</label>
                <input
                  type="text"
                  value={extractSelector}
                  onChange={(e) => setExtractSelector(e.target.value)}
                  placeholder="e.g. .content, #table, table"
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-purple-500 focus:outline-none focus:ring-1 focus:ring-purple-500"
                />
              </div>
              <button
                onClick={handleExtract}
                disabled={isLoading}
                className="w-full rounded-md bg-purple-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-purple-700 disabled:opacity-50"
              >
                Extract Text
              </button>
            </>
          )}

          {error && (
            <div className="mt-3 rounded-md bg-red-50 p-3 text-sm text-red-600">
              {error}
            </div>
          )}
        </div>

        {/* Right Preview */}
        <div className="min-w-0 flex-1 overflow-hidden rounded-lg border border-slate-200 bg-slate-900">
          <div className="flex h-full flex-col">
            <div className="flex items-center justify-between border-b border-slate-700 bg-slate-800 px-4 py-2">
              <span className="text-xs font-medium text-slate-300">
                {smartResult ? "AI Fill Result" : fillResult ? "Fill Result" : browseResult ? "Page Preview" : "Preview"}
              </span>
              <span className="text-xs text-slate-500">
                {smartResult
                  ? `${smartResult.fields_filled} fields · ${smartResult.submitted ? "Submitted" : "Not submitted"}`
                  : fillResult
                  ? `${fillResult.fields_filled} fields · ${fillResult.submitted ? "Submitted" : "Not submitted"}`
                  : browseResult
                  ? `${browseResult.width}×${browseResult.height}`
                  : ""}
              </span>
            </div>

            <div className="flex-1 overflow-auto p-4">
              {(smartResult?.screenshot_base64 || fillResult?.screenshot_base64) ? (
                <img
                  src={`data:${(smartResult || fillResult)?.screenshot_mime};base64,${(smartResult || fillResult)?.screenshot_base64}`}
                  alt="result"
                  className="mx-auto max-w-full rounded border border-slate-700"
                />
              ) : browseResult?.screenshot_base64 ? (
                <img
                  src={`data:${browseResult.screenshot_mime};base64,${browseResult.screenshot_base64}`}
                  alt="page preview"
                  className="mx-auto max-w-full rounded border border-slate-700"
                />
              ) : extractResult ? (
                <div className="space-y-2 text-sm">
                  {extractResult.content?.map((item: any, i: number) => (
                    <div key={i} className="rounded bg-slate-800 p-3">
                      <div className="mb-1 text-xs text-slate-500">[{item.tag}] Index: {item.index}</div>
                      <div className="text-slate-300">{item.text}</div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex h-full flex-col items-center justify-center text-slate-500">
                  <svg className="mb-3 h-16 w-16 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                  </svg>
                  <p className="text-sm">Enter a URL to get started</p>
                  <p className="mt-1 text-xs">AI Smart Fill can fill forms in one step</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}