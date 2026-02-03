# LifeOS Telegram Bot (личный)

## Что делает
- Меню по плану (спорт, учеба, досуг, моралька, привычки).
- Хранит всё в **SQLite** (быстро, без внешних сервисов).
- Встроенная логика считает КБЖУ, качество дня и список «не заполнено».

## Быстрый старт
1. Скопируй `.env.example` → `.env` и заполни:
   - `TELEGRAM_BOT_TOKEN`
   - `DB_PATH` (по умолчанию `data/lifeos.db`)
   - `TIMEZONE` (например, `Europe/Moscow`)
   - `ALLOWED_USER_ID` (опционально)
2. Установи зависимости:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
3. Запусти:
   ```powershell
   python app.py
   ```

## Данные и структура
- `data/food_items.csv` — список продуктов (БЖУК на 100г).
- `data/portions.csv` — порции (код, продукт, вес порции).
- При первом запуске бот автоматически создаёт БД и засевает эти данные.

## Экспорт
- Команда `/export` отдаёт `.xlsx` (дневные итоги, еда, сессии, привычки, справочники).

## Синк (Health Connect) — вариант 1 (HTTP эндпоинт)
Бот может принимать JSON по HTTP (удобно для Android‑клиента или Tasker).
1. В `.env` задай:
   - `SYNC_HTTP_HOST=0.0.0.0`
   - `SYNC_HTTP_PORT=8088`
   - `SYNC_HTTP_TOKEN=любой_секрет` (обязательно)
2. Запусти бота. Эндпоинт:
   - `POST http://<server>:8088/sync`
   - Заголовок: `X-Api-Key: <SYNC_HTTP_TOKEN>` или `Authorization: Bearer <token>`
3. Тело запроса — JSON (см. ниже).

Пример:
```bash
curl -X POST http://localhost:8088/sync \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: TOKEN" \
  -d '{"date":"2026-02-01","steps":12345,"active_kcal":420,"weight":72.4,"sleep_hours":7.2,"english_min":30,"ml_min":60,"food":{"kcal":1800,"protein":130,"fat":60,"carb":170}}'
```

## Синк (Health Connect) — вариант 2 (через Telegram /sync)
Для личного Android‑клиента можно отправлять данные через команду:
```
/sync {"date":"2026-02-01","steps":12345,"active_kcal":420,"weight":72.4,"sleep_hours":7.2,"english_min":30,"ml_min":60,"food":{"kcal":1800,"protein":130,"fat":60,"carb":170}}
```
Поддерживаются поля: `steps`, `active_kcal`, `weight`, `sleep_hours`, `english_min`, `ml_min`, `algo_min`, `food` (kcal/protein/fat/carb).

## Как пользоваться
- `/start` открывает главное меню.
- Метрики (шаги/сон/вес/КБЖУ) приходят из синка, остальное отмечаешь кнопками.

## Настройка точности
- Можно поправить граммы в `data/portions.csv` (например, яйца или банан под свой вес).
- Для новых продуктов лучше добавить через кнопку **Еда → Другое**.
