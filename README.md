# Dating Bot — Telegram-бот для знакомств (aiogram 3.x + SQLite)

## Возможности
- /start + главное меню (9 кнопок), помощь
- Автосохранение telegram_id/username через `upsert_user()`
- Анкета по шагам (FSM): имя, возраст 18+, пол, поиск, город с онлайн-проверкой и кнопкой геолокации, био, интересы, фото (file_id, необязательно), телефон (кнопка контакта, только свой), превью, публикация draft→active
- Без опубликованной анкеты доступен только её создание (строгий гейт)
- Поиск «рядом»: координаты хранятся, другим виден только город и примерное расстояние; радиус 10/25/50/100 км в настройках
- Лента анкет с фильтрами, лайки, взаимные совпадения, чаты только при совпадении, блокировки, жалобы
- Настройки: фильтры, уведомления, видимость, удаление анкеты/данных
- Панель: статистика, пользователи, анкеты, поиск, портрет, досье TXT, воронка, связи, активность, фейки, слова, когорты, приглашения, экспорт, рассылки, журнал
- Доверие 0–100, заявленное vs реальное, хронотип, сессии, возвраты/спящие, топ жалоб
- Анкета +10 полей, мета фото (размеры), правки сообщений, коллекция стикерпаков, граф 2-й степени
- Аналитика: воронка start→chat, heatmap активности, история геолокаций, поиск дублей фото/телефона
- Невидимый след (без новых вопросов): время раздумий над анкетой, мета сообщений (тип/длина/эмодзи/голосовые секунды/пересылки/стикеры), скорость ответов, смены username/имени/языка, Premium, число аватарок, история аватарок, источники пересылок, примерный часовой пояс, язык анкеты vs язык TG, история правок анкеты, ключевые слова в полях анкеты
- Статистика, пользователи (по 10), анкеты, поиск, модерация, жалобы, экспорт TXT/JSON, рассылки (превью/аудитория/тест/подтверждение/rate-limit/статистика), история, логи, выход

## Структура
```
dating_bot/
├── bot.py config.py database.py requirements.txt .env.example .gitignore README.md
├── handlers/ start.py profile.py discovery.py likes.py matches.py chat.py settings.py admin.py
├── keyboards/ main.py profile.py discovery.py admin.py
├── services/ export.py matching.py security.py broadcast.py moderation.py messaging.py
├── states/ profile.py admin.py broadcast.py
├── tests/ test_database.py test_profiles.py test_security.py test_export.py
└── data/.gitkeep
```

## Установка (Windows)
```powershell
python --version  # 3.12+
# бот: @BotFather → /newbot → токен
# свой ID: @userinfobot
copy .env.example .env
# отредактируй .env: BOT_TOKEN, ADMIN_IDS, ADMIN_PASSWORD
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python bot.py
```

## Установка (Linux / VPS)
```bash
python3 --version
cp .env.example .env && nano .env
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python bot.py
# фон: nohup python bot.py > bot.log 2>&1 &
# systemd unit по желанию; бэкап: cp data/bot.db data/backup_$(date +%F).db
```

## .env
```
BOT_TOKEN=123:ABC
ADMIN_IDS=111111,222222
ADMIN_PASSWORD=356872
DATABASE_PATH=data/bot.db
ADMIN_SESSION_MINUTES=30
BROADCAST_DELAY=0.05
```

## Использование
- Пользователь: /start → Создать анкету → Смотреть анкеты → ❤️/👎 → Совпадения → Чаты (пишешь — бот пересылает).
- Админ: `/admin356872` → пароль → Статистика/Пользователи/Анкеты/Поиск/Жалобы/Экспорт TXT·JSON/Рассылка/История/Журнал/Выход.

## Тесты
```bash
pytest -v
```
Используется временная БД (tmp_path), реальные данные не трогаются.

## Безопасность
- Токен/пароль только в .env, в логах и экспорте их нет.
- Параметризованные SQL, валидация возраста/длины, file_id вместо base64, проверка своего контакта, чат только при `has_match` и без блокировок, rate-limit рассылок и антиспам чата.
