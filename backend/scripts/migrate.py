"""
Alembic 迁移管理脚本。

提供便捷的命令行接口来运行数据库迁移。

Usage::

    python -m scripts.migrate upgrade   # 升级到最新
    python -m scripts.migrate downgrade # 回滚一个版本
    python -m scripts.migrate current   # 查看当前版本
    python -m scripts.migrate history   # 查看迁移历史
    python -m scripts.migrate create    # 创建新迁移脚本
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]


def run_alembic(*args: str) -> int:
    """运行 alembic 命令。"""
    cmd = [sys.executable, "-m", "alembic"] + list(args)
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(BACKEND_ROOT))
    return result.returncode


def main() -> int:
    """主入口。"""
    if len(sys.argv) < 2:
        print(__doc__)
        return 0

    command = sys.argv[1]
    args = sys.argv[2:]

    commands = {
        "upgrade": lambda: run_alembic("upgrade", "head", *args),
        "downgrade": lambda: run_alembic("downgrade", "-1", *args),
        "current": lambda: run_alembic("current", *args),
        "history": lambda: run_alembic("history", *args),
        "stamp": lambda: run_alembic("stamp", *args),
        "create": lambda: run_alembic(
            "revision", "--autogenerate", "-m", args[0] if args else "new_migration"
        ),
        "drop": lambda: run_alembic("downgrade", "base"),
    }

    if command == "help":
        print(__doc__)
        return 0

    if command not in commands:
        print(f"Unknown command: {command}")
        print(__doc__)
        return 1

    return commands[command]()


if __name__ == "__main__":
    sys.exit(main())
