import argparse
import importlib.util
import json
import sys
from pathlib import Path

from .cancellation import CancellationToken
from .config import COURSE_CENTER_URL, DEFAULT_STATE_PATH, PLAYBACK_RATES, Settings
from .errors import UserCancelled
from .workflow import Workflow


def doctor():
    settings = Settings()
    result = {
        "python": sys.version.split()[0], "executable": sys.executable,
        "playwright_available": importlib.util.find_spec("playwright") is not None,
        "tkinter_available": importlib.util.find_spec("tkinter") is not None,
        "project_browser": settings.executable(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["playwright_available"] else 1


def choose(title, choices, token):
    print(f"\n请选择{title}：")
    for index, choice in enumerate(choices, 1):
        detail = f" ({choice.detail})" if choice.detail else ""
        print(f"  {index}. {choice.label}{detail}")
    while True:
        token.check()
        try:
            raw = input("输入序号（多个用逗号分隔）、a 全选，或 q 取消：").strip()
        except (EOFError, KeyboardInterrupt):
            raise UserCancelled("选择已取消。") from None
        if raw.lower() == "q":
            raise UserCancelled("选择已取消。")
        if raw.lower() == "a":
            return [choice.key for choice in choices]
        values = raw.replace("，", ",").split(",")
        if all(value.strip().isdecimal() and 1 <= int(value) <= len(choices) for value in values):
            return list(dict.fromkeys(choices[int(value) - 1].key for value in values))
        print("请输入列表中的有效序号。")


def main(argv=None):
    parser = argparse.ArgumentParser(description="树屋：扫描并选择智慧树课程与视频。")
    parser.add_argument("entry", nargs="?", default=COURSE_CENTER_URL,
                        help="课程中心 URL，或 doctor 检查运行环境")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--state", type=Path,
                        default=DEFAULT_STATE_PATH if DEFAULT_STATE_PATH.is_file() else None,
                        help="已有 Playwright 登录态，默认使用已存在的 .state/auth.json")
    parser.add_argument("--save-state", type=Path, help="人工登录后保存到该文件")
    parser.add_argument("--login-timeout", type=float, default=300)
    parser.add_argument("--video-timeout", type=float, default=7200)
    parser.add_argument("--speed", type=float, choices=PLAYBACK_RATES, default=1.0,
                        help="请求播放速度，仅使用课程开放的倍速菜单")
    parser.add_argument('--connection-mode', choices=('system', 'direct'), default='system',
                        help='system 跟随系统代理；direct 不使用代理')
    parser.add_argument("--manual-verification", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--playback-only", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.entry == "doctor":
        return doctor()
    try:
        settings = Settings(
            start_url=args.entry, headless=args.headless, state_path=args.state,
            save_state_path=args.save_state, login_timeout=args.login_timeout,
            video_timeout=args.video_timeout,
            playback_rate=args.speed,
            connection_mode=args.connection_mode,
        ).validate()
    except Exception as error:
        parser.error(str(error))
    token = CancellationToken()

    def show(event):
        if event.kind == "log":
            print(event.data["message"])
        elif event.kind == "progress":
            print(f"\r播放进度 {event.data['percent']:5.1f}%", end="", flush=True)

    try:
        outcome = Workflow(settings, choose, show, token).run()
    except KeyboardInterrupt:
        token.cancel()
        return 2
    print(f"\n{outcome.message}\n诊断目录：{outcome.diagnostic_dir}")
    return outcome.exit_code
