# 💘 Telegram Dating Bot

Бот для знакомств в Telegram на **aiogram 3.x** + **SQLite**.
Анкеты, фотографии, лайки, взаимные совпадения, переписка через бота и закрытая админ-панель с аналитикой.

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.13-24A1DE?style=flat-square&logo=telegram&logoColor=white)](https://docs.aiogram.dev/)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![DB](https://img.shields.io/badge/database-SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white)](https://www.sqlite.org/)

---

## Возможности

### Для пользователя
| Раздел | Что умеет |
|---|---|
| **Анкета** | 20 полей по шагам (FSM), возраст 18+, пропуск необязательных, назад, отмена, предпросмотр |
| **Фото** | загрузка через Telegram, хранение `file_id`, замена и удаление |
| **Телефон** | строго добровольно, кнопкой «Отправить контакт», проверка что контакт свой |
| **Геолокация** | город через онлайн-проверку (Nominatim), кнопка «Отправить местоположение» |
| **Поиск «рядом»** | радиус 10/25/50/100 км, показывается примерное расстояние, точные координаты скрыты |
| **Лайки и совпадения** | без дублей, взаимный лайк создаёт совпадение, оба получают уведомление |
| **Переписка** | только при совпадении, фото/видео/голосовые/стикеры, антиспам |
| **Жалобы** | 6 причин, модерация в админ-панели |
| **Настройки** | фильтры, уведомления, видимость, удаление анкеты и всех данных |

### Для администратора
| Раздел | Что умеет |
|---|---|
| **Доступ** | `/admin356872` + пароль + `ADMIN_IDS`, сессия с TTL, антибрутфорс, журнал |
| **Статистика** | регистрации, анкеты, лайки, совпадения, сообщения, блокировки, жалобы |
| **Пользователи** | постраничный список, поиск по ID/username/имени/городу |
| **Портрет** | полный слепок человека: анкета, предпочтения, поведение, геоточки, история правок |
| **Аналитика** | воронка, активность по часам, связи, круг 2-й степени, когорты, приглашения |
| **Детекция фейков** | одинаковые фото (`file_unique_id`) и телефоны у разных аккаунтов |
| **Экспорт** | TXT и JSON (UTF-8, `ensure_ascii=False`) |
| **Рассылки** | превью, выбор аудитории, тест себе, подтверждение, rate-limit, статистика |

---

## Быстрый старт

### Windows
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # заполнить BOT_TOKEN и ADMIN_IDS
python bot.py
```

### Linux / VPS
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env         # заполнить BOT_TOKEN и ADMIN_IDS
python bot.py
```

Подробная инструкция: [`docs/КАК_ЗАПУСТИТЬ.txt`](docs/КАК_ЗАПУСТИТЬ.txt)

### Конфигурация (`.env`)
```ini
BOT_TOKEN=123456:ABC...        # токен от @BotFather
ADMIN_IDS=111111,222222        # Telegram ID администраторов
ADMIN_PASSWORD=CHANGE_ME       # пароль входа в панель
DATABASE_PATH=data/bot.db
ADMIN_SESSION_MINUTES=30
BROADCAST_DELAY=0.05
```

---

## Структура проекта
```
├── bot.py              точка входа, middleware регистрации
├── config.py           конфигурация из .env
├── database.py         SQLite: схема, миграции, все запросы
├── handlers/           обработчики Telegram
│   ├── start.py        /start, главное меню
│   ├── profile.py      создание и редактирование анкет (FSM)
│   ├── discovery.py    лента, лайки, блокировки, жалобы
│   ├── likes.py        полученные лайки
│   ├── matches.py      совпадения
│   ├── chat.py         переписка
│   ├── settings.py     настройки пользователя
│   └── admin.py        админ-панель
├── keyboards/          inline и reply клавиатуры
├── services/           бизнес-логика
│   ├── geo.py          геокодинг и расстояния
│   ├── matching.py     лайки и совпадения
│   ├── messaging.py    проверка права на переписку
│   ├── export.py       экспорт TXT/JSON
│   ├── broadcast.py    рассылки
│   ├── security.py     пароли, сессии, антиспам
│   ├── moderation.py   жалобы
│   └── watchlist.py    ключевые слова
├── states/             FSM-состояния
├── deploy/             systemd-юнит
├── tools/              вспомогательные скрипты
├── docs/               инструкции
└── data/               база данных (создаётся сама)
```

---

## Безопасность и приватность

Проект собирает данные, поэтому относится к ним честно:

- **Токен и пароль** — только в `.env`, в репозиторий не попадают
- **SQL** — все запросы параметризованы
- **Админ-доступ** — проверяется Telegram ID *и* пароль, сессии с TTL, ограничение попыток
- **Переписка** — бот пересылает сообщения, но **не хранит их тексты**, только метаданные (тип, длина, время)
- **Геолокация** — точные координаты не показываются никому, только город и примерное расстояние
- **Телефон** — видит только владелец анкеты и администратор
- **Пользователь** может удалить анкету или все свои данные в настройках

---

## Схема базы данных

`users` · `profiles` · `likes` · `matches` · `blocks` · `reports` · `messages` · `admin_logs` · `broadcasts` · `admin_sessions` · `views` · `funnel_events` · `activity_events` · `geo_history` · `avatar_history` · `profile_history` · `tg_history`

Все таблицы создаются автоматически при первом запуске, миграции добавляют новые колонки без потери данных.

---

## Лицензия

MIT — см. [LICENSE](LICENSE)