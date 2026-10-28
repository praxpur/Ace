"""Browser connection preference and actionable network error messages."""
import json
import os
import tempfile
from pathlib import Path


CONNECTION_MODES = ('system', 'direct')
CONNECTION_LABELS = {'system': '跟随系统代理', 'direct': '直接连接（不使用代理）'}


def load_connection_mode(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        mode = data.get('mode') if isinstance(data, dict) else None
        return mode if mode in CONNECTION_MODES else 'system'
    except (OSError, ValueError, TypeError):
        return 'system'


def save_connection_mode(path: Path, mode: str) -> None:
    if mode not in CONNECTION_MODES:
        raise ValueError('未知的连接方式')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='connection-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump({'mode': mode}, stream, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def network_error_message(error: Exception) -> str | None:
    text = str(error)
    if ('net::ERR_TIMED_OUT' in text or
            ('Timeout ' in text and 'navigating to' in text)):
        return ('连接课程网站超时。请检查网络和系统代理；'
                '如果系统代理不可用，可在“连接与设置”页选择“直接连接”后重试。')
    if any(code in text for code in ('net::ERR_PROXY_CONNECTION_FAILED',
                                     'net::ERR_TUNNEL_CONNECTION_FAILED')):
        return '连接系统代理失败。请检查代理，或在“连接与设置”页选择“直接连接”后重试。'
    if 'net::ERR_NAME_NOT_RESOLVED' in text:
        return '课程网站域名解析失败。请检查网络和 DNS，或尝试其他连接方式。'
    if 'net::ERR_INTERNET_DISCONNECTED' in text:
        return '网络连接已断开。请连接网络后重试。'
    if any(code in text for code in ('net::ERR_CONNECTION_CLOSED',
                                     'net::ERR_CONNECTION_RESET',
                                     'net::ERR_CONNECTION_REFUSED',
                                     'net::ERR_EMPTY_RESPONSE')):
        return ('课程网站连接中断。请检查网络和系统代理；'
                '如有需要，可在“连接与设置”页选择“直接连接”后重试。')
    return None
