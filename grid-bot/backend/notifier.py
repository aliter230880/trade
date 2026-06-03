"""Telegram-уведомления. Вызовы fire-and-forget, не должны ронять бота."""

import logging
import socket
from typing import Optional

import httpx

from .config import settings

log = logging.getLogger("notifier")

# Список IP api.telegram.org. Используется fallback'ом если стандартный
# DNS-резолв ведёт на заблокированный РКН-провайдером IP.
_TELEGRAM_API_IPS = [
    "149.154.167.220",
    "149.154.167.197",
    "149.154.175.50",
    "149.154.166.110",
]


class _PinnedIPTransport(httpx.HTTPTransport):
    """HTTP-транспорт, направляющий запросы на конкретный IP, сохраняя
    оригинальный hostname в SNI и Host-заголовке (для валидного TLS)."""

    def __init__(self, host: str, ip: str, **kwargs):
        super().__init__(**kwargs)
        self._host = host
        self._ip = ip

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        # Подменяем host в URL на IP, но Host-header и SNI остаются прежними
        original_url = request.url
        if original_url.host == self._host:
            new_url = original_url.copy_with(host=self._ip)
            request.url = new_url
            request.headers.setdefault("Host", self._host)
            # SNI httpx подцепит из оригинального URL — нужно вернуть extension
            request.extensions["sni_hostname"] = self._host
        return super().handle_request(request)


def _post_telegram(token: str, chat_id: str, text: str) -> bool:
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    # Стандартный путь
    try:
        with httpx.Client(timeout=5.0) as c:
            r = c.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json=payload,
            )
            if r.status_code == 200:
                return True
    except Exception:
        pass

    # Fallback по IP
    for ip in _TELEGRAM_API_IPS:
        try:
            transport = _PinnedIPTransport(host="api.telegram.org", ip=ip)
            with httpx.Client(timeout=5.0, transport=transport) as c:
                r = c.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    json=payload,
                )
                if r.status_code == 200:
                    log.info("telegram: используется fallback IP %s", ip)
                    return True
        except Exception as exc:
            log.debug("telegram via %s failed: %s", ip, exc)
            continue
    return False


def send_telegram(text: str) -> None:
    token = settings.telegram_bot_token
    chat_id = settings.telegram_chat_id
    if not token or not chat_id:
        return
    try:
        ok = _post_telegram(token, chat_id, text)
        if not ok:
            log.warning("telegram: все попытки отправки не удались")
    except Exception as exc:
        log.warning("telegram send failed: %s", exc)


def notify_fill(bot_id: int, symbol: str, side: str, price: float,
                qty: float, realized: float, open_count: int) -> None:
    emoji = "🟢" if side == "sell" else "🔵"
    pnl_str = (f"<b>P&L: {'+' if realized >= 0 else ''}{realized:.4f} USDT</b>"
               if realized != 0 else "")
    text = (
        f"{emoji} <b>Bot #{bot_id}</b> {symbol}\n"
        f"{side.upper()} filled @ <code>{price}</code>\n"
        f"Qty: <code>{qty}</code>\n"
        f"{pnl_str}\n"
        f"Open: {open_count}"
    )
    send_telegram(text)


def notify_started(bot_id: int, symbol: str, levels: int,
                   lower: float, upper: float) -> None:
    text = (
        f"▶️ <b>Bot #{bot_id}</b> запущен\n"
        f"{symbol}, {levels} уровней\n"
        f"Диапазон: <code>{lower}</code> – <code>{upper}</code>"
    )
    send_telegram(text)


def notify_stopped(bot_id: int, realized_pnl: float) -> None:
    text = (
        f"⏹ <b>Bot #{bot_id}</b> остановлен\n"
        f"Realized P&L: <b>{realized_pnl:+.4f} USDT</b>"
    )
    send_telegram(text)


def notify_error(bot_id: int, error: str) -> None:
    text = f"⚠️ <b>Bot #{bot_id}</b> ошибка:\n<code>{error[:300]}</code>"
    send_telegram(text)
