# LifeOS Telegram Bot (личный)

## Что делает
- Инлайн-меню по плану (спорт, учеба, досуг, еда, моралька).
- Записывает всё в Google Sheets.
- Вкладка **Dashboard** показывает «Результаты дня» и «Не заполнено».

## Быстрый старт
1. **Загрузи** `lifeos_template.xlsx` в Google Drive и открой как Google Sheets.
2. Включи **Google Sheets API** в Google Cloud.
3. Создай **service account** и скачай JSON ключ.
4. Поделись таблицей с почтой service account (вида `...@...gserviceaccount.com`).
5. Скопируй `.env.example` в `.env` и заполни:
   - `TELEGRAM_BOT_TOKEN`
   - `GOOGLE_SHEETS_ID` (ID из URL таблицы)
   - `GOOGLE_SERVICE_ACCOUNT_FILE` (путь к JSON)
   - `TIMEZONE` (например, `Europe/Moscow`)

## Запуск
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

## Как пользоваться
- `/start` открывает главное меню.
- **Сегодня** показывает итоги дня и что не заполнено.
- **Еда**: выбираешь продукт → количество порций.
- **Другое**: можно добавить продукт вручную (название + БЖУК на 100г + граммы).

## Таблица (основные листы)
- **Daily** — агрегированные данные дня.
- **FoodLog** — все приёмы еды (макросы считаются формулами).
- **FoodItems** — БЖУК на 100г.
- **Portions** — порции (вес одной порции, яйца C0/C1/C2 и т.д.).
- **Dictionaries** — списки и шкалы для качества дня.
- **Dashboard** — результаты дня.

## Настройка точности
- Можно поправить граммы в `Portions` (например, яйца или банан под свой вес).
- Для новых продуктов лучше добавить через кнопку **Еда → Другое**.
