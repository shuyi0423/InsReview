#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import ssl
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_env_file(path: Path, *, override: bool) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if override or key not in os.environ:
            os.environ[key] = value


def load_profile_env(profile: str) -> None:
    load_env_file(PROJECT_ROOT / ".env", override=False)
    if profile != "local":
        profile_path = PROJECT_ROOT / "env" / f"{profile}.env"
        if not profile_path.exists():
            raise SystemExit(f"Missing env profile file: {profile_path}")
        load_env_file(profile_path, override=True)


def chrome_time_to_unix(expires_utc: int) -> int:
    return int((expires_utc / 1_000_000) - 11_644_473_600)


def mac_chrome_safe_storage_password() -> bytes:
    try:
        return subprocess.check_output(
            ["security", "find-generic-password", "-w", "-s", "Chrome Safe Storage"],
            stderr=subprocess.DEVNULL,
        ).rstrip(b"\n")
    except subprocess.CalledProcessError as error:
        raise RuntimeError("Unable to read macOS Chrome Safe Storage keychain item.") from error


def decrypt_mac_chrome_cookie(host_key: str, encrypted_value: bytes) -> str:
    if not encrypted_value:
        return ""
    if encrypted_value[:3] not in (b"v10", b"v11"):
        raise RuntimeError(f"Unsupported Chrome cookie prefix for {host_key!r}: {encrypted_value[:3]!r}")

    password = mac_chrome_safe_storage_password()
    key = hashlib.pbkdf2_hmac("sha1", password, b"saltysalt", 1003, 16)
    iv = b" " * 16
    decrypted = subprocess.run(
        ["openssl", "enc", "-d", "-aes-128-cbc", "-K", key.hex(), "-iv", iv.hex()],
        input=encrypted_value[3:],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    ).stdout

    # Chrome 130+ stores SHA256(host_key) before the actual cookie plaintext.
    if len(decrypted) > 35 and decrypted[32:35] == b"eyJ":
        decrypted = decrypted[32:]
    return decrypted.decode("utf-8")


def default_myaccount_host(app_host: str) -> str | None:
    if app_host == "contract-agent.qfei.cn":
        return "myaccount.qfei.cn"
    if app_host.endswith("-contract-agent.qtech.cn"):
        return app_host.replace("-contract-agent.qtech.cn", "-myaccount.qtech.cn")
    return None


def default_micro_app_host(app_host: str) -> str | None:
    if app_host == "contract-agent.qfei.cn":
        return "contract.qfei.cn"
    if app_host.endswith("-contract-agent.qtech.cn"):
        return app_host.replace("-contract-agent.qtech.cn", "-contract.qtech.cn")
    return None


def cookie_query_hosts(app_host: str) -> list[str]:
    hosts = [app_host, f".{app_host}"]
    myaccount_host = default_myaccount_host(app_host)
    if myaccount_host:
        hosts.extend([myaccount_host, f".{myaccount_host}"])
    micro_app_host = default_micro_app_host(app_host)
    if micro_app_host:
        hosts.extend([micro_app_host, f".{micro_app_host}"])
    return hosts


def same_site_value(value: int) -> str | None:
    if value == 0:
        return "None"
    if value == 1:
        return "Lax"
    if value == 2:
        return "Strict"
    # Playwright's storage_state schema expects an explicit value.
    return "Lax"


def read_chrome_cookies(
    cookie_db: Path,
    app_host: str,
) -> list[dict[str, Any]]:
    if not cookie_db.exists():
        raise RuntimeError(f"Chrome cookie database does not exist: {cookie_db}")

    hosts = cookie_query_hosts(app_host)
    placeholders = ",".join("?" for _ in hosts)
    query = f"""
        select host_key, name, value, encrypted_value, path, expires_utc,
               is_secure, is_httponly, samesite
        from cookies
        where host_key in ({placeholders})
          and name = 'zs_session'
    """

    connection = sqlite3.connect(str(cookie_db))
    rows = connection.execute(query, hosts).fetchall()
    if not rows:
        raise RuntimeError(
            "No zs_session cookie found in Chrome profile for: " + ", ".join(hosts)
        )

    cookies: list[dict[str, Any]] = []
    for host_key, name, value, encrypted_value, path, expires_utc, is_secure, is_httponly, samesite in rows:
        cookie_value = value or decrypt_mac_chrome_cookie(host_key, encrypted_value)
        if not cookie_value:
            continue
        cookie: dict[str, Any] = {
            "name": name,
            "value": cookie_value,
            "domain": host_key,
            "path": path or "/",
            "expires": chrome_time_to_unix(expires_utc),
            "httpOnly": bool(is_httponly),
            "secure": bool(is_secure),
        }
        same_site = same_site_value(int(samesite))
        if same_site:
            cookie["sameSite"] = same_site
        cookies.append(cookie)

    if not cookies:
        raise RuntimeError("Chrome profile contained zs_session rows, but no readable values.")
    return cookies


def fetch_user_info(app_origin: str, app_cookie: dict[str, Any]) -> dict[str, Any]:
    request = Request(
        f"{app_origin}/api/v2/smart/v1/auth/user-info",
        headers={
            "Accept": "application/json",
            "Cookie": f"{app_cookie['name']}={app_cookie['value']}",
            "User-Agent": "Mozilla/5.0",
        },
    )
    context = ssl._create_unverified_context()
    with urlopen(request, timeout=60, context=context) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("code") != 200 or not isinstance(payload.get("data"), dict):
        raise RuntimeError(f"user-info response is not successful: {payload}")
    return payload["data"]


def app_cookie_for_host(cookies: list[dict[str, Any]], app_host: str) -> dict[str, Any]:
    for cookie in cookies:
        domain = cookie.get("domain", "")
        if domain in (app_host, f".{app_host}"):
            return cookie
    raise RuntimeError(f"No app zs_session cookie found for {app_host}")


def load_existing_origins(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data.get("origins", [])


def build_auth_state(
    cookies: list[dict[str, Any]],
    app_origin: str,
    user_info: dict[str, Any],
    existing_origins: list[dict[str, Any]],
) -> dict[str, Any]:
    origins = [origin for origin in existing_origins if origin.get("origin") != app_origin]
    existing_local_storage: list[dict[str, str]] = []
    for origin in existing_origins:
        if origin.get("origin") == app_origin:
            existing_local_storage = [
                item
                for item in origin.get("localStorage", [])
                if item.get("name") not in {"auth", "userInfo", "token"}
            ]
            break

    local_storage = [
        *existing_local_storage,
        {"name": "auth", "value": "true"},
        {"name": "userInfo", "value": json.dumps(user_info, ensure_ascii=False)},
    ]
    token = user_info.get("token")
    if token:
        local_storage.append({"name": "token", "value": token})
    origins.append({"origin": app_origin, "localStorage": local_storage})
    return {"cookies": cookies, "origins": origins}


def resolve_project_path(path_value: str) -> Path:
    path = Path(path_value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Refresh InsReview Playwright auth state from a local Chrome profile."
    )
    parser.add_argument(
        "profile",
        nargs="?",
        default="test",
        choices=("local", "dev", "test", "online"),
        help="InsReview env profile to load.",
    )
    parser.add_argument(
        "--chrome-user-data-dir",
        default=os.getenv("CHROME_USER_DATA_DIR", "~/Library/Application Support/Google/Chrome"),
        help="Chrome user data root directory.",
    )
    parser.add_argument(
        "--chrome-profile",
        default=os.getenv("CHROME_PROFILE_DIRECTORY", "Default"),
        help="Chrome profile directory, for example Default or Profile 1.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output storage_state JSON path. Defaults to AUTH_STORAGE_STATE_PATH from the env profile.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_profile_env(args.profile)

    app_login_url = os.getenv("APP_LOGIN_URL")
    if not app_login_url:
        raise SystemExit("APP_LOGIN_URL is required. Use an env profile or set it explicitly.")
    parsed = urlparse(app_login_url)
    app_origin = f"{parsed.scheme}://{parsed.netloc}"
    app_host = parsed.netloc

    output = resolve_project_path(args.output or os.getenv("AUTH_STORAGE_STATE_PATH", ".auth/feishu-login-state.json"))
    chrome_profile = Path(args.chrome_user_data_dir).expanduser() / args.chrome_profile
    cookie_db = chrome_profile / "Cookies"

    cookies = read_chrome_cookies(cookie_db, app_host)
    user_info = fetch_user_info(app_origin, app_cookie_for_host(cookies, app_host))
    state = build_auth_state(cookies, app_origin, user_info, load_existing_origins(output))

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "profile": args.profile,
                "chromeProfile": str(chrome_profile),
                "output": str(output),
                "cookieDomains": [cookie["domain"] for cookie in cookies],
                "user": user_info.get("name"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"refresh_auth_from_chrome failed: {error}", file=sys.stderr)
        raise SystemExit(1)
