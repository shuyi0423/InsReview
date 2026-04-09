from __future__ import annotations

import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import Error as PlaywrightError, Locator, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"


def load_env_file(path: Path) -> None:
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
        os.environ.setdefault(key, value)


load_env_file(ENV_FILE)


@dataclass(frozen=True)
class LoginConfig:
    app_login_url: str
    login_entry_selector: str
    reuse_saved_auth: bool
    auth_storage_state_path: str | None
    auth_state_check_timeout_ms: int
    force_qr_login: bool
    reuse_local_chrome_profile: bool
    chrome_user_data_dir: str | None
    chrome_profile_directory: str | None
    feishu_account_picker_text: str | None
    feishu_qr_login_selector: str | None
    manual_scan_timeout_ms: int
    login_success_eval: str | None
    login_success_url_contains: str | None
    login_success_selector: str | None
    browser_name: str
    browser_channel: str | None
    browser_executable_path: str | None
    headless: bool
    slow_mo: int
    timeout_ms: int
    authorize_selector: str | None

    @property
    def app_host(self) -> str:
        return urlparse(self.app_login_url).netloc


def read_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config() -> LoginConfig:
    missing = [key for key in ("APP_LOGIN_URL",) if not os.getenv(key)]
    if missing:
        joined = ", ".join(missing)
        raise AssertionError(
            f"缺少环境变量: {joined}。请先参考 .env.example 创建 .env。"
        )

    return LoginConfig(
        app_login_url=os.environ["APP_LOGIN_URL"],
        login_entry_selector=os.getenv("LOGIN_ENTRY_SELECTOR", "text=使用飞书登录"),
        reuse_saved_auth=read_bool("REUSE_SAVED_AUTH", True),
        auth_storage_state_path=os.getenv("AUTH_STORAGE_STATE_PATH", ".auth/feishu-login-state.json"),
        auth_state_check_timeout_ms=int(os.getenv("AUTH_STATE_CHECK_TIMEOUT_MS", "5000")),
        force_qr_login=read_bool("FORCE_QR_LOGIN", False),
        reuse_local_chrome_profile=read_bool("REUSE_LOCAL_CHROME_PROFILE", False),
        chrome_user_data_dir=os.getenv("CHROME_USER_DATA_DIR"),
        chrome_profile_directory=os.getenv("CHROME_PROFILE_DIRECTORY"),
        feishu_account_picker_text=os.getenv("FEISHU_ACCOUNT_PICKER_TEXT"),
        feishu_qr_login_selector=os.getenv("FEISHU_QR_LOGIN_SELECTOR", "text=扫码登录"),
        manual_scan_timeout_ms=int(os.getenv("MANUAL_SCAN_TIMEOUT_MS", "180000")),
        login_success_eval=os.getenv("LOGIN_SUCCESS_EVAL"),
        login_success_url_contains=os.getenv("LOGIN_SUCCESS_URL_CONTAINS"),
        login_success_selector=os.getenv("LOGIN_SUCCESS_SELECTOR"),
        browser_name=os.getenv("PLAYWRIGHT_BROWSER", "chromium"),
        browser_channel=os.getenv("PLAYWRIGHT_CHANNEL"),
        browser_executable_path=os.getenv("PLAYWRIGHT_EXECUTABLE_PATH"),
        headless=read_bool("HEADLESS", True),
        slow_mo=int(os.getenv("SLOW_MO", "0")),
        timeout_ms=int(os.getenv("UI_TIMEOUT_MS", "30000")),
        authorize_selector=os.getenv("FEISHU_AUTHORIZE_SELECTOR"),
    )


def selector_candidates(custom: str | None, defaults: list[str]) -> list[str]:
    return [selector for selector in [custom, *defaults] if selector]


def resolve_project_path(path_value: str) -> Path:
    path = Path(path_value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def get_auth_storage_state_path(config: LoginConfig) -> Path | None:
    if not config.auth_storage_state_path:
        return None
    return resolve_project_path(config.auth_storage_state_path)


def candidate_scopes(page: Page) -> list[Any]:
    return [page.main_frame, *[frame for frame in page.frames if frame != page.main_frame]]


def first_visible_locator(page: Page, selectors: list[str], timeout_ms: int) -> Locator | None:
    deadline = time.time() + (timeout_ms / 1000)
    filtered_selectors = [selector for selector in selectors if selector]
    while time.time() < deadline:
        for scope in candidate_scopes(page):
            for selector in filtered_selectors:
                locator = scope.locator(selector).first
                try:
                    if locator.is_visible():
                        return locator
                except PlaywrightError:
                    return None
        page.wait_for_timeout(250)
    return None


def click_first(page: Page, selectors: list[str], timeout_ms: int, required: bool = False) -> bool:
    locator = first_visible_locator(page, selectors, timeout_ms)
    if locator is None:
        if required:
            raise AssertionError(f"没有找到可点击元素，候选选择器: {selectors}")
        return False

    try:
        locator.click(force=True)
    except PlaywrightError:
        try:
            locator.evaluate("(el) => el.click()")
        except PlaywrightError:
            if required:
                raise
            return False
    return True


def save_screenshot(page: Page, filename: str) -> None:
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    page.screenshot(path=str(ARTIFACTS_DIR / filename), full_page=True)


def save_auth_state(context, config: LoginConfig) -> None:
    storage_state_path = get_auth_storage_state_path(config)
    if storage_state_path is None:
        return

    storage_state_path.parent.mkdir(parents=True, exist_ok=True)
    context.storage_state(path=str(storage_state_path))


def is_retryable_navigation_error(error: Exception) -> bool:
    message = str(error)
    return any(
        keyword in message
        for keyword in (
            "ERR_CONNECTION_CLOSED",
            "ERR_CONNECTION_RESET",
            "ERR_NETWORK_CHANGED",
            "ERR_ABORTED",
        )
    )


def goto_page_with_retry(
    page: Page,
    url: str,
    *,
    wait_until: str = "domcontentloaded",
    attempts: int = 5,
    retry_delay_ms: int = 1500,
) -> None:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            page.goto(url, wait_until=wait_until)
            return
        except PlaywrightError as error:
            last_error = error
            if not is_retryable_navigation_error(error) or attempt == attempts - 1:
                raise
            page.wait_for_timeout(retry_delay_ms)

    assert last_error is not None
    raise last_error


def is_feishu_url(url: str) -> bool:
    return any(keyword in url for keyword in ("feishu", "larksuite"))


def close_feishu_pages_after_success(context) -> None:
    for candidate in context.pages:
        if candidate.is_closed():
            continue
        try:
            candidate_url = candidate.url
        except PlaywrightError:
            continue
        if is_feishu_url(candidate_url):
            try:
                candidate.close()
            except PlaywrightError:
                continue


def get_feishu_login_page(app_page: Page, config: LoginConfig) -> Page:
    if any(keyword in app_page.url for keyword in ("/logout", "sso/logout")):
        goto_page_with_retry(app_page, config.app_login_url)

    trigger = first_visible_locator(
        app_page,
        selector_candidates(
            config.login_entry_selector,
            [
                "text=飞书登录",
                "button:has-text('飞书')",
                "a:has-text('飞书')",
                "[data-testid='feishu-login']",
            ],
        ),
        timeout_ms=config.timeout_ms,
    )
    if trigger is None:
        raise AssertionError("没有找到业务系统里的飞书登录入口。")

    existing_pages = {id(page) for page in app_page.context.pages}
    trigger.click()

    deadline = time.time() + (config.timeout_ms / 1000)
    while time.time() < deadline:
        live_pages = [page for page in app_page.context.pages if not page.is_closed()]
        new_pages = [page for page in live_pages if id(page) not in existing_pages]
        if new_pages:
            login_page = new_pages[-1]
            login_page.wait_for_load_state("domcontentloaded")
            return login_page

        if any(keyword in app_page.url for keyword in ("feishu", "larksuite")):
            app_page.wait_for_load_state("domcontentloaded")
            return app_page

        if any(keyword in app_page.url for keyword in ("/logout", "sso/logout")):
            goto_page_with_retry(app_page, config.app_login_url)
            if first_visible_locator(
                app_page,
                selector_candidates(
                    config.login_entry_selector,
                    [
                        "text=飞书登录",
                        "button:has-text('飞书')",
                        "a:has-text('飞书')",
                        "[data-testid='feishu-login']",
                    ],
                ),
                timeout_ms=3000,
            ):
                return get_feishu_login_page(app_page, config)

        app_page.wait_for_timeout(500)

    return app_page


def switch_to_qr_login(page: Page, config: LoginConfig) -> None:
    click_first(
        page,
        selector_candidates(
            config.feishu_qr_login_selector,
            [
                "text=扫码登录",
                "button:has-text('扫码登录')",
                "[role='button']:has-text('扫码登录')",
            ],
        ),
        timeout_ms=5000,
        required=False,
    )


def is_feishu_authorization_page(page: Page) -> bool:
    try:
        current_url = page.url
    except PlaywrightError:
        return False
    return "apply_authorization" in current_url


def click_rightmost_button_by_text(page: Page, button_texts: tuple[str, ...]) -> bool:
    candidates: list[tuple[float, float, Locator]] = []
    buttons = page.locator("button")
    for index in range(buttons.count()):
        button = buttons.nth(index)
        try:
            if not button.is_visible():
                continue
            text = button.inner_text().strip()
            if text not in button_texts:
                continue
            box = button.bounding_box()
            if not box:
                continue
            candidates.append((box["x"], box["y"], button))
        except PlaywrightError:
            continue

    if not candidates:
        return False

    _, _, target = sorted(candidates, key=lambda item: (item[1], item[0]), reverse=True)[0]
    try:
        target.click(force=True)
    except PlaywrightError:
        try:
            target.evaluate("(el) => el.click()")
        except PlaywrightError:
            return False
    return True


def click_feishu_authorize_button(page: Page) -> bool:
    # 飞书授权页底部通常是“拒绝 | 授权”，只点这一组里的最右侧按钮，避免误点正文链接。
    return click_rightmost_button_by_text(
        page,
        ("授权", "确认授权", "确认并授权", "继续登录", "确认登录"),
    )


def handle_feishu_login(page: Page, config: LoginConfig) -> None:
    approve_if_needed(page, config)
    if page.is_closed():
        return

    if is_feishu_authorization_page(page):
        return

    if config.feishu_account_picker_text:
        click_first(
            page,
            selector_candidates(
                None,
                [
                    f"button:has-text('{config.feishu_account_picker_text}')",
                    f"[role='button']:has-text('{config.feishu_account_picker_text}')",
                    f"text={config.feishu_account_picker_text}",
                ],
            ),
            timeout_ms=8000,
            required=False,
        )
        if page.is_closed():
            return

        approve_if_needed(page, config)
        if page.is_closed():
            return

    switch_to_qr_login(page, config)
    if page.is_closed():
        return

    approve_if_needed(page, config)


def approve_if_needed(page: Page, config: LoginConfig) -> None:
    deadline = time.time() + 12
    while time.time() < deadline:
        if page.is_closed():
            return
        if click_feishu_authorize_button(page):
            return

        try:
            current_url = page.url
        except PlaywrightError:
            return

        if not any(keyword in current_url for keyword in ("feishu", "larksuite")):
            return

        time.sleep(0.8)


def is_success_page(page: Page, config: LoginConfig) -> bool:
    if page.is_closed():
        return False

    url = page.url
    if any(keyword in url for keyword in ("feishu", "larksuite")):
        return False

    if config.login_success_eval:
        try:
            if page.evaluate(config.login_success_eval):
                return True
        except Exception:
            return False

    if config.login_success_url_contains and config.login_success_url_contains not in url:
        return False

    if config.login_success_selector:
        locator = page.locator(config.login_success_selector).first
        try:
            locator.wait_for(state="visible", timeout=1200)
        except PlaywrightTimeoutError:
            return False

    if config.login_success_url_contains or config.login_success_selector:
        return True

    return config.app_host in url and url != config.app_login_url


def wait_for_login_success(
    app_page: Page,
    config: LoginConfig,
    timeout_ms: int,
    raise_on_timeout: bool = True,
) -> Page | None:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        live_pages = [page for page in app_page.context.pages if not page.is_closed()]
        for candidate in live_pages:
            try:
                candidate_url = candidate.url
            except PlaywrightError:
                continue

            if any(keyword in candidate_url for keyword in ("feishu", "larksuite")):
                try:
                    approve_if_needed(candidate, config)
                except PlaywrightError:
                    continue

            if candidate.is_closed():
                continue

            try:
                if is_success_page(candidate, config):
                    close_feishu_pages_after_success(app_page.context)
                    return candidate
            except PlaywrightError:
                continue
        time.sleep(1)

    if not raise_on_timeout:
        return None

    current_urls = [page.url for page in app_page.context.pages if not page.is_closed()]
    raise AssertionError(
        "登录后没有等到业务系统回跳成功。"
        f" 当前页面: {current_urls}。"
        " 如果你的页面不是通过 URL 变化判断成功，请配置 LOGIN_SUCCESS_SELECTOR。"
    )


def get_browser_launcher(playwright, browser_name: str):
    try:
        return getattr(playwright, browser_name)
    except AttributeError as error:
        raise AssertionError(
            f"不支持的浏览器类型: {browser_name}，可选值为 chromium / firefox / webkit。"
        ) from error


def build_ui_launch_options(config: LoginConfig) -> dict[str, Any]:
    launch_options: dict[str, Any] = {
        "headless": config.headless,
        "slow_mo": config.slow_mo,
        "args": ["--start-maximized"],
    }
    if config.browser_channel:
        launch_options["channel"] = config.browser_channel
    if config.browser_executable_path:
        launch_options["executable_path"] = config.browser_executable_path
    return launch_options


def prepare_profile_snapshot(config: LoginConfig) -> Path:
    if not config.chrome_user_data_dir:
        raise AssertionError("开启 REUSE_LOCAL_CHROME_PROFILE 时必须配置 CHROME_USER_DATA_DIR。")

    source_root = Path(config.chrome_user_data_dir).expanduser()
    profile_name = config.chrome_profile_directory or "Default"
    source_profile = source_root / profile_name
    if not source_root.exists():
        raise AssertionError(f"本地 Chrome 用户目录不存在: {source_root}")
    if not source_profile.exists():
        raise AssertionError(f"本地 Chrome Profile 不存在: {source_profile}")

    snapshot_root = Path(tempfile.mkdtemp(prefix="playwright-chrome-profile-"))
    for filename in ("Local State", "First Run"):
        source_file = source_root / filename
        if source_file.exists():
            shutil.copy2(source_file, snapshot_root / filename)

    shutil.copytree(source_profile, snapshot_root / profile_name, dirs_exist_ok=True)
    return snapshot_root


def test_feishu_login_redirect_success() -> None:
    config = load_config()
    profile_snapshot_dir: Path | None = None
    saved_auth_path = get_auth_storage_state_path(config)
    should_try_saved_auth = bool(
        config.reuse_saved_auth
        and not config.force_qr_login
        and saved_auth_path
        and saved_auth_path.exists()
    )

    with sync_playwright() as playwright:
        launch_options = build_ui_launch_options(config)
        browser = None
        launcher = get_browser_launcher(playwright, config.browser_name)

        if config.reuse_local_chrome_profile:
            profile_snapshot_dir = prepare_profile_snapshot(config)
            persistent_options = dict(launch_options)
            persistent_options["ignore_https_errors"] = True
            persistent_options["no_viewport"] = True
            persistent_options["args"] = [
                *persistent_options.get("args", []),
                f"--profile-directory={config.chrome_profile_directory or 'Default'}"
            ]
            context = launcher.launch_persistent_context(
                user_data_dir=str(profile_snapshot_dir),
                **persistent_options,
            )
            app_page = context.pages[0] if context.pages else context.new_page()
        else:
            browser = launcher.launch(**launch_options)
            new_context_options: dict[str, Any] = {"ignore_https_errors": True, "no_viewport": True}
            if should_try_saved_auth and saved_auth_path:
                new_context_options["storage_state"] = str(saved_auth_path)
            context = browser.new_context(**new_context_options)
            app_page = context.new_page()

        context.set_default_timeout(config.timeout_ms)

        try:
            goto_page_with_retry(app_page, config.app_login_url)
            success_page = wait_for_login_success(
                app_page,
                config,
                timeout_ms=config.auth_state_check_timeout_ms,
                raise_on_timeout=False,
            )
            if success_page is None:
                feishu_page = get_feishu_login_page(app_page, config)
                handle_feishu_login(feishu_page, config)
                success_page = wait_for_login_success(
                    app_page,
                    config,
                    timeout_ms=max(config.timeout_ms, config.manual_scan_timeout_ms),
                )

            save_auth_state(context, config)
            save_screenshot(success_page, "feishu-login-success.png")
        except Exception:
            for index, page in enumerate(context.pages, start=1):
                if not page.is_closed():
                    save_screenshot(page, f"feishu-login-failed-{index}.png")
            raise
        finally:
            context.close()
            if browser:
                browser.close()
            if profile_snapshot_dir:
                shutil.rmtree(profile_snapshot_dir, ignore_errors=True)
