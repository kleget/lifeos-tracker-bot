from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
    try:
        return datetime.now(ZoneInfo(tz_name))
    except ZoneInfoNotFoundError:
        LOGGER.warning("Timezone '%s' not found. Falling back to local time.", tz_name)
        return datetime.now()


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
    cfg = context.application.bot_data["config"]
    date_str = today_str(cfg.timezone)
    summary = await build_daily_summary(context, date_str)
    await update.message.reply_text(
        f"{summary}\n\nВыбери раздел:",
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

def parse_sheet_number(value: object) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(" ", "").replace(",", ".")
    num = ""
    for ch in text:
        if ch.isdigit() or ch in {".", "-"}:
            num += ch
        elif num:
            break
    try:
        return float(num)
    except ValueError:
        return 0.0


def fmt_num(value: float, digits: int = 0) -> str:
    if digits <= 0:
        return str(int(round(value)))
    formatted = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return formatted.replace(".", ",")


def fmt_value(value: object) -> str:
    return str(value) if value not in (None, "") else "—"


def display_training(value: object) -> str | None:
    if value in (None, ""):
        return None
    if value == "Ноги":
        return "Низ"
    return str(value)


def day_targets(training_value: str | None) -> dict | None:
    if training_value in {"Ноги", "Низ", "Верх"}:
        return {
            "label": "Тренировочный день",
            "kcal": (1900, 2000),
            "protein": (125, 135),
            "fat": (55, 65),
            "carb": (180, 210),
        }
    if training_value in {"Отдых", "Пропустил"}:
        return {
            "label": "День отдыха",
            "kcal": (1700, 1800),
            "protein": (120, 130),
            "fat": (55, 65),
            "carb": (140, 170),
        }
    return None


def mark_set_buttons(buttons: list[tuple[str, str]], current_value: object) -> list[tuple[str, str]]:
    current = "" if current_value is None else str(current_value)
    if current.endswith(".0"):
        current = current[:-2]
    marked: list[tuple[str, str]] = []
    for label, data in buttons:
        if data.startswith("set:"):
            parts = data.split(":", 2)
            value = parts[2] if len(parts) > 2 else ""
            if value == current:
                label = f"✅ {label}"
        marked.append((label, data))
    return marked


def get_daily_data(context: ContextTypes.DEFAULT_TYPE, date_str: str) -> dict:
    cfg = context.application.bot_data["config"]
    sheets = get_sheets(context)
    row = sheets.get_daily_row(date_str, max_rows=cfg.daily_max_rows)
    if not row:
        return {}
    values = row.values + [""] * (len(DAILY_HEADERS) - len(row.values))
    return dict(zip(DAILY_HEADERS, values))


def build_sport_menu(data: dict) -> list[tuple[str, str]]:
    training = data.get("Тренировка")
    training_display = display_training(training)
    training_selected = training_display is not None
    training_label = "Тренировка"
    if training_display:
        training_label = f"Тренировка: {training_display}"

    rest_selected = training == "Отдых"
    skip_selected = training == "Пропустил"

    cardio = data.get("Кардио_мин")
    cardio_label = "Кардио"
    if cardio not in (None, ""):
        cardio_label = f"Кардио: {cardio}м"

    steps = data.get("Шаги_категория")
    steps_label = "Шаги"
    if steps not in (None, ""):
        steps_label = f"Шаги: {steps}"

    buttons = [
        (f"✅ {training_label}" if training_selected else training_label, "sport:training"),
        ("✅ Отдых" if rest_selected else "Отдых", "sport:rest"),
        ("✅ Пропуск" if skip_selected else "Пропуск", "sport:skip"),
        (f"✅ {cardio_label}" if cardio not in (None, "") else cardio_label, "sport:cardio"),
        (f"✅ {steps_label}" if steps not in (None, "") else steps_label, "sport:steps"),
    ]
    return buttons


def build_study_menu(data: dict) -> list[tuple[str, str]]:
    english = data.get("Английский_мин")
    english_label = "Английский" if english in (None, "") else f"Английский: {english}м"

    code_mode = data.get("Код_режим")
    code_topic = data.get("Код_тема")
    code_label = "Код"
    if code_mode or code_topic:
        code_label = f"Код: {code_mode or '—'}/{code_topic or '—'}"

    reading = data.get("Чтение_стр")
    reading_label = "Чтение" if reading in (None, "") else f"Чтение: {reading} стр"

    return [
        (f"✅ {english_label}" if english not in (None, "") else english_label, "study:english"),
        (f"✅ {code_label}" if (code_mode or code_topic) else code_label, "study:code"),
        (f"✅ {reading_label}" if reading not in (None, "") else reading_label, "study:reading"),
    ]


def build_leisure_menu(data: dict) -> list[tuple[str, str]]:
    rest_time = data.get("Отдых_время")
    rest_label = "Отдых" if rest_time in (None, "") else f"Отдых: {rest_time}"

    sleep_hours = data.get("Сон_часы")
    sleep_label = "Сон" if sleep_hours in (None, "") else f"Сон: {sleep_hours}ч"

    productivity = data.get("Продуктивность")
    prod_label = "Продуктивность" if productivity in (None, "") else f"Продуктивность: {productivity}%"

    return [
        (f"✅ {rest_label}" if rest_time not in (None, "") else rest_label, "leisure:rest"),
        (f"✅ {sleep_label}" if sleep_hours not in (None, "") else sleep_label, "leisure:sleep"),
        (f"✅ {prod_label}" if productivity not in (None, "") else prod_label, "leisure:productivity"),
    ]


def build_morale_menu(data: dict) -> list[tuple[str, str]]:
    mood = data.get("Настроение")
    energy = data.get("Энергия")
    weight = data.get("Вес")
    return [
        (f"✅ Настроение: {mood}" if mood not in (None, "") else "Настроение", "morale:mood"),
        (f"✅ Энергия: {energy}" if energy not in (None, "") else "Энергия", "morale:energy"),
        (f"✅ Вес: {weight}" if weight not in (None, "") else "Вес", "morale:weight"),
        ("О чем жалею", "morale:regret"),
        ("Отзыв о дне", "morale:review"),
    ]


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
        summary = await build_daily_summary(context, date_str)
        await query.edit_message_text(f"{summary}\n\nВыбери раздел:", reply_markup=build_keyboard(MAIN_MENU, cols=2))
        return
    if data == "menu:today":
        await query.answer()
        summary = await build_daily_summary(context, date_str)
        await query.edit_message_text(summary, reply_markup=build_keyboard(MAIN_MENU, cols=2))
        return
    if data == "menu:sport":
        daily = get_daily_data(context, date_str)
        await show_menu(query, "Спорт:", build_sport_menu(daily))
        return
    if data == "menu:study":
        daily = get_daily_data(context, date_str)
        await show_menu(query, "Учеба:", build_study_menu(daily))
        return
    if data == "menu:leisure":
        daily = get_daily_data(context, date_str)
        await show_menu(query, "Досуг:", build_leisure_menu(daily))
        return
    if data == "menu:food":
        await query.answer()
        summary = await build_food_summary(context, date_str)
        await query.edit_message_text(
            summary,
            reply_markup=build_keyboard(FOOD_MENU, cols=2, back=("⬅️ Назад", "menu:main")),
        )
        return
    if data == "menu:morale":
        daily = get_daily_data(context, date_str)
        await show_menu(query, "Моралька:", build_morale_menu(daily))
        return
    if data == "menu:habits":
        await show_menu(query, "Привычки:", HABITS_MENU)
        return

    if data == "sport:training":
        daily = get_daily_data(context, date_str)
        current = daily.get("Тренировка")
        await show_menu(query, "Тренировка:", mark_set_buttons(TRAINING_OPTIONS, current), back_to="menu:sport", cols=2)
        return
    if data == "sport:rest":
        sheets.update_daily_fields(date_str, {COLUMN_MAP["training"]: "Отдых"}, max_rows=cfg.daily_max_rows)
        daily = get_daily_data(context, date_str)
        await show_menu(query, "Спорт:", build_sport_menu(daily))
        return
    if data == "sport:skip":
        sheets.update_daily_fields(date_str, {COLUMN_MAP["training"]: "Пропустил"}, max_rows=cfg.daily_max_rows)
        daily = get_daily_data(context, date_str)
        await show_menu(query, "Спорт:", build_sport_menu(daily))
        return
    if data == "sport:cardio":
        daily = get_daily_data(context, date_str)
        current = daily.get("Кардио_мин")
        await show_menu(query, "Кардио (мин):", mark_set_buttons(CARDIO_OPTIONS, current), back_to="menu:sport", cols=3)
        return
    if data == "sport:steps":
        daily = get_daily_data(context, date_str)
        current = daily.get("Шаги_категория")
        await show_menu(query, "Шаги:", mark_set_buttons(STEPS_OPTIONS, current), back_to="menu:sport", cols=2)
        return

    if data == "study:english":
        daily = get_daily_data(context, date_str)
        current = daily.get("Английский_мин")
        await show_menu(query, "Английский:", mark_set_buttons(ENGLISH_OPTIONS, current), back_to="menu:study", cols=3)
        return
    if data == "study:code":
        daily = get_daily_data(context, date_str)
        current = daily.get("Код_режим")
        await show_menu(query, "Код: режим", mark_set_buttons(CODE_MODE_OPTIONS, current), back_to="menu:study", cols=1)
        return
    if data == "study:reading":
        daily = get_daily_data(context, date_str)
        current = daily.get("Чтение_стр")
        await show_menu(query, "Чтение:", mark_set_buttons(READING_OPTIONS, current), back_to="menu:study", cols=4)
        return

    if data == "leisure:rest":
        daily = get_daily_data(context, date_str)
        current = daily.get("Отдых_время")
        await show_menu(query, "Отдых: время", mark_set_buttons(REST_TIME_OPTIONS, current), back_to="menu:leisure", cols=2)
        return
    if data == "leisure:sleep":
        daily = get_daily_data(context, date_str)
        current = daily.get("Сон_отбой")
        await show_menu(query, "Сон: во сколько заснул?", mark_set_buttons(SLEEP_BEDTIME_OPTIONS, current), back_to="menu:leisure", cols=3)
        return
    if data == "leisure:productivity":
        daily = get_daily_data(context, date_str)
        current = daily.get("Продуктивность")
        await show_menu(query, "Продуктивность:", mark_set_buttons(PRODUCTIVITY_OPTIONS, current), back_to="menu:leisure", cols=3)
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
        daily = get_daily_data(context, date_str)
        current = daily.get("Настроение")
        await show_menu(query, "Настроение:", mark_set_buttons(MOOD_OPTIONS, current), back_to="menu:morale", cols=2)
        return
    if data == "morale:energy":
        daily = get_daily_data(context, date_str)
        current = daily.get("Энергия")
        await show_menu(query, "Энергия:", mark_set_buttons(ENERGY_OPTIONS, current), back_to="menu:morale", cols=2)
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
            daily = get_daily_data(context, date_str)
            current_topic = daily.get("Код_тема")
            await show_menu(query, "Код: тема", mark_set_buttons(CODE_TOPIC_OPTIONS, current_topic), back_to="menu:study", cols=2)
            return
        if field_key == "code_topic":
            sheets.update_daily_fields(date_str, {COLUMN_MAP["code_topic"]: value}, max_rows=cfg.daily_max_rows)
            daily = get_daily_data(context, date_str)
            await show_menu(query, "Учеба:", build_study_menu(daily))
            return
        if field_key == "rest_time":
            sheets.update_daily_fields(date_str, {COLUMN_MAP["rest_time"]: value}, max_rows=cfg.daily_max_rows)
            daily = get_daily_data(context, date_str)
            current_type = daily.get("Отдых_тип")
            await show_menu(query, "Отдых: тип", mark_set_buttons(REST_TYPE_OPTIONS, current_type), back_to="menu:leisure", cols=2)
            return
        if field_key == "rest_type":
            sheets.update_daily_fields(date_str, {COLUMN_MAP["rest_type"]: value}, max_rows=cfg.daily_max_rows)
            daily = get_daily_data(context, date_str)
            await show_menu(query, "Досуг:", build_leisure_menu(daily))
            return
        if field_key == "sleep_bed":
            sheets.update_daily_fields(date_str, {COLUMN_MAP["sleep_bed"]: value}, max_rows=cfg.daily_max_rows)
            daily = get_daily_data(context, date_str)
            current_hours = daily.get("Сон_часы")
            await show_menu(query, "Сон: сколько часов?", mark_set_buttons(SLEEP_HOURS_OPTIONS, current_hours), back_to="menu:leisure", cols=3)
            return
        if field_key == "sleep_hours":
            sheets.update_daily_fields(date_str, {COLUMN_MAP["sleep_hours"]: value}, max_rows=cfg.daily_max_rows)
            daily = get_daily_data(context, date_str)
            current_regime = daily.get("Режим")
            await show_menu(query, "Сон: режим", mark_set_buttons(SLEEP_REGIME_OPTIONS, current_regime), back_to="menu:leisure", cols=2)
            return
        if field_key == "sleep_regime":
            sheets.update_daily_fields(date_str, {COLUMN_MAP["sleep_regime"]: value}, max_rows=cfg.daily_max_rows)
            daily = get_daily_data(context, date_str)
            await show_menu(query, "Досуг:", build_leisure_menu(daily))
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
                daily = get_daily_data(context, date_str)
                await show_menu(query, "Спорт:", build_sport_menu(daily))
                return
            if field_key in {"english", "reading"}:
                daily = get_daily_data(context, date_str)
                await show_menu(query, "Учеба:", build_study_menu(daily))
                return
            if field_key == "productivity":
                daily = get_daily_data(context, date_str)
                await show_menu(query, "Досуг:", build_leisure_menu(daily))
                return
            if field_key in {"mood", "energy"}:
                daily = get_daily_data(context, date_str)
                await show_menu(query, "Моралька:", build_morale_menu(daily))
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
        return "📅 Сегодня пока нет данных."

    values = row.values + [""] * (len(DAILY_HEADERS) - len(row.values))
    data = dict(zip(DAILY_HEADERS, values))

    kcal = parse_sheet_number(data.get("Ккал"))
    protein = parse_sheet_number(data.get("Белки"))
    fat = parse_sheet_number(data.get("Жиры"))
    carbs = parse_sheet_number(data.get("Угли"))

    lines = [
        f"📅 Сегодня: {date_str}",
        f"⭐ Качество дня: {fmt_value(data.get('Качество_дня'))}",
        f"🍽 КБЖУ: {fmt_num(kcal)} ккал | Б {fmt_num(protein, 1)} | Ж {fmt_num(fat, 1)} | У {fmt_num(carbs, 1)}",
    ]

    sport_parts = []
    training_display = display_training(data.get("Тренировка"))
    if training_display:
        sport_parts.append(training_display)
    if data.get("Кардио_мин"):
        sport_parts.append(f"кардио {data.get('Кардио_мин')}м")
    if data.get("Шаги_категория"):
        sport_parts.append(f"шаги {data.get('Шаги_категория')}")
    if sport_parts:
        lines.append(f"🏋️ Спорт: {', '.join(sport_parts)}")

    study_parts = []
    if data.get("Английский_мин"):
        study_parts.append(f"англ {data.get('Английский_мин')}м")
    if data.get("Код_режим") or data.get("Код_тема"):
        mode = data.get("Код_режим") or "—"
        topic = data.get("Код_тема") or "—"
        study_parts.append(f"код {mode}/{topic}")
    if data.get("Чтение_стр"):
        study_parts.append(f"чтение {data.get('Чтение_стр')} стр")
    if study_parts:
        lines.append(f"📚 Учеба: {', '.join(study_parts)}")

    sleep_parts = []
    if data.get("Сон_часы"):
        sleep_parts.append(f"{data.get('Сон_часы')} ч")
    if data.get("Режим"):
        sleep_parts.append(f"режим {data.get('Режим')}")
    if sleep_parts:
        lines.append(f"🌙 Сон: {', '.join(sleep_parts)}")

    leisure_parts = []
    if data.get("Продуктивность"):
        leisure_parts.append(f"продуктивность {data.get('Продуктивность')}%")
    if data.get("Настроение"):
        leisure_parts.append(f"настроение {data.get('Настроение')}")
    if data.get("Энергия"):
        leisure_parts.append(f"энергия {data.get('Энергия')}")
    if leisure_parts:
        lines.append(f"🙂 Моралька: {', '.join(leisure_parts)}")

    if data.get("Вес"):
        lines.append(f"⚖️ Вес: {data.get('Вес')}")
    if data.get("О_чем_жалею"):
        lines.append(f"📝 О чем жалею: {data.get('О_чем_жалею')}")
    if data.get("Отзыв_о_дне"):
        lines.append(f"🗒 Отзыв: {data.get('Отзыв_о_дне')}")
    if data.get("Привычки"):
        lines.append(f"🧠 Привычки: {data.get('Привычки')}")

    missing = data.get("Не_заполнено")
    if missing not in (None, ""):
        lines.append(f"⚠️ Не заполнено: {missing}")

    return "\n".join(lines)


async def build_food_summary(context: ContextTypes.DEFAULT_TYPE, date_str: str) -> str:
    cfg = context.application.bot_data["config"]
    sheets = get_sheets(context)
    row = sheets.get_daily_row(date_str, max_rows=cfg.daily_max_rows)
    if not row:
        return "🍽 Еда: сегодня пока нет данных."

    values = row.values + [""] * (len(DAILY_HEADERS) - len(row.values))
    data = dict(zip(DAILY_HEADERS, values))

    kcal = parse_sheet_number(data.get("Ккал"))
    protein = parse_sheet_number(data.get("Белки"))
    fat = parse_sheet_number(data.get("Жиры"))
    carbs = parse_sheet_number(data.get("Угли"))

    lines = [
        "🍽 Еда за сегодня",
        f"• Ккал: {fmt_num(kcal)}",
        f"• Б/Ж/У: {fmt_num(protein, 1)} / {fmt_num(fat, 1)} / {fmt_num(carbs, 1)}",
    ]

    # List of foods eaten today
    food_rows = sheets.get_values(f"FoodLog!A2:E{cfg.foodlog_max_rows + 1}")
    portion_rows = sheets.get_values("Portions!A2:C")
    portion_map: dict[str, str] = {}
    for row_item in portion_rows:
        if not row_item or len(row_item) < 2:
            continue
        code = str(row_item[0])
        product = str(row_item[1])
        desc = str(row_item[2]) if len(row_item) > 2 and row_item[2] not in (None, "") else ""
        label = f"{product} ({desc})" if desc else product
        portion_map[code] = label

    eaten: dict[str, dict[str, float]] = {}
    for row_item in food_rows:
        if not row_item or len(row_item) < 4:
            continue
        if row_item[0] != date_str:
            continue
        code = str(row_item[2])
        qty = parse_sheet_number(row_item[3])
        grams = parse_sheet_number(row_item[4]) if len(row_item) > 4 else 0.0
        label = portion_map.get(code, code)
        if label not in eaten:
            eaten[label] = {"qty": 0.0, "grams": 0.0}
        eaten[label]["qty"] += qty
        eaten[label]["grams"] += grams

    if eaten:
        lines.append("")
        lines.append("🧾 Съел сегодня:")
        items = list(eaten.items())
        max_items = 12
        for label, stats in items[:max_items]:
            qty = stats["qty"]
            grams = stats["grams"]
            qty_str = fmt_num(qty, 1) if qty % 1 else str(int(qty))
            line = f"• {label} ×{qty_str}"
            if grams > 0:
                line += f" (~{fmt_num(grams)} г)"
            lines.append(line)
        if len(items) > max_items:
            lines.append(f"… ещё {len(items) - max_items} позиций")

    targets = day_targets(data.get("Тренировка"))
    if not targets:
        lines.append("")
        lines.append("⚠️ Тип дня не задан. Выбери тренировку/отдых в разделе «Спорт»,")
        lines.append("чтобы увидеть цели по КБЖУ.")
        return "\n".join(lines)

    kcal_min, kcal_max = targets["kcal"]
    p_min, p_max = targets["protein"]
    f_min, f_max = targets["fat"]
    c_min, c_max = targets["carb"]

    lines.append("")
    lines.append(f"🎯 Цель ({targets['label']})")
    lines.append(f"• Ккал: {kcal_min}–{kcal_max}")
    lines.append(f"• Б/Ж/У: {p_min}–{p_max} / {f_min}–{f_max} / {c_min}–{c_max}")

    def delta_to_min(value: float, min_val: float) -> float:
        return max(0.0, min_val - value)

    def delta_to_max(value: float, max_val: float) -> float:
        return max(0.0, max_val - value)

    def over_max(value: float, max_val: float) -> float:
        return max(0.0, value - max_val)

    d_kcal_min = delta_to_min(kcal, kcal_min)
    d_p_min = delta_to_min(protein, p_min)
    d_f_min = delta_to_min(fat, f_min)
    d_c_min = delta_to_min(carbs, c_min)

    d_kcal_max = delta_to_max(kcal, kcal_max)
    d_p_max = delta_to_max(protein, p_max)
    d_f_max = delta_to_max(fat, f_max)
    d_c_max = delta_to_max(carbs, c_max)

    over_kcal = over_max(kcal, kcal_max)
    over_p = over_max(protein, p_max)
    over_f = over_max(fat, f_max)
    over_c = over_max(carbs, c_max)

    lines.append("")
    lines.append(
        f"⏳ До минимума: Ккал +{fmt_num(d_kcal_min)} | Б +{fmt_num(d_p_min, 1)} | Ж +{fmt_num(d_f_min, 1)} | У +{fmt_num(d_c_min, 1)}"
    )
    lines.append(
        f"📈 До максимума: Ккал {fmt_num(d_kcal_max)} | Б {fmt_num(d_p_max, 1)} | Ж {fmt_num(d_f_max, 1)} | У {fmt_num(d_c_max, 1)}"
    )
    if any(x > 0 for x in (over_kcal, over_p, over_f, over_c)):
        lines.append(
            f"🚨 Перебор: Ккал +{fmt_num(over_kcal)} | Б +{fmt_num(over_p, 1)} | Ж +{fmt_num(over_f, 1)} | У +{fmt_num(over_c, 1)}"
        )

    return "\n".join(lines)


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
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    app.run_polling()


if __name__ == "__main__":
    main()
