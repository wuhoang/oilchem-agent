/**
 * App 根组件。
 *
 * 布局：NavRail（窄图标导航） + 功能区 + ChatPanel（常驻右侧聊天面板）。
 * 聊天不再是 Tab：用户在任意功能页面都可直接对话，当前页面作为
 * context 传给后端，后端据此加载对应的工具子集。
 */

import { useEffect, useState } from "react";
import { NavRail } from "./components/NavRail";
import { ChatPanel } from "./components/ChatPanel";
import { FileBrowser } from "./components/FileBrowser";
import { HardwarePanel } from "./components/HardwarePanel";
import { DatabasePanel } from "./components/DatabasePanel";
import { WebFormPanel } from "./components/WebFormPanel";
import { ExperimentCenter } from "./components/ExperimentCenter";
import { ErrorToast } from "./components/ErrorToast";
import { LoginPage } from "./components/LoginPage";
import { fetchMe, setToken, type AuthUser } from "./services/api";

type TabType = "experiments" | "files" | "hardware" | "database" | "webform";

function App() {
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [sidebarRefresh, setSidebarRefresh] = useState(0);
  const [activeTab, setActiveTab] = useState<TabType>("experiments");
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [authEnabled, setAuthEnabled] = useState(false);
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    fetchMe()
      .then((res) => {
        setAuthEnabled(res.auth_enabled);
        setCurrentUser(res.user);
      })
      .catch(() => {
        // 后端不可达时不拦截页面，保持开放模式
      })
      .finally(() => setAuthChecked(true));
  }, []);

  useEffect(() => {
    const onAuthExpired = () => {
      setCurrentUser(null);
    };
    window.addEventListener("auth:expired", onAuthExpired);
    return () => window.removeEventListener("auth:expired", onAuthExpired);
  }, []);

  const handleLoginSuccess = (username: string, role: string) => {
    setCurrentUser({ id: 0, username, role });
    setAuthEnabled(true);
  };

  const handleLogout = () => {
    setToken(null);
    setCurrentUser(null);
  };

  if (authChecked && authEnabled && !currentUser) {
    return (
      <>
        <LoginPage onLoginSuccess={handleLoginSuccess} />
        <ErrorToast />
      </>
    );
  }

  const handleSelectSession = (sessionId: string) => {
    setCurrentSessionId(sessionId);
  };

  const handleNewSession = () => {
    setCurrentSessionId(null);
    setSidebarRefresh((k) => k + 1);
  };

  const handleSessionCreated = (sessionId: string) => {
    setCurrentSessionId(sessionId);
    setSidebarRefresh((k) => k + 1);
  };

  const handleMessageComplete = () => {
    setSidebarRefresh((k) => k + 1);
  };

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-gradient-to-br from-slate-50 via-slate-50 to-blue-50/30">
      {/* 左侧：窄图标导航 */}
      <NavRail
        activeTab={activeTab}
        onTabChange={(tab) => setActiveTab(tab as TabType)}
      />

      {/* 中间：功能区 */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* 顶部栏（无 Tab 切换，仅标题 + 用户信息） */}
        <header className="flex items-center border-b border-slate-200 bg-white/80 px-4 py-2 backdrop-blur">
          <div className="mr-4 hidden items-center gap-2 md:flex">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 via-teal-500 to-emerald-500 text-sm font-bold text-white shadow-sm">
              OC
            </div>
            <div className="leading-tight">
              <div className="text-sm font-semibold text-slate-800">
                OilChem Agent
              </div>
              <div className="text-xs text-slate-400">
                智能实验室 · 人-机-物 中间层
              </div>
            </div>
          </div>

          <div className="ml-auto flex items-center gap-3 text-xs text-slate-500">
            {currentUser && (
              <span className="flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
                {currentUser.username}
                <span className="text-slate-400">({currentUser.role})</span>
                <button
                  onClick={handleLogout}
                  className="ml-1 text-slate-400 hover:text-red-500"
                  title="退出登录"
                >
                  退出
                </button>
              </span>
            )}
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-500" />
              服务正常
            </span>
            <span className="hidden md:inline">v2.1.1</span>
          </div>
        </header>

        {/* 主内容 */}
        <main className="flex min-h-0 flex-1 overflow-hidden">
          {activeTab === "experiments" && <ExperimentCenter />}
          {activeTab === "files" && <FileBrowser />}
          {activeTab === "hardware" && <HardwarePanel />}
          {activeTab === "database" && <DatabasePanel />}
          {activeTab === "webform" && <WebFormPanel />}
        </main>
      </div>

      {/* 右侧：常驻聊天面板（可折叠） */}
      <ChatPanel
        currentSessionId={currentSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        refreshKey={sidebarRefresh}
        onSessionCreated={handleSessionCreated}
        onMessageComplete={handleMessageComplete}
        context={activeTab}
        collapsed={chatCollapsed}
        onToggleCollapsed={() => setChatCollapsed((c) => !c)}
      />

      {/* 全局错误提示 */}
      <ErrorToast />
    </div>
  );
}

export default App;
