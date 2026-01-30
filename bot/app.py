from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import load_config
from menus import (
    MAIN_MENU,
    SPORT_MENU,
    TRAINING_OPTIONS,
    CARDIO_OPTIONS,
    STEPS_OPTIONS,
    STUDY_MENU,
    ENGLISH_OPTIONS,
    CODE_MODE_OPTIONS,
    CODE_TOPIC_OPTIONS,
    READING_OPTIONS,
    LEISURE_MENU,
    REST_TIME_OPTIONS,
    REST_TYPE_OPTIONS,
    SLEEP_BEDTIME_OPTIONS,
    SLEEP_HOURS_OPTIONS,
    SLEEP_REGIME_OPTIONS,
    PRODUCTIVITY_OPTIONS,
    FOOD_MENU,
    FOOD_PROTEIN_OPTIONS,
    FOOD_GARNISH_OPTIONS,
    FOOD_SWEET_OPTIONS,
    MORALE_MENU,
    MOOD_OPTIONS,
    ENERGY_OPTIONS,
    HABITS_MENU,
    build_keyboard,
    quantity_keyboard,
)
from sheets import SheetsClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
LOGGER = logging.getLogger("lifeos-bot")

DAILY_HEADERS = [
    'Дата','Тренировка','Кардио_мин','Шаги_категория','Английский_мин','Код_режим','Код_тема','Чтение_стр',
    'Отдых_время','Отдых_тип','Сон_отбой','Сон_часы','Режим','Продуктивность','Настроение','Энергия',
    'Вес','О_чем_жалею','Отзыв_о_дне','Привычки','Ккал','Белки','Жиры','Угли','Качество_дня','Не_заполнено'
]

COLUMN_MAP = {
    "training": "B",
    "cardio": "C",
    "steps": "D",
    "english": "E",
    "code_mode": "F",
    "code_topic": "G",
    "reading": "H",
    "rest_time": "I",
    "rest_type": "J",
    "sleep_bed": "K",
    "sleep_hours": "L",
    "sleep_regime": "M",
    "productivity": "N",
    "mood": "O",
    "energy": "P",
    "weight": "Q",
    "regret": "R",
    "review": "S",
    "habits": "T",
}

NUMERIC_FIELDS = {"cardio", "english", "reading", "productivity"}


def get_now(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def today_str(tz_name: str) -> str:
    return get_now(tz_name).strftime("%Y-%m-%d")


def time_str(tz_name: str) -> str:
    return get_now(tz_name).strftime("%H:%M")


def get_sheets(context: ContextTypes.DEFAULT_TYPE) -> SheetsClient:
    return context.application.bot_data["sheets"]


def is_authorized(context: ContextTypes.DEFAULT_TYPE, user_id: int | None) -> bool:
    allowed = context.application.bot_data.get("allowed_user_id")
    if not allowed:
        return True
    return user_id == allowed


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(context, update.effective_user.id if update.effective_user else None):
        return
    await update.message.reply_text(
        "Главное меню:",
        reply_markup=build_keyboard(MAIN_MENU, cols=2),
    )


async def show_menu(query, title: str, buttons, back_to: str = "menu:main", cols: int = 2) -> None:
    await query.answer()
    await query.edit_message_text(title, reply_markup=build_keyboard(buttons, cols=cols, back=("⬅️ Назад", back_to)))


def parse_number(value: str) -> float:
    value = value.replace(",", ".").strip()
    return float(value)


def parse_numbers(text: str, count: int) -> list[float]:
    parts = [p for p in text.replace(",", ".").split() if p.strip()]
    if len(parts) != count:
        raise ValueError
    return [float(p) for p in parts]


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(context, update.effective_user.id if update.effective_user else None):
        return
    query = update.callback_query
    data = query.data
    cfg = context.application.bot_data["config"]
    sheets = get_sheets(context)
    date_str = today_str(cfg.timezone)

    if data == "menu:main":
        await query.answer()
        await query.edit_message_text("Главное меню:", reply_markup=build_keyboard(MAIN_MENU, cols=2))
        return
    if data == "menu:today":
        await query.answer()
        summary = await build_daily_summary(context, date_str)
        await query.edit_message_text(summary, reply_markup=build_keyboard(MAIN_MENU, cols=2))
        return
    if data == "menu:sport":
        await show_menu(query, "Спорт:", SPORT_MENU)
        return
    if data == "menu:study":
        await show_menu(query, "Учеба:", STUDY_MENU)
        return
    if data == "menu:leisure":
        await show_menu(query, "Досуг:", LEISURE_MENU)
        return
    if data == "menu:food":
        await show_menu(query, "Еда:", FOOD_MENU)
        return
    if data == "menu:morale":
        await show_menu(query, "Моралька:", MORALE_MENU)
        return
    if data == "menu:habits":
        await show_menu(query, "Привычки:", HABITS_MENU)
        return

    if data == "sport:training":
        await show_menu(query, "Тренировка:", TRAINING_OPTIONS, back_to="menu:sport", cols=2)
        return
    if data == "sport:cardio":
        await show_menu(query, "Кардио (мин):", CARDIO_OPTIONS, back_to="menu:sport", cols=3)
        return
    if data == "sport:steps":
        await show_menu(query, "Шаги:", STEPS_OPTIONS, back_to="menu:sport", cols=2)
        return

    if data == "study:english":
        await show_menu(query, "Английский:", ENGLISH_OPTIONS, back_to="menu:study", cols=3)
        return
    if data == "study:code":
        await show_menu(query, "Код: режим", CODE_MODE_OPTIONS, back_to="menu:study", cols=1)
        return
    if data == "study:reading":
        await show_menu(query, "Чтение:", READING_OPTIONS, back_to="menu:study", cols=4)
        return

    if data == "leisure:rest":
        await show_menu(query, "Отдых: время", REST_TIME_OPTIONS, back_to="menu:leisure", cols=2)
        return
    if data == "leisure:sleep":
        await show_menu(query, "Сон: во сколько заснул?", SLEEP_BEDTIME_OPTIONS, back_to="menu:leisure", cols=3)
        return
    if data == "leisure:productivity":
        await show_menu(query, "Продуктивность:", PRODUCTIVITY_OPTIONS, back_to="menu:leisure", cols=3)
        return

    if data == "food:protein":
        await show_menu(query, "Еда: белковое", FOOD_PROTEIN_OPTIONS, back_to="menu:food", cols=2)
        return
    if data == "food:garnish":
        await show_menu(query, "Еда: гарнир", FOOD_GARNISH_OPTIONS, back_to="menu:food", cols=2)
        return
    if data == "food:sweet":
        await show_menu(query, "Еда: сладкое", FOOD_SWEET_OPTIONS, back_to="menu:food", cols=2)
        return
    if data == "food:custom":
        await query.answer()
        context.user_data.clear()
        context.user_data["expect"] = "custom_name"
        await query.edit_message_text(
            "Введи название продукта (например, \"Миндаль\").",
            reply_markup=build_keyboard([("⬅️ Назад", "menu:food")], cols=1),
        )
        return

    if data == "morale:mood":
        await show_menu(query, "Настроение:", MOOD_OPTIONS, back_to="menu:morale", cols=2)
        return
    if data == "morale:energy":
        await show_menu(query, "Энергия:", ENERGY_OPTIONS, back_to="menu:morale", cols=2)
        return
    if data == "morale:weight":
        await query.answer()
        context.user_data["expect"] = "weight"
        await query.edit_message_text("Введи вес (например, 72.4):")
        return
    if data == "morale:regret":
        await query.answer()
        context.user_data["expect"] = "regret"
        await query.edit_message_text("О чем жалеешь сегодня? Напиши текст.")
        return
    if data == "morale:review":
        await query.answer()
        context.user_data["expect"] = "review"
        await query.edit_message_text("Отзыв о дне: напиши коротко.")
        return

    if data == "habits:text":
        await query.answer()
        context.user_data["expect"] = "habits"
        await query.edit_message_text("Привычки: напиши текст.")
        return

    if data.startswith("set:"):
        parts = data.split(":", 2)
        if len(parts) < 3:
            return
        field_key, value = parts[1], parts[2]
        if field_key == "code_mode":
            sheets.update_daily_fields(date_str, {COLUMN_MAP["code_mode"]: value}, max_rows=cfg.daily_max_rows)
            await show_menu(query, "Код: тема", CODE_TOPIC_OPTIONS, back_to="menu:study", cols=2)
            return
        if field_key == "code_topic":
            sheets.update_daily_fields(date_str, {COLUMN_MAP["code_topic"]: value}, max_rows=cfg.daily_max_rows)
            await show_menu(query, "Учеба:", STUDY_MENU)
            return
        if field_key == "rest_time":
            sheets.update_daily_fields(date_str, {COLUMN_MAP["rest_time"]: value}, max_rows=cfg.daily_max_rows)
            await show_menu(query, "Отдых: тип", REST_TYPE_OPTIONS, back_to="menu:leisure", cols=2)
            return
        if field_key == "rest_type":
            sheets.update_daily_fields(date_str, {COLUMN_MAP["rest_type"]: value}, max_rows=cfg.daily_max_rows)
            await show_menu(query, "Досуг:", LEISURE_MENU)
            return
        if field_key == "sleep_bed":
            sheets.update_daily_fields(date_str, {COLUMN_MAP["sleep_bed"]: value}, max_rows=cfg.daily_max_rows)
            await show_menu(query, "Сон: сколько часов?", SLEEP_HOURS_OPTIONS, back_to="menu:leisure", cols=3)
            return
        if field_key == "sleep_hours":
            sheets.update_daily_fields(date_str, {COLUMN_MAP["sleep_hours"]: value}, max_rows=cfg.daily_max_rows)
            await show_menu(query, "Сон: режим", SLEEP_REGIME_OPTIONS, back_to="menu:leisure", cols=2)
            return
        if field_key == "sleep_regime":
            sheets.update_daily_fields(date_str, {COLUMN_MAP["sleep_regime"]: value}, max_rows=cfg.daily_max_rows)
            await show_menu(query, "Досуг:", LEISURE_MENU)
            return

        field_map = {
            "training": "training",
            "cardio": "cardio",
            "steps": "steps",
            "english": "english",
            "reading": "reading",
            "productivity": "productivity",
            "mood": "mood",
            "energy": "energy",
        }
        if field_key in field_map:
            key = field_map[field_key]
            col = COLUMN_MAP[key]
            if key in NUMERIC_FIELDS:
                value = int(float(value))
            sheets.update_daily_fields(date_str, {col: value}, max_rows=cfg.daily_max_rows)
            if field_key in {"training", "cardio", "steps"}:
                await show_menu(query, "Спорт:", SPORT_MENU)
                return
            if field_key in {"english", "reading"}:
                await show_menu(query, "Учеба:", STUDY_MENU)
                return
            if field_key == "productivity":
                await show_menu(query, "Досуг:", LEISURE_MENU)
                return
            if field_key in {"mood", "energy"}:
                await show_menu(query, "Моралька:", MORALE_MENU)
                return

    if data.startswith("food_item:"):
        portion_code = data.split(":", 1)[1]
        await query.answer()
        await query.edit_message_text("Сколько порций?", reply_markup=quantity_keyboard(portion_code))
        return

    if data.startswith("food_qty:"):
        _, portion_code, qty_str = data.split(":", 2)
        qty = int(qty_str)
        sheets.add_food_log(
            date_str,
            time_str(cfg.timezone),
            portion_code,
            qty,
            max_rows=cfg.foodlog_max_rows,
        )
        await query.answer()
        await query.edit_message_text(
            f"✅ Записал еду: {portion_code} × {qty}",
            reply_markup=build_keyboard(FOOD_MENU, cols=2, back=("⬅️ Назад", "menu:main")),
        )
        return


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(context, update.effective_user.id if update.effective_user else None):
        return
    expect = context.user_data.get("expect")
    if not expect:
        return
    cfg = context.application.bot_data["config"]
    sheets = get_sheets(context)
    date_str = today_str(cfg.timezone)
    text = update.message.text.strip()

    if expect == "weight":
        try:
            weight = parse_number(text)
        except ValueError:
            await update.message.reply_text("Не понял вес. Пример: 72.4")
            return
        sheets.update_daily_fields(date_str, {COLUMN_MAP["weight"]: weight}, max_rows=cfg.daily_max_rows)
        context.user_data.clear()
        await update.message.reply_text("✅ Вес записан.")
        return

    if expect == "regret":
        sheets.update_daily_fields(date_str, {COLUMN_MAP["regret"]: text}, max_rows=cfg.daily_max_rows)
        context.user_data.clear()
        await update.message.reply_text("✅ Записал.")
        return

    if expect == "review":
        sheets.update_daily_fields(date_str, {COLUMN_MAP["review"]: text}, max_rows=cfg.daily_max_rows)
        context.user_data.clear()
        await update.message.reply_text("✅ Записал.")
        return

    if expect == "habits":
        sheets.update_daily_fields(date_str, {COLUMN_MAP["habits"]: text}, max_rows=cfg.daily_max_rows)
        context.user_data.clear()
        await update.message.reply_text("✅ Записал.")
        return

    if expect == "custom_name":
        context.user_data["custom_name"] = text
        context.user_data["expect"] = "custom_macros"
        await update.message.reply_text("Введи Б/Ж/У/Ккал на 100г (4 числа через пробел).")
        return

    if expect == "custom_macros":
        try:
            proteins, fats, carbs, kcal = parse_numbers(text, 4)
        except ValueError:
            await update.message.reply_text("Нужны 4 числа. Пример: 20 5 10 150")
            return
        context.user_data["custom_macros"] = (proteins, fats, carbs, kcal)
        context.user_data["expect"] = "custom_grams"
        await update.message.reply_text("Сколько грамм съел? (одно число)")
        return

    if expect == "custom_grams":
        try:
            grams = parse_number(text)
        except ValueError:
            await update.message.reply_text("Нужны граммы числом. Пример: 120")
            return
        name = context.user_data.get("custom_name", "Продукт")
        proteins, fats, carbs, kcal = context.user_data.get("custom_macros", (0, 0, 0, 0))
        code = f"CUST_{get_now(cfg.timezone).strftime('%y%m%d%H%M%S')}"
        sheets.ensure_food_item(name, proteins, fats, carbs, kcal)
        sheets.ensure_portion(code, name, f"{grams} г (custom)", grams)
        sheets.add_food_log(
            date_str,
            time_str(cfg.timezone),
            code,
            1,
            comment="custom",
            max_rows=cfg.foodlog_max_rows,
        )
        context.user_data.clear()
        await update.message.reply_text("✅ Продукт добавлен и записан в еду.")
        return


async def build_daily_summary(context: ContextTypes.DEFAULT_TYPE, date_str: str) -> str:
    cfg = context.application.bot_data["config"]
    sheets = get_sheets(context)
    row = sheets.get_daily_row(date_str, max_rows=cfg.daily_max_rows)
    if not row:
        return "Сегодня пока нет данных."

    values = row.values + [""] * (len(DAILY_HEADERS) - len(row.values))
    data = dict(zip(DAILY_HEADERS, values))

    def fmt(value: str) -> str:
        return value if value not in (None, "") else "—"

    summary = [
        f"Дата: {date_str}",
        f"Качество: {fmt(data.get('Качество_дня'))}",
        f"Ккал/Б/Ж/У: {fmt(data.get('Ккал'))}/{fmt(data.get('Белки'))}/{fmt(data.get('Жиры'))}/{fmt(data.get('Угли'))}",
        f"Не заполнено: {fmt(data.get('Не_заполнено'))}",
    ]
    return "\n".join(summary)


def main() -> None:
    config = load_config()
    sheets = SheetsClient(config.spreadsheet_id, config.service_account_file)

    app = ApplicationBuilder().token(config.telegram_token).build()
    app.bot_data["sheets"] = sheets
    app.bot_data["config"] = config
    app.bot_data["allowed_user_id"] = config.allowed_user_id

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    LOGGER.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
