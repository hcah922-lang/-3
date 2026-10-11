"""Безопасность: проверка админов, пароля, сессий, антиспам."""
from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass, field

from config import config


def is_admin_id(tid: int) -> bool:
    return tid in config.ADMIN_IDS


def check_password(pw: str) -> bool:
    return hmac.compare_digest(pw.strip(), config.ADMIN_PASSWORD)


def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


@dataclass
class LoginGuard:
    attempts: dict[int, list[float]] = field(default_factory=dict)
    blocked_until: dict[int, float] = field(default_factory=dict)

    def is_blocked(self, tid: int) -> bool:
        return self.blocked_until.get(tid, 0) > time.time()

    def register_fail(self, tid: int) -> None:
        now = time.time()
        lst = [t for t in self.attempts.get(tid, []) if now - t < 900]
        lst.append(now)
        self.attempts[tid] = lst
        if len(lst) >= config.MAX_LOGIN_ATTEMPTS:
            self.blocked_until[tid] = now + config.LOGIN_BLOCK_MINUTES * 60
            self.attempts[tid] = []

    def register_ok(self, tid: int) -> None:
        self.attempts.pop(tid, None)
        self.blocked_until.pop(tid, None)


login_guard = LoginGuard()


class SpamGuard:
    def __init__(self, min_interval: float = 1.0):
        self.last: dict[int, float] = {}
        self.min_interval = min_interval

    def allowed(self, tid: int) -> bool:
        now = time.time()
        if now - self.last.get(tid, 0) < self.min_interval:
            return False
        self.last[tid] = now
        return True


spam_guard = SpamGuard()


def esc(text: str | None) -> str:
    if not text:
        return "Не указано"
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def profile_text(p: dict) -> str:
    g = {"male": "Мужской", "female": "Женский"}.get(p.get("gender") or "", p.get("gender") or "Не указано")
    lf = {"male": "Мужчину", "female": "Женщину", "any": "Всех"}.get(p.get("looking_for") or "", p.get("looking_for") or "Не указано")
    txt = (f"👤 <b>{esc(p.get('profile_name'))}</b>, {p.get('age') or '?'} • {esc(p.get('city'))}\n"
           f"Пол: {esc(g)} • Ищет: {esc(lf)}\n\n"
           f"{esc(p.get('bio'))}\n\n"
           f"Интересы: {esc(p.get('interests'))}")
    extra_lines = []
    for key, label in [("zodiac", "Зодиак"), ("height", "Рост"), ("education", "Образование"),
                       ("job", "Работа"), ("languages", "Языки"), ("kids", "Дети"),
                       ("smoking", "Курение"), ("alcohol", "Алкоголь"), ("goal", "Цель"),
                       ("schedule", "График")]:
        if p.get(key):
            extra_lines.append(f"{label}: {esc(p.get(key))}")
    if extra_lines:
        txt += "\n\n" + "\n".join(extra_lines)
    return txt
