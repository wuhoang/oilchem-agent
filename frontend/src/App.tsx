/**
 * App 根组件。
 *
 * 布局：左侧会话/模块导航 + 右侧主内容区
 * 支持 Tab 切换：对话、文件、硬件、数据库
 */

import { useEffect, useState } from "react";
import { Sidebar } from "./components/Sidebar";
import { ChatWindow } from "./components/ChatWindow";
import { FileBrowser } from "./components/FileBrowser";
import { HardwarePanel } from "./components/HardwarePanel";
import { DatabasePanel } from "./components/DatabasePanel";
import { WebFormPanel } from "./components/WebFormPanel";
import { ExperimentCenter } from "./components/ExperimentCenter";
import { ErrorToast } from "./components/ErrorToast";
import { LoginPage } from "./components/LoginPage";
import { fetchMe, setToken, type AuthUser } from "./services/api";

type TabType = "chat" | "experiments" | "files" | "hardware" | "database" | "webform";

const TABS: {
  key: TabType;
  label: string;
  icon: JSX.Element;
  accent: string;
}[] = [
  {
    key: "chat",
    label: "智能对话",
    accent: "text-blue-600",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
      </svg>
    ),
  },
  {
    key: "experiments",
    label: "实验中心",
    accent: "text-rose-600",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23-.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
      </svg>
    ),
  },
  {
    key: "files",
    label: "文件管理",
    accent: "text-amber-600",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
      </svg>
    ),
  },
  {
    key: "hardware",
    label: "硬件设备",
    accent: "text-emerald-600",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23-.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5" />
      </svg>
    ),
  },
  {
    key: "database",
    label: "数据管理",
    accent: "text-violet-600",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M20.25 6.375c0 2.278-3.694 4.125-8.25 4.125S3.75 8.653 3.75 6.375m16.5 0c0-2.278-3.694-4.125-8.25-4.125S3.75 4.097 3.75 6.375m16.5 0v11.25c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125V6.375m16.5 0v3.75m-16.5-3.75v3.75m16.5 0v3.75C20.25 16.153 16.556 18 12 18s-8.25-1.847-8.25-4.125v-3.75m16.5 0c0 2.278-3.694 4.125-8.25 4.125s-8.25-1.847-8.25-4.125" />
      </svg>
    ),
  },
  {
    key: "webform",
    label: "网页填表",
    accent: "text-purple-600",
    icon: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418" />
      </svg>
    ),
  },
];

function App() {
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [sidebarRefresh, setSidebarRefresh] = useState(0);
  const [activeTab, setActiveTab] = useState<TabType>("chat");
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
      setActiveTab("chat");
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
    setActiveTab("chat");
  };

  const handleNewSession = () => {
    setCurrentSessionId(null);
    setSidebarRefresh((k) => k + 1);
    setActiveTab("chat");
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
      <Sidebar
        currentSessionId={currentSessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        refreshKey={sidebarRefresh}
      />

      <div className="flex flex-1 flex-col min-w-0">
        {/* 顶部导航 */}
        <header className="flex items-center gap-1 border-b border-slate-200 bg-white/80 px-4 py-2 backdrop-blur">
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

          <nav className="flex items-center gap-1">
            {TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm font-medium transition ${
                  activeTab === tab.key
                    ? `bg-slate-900 text-white shadow-sm`
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <span className={activeTab === tab.key ? "" : tab.accent}>
                  {tab.icon}
                </span>
                {tab.label}
              </button>
            ))}
          </nav>

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
            <span className="hidden md:inline">v1.3.2</span>
          </div>
        </header>

        {/* 主内容 */}
        <main className="flex min-h-0 flex-1 overflow-hidden">
          <div className={activeTab === "chat" ? "flex h-full w-full flex-1" : "hidden"}>
            <ChatWindow
              sessionId={currentSessionId}
              onSessionCreated={handleSessionCreated}
              onMessageComplete={handleMessageComplete}
            />
          </div>
          {activeTab === "files" && <FileBrowser />}
          {activeTab === "experiments" && <ExperimentCenter />}
          {activeTab === "hardware" && <HardwarePanel />}
          {activeTab === "database" && <DatabasePanel />}
          {activeTab === "webform" && <WebFormPanel />}
        </main>
      </div>

      {/* 全局错误提示 */}
      <ErrorToast />
    </div>
  );
}

export default App;
