"""
OilChem Agent 一键启动器。

自动完成环境检查、依赖安装、配置生成和服务启动。
支持 Windows / Linux / macOS。
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# ── 路径常量 ──────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"
VENV_DIR = BACKEND_DIR / ".venv"
VENV_PYTHON = VENV_DIR / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
NODE_MODULES = FRONTEND_DIR / "node_modules"
ENV_FILE = BACKEND_DIR / ".env"
ENV_EXAMPLE = BACKEND_DIR / ".env.example"

BACKEND_PORT = 8000
FRONTEND_PORT = 5173

# 解析 npm 路径（Windows 下是 npm.cmd）
_NPM_PATH = shutil.which("npm")
if _NPM_PATH and sys.platform == "win32":
    npm_cmd = _NPM_PATH
else:
    npm_cmd = _NPM_PATH or "npm"


# ── 工具函数 ──────────────────────────────────────────────────────
def banner():
    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║       OilChem Agent  一键启动器                    ║")
    print("║       石油化工智能实验室 Agent 平台                  ║")
    print("╚══════════════════════════════════════════════════╝")
    print()


def step(msg: str):
    print(f"  ▶ {msg} ...")


def ok(msg: str = ""):
    print(f"    ✅ {msg}")


def fail(msg: str):
    print(f"    ❌ {msg}")


def skip(msg: str):
    print(f"    ⏭ {msg}")


def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess | None:
    """运行命令并打印输出。自动解析 npm 路径。"""
    display = " ".join(cmd)
    print(f"    $ {display}")
    try:
        actual_cmd = _resolve_cmd(cmd)
        result = subprocess.run(
            actual_cmd,
            cwd=kwargs.pop("cwd", ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=(sys.platform == "win32"),
            **kwargs,
        )
        if result.stdout.strip():
            for line in result.stdout.strip().split("\n")[-5:]:
                print(f"      {line}")
        if result.returncode != 0 and result.stderr.strip():
            for line in result.stderr.strip().split("\n")[-5:]:
                print(f"      ⚠ {line}")
        return result
    except FileNotFoundError:
        return None


def _resolve_cmd(cmd: list[str]) -> list[str]:
    """解析命令，替换 npm 等需要在 Windows 下找 .cmd 版本的工具。"""
    if cmd and cmd[0] == "npm" and npm_cmd:
        return [npm_cmd] + cmd[1:]
    return cmd


def port_in_use(port: int) -> bool:
    """检查端口是否被占用。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def kill_port(port: int):
    """杀掉占用指定端口的进程。"""
    if not port_in_use(port):
        return
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["netstat", "-aon"],
                capture_output=True, text=True, shell=True,
            )
            for line in result.stdout.splitlines():
                if f":{port}" in line and "LISTENING" in line:
                    parts = line.strip().split()
                    pid = int(parts[-1])
                    subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                                   capture_output=True, shell=True)
                    print(f"    🧹 已清理端口 {port} 上的进程 PID={pid}")
        except Exception:
            pass
    else:
        try:
            subprocess.run(
                ["fuser", "-k", str(port)],
                capture_output=True, shell=True,
            )
        except Exception:
            pass


# ── 步骤函数 ──────────────────────────────────────────────────────
def check_prerequisites() -> bool:
    """检查 Python 和 Node.js 环境。"""
    step("检查 Python 环境")
    result = run([sys.executable, "--version"])
    if result and result.returncode == 0:
        ok(f"Python {result.stdout.strip()}")
    else:
        fail("未检测到 Python，请先安装 Python 3.12+")
        return False

    step("检查 Node.js 环境")
    node_path = shutil.which("node")
    if node_path:
        result = run(["node", "--version"])
        if result and result.returncode == 0:
            ok(f"Node.js {result.stdout.strip()}")
        else:
            fail("Node.js 异常")
            return False
    else:
        fail("未检测到 Node.js，请先安装 Node.js 22+")
        return False

    step("检查 npm 环境")
    if npm_cmd:
        result = run(["npm", "--version"])
        if result and result.returncode == 0:
            ok(f"npm {result.stdout.strip()}")
        else:
            fail("npm 异常")
            return False
    else:
        fail("未检测到 npm")
        return False

    return True


def setup_backend_venv() -> bool:
    """创建后端虚拟环境。"""
    if VENV_PYTHON.exists():
        skip("虚拟环境已存在")
        return True

    step("创建后端虚拟环境")
    result = run([sys.executable, "-m", "venv", str(VENV_DIR)], cwd=BACKEND_DIR)
    if result and result.returncode == 0:
        ok("虚拟环境创建成功")
        return True
    else:
        fail("虚拟环境创建失败")
        return False


def install_backend_deps() -> bool:
    """安装后端 Python 依赖。"""
    step("安装后端依赖（首次可能较慢）")
    result = run(
        [str(VENV_PYTHON), "-m", "pip", "install", "-r", "requirements.txt"],
        cwd=BACKEND_DIR,
    )
    if result and result.returncode == 0:
        ok("后端依赖安装完成")
        return True
    else:
        fail("后端依赖安装失败")
        return False


def setup_env() -> bool:
    """创建 .env 配置文件。"""
    if ENV_FILE.exists():
        skip(".env 已存在")
        return True

    step("创建 .env 配置文件")
    if ENV_EXAMPLE.exists():
        shutil.copy(ENV_EXAMPLE, ENV_FILE)
        ok(f"已从 .env.example 复制，请编辑 {ENV_FILE} 配置 LLM")
        print("      ⓘ 首次使用请在 .env 中设置 MODEL_NAME 和 API Key")
        return True
    else:
        fail(".env.example 不存在")
        return False


def install_frontend_deps() -> bool:
    """安装前端 npm 依赖。"""
    if NODE_MODULES.exists():
        skip("前端依赖已存在")
        return True

    step("安装前端依赖（首次可能较慢）")
    result = run(["npm", "install"], cwd=FRONTEND_DIR)
    if result and result.returncode == 0:
        ok("前端依赖安装完成")
        return True
    else:
        fail("前端依赖安装失败")
        return False


def start_backend() -> subprocess.Popen | None:
    """在独立进程中启动后端服务。"""
    if port_in_use(BACKEND_PORT):
        print(f"    ⚠ 端口 {BACKEND_PORT} 已被占用，正在清理...")
        kill_port(BACKEND_PORT)
        time.sleep(1)
        if port_in_use(BACKEND_PORT):
            print(f"    ⚠ 端口 {BACKEND_PORT} 仍被占用，请手动释放后重试")
            return None

    step("启动后端服务")
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    if sys.platform == "win32":
        DETACHED_PROCESS = 0x00000008
        proc = subprocess.Popen(
            [str(VENV_PYTHON), "-m", "app.main"],
            cwd=str(BACKEND_DIR),
            env=env,
            creationflags=DETACHED_PROCESS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        proc = subprocess.Popen(
            [str(VENV_PYTHON), "-m", "app.main"],
            cwd=str(BACKEND_DIR),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    time.sleep(2)
    ok(f"后端 PID={proc.pid}")
    return proc


def start_frontend() -> subprocess.Popen | None:
    """在独立进程中启动前端开发服务器。"""
    if port_in_use(FRONTEND_PORT):
        print(f"    ⚠ 端口 {FRONTEND_PORT} 已被占用，正在清理...")
        kill_port(FRONTEND_PORT)
        time.sleep(1)
        if port_in_use(FRONTEND_PORT):
            print(f"    ⚠ 端口 {FRONTEND_PORT} 仍被占用，请手动释放后重试")
            return None

    step("启动前端开发服务器")
    npm_exe = npm_cmd or "npm"

    if sys.platform == "win32":
        DETACHED_PROCESS = 0x00000008
        proc = subprocess.Popen(
            [npm_exe, "run", "dev"],
            cwd=str(FRONTEND_DIR),
            creationflags=DETACHED_PROCESS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            shell=True,
        )
    else:
        proc = subprocess.Popen(
            [npm_exe, "run", "dev"],
            cwd=str(FRONTEND_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            shell=True,
        )

    time.sleep(3)
    ok(f"前端 PID={proc.pid}")
    return proc


def print_summary():
    """打印启动完成信息。"""
    print()
    print("╔══════════════════════════════════════════════════╗")
    print("║  🎉 服务已启动！                                 ║")
    print("╠══════════════════════════════════════════════════╣")
    print(f"║  🖥  前端界面:  http://localhost:{FRONTEND_PORT}")
    print(f"║  ⚙  后端 API:  http://localhost:{BACKEND_PORT}")
    print(f"║  📖 文档:      http://localhost:{BACKEND_PORT}/docs")
    print("╠══════════════════════════════════════════════════╣")
    print("║  📌 提示:                                       ║")
    print("║  • 首次使用请编辑 backend/.env 配置 LLM          ║")
    print("║  • 停止服务: 双击 stop.bat 即可                 ║")
    print("╚══════════════════════════════════════════════════╝")
    print()

    try:
        webbrowser.open(f"http://localhost:{FRONTEND_PORT}")
        ok("已自动打开浏览器")
    except Exception:
        print("    ⓘ 请手动打开浏览器访问上述地址")


def main():
    banner()

    # 1. 环境检查
    if not check_prerequisites():
        print("\n  ❌ 环境检查未通过，请先安装缺失的依赖后重试。\n")
        sys.exit(1)

    print()

    # 2. 后端准备
    if not setup_backend_venv():
        sys.exit(1)
    if not install_backend_deps():
        sys.exit(1)
    if not setup_env():
        sys.exit(1)

    print()

    # 3. 前端准备
    if not install_frontend_deps():
        sys.exit(1)

    print()

    # 4. 启动服务
    backend_proc = start_backend()
    frontend_proc = start_frontend()

    print()

    # 5. 等待后端就绪
    step("等待后端服务就绪")
    for i in range(15):
        if port_in_use(BACKEND_PORT):
            ok("后端服务已就绪")
            break
        time.sleep(0.5)
    else:
        print("    ⚠ 后端服务可能仍在启动中，请稍候")

    # 6. 等待前端就绪
    step("等待前端服务就绪")
    for i in range(15):
        if port_in_use(FRONTEND_PORT):
            ok("前端服务已就绪")
            break
        time.sleep(0.5)
    else:
        print("    ⚠ 前端服务可能仍在启动中，请稍候")

    print_summary()

    # 保持运行直到用户按回车
    try:
        input("按回车键退出（服务将继续在后台运行）...")
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    main()