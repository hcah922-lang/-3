"""Ключевые слова по опубликованным полям анкеты (не переписки).

Контекст = полный текст поля, где найдено слово.
Шумные слова вроде '@' дают ложные срабатывания — это нормально
и даже полезно для демо: так видно цену слежки по словам.
"""
from __future__ import annotations

# стартовый список: скам, увод контактов, маркеры возраста
WORDS = [
    "инвест", "крипт", "заработок", "доход", "перейди по", "http", "t.me/",
    "@", "напиши", "whatsapp", "вацап", "телеграм", "карта", "перевод",
    "предоплат", "залог", "мне 17", "мне 16", "мне 15", "эскорт", "досуг",
]

FIELDS = ("profile_name", "city", "bio", "interests")


def find_hits(profile: dict, words: list[str] | None = None) -> list[dict[str, str]]:
    """Возвращает [{'word', 'field', 'context'}] — context это полный текст поля."""
    out = []
    for w in (words or WORDS):
        lw = w.lower()
        for f in FIELDS:
            val = profile.get(f) or ""
            if lw in str(val).lower():
                out.append({"word": w, "field": f, "context": str(val)[:300]})
                break
    return out
