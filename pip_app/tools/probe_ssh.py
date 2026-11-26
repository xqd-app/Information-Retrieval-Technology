"""探测服务器凭据组合（只试用户给的那串的合理拆分）并读取环境信息。"""

import sys

import paramiko

HOST = "de3.nodaroo.fun"
PORT = 2022
TOKEN = "free_1564394058917482544.27cfb8f4"

CANDIDATES = [
    (TOKEN, TOKEN),
    (TOKEN, "27cfb8f4"),
    ("free_1564394058917482544", "27cfb8f4"),
    ("free_1564394058917482544", TOKEN),
]

PROBE = (
    "echo '--- id ---'; id; "
    "echo '--- os ---'; uname -a; "
    "echo '--- python ---'; (python3 --version || python --version) 2>&1; "
    "echo '--- home ---'; pwd; ls -la ~ | head -20; "
    "echo '--- disk ---'; df -h ~ | tail -2; "
    "echo '--- ports ---'; (ss -tlnp 2>/dev/null || netstat -tln 2>/dev/null) | head -15; "
    "echo '--- web ---'; (which nginx caddy apache2 2>/dev/null); "
    "echo '--- proc ---'; ps -eo pid,comm --sort=-%mem 2>/dev/null | head -8"
)


def try_login(user: str, password: str):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(HOST, port=PORT, username=user, password=password,
                       timeout=15, banner_timeout=20, auth_timeout=20,
                       allow_agent=False, look_for_keys=False)
    except paramiko.AuthenticationException:
        return None, "认证失败"
    except Exception as exc:  # noqa: BLE001
        return None, f"{type(exc).__name__}: {exc}"
    return client, "ok"


def main() -> None:
    for user, password in CANDIDATES:
        label = f"user={user[:34]:<34} pwd={'同串' if password == user else password[:14]}"
        client, status = try_login(user, password)
        if client is None:
            print(f"FAIL {label}  {status}")
            continue
        print(f"OK   {label}")
        try:
            _stdin, stdout, stderr = client.exec_command(PROBE, timeout=30)
            print(stdout.read().decode("utf-8", "replace"))
            err = stderr.read().decode("utf-8", "replace").strip()
            if err:
                print("[stderr]", err[:400])
        finally:
            client.close()
        return
    print("\n所有组合都失败：需要正确的密码（或把本机公钥加到服务器）")
    sys.exit(1)


if __name__ == "__main__":
    main()
