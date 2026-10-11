"""Экспорт TXT / JSON."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _v(x, default="Не указано"):
    if x is None or x == "":
        return default
    return x


def build_txt(rows: list[dict]) -> str:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [f"Экспорт Dating Bot. Дата формирования: {now}", f"Всего записей: {len(rows)}", ""]
    for i, r in enumerate(rows, 1):
        banned = "Да" if r.get("is_banned") else "Нет"
        uname = f"@{r['username']}" if r.get("username") else "Не указан"
        lines += [
            "=" * 40, f"ПОЛЬЗОВАТЕЛЬ № {i}", "=" * 40, "",
            f"Telegram ID: {r.get('telegram_id')}",
            f"Username: {uname}",
            f"Имя Telegram: {_v(r.get('first_name'))}",
            f"Фамилия Telegram: {_v(r.get('last_name'))}",
            f"Дата регистрации: {_v(r.get('created_at'))}",
            f"Последняя активность: {_v(r.get('last_active_at'))}",
            f"Статус блокировки: {banned}", "",
            "АНКЕТА", "",
            f"Имя: {_v(r.get('profile_name'))}",
            f"Возраст: {_v(r.get('age'))}",
            f"Пол: {_v(r.get('gender'))}",
            f"Кого ищет: {_v(r.get('looking_for'))}",
            f"Город: {_v(r.get('city'))}",
            f"Описание: {_v(r.get('bio'))}",
            f"Интересы: {_v(r.get('interests'))}",
            f"Телефон: {r.get('phone_number') or 'Не указан'}",
            f"Фото: {'Добавлено' if r.get('photo_file_id') else 'Нет'}",
            f"Статус анкеты: {_v(r.get('profile_status'), 'нет анкеты')}", "",
            "=" * 40, "",
        ]
    return "\n".join(lines)


def build_json(rows: list[dict]) -> str:
    data = {"exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "count": len(rows), "users": []}
    for r in rows:
        data["users"].append({
            "telegram_id": r.get("telegram_id"), "username": r.get("username"),
            "first_name": r.get("first_name"), "last_name": r.get("last_name"),
            "language_code": r.get("language_code"), "created_at": r.get("created_at"),
            "last_active_at": r.get("last_active_at"), "is_banned": bool(r.get("is_banned")),
            "profile": {
                "profile_name": r.get("profile_name"), "age": r.get("age"),
                "gender": r.get("gender"), "looking_for": r.get("looking_for"),
                "city": r.get("city"), "bio": r.get("bio"), "interests": r.get("interests"),
                "phone_number": r.get("phone_number"),
                "has_photo": bool(r.get("photo_file_id")),
                "profile_status": r.get("profile_status"),
                "published_at": r.get("published_at"),
            }})
    return json.dumps(data, ensure_ascii=False, indent=2)


def write_temp(content: str, suffix: str) -> str:
    tmp = Path("data") / f"export_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}{suffix}"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(content, encoding="utf-8")
    return str(tmp)


def build_dossier(pt: dict, behavior: dict, tg_hist: list[dict], prof_hist: list[dict],
                  geo: tuple[int, list[dict]], revealed: dict, trust: tuple[int, list[str]]) -> str:
    """Досье одного пользователя одним TXT: всё из портрета текстом."""
    u, p = pt.get("user", {}), pt.get("profile", {})
    lines = ["ДОСЬЕ", f"Telegram ID: {u.get('telegram_id')}",
             f"Username: @{u.get('username') or 'не указан'}",
             f"TG: {u.get('first_name') or ''} {u.get('last_name') or ''} ({u.get('language_code') or '?'})",
             f"Premium: {'да' if u.get('is_premium') else 'нет'}",
             f"Пришёл от: {u.get('invited_by') or '—'}",
             f"Регистрация: {u.get('created_at')}", f"Активность: {u.get('last_active_at')}",
             f"Бан: {'да' if u.get('is_banned') else 'нет'}", "",
             f"Анкета: {p.get('profile_name')}, {p.get('age')}, {p.get('city')} [{p.get('profile_status') or 'нет'}]",
             f"Пол: {p.get('gender')} | Ищет: {p.get('looking_for')}",
             f"Био: {p.get('bio') or '—'}", f"Интересы: {p.get('interests') or '—'}",
             f"Телефон: {p.get('phone_number') or 'не указан'}",
             f"Фото: {'да' if p.get('photo_file_id') else 'нет'}", "",
             f"Доверие: {trust[0]}/100 ({'; '.join(trust[1]) or 'чисто'})",
             f"Реальное поведение: {revealed.get('text')}",
             *[f"⚠ {f}" for f in revealed.get("flags", [])], "",
             f"Лайки отдано/получено: {pt.get('likes_given')}/{pt.get('likes_got')}",
             f"Совпадения: {pt.get('matches')} | Сообщений: {pt.get('messages')} | Жалоб на него: {pt.get('reports_got')}",
             f"Воронка: {', '.join(pt.get('steps', [])) or '—'}",
             f"Решения: {behavior.get('decisions')}",
             f"Типы сообщений: {behavior.get('kinds')}",
             f"Средний ответ: {behavior.get('avg_reply_sec')}с", "",
             "Смены TG-профиля:"]
    lines += [f"• {h['field']}: {h['old_value']} → {h['new_value']} ({h['created_at']})" for h in tg_hist] or ["—"]
    lines.append("Менял в анкете:")
    lines += [f"• {h['field']}: {(h['old_value'] or '—')[:80]} → {(h['new_value'] or '—')[:80]} ({h['created_at']})"
              for h in prof_hist] or ["—"]
    lines.append(f"Геоточек: {geo[0]}")
    lines += [f"• {g.get('city')} ({g.get('created_at')})" for g in geo[1]] or []
    return "\n".join(lines)
