/**
 * 登录页。
 *
 * 账号密码登录，成功后进入主界面。
 */

import { useState } from "react";
import { login } from "../services/api";

interface LoginPageProps {
  onLoginSuccess: (username: string, role: string) => void;
}

export function LoginPage({ onLoginSuccess }: LoginPageProps) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      setError("请输入用户名和密码");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const user = await login(username.trim(), password);
      onLoginSuccess(user.username, user.role);
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败，请重试");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-screen items-center justify-center bg-gradient-to-br from-slate-50 via-slate-50 to-blue-50/30">
      <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white/90 p-8 shadow-lg backdrop-blur">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 via-teal-500 to-emerald-500 text-sm font-bold text-white shadow-sm">
            OC
          </div>
          <div>
            <div className="text-lg font-semibold text-slate-800">
              OilChem Agent
            </div>
            <div className="text-xs text-slate-400">智能实验室 · 登录</div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">
              用户名
            </label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              placeholder="请输入用户名"
              autoFocus
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">
              密码
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
              placeholder="请输入密码"
            />
          </div>

          {error && (
            <div className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-600">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-slate-900 py-2 text-sm font-medium text-white transition hover:bg-slate-700 disabled:opacity-50"
          >
            {loading ? "登录中..." : "登 录"}
          </button>
        </form>

        <div className="mt-4 text-center text-xs text-slate-400">
          演示账号：admin / operator / reviewer（密码见 backend/.env）
        </div>
      </div>
    </div>
  );
}