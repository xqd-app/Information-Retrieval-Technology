"""把部署包上传到服务器并远程解压安装。

凭据从环境变量读，不写进代码：
    PIP_SSH_USER      默认 free_1564394058917482544.27cfb8f4
    PIP_SSH_PASSWORD  必填（或改用 PIP_SSH_KEY 指向私钥）
    PIP_SSH_HOST      默认 de3.nodaroo.fun
    PIP_SSH_PORT      默认 2022
    PIP_REMOTE_DIR    默认 ~/pip

用法：
    PIP_SSH_PASSWORD=xxx python -m pip_app.tools.deploy_sftp
    PIP_SSH_PASSWORD=xxx python -m pip_app.tools.deploy_sftp --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys
import tarfile
import time
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parent.parent.parent
PACKAGE = ROOT / "dist" / "pip-deploy.tar.gz"

HOST = os.environ.get("PIP_SSH_HOST", "de3.nodaroo.fun")
PORT = int(os.environ.get("PIP_SSH_PORT", "2022"))
USER = os.environ.get("PIP_SSH_USER", "free_1564394058917482544.27cfb8f4")
PASSWORD = os.environ.get("PIP_SSH_PASSWORD", "")
KEY = os.environ.get("PIP_SSH_KEY", "")
REMOTE_DIR = os.environ.get("PIP_REMOTE_DIR", "pip")

SETUP = """
set -e
cd ~/{remote}
echo '--- 环境 ---'
python3 --version || python --version
echo '--- 解压 ---'
tar xzf pip-deploy.tar.gz
echo '--- 建库 ---'
python3 -m pip_app.cli db init || true
python3 -m pip_app.cli db sync --days 7 || true
echo '--- 自检 ---'
python3 -c "import sys; sys.path.insert(0,'.'); from pip_app import server; print('import ok')"
echo '--- 启动 ---'
mkdir -p logs
pkill -f 'pip_app.server' 2>/dev/null || true
sleep 1
PIP_HOST=0.0.0.0 PIP_PORT=8080 nohup python3 -m pip_app.server > logs/pip.log 2>&1 &
sleep 3
echo '--- 探活 ---'
curl -s --max-time 5 http://127.0.0.1:8080/healthz || echo '(curl 不可用，查看 logs/pip.log)'
echo
echo '--- 监听 ---'
(ss -tlnp 2>/dev/null || netstat -tln 2>/dev/null) | grep 8080 || true
"""


def connect() -> paramiko.SSHClient:
    if not PASSWORD and not KEY:
        raise SystemExit("缺少凭据：设置 PIP_SSH_PASSWORD（或 PIP_SSH_KEY 指向私钥）")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kwargs = dict(hostname=HOST, port=PORT, username=USER, timeout=20,
                  banner_timeout=25, auth_timeout=25, allow_agent=False, look_for_keys=False)
    if PASSWORD:
        kwargs["password"] = PASSWORD
    else:
        kwargs["key_filename"] = KEY
    client.connect(**kwargs)
    return client


def run(client: paramiko.SSHClient, command: str, timeout: int = 120) -> tuple[int, str, str]:
    _stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    return stdout.channel.recv_exit_status(), out, err


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="部署到 SFTP/SSH 服务器")
    parser.add_argument("--dry-run", action="store_true", help="只连接并打印环境，不上传")
    parser.add_argument("--keep-running", action="store_true", help="保留远程已运行的服务不重启")
    args = parser.parse_args(argv)

    if not PACKAGE.exists():
        raise SystemExit(f"找不到部署包：{PACKAGE}\n先运行 python -m pip_app.tools.pack_deploy")

    print(f"连接 {USER}@{HOST}:{PORT} …")
    client = connect()
    try:
        code, out, err = run(client, "id; uname -s; python3 --version 2>&1 || true; df -h ~ | tail -1")
        print("[remote]", out.strip() or err.strip())
        if args.dry_run:
            print("dry-run：仅探测，未上传")
            return 0

        sftp = client.open_sftp()
        try:
            run(client, f"mkdir -p ~/{REMOTE_DIR}")
            remote_path = f"{REMOTE_DIR}/pip-deploy.tar.gz"
            size = PACKAGE.stat().st_size
            started = time.time()
            sftp.put(str(PACKAGE), remote_path, callback=lambda sent, total: None)
            elapsed = time.time() - started
            print(f"上传完成 {size/1024/1024:.2f} MB / {elapsed:.1f}s")
        finally:
            sftp.close()

        command = SETUP.format(remote=REMOTE_DIR)
        if args.keep_running:
            command = command.replace("pkill -f 'pip_app.server' 2>/dev/null || true\nsleep 1\n", "")
        code, out, err = run(client, command, timeout=300)
        print(out)
        if err.strip():
            print("[stderr]", err.strip()[:1200])
        print(f"退出码 {code}")
        return code
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
