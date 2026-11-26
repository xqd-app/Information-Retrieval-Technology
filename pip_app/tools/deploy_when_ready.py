"""等服务器接受公钥后自动部署（轮询，最多等 12 分钟）。

用途：用户去面板粘贴公钥的这段时间，这边可以自动接手，无需再同步一次。
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

HOST = os.environ.get("PIP_SSH_HOST", "de3.nodaroo.fun")
PORT = int(os.environ.get("PIP_SSH_PORT", "2022"))
USER = os.environ.get("PIP_SSH_USER", "free_1564394058917482544.27cfb8f4")
KEY = os.environ.get("PIP_SSH_KEY", str(Path.home() / ".ssh" / "pip_deploy"))
REMOTE_DIR = os.environ.get("PIP_REMOTE_DIR", "pip")

PROBE = "echo READY; id; python3 --version 2>&1 || python --version 2>&1"


def try_connect(timeout: float = 12) -> paramiko.SSHClient | None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            HOST, port=PORT, username=USER, key_filename=KEY,
            timeout=timeout, banner_timeout=20, auth_timeout=20,
            allow_agent=False, look_for_keys=False,
        )
        return client
    except paramiko.AuthenticationException:
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"  连接异常：{type(exc).__name__}: {exc}", flush=True)
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rounds", type=int, default=48, help="轮询次数")
    parser.add_argument("--interval", type=int, default=15, help="间隔秒")
    parser.add_argument("--deploy", action="store_true", help="连上后立即部署")
    args = parser.parse_args(argv)

    if not Path(KEY).exists():
        print(f"找不到私钥：{KEY}")
        return 2

    print(f"等待 {USER}@{HOST}:{PORT} 接受公钥（{args.rounds} 轮 × {args.interval}s）…", flush=True)
    for i in range(1, args.rounds + 1):
        client = try_connect()
        if client:
            print(f"第 {i} 轮：公钥已生效", flush=True)
            try:
                _in, out, err = client.exec_command(PROBE, timeout=25)
                print(out.read().decode("utf-8", "replace").strip(), flush=True)
                tail = err.read().decode("utf-8", "replace").strip()
                if tail:
                    print("[stderr]", tail[:300], flush=True)
            finally:
                client.close()

            if args.deploy:
                from pip_app.tools import deploy_sftp

                os.environ.setdefault("PIP_SSH_KEY", KEY)
                print("开始部署 …", flush=True)
                return deploy_sftp.main([])
            return 0
        print(f"第 {i} 轮：未生效，{args.interval}s 后重试", flush=True)
        time.sleep(args.interval)

    print("超时：服务器仍未接受公钥")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
