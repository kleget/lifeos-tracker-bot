from __future__ import annotations

import asyncio
import logging
import re
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
    PROCRASTINATION_OPTIONS,
    FOOD_MENU,
    FOOD_PROTEIN_OPTIONS,
    FOOD_GARNISH_OPTIONS,
    FOOD_SWEET_OPTIONS,
    FOOD_OIL_OPTIONS,
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

FORMULA_COLUMNS = ["U", "V", "W", "X", "Y", "Z"]
FORMULA_TEMPLATE_RANGE = "Daily!U2:Z2"


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


async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    LOGGER.exception("Unhandled error: %s", context.error)
    if update is None:
        return
    try:
        if hasattr(update, "effective_chat") and update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⚠️ Ошибка при обращении к таблице. Попробуй ещё раз через минуту.",
            )
    except Exception:
        LOGGER.exception("Failed to send error message")


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


def reading_is_set(value: object) -> bool:
    return value not in (None, "")


def format_reading_label(value: object) -> str:
    if value in (None, ""):
        return "Чтение"
    text = normalize_choice(value)
    if text in {"0", "0.0"}:
        return "Чтение: не читал"
    return f"Чтение: {text} стр"


_CELL_REF_RE = re.compile(r"(\$?[A-Z]{1,2})(\$?)2\b")


def adjust_formula_row(formula: str, row_index: int) -> str:
    if row_index == 2:
        return formula

    def repl(match: re.Match) -> str:
        col = match.group(1)
        row_abs = match.group(2)
        return f"{col}{row_abs}{row_index}"

    return _CELL_REF_RE.sub(repl, formula)


def get_daily_formula_templates(context: ContextTypes.DEFAULT_TYPE) -> list[str]:
    cached = context.application.bot_data.get("daily_formula_templates")
    if cached:
        return cached
    sheets = get_sheets(context)
    rows = sheets.get_values(FORMULA_TEMPLATE_RANGE, value_render_option="FORMULA")
    if not rows or not rows[0]:
        return []
    templates = rows[0] + [""] * (len(FORMULA_COLUMNS) - len(rows[0]))
    context.application.bot_data["daily_formula_templates"] = templates
    return templates


def ensure_daily_formulas(context: ContextTypes.DEFAULT_TYPE, row_index: int) -> bool:
    templates = get_daily_formula_templates(context)
    if not templates:
        return False
    sheets = get_sheets(context)
    existing = sheets.get_values(
        f"Daily!{FORMULA_COLUMNS[0]}{row_index}:{FORMULA_COLUMNS[-1]}{row_index}",
        value_render_option="FORMULA",
    )
    row_vals = existing[0] if existing else []
    updates = []
    for idx, tmpl in enumerate(templates):
        if not tmpl:
            continue
        current = row_vals[idx] if idx < len(row_vals) else ""
        if current not in (None, ""):
            continue
        formula = adjust_formula_row(tmpl, row_index)
        updates.append(
            {
                "range": f"Daily!{FORMULA_COLUMNS[idx]}{row_index}",
                "values": [[formula]],
            }
        )
    if updates:
        sheets.batch_update_values(updates)
        return True
    return False


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


def mark_choice_buttons(buttons: list[tuple[str, str]], current_value: object, prefix: str) -> list[tuple[str, str]]:
    current = normalize_choice(current_value)
    marked: list[tuple[str, str]] = []
    for label, data in buttons:
        if data.startswith(prefix):
            value = data.split(":", 1)[1] if ":" in data else ""
            if normalize_choice(value) == current and current:
                label = f"✅ {label}"
        marked.append((label, data))
    return marked


def get_daily_data(context: ContextTypes.DEFAULT_TYPE, date_str: str) -> dict:
    cfg = context.application.bot_data["config"]
    sheets = get_sheets(context)
    row = sheets.get_daily_row(date_str, max_rows=cfg.daily_max_rows)
    if not row:
        return {}
    if ensure_daily_formulas(context, row.row_index):
        row = sheets.get_daily_row(date_str, max_rows=cfg.daily_max_rows)
        if not row:
            return {}
    values = row.values + [""] * (len(DAILY_HEADERS) - len(row.values))
    return dict(zip(DAILY_HEADERS, values))


def normalize_choice(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.endswith(".0"):
        text = text[:-2]
    return text


def parse_habits_value(value: object) -> list[str]:
    if value in (None, ""):
        return []
    text = str(value).replace(",", ";")
    return [part.strip() for part in text.split(";") if part.strip()]


def format_habits_value(items: list[str]) -> str:
    return "; ".join(items)


FIELD_HEADERS = {
    "training": "Тренировка",
    "cardio": "Кардио_мин",
    "steps": "Шаги_категория",
    "english": "Английский_мин",
    "code_mode": "Код_режим",
    "code_topic": "Код_тема",
    "reading": "Чтение_стр",
    "rest_time": "Отдых_время",
    "rest_type": "Отдых_тип",
    "sleep_bed": "Сон_отбой",
    "sleep_hours": "Сон_часы",
    "sleep_regime": "Режим",
    "productivity": "Продуктивность",
    "mood": "Настроение",
    "energy": "Энергия",
}

FIELD_LABELS = {
    "training": "Тренировка",
    "cardio": "Кардио",
    "steps": "Шаги",
    "english": "Английский",
    "code_mode": "Код (режим)",
    "code_topic": "Код (тема)",
    "reading": "Чтение",
    "rest_time": "Отдых (время)",
    "rest_type": "Отдых (тип)",
    "sleep_bed": "Сон (отбой)",
    "sleep_hours": "Сон (часы)",
    "sleep_regime": "Режим",
    "productivity": "Продуктивность",
    "mood": "Настроение",
    "energy": "Энергия",
}


def build_sport_menu(data: dict) -> list[tuple[str, str]]:
    training = data.get("Тренировка")
    training_display = display_training(training) if training in {"Ноги", "Верх"} else None
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


def build_study_menu(
    data: dict,
    *,
    code_label: str | None = None,
    code_selected: bool = False,
) -> list[tuple[str, str]]:
    english = data.get("Английский_мин")
    english_label = "Английский" if english in (None, "") else f"Английский: {english}м"

    if code_label is None:
        code_mode = data.get("Код_режим")
        code_topic = data.get("Код_тема")
        code_label = "Код"
        if code_mode or code_topic:
            code_label = f"Код: {code_mode or '—'}/{code_topic or '—'}"
        code_selected = bool(code_mode or code_topic)

    reading = data.get("Чтение_стр")
    reading_label = format_reading_label(reading)

    return [
        (f"✅ {english_label}" if english not in (None, "") else english_label, "study:english"),
        (f"✅ {code_label}" if code_selected else code_label, "study:code"),
        (f"✅ {reading_label}" if reading_is_set(reading) else reading_label, "study:reading"),
    ]


def build_leisure_menu(data: dict) -> list[tuple[str, str]]:
    rest_time = data.get("Отдых_время")
    rest_label = "Отдых" if rest_time in (None, "") else f"Отдых: {rest_time}"

    sleep_hours = data.get("Сон_часы")
    sleep_label = "Сон" if sleep_hours in (None, "") else f"Сон: {sleep_hours}ч"

    productivity = data.get("Продуктивность")
    prod_label = "Продуктивность" if productivity in (None, "") else f"Продуктивность: {productivity}%"

    anti_count = data.get("_anti_count")
    anti_label = "Анти‑прокраст."
    if anti_count:
        anti_label = f"Анти‑прокраст.: {anti_count}"

    return [
        (f"✅ {rest_label}" if rest_time not in (None, "") else rest_label, "leisure:rest"),
        (f"✅ {sleep_label}" if sleep_hours not in (None, "") else sleep_label, "leisure:sleep"),
        (f"✅ {prod_label}" if productivity not in (None, "") else prod_label, "leisure:productivity"),
        (f"✅ {anti_label}" if anti_count else anti_label, "leisure:anti"),
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


def build_code_buttons(current_mode: object) -> list[tuple[str, str]]:
    buttons = mark_choice_buttons(CODE_MODE_OPTIONS, current_mode, "code_mode:")
    buttons.append(("↩️ Удалить последнюю", "code:undo"))
    buttons.append(("🗑 Очистить код за сегодня", "code:clear"))
    return buttons


async def build_code_menu(context: ContextTypes.DEFAULT_TYPE, date_str: str) -> tuple[str, list[tuple[str, str]]]:
    sheets = get_sheets(context)
    sessions = sheets.get_sessions(date_str, category="Код")
    current_mode = context.user_data.get("code_mode")

    lines = ["💻 Код за сегодня"]
    if not sessions:
        lines.append("Пока нет записей.")
    else:
        labels = [s.get("subcategory") for s in sessions if s.get("subcategory")]
        max_items = 6
        for label in labels[:max_items]:
            lines.append(f"• {label}")
        if len(labels) > max_items:
            lines.append(f"… ещё {len(labels) - max_items}")

    if current_mode:
        lines.append("")
        lines.append(f"Выбран режим: {current_mode}")

    return "\n".join(lines), build_code_buttons(current_mode)


async def build_habits_menu(context: ContextTypes.DEFAULT_TYPE, date_str: str) -> tuple[str, list[tuple[str, str]]]:
    sheets = get_sheets(context)
    habits = sheets.get_habits()
    daily = get_daily_data(context, date_str)
    completed = set(parse_habits_value(daily.get("Привычки")))

    total = len(habits)
    done = sum(1 for habit in habits if habit in completed)
    if total:
        header = f"🧠 Привычки сегодня: {done}/{total}"
    else:
        header = "🧠 Привычки: пока нет списка"

    buttons: list[tuple[str, str]] = []
    context.user_data["habit_list"] = habits
    max_items = 10
    for idx, habit in enumerate(habits[:max_items]):
        status = "✅" if habit in completed else "⬜"
        buttons.append((f"{status} {habit}", f"habit:toggle:{idx}"))
    if len(habits) > max_items:
        header = f"{header}\n… ещё {len(habits) - max_items} привычек не показаны"

    buttons.append(("➕ Добавить привычку", "habit:add"))
    if completed:
        buttons.append(("🧹 Сбросить отметки", "habit:clear"))

    return header, buttons


def sync_code_fields(sheets: SheetsClient, date_str: str, *, max_rows: int = 400) -> None:
    sessions = sheets.get_sessions(date_str, category="Код")
    if not sessions:
        sheets.update_daily_fields(date_str, {COLUMN_MAP["code_mode"]: "", COLUMN_MAP["code_topic"]: ""}, max_rows=max_rows)
        return
    last = sessions[-1].get("subcategory") or ""
    if "/" in last:
        mode, topic = last.split("/", 1)
    else:
        mode, topic = last, ""
    sheets.update_daily_fields(date_str, {COLUMN_MAP["code_mode"]: mode, COLUMN_MAP["code_topic"]: topic}, max_rows=max_rows)


async def build_anti_menu(context: ContextTypes.DEFAULT_TYPE, date_str: str) -> tuple[str, list[tuple[str, str]]]:
    sheets = get_sheets(context)
    sessions = sheets.get_sessions(date_str, category="Анти")
    counts: dict[str, int] = {}
    for item in sessions:
        reason = item.get("subcategory") or ""
        if not reason:
            continue
        counts[reason] = counts.get(reason, 0) + 1

    lines = ["🧯 Анти‑прокрастинация"]
    if counts:
        summary = ", ".join(f"{k}×{v}" for k, v in list(counts.items())[:6])
        lines.append(f"Сегодня: {summary}")
    else:
        lines.append("Сегодня пока нет отметок.")

    buttons: list[tuple[str, str]] = []
    for label, data in PROCRASTINATION_OPTIONS:
        count = counts.get(label)
        display = f"{label} ({count})" if count else label
        buttons.append((display, data))
    buttons.append(("✍️ Другое", "anti:custom"))
    buttons.append(("↩️ Удалить последнюю", "anti:undo"))
    if counts:
        buttons.append(("🗑 Очистить сегодня", "anti:clear"))

    return "\n".join(lines), buttons


def build_code_label(sessions: list[dict]) -> tuple[str, bool]:
    if not sessions:
        return ("Код", False)
    labels = [s.get("subcategory") for s in sessions if s.get("subcategory")]
    preview = ", ".join(labels[:2])
    if len(labels) > 2:
        preview = f"{preview} +{len(labels) - 2}"
    label = f"Код: {preview}" if preview else f"Код: {len(labels)}"
    return (label, True)


async def show_study_menu(query, context: ContextTypes.DEFAULT_TYPE, date_str: str) -> None:
    sheets = get_sheets(context)
    daily = get_daily_data(context, date_str)
    sessions = sheets.get_sessions(date_str, category="Код")
    code_label, code_selected = build_code_label(sessions)
    await show_menu(query, "Учеба:", build_study_menu(daily, code_label=code_label, code_selected=code_selected))


def compute_portions(portion_rows: list[list[object]], food_rows: list[list[object]]) -> list[dict]:
    product_map: dict[str, dict[str, float]] = {}
    for row in food_rows:
        if len(row) < 5:
            continue
        name = str(row[0]).strip()
        if not name:
            continue
        product_map[name] = {
            "protein": parse_sheet_number(row[1]),
            "fat": parse_sheet_number(row[2]),
            "carb": parse_sheet_number(row[3]),
            "kcal": parse_sheet_number(row[4]),
        }

    portions: list[dict] = []
    for row in portion_rows:
        if len(row) < 4:
            continue
        code = str(row[0]).strip()
        product = str(row[1]).strip() if row[1] else ""
        desc = str(row[2]).strip() if row[2] else ""
        grams = parse_sheet_number(row[3])
        if not code or not product or grams <= 0:
            continue
        per100 = product_map.get(product)
        if not per100:
            continue
        macros = {
            "kcal": grams / 100 * per100["kcal"],
            "protein": grams / 100 * per100["protein"],
            "fat": grams / 100 * per100["fat"],
            "carb": grams / 100 * per100["carb"],
        }
        label = f"{product} ({desc})" if desc else product
        portions.append(
            {
                "code": code,
                "product": product,
                "label": label,
                "grams": grams,
                "macros": macros,
            }
        )
    return portions


def recommend_portions(
    current: dict,
    target_mid: dict,
    portions: list[dict],
    *,
    eaten_products: set[str],
    max_items: int = 3,
) -> list[dict]:
    weights = {"kcal": 1.0, "protein": 1.3, "fat": 0.8, "carb": 1.0}

    def deficit(vec):
        return {
            key: max(0.0, target_mid[key] - vec.get(key, 0.0))
            for key in target_mid
        }

    base_def = deficit(current)
    base_score = sum((base_def[k] ** 2) * weights[k] for k in base_def)

    scored = []
    for portion in portions:
        new_vec = {
            key: current.get(key, 0.0) + portion["macros"].get(key, 0.0)
            for key in target_mid
        }
        new_def = deficit(new_vec)
        new_score = sum((new_def[k] ** 2) * weights[k] for k in new_def)
        improvement = base_score - new_score
        if improvement <= 0:
            continue
        penalty = 0.6 if portion["product"] in eaten_products else 1.0
        scored.append((improvement * penalty, portion))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:max_items]]


def build_plan(
    current: dict,
    target_mid: dict,
    portions: list[dict],
    *,
    eaten_products: set[str],
    max_steps: int = 4,
) -> list[dict]:
    plan: list[dict] = []
    temp = current.copy()
    used_products: set[str] = set()
    for _ in range(max_steps):
        candidates = recommend_portions(
            temp,
            target_mid,
            portions,
            eaten_products=eaten_products.union(used_products),
            max_items=1,
        )
        if not candidates:
            break
        choice = candidates[0]
        plan.append(choice)
        used_products.add(choice["product"])
        for key in target_mid:
            temp[key] = temp.get(key, 0.0) + choice["macros"].get(key, 0.0)
    return plan


def menu_config(menu_key: str, data: dict) -> tuple[str, list[tuple[str, str]], str, int]:
    if menu_key == "sport":
        return ("Спорт:", build_sport_menu(data), "menu:main", 2)
    if menu_key == "study":
        return ("Учеба:", build_study_menu(data), "menu:main", 2)
    if menu_key == "leisure":
        return ("Досуг:", build_leisure_menu(data), "menu:main", 2)
    if menu_key == "morale":
        return ("Моралька:", build_morale_menu(data), "menu:main", 2)
    if menu_key == "training":
        return ("Тренировка:", mark_set_buttons(TRAINING_OPTIONS, data.get("Тренировка")), "menu:sport", 2)
    if menu_key == "cardio":
        return ("Кардио (мин):", mark_set_buttons(CARDIO_OPTIONS, data.get("Кардио_мин")), "menu:sport", 3)
    if menu_key == "steps":
        return ("Шаги:", mark_set_buttons(STEPS_OPTIONS, data.get("Шаги_категория")), "menu:sport", 2)
    if menu_key == "english":
        return ("Английский:", mark_set_buttons(ENGLISH_OPTIONS, data.get("Английский_мин")), "menu:study", 3)
    if menu_key == "code_mode":
        return ("Код: режим", mark_set_buttons(CODE_MODE_OPTIONS, data.get("Код_режим")), "menu:study", 1)
    if menu_key == "code_topic":
        return ("Код: тема", mark_set_buttons(CODE_TOPIC_OPTIONS, data.get("Код_тема")), "menu:study", 2)
    if menu_key == "reading":
        return ("Чтение:", mark_set_buttons(READING_OPTIONS, data.get("Чтение_стр")), "menu:study", 4)
    if menu_key == "rest_time":
        return ("Отдых: время", mark_set_buttons(REST_TIME_OPTIONS, data.get("Отдых_время")), "menu:leisure", 2)
    if menu_key == "rest_type":
        return ("Отдых: тип", mark_set_buttons(REST_TYPE_OPTIONS, data.get("Отдых_тип")), "menu:leisure", 2)
    if menu_key == "sleep_bed":
        return ("Сон: во сколько заснул?", mark_set_buttons(SLEEP_BEDTIME_OPTIONS, data.get("Сон_отбой")), "menu:leisure", 3)
    if menu_key == "sleep_hours":
        return ("Сон: сколько часов?", mark_set_buttons(SLEEP_HOURS_OPTIONS, data.get("Сон_часы")), "menu:leisure", 3)
    if menu_key == "sleep_regime":
        return ("Сон: режим", mark_set_buttons(SLEEP_REGIME_OPTIONS, data.get("Режим")), "menu:leisure", 2)
    if menu_key == "productivity":
        return ("Продуктивность:", mark_set_buttons(PRODUCTIVITY_OPTIONS, data.get("Продуктивность")), "menu:leisure", 3)
    if menu_key == "mood":
        return ("Настроение:", mark_set_buttons(MOOD_OPTIONS, data.get("Настроение")), "menu:morale", 2)
    if menu_key == "energy":
        return ("Энергия:", mark_set_buttons(ENERGY_OPTIONS, data.get("Энергия")), "menu:morale", 2)
    return ("Главное меню:", MAIN_MENU, "menu:main", 2)


async def confirm_override(
    context: ContextTypes.DEFAULT_TYPE,
    query,
    *,
    field_key: str,
    current_value: object,
    new_value: object,
    return_menu: str,
    next_menu: str | None = None,
) -> None:
    label = FIELD_LABELS.get(field_key, field_key)
    current_display = display_training(current_value) if field_key == "training" else fmt_value(current_value)
    new_display = display_training(new_value) if field_key == "training" else fmt_value(new_value)
    context.user_data["pending_set"] = {
        "field_key": field_key,
        "value": new_value,
        "return_menu": return_menu,
        "next_menu": next_menu,
    }
    buttons = [("✅ Да", "confirm:yes"), ("↩️ Нет", "confirm:no")]
    back_cb = return_menu if return_menu.startswith("menu:") else f"menu:{return_menu}"
    await query.answer()
    await query.edit_message_text(
        f"⚠️ {label}\nСейчас: {current_display}\nЗаменить на: {new_display}?",
        reply_markup=build_keyboard(buttons, cols=2, back=("⬅️ Назад", back_cb)),
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(context, update.effective_user.id if update.effective_user else None):
        return
    query = update.callback_query
    data = query.data
    cfg = context.application.bot_data["config"]
    sheets = get_sheets(context)
    date_str = today_str(cfg.timezone)

    if data.startswith("confirm:"):
        await query.answer()
        pending = context.user_data.get("pending_set")
        if not pending:
            await query.edit_message_text("Главное меню:", reply_markup=build_keyboard(MAIN_MENU, cols=2))
            return
        if data == "confirm:yes":
            field_key = pending["field_key"]
            value = pending["value"]
            next_menu = pending.get("next_menu")
            return_menu = pending.get("return_menu", "menu:main")
            sheets.update_daily_fields(date_str, {COLUMN_MAP[field_key]: value}, max_rows=cfg.daily_max_rows)
            context.user_data.pop("pending_set", None)
            daily = get_daily_data(context, date_str)
            menu_key = next_menu or return_menu
            if menu_key == "study":
                await show_study_menu(query, context, date_str)
                return
            title, buttons, back_to, cols = menu_config(menu_key, daily)
            await show_menu(query, title, buttons, back_to=back_to, cols=cols)
            return
        if data == "confirm:no":
            return_menu = pending.get("return_menu", "menu:main")
            context.user_data.pop("pending_set", None)
            daily = get_daily_data(context, date_str)
            if return_menu == "study":
                await show_study_menu(query, context, date_str)
                return
            title, buttons, back_to, cols = menu_config(return_menu, daily)
            await show_menu(query, title, buttons, back_to=back_to, cols=cols)
            return

    if data == "menu:main":
        await query.answer()
        summary = await build_daily_summary(context, date_str)
        await query.edit_message_text(f"{summary}\n\nВыбери раздел:", reply_markup=build_keyboard(MAIN_MENU, cols=2))
        return
    if data == "menu:sport":
        daily = get_daily_data(context, date_str)
        await show_menu(query, "Спорт:", build_sport_menu(daily))
        return
    if data == "menu:study":
        await show_study_menu(query, context, date_str)
        return
    if data == "menu:leisure":
        daily = get_daily_data(context, date_str)
        anti_sessions = sheets.get_sessions(date_str, category="Анти")
        if anti_sessions:
            daily["_anti_count"] = len(anti_sessions)
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
        await query.answer()
        text, buttons = await build_habits_menu(context, date_str)
        await query.edit_message_text(
            text,
            reply_markup=build_keyboard(buttons, cols=1, back=("⬅️ Назад", "menu:main")),
        )
        return

    if data.startswith("habit:toggle:"):
        await query.answer()
        try:
            idx = int(data.split(":")[2])
        except (IndexError, ValueError):
            return
        habits = context.user_data.get("habit_list") or sheets.get_habits()
        if idx < 0 or idx >= len(habits):
            return
        habit = habits[idx]
        daily = get_daily_data(context, date_str)
        completed = parse_habits_value(daily.get("Привычки"))
        if habit in completed:
            completed = [h for h in completed if h != habit]
        else:
            completed.append(habit)
        sheets.update_daily_fields(date_str, {COLUMN_MAP["habits"]: format_habits_value(completed)}, max_rows=cfg.daily_max_rows)
        text, buttons = await build_habits_menu(context, date_str)
        await query.edit_message_text(
            text,
            reply_markup=build_keyboard(buttons, cols=1, back=("⬅️ Назад", "menu:main")),
        )
        return

    if data == "habit:add":
        await query.answer()
        context.user_data["expect"] = "habit_add"
        await query.edit_message_text("Введи название новой привычки (например, \"Зарядка\"):")
        return

    if data == "habit:clear":
        await query.answer()
        await query.edit_message_text(
            "Сбросить все отметки привычек за сегодня?",
            reply_markup=build_keyboard([("✅ Да", "habit_clear:yes"), ("↩️ Нет", "habit_clear:no")], cols=2, back=("⬅️ Назад", "menu:habits")),
        )
        return

    if data.startswith("habit_clear:"):
        await query.answer()
        if data == "habit_clear:yes":
            sheets.update_daily_fields(date_str, {COLUMN_MAP["habits"]: ""}, max_rows=cfg.daily_max_rows)
        text, buttons = await build_habits_menu(context, date_str)
        await query.edit_message_text(
            text,
            reply_markup=build_keyboard(buttons, cols=1, back=("⬅️ Назад", "menu:main")),
        )
        return

    if data.startswith("anti:"):
        await query.answer()
        reason = data.split(":", 1)[1] if ":" in data else ""
        if reason == "custom":
            context.user_data["expect"] = "anti_custom"
            await query.edit_message_text("Напиши причину прокрастинации (коротко):")
            return
        if reason == "undo":
            removed = sheets.delete_last_session(date_str, category="Анти")
            text, buttons = await build_anti_menu(context, date_str)
            prefix = "↩️ Удалил последнюю.\n\n" if removed else "Нет записей для удаления.\n\n"
            await query.edit_message_text(
                f"{prefix}{text}",
                reply_markup=build_keyboard(buttons, cols=2, back=("⬅️ Назад", "menu:leisure")),
            )
            return
        if reason == "clear":
            sheets.clear_sessions(date_str, category="Анти")
            text, buttons = await build_anti_menu(context, date_str)
            await query.edit_message_text(
                f"🗑 Очистил записи.\n\n{text}",
                reply_markup=build_keyboard(buttons, cols=2, back=("⬅️ Назад", "menu:leisure")),
            )
            return
        # regular reason
        sheets.add_session(date_str, time_str(cfg.timezone), "Анти", reason, 0, "")
        text, buttons = await build_anti_menu(context, date_str)
        await query.edit_message_text(
            text,
            reply_markup=build_keyboard(buttons, cols=2, back=("⬅️ Назад", "menu:leisure")),
        )
        return

    if data == "sport:training":
        daily = get_daily_data(context, date_str)
        current = daily.get("Тренировка")
        await show_menu(query, "Тренировка:", mark_set_buttons(TRAINING_OPTIONS, current), back_to="menu:sport", cols=2)
        return
    if data == "sport:rest":
        daily = get_daily_data(context, date_str)
        current = daily.get("Тренировка")
        new_value = "Отдых"
        if normalize_choice(current) and normalize_choice(current) != normalize_choice(new_value):
            await confirm_override(
                context,
                query,
                field_key="training",
                current_value=current,
                new_value=new_value,
                return_menu="sport",
            )
            return
        sheets.update_daily_fields(date_str, {COLUMN_MAP["training"]: new_value}, max_rows=cfg.daily_max_rows)
        daily = get_daily_data(context, date_str)
        await show_menu(query, "Спорт:", build_sport_menu(daily))
        return
    if data == "sport:skip":
        daily = get_daily_data(context, date_str)
        current = daily.get("Тренировка")
        new_value = "Пропустил"
        if normalize_choice(current) and normalize_choice(current) != normalize_choice(new_value):
            await confirm_override(
                context,
                query,
                field_key="training",
                current_value=current,
                new_value=new_value,
                return_menu="sport",
            )
            return
        sheets.update_daily_fields(date_str, {COLUMN_MAP["training"]: new_value}, max_rows=cfg.daily_max_rows)
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
        await query.answer()
        text, buttons = await build_code_menu(context, date_str)
        await query.edit_message_text(
            text,
            reply_markup=build_keyboard(buttons, cols=1, back=("⬅️ Назад", "menu:study")),
        )
        return
    if data == "study:reading":
        daily = get_daily_data(context, date_str)
        current = daily.get("Чтение_стр")
        await show_menu(query, "Чтение:", mark_set_buttons(READING_OPTIONS, current), back_to="menu:study", cols=4)
        return

    if data.startswith("code_mode:"):
        mode = data.split(":", 1)[1]
        context.user_data["code_mode"] = mode
        await query.answer()
        await query.edit_message_text(
            f"💻 Режим: {mode}\nВыбери тему:",
            reply_markup=build_keyboard(mark_choice_buttons(CODE_TOPIC_OPTIONS, None, "code_topic:"), cols=2, back=("⬅️ Назад", "study:code")),
        )
        return

    if data.startswith("code_topic:"):
        topic = data.split(":", 1)[1]
        mode = context.user_data.get("code_mode")
        if not mode:
            await query.answer()
            await query.edit_message_text(
                "Сначала выбери режим:",
                reply_markup=build_keyboard(mark_choice_buttons(CODE_MODE_OPTIONS, None, "code_mode:"), cols=2, back=("⬅️ Назад", "menu:study")),
            )
            return
        sheets.add_session(date_str, time_str(cfg.timezone), "Код", f"{mode}/{topic}", 0, "")
        sync_code_fields(sheets, date_str, max_rows=cfg.daily_max_rows)
        context.user_data.pop("code_mode", None)
        text, buttons = await build_code_menu(context, date_str)
        await query.answer()
        await query.edit_message_text(
            f"✅ Добавил: {mode}/{topic}\n\n{text}",
            reply_markup=build_keyboard(buttons, cols=1, back=("⬅️ Назад", "menu:study")),
        )
        return

    if data == "code:undo":
        removed = sheets.delete_last_session(date_str, category="Код")
        if removed:
            sync_code_fields(sheets, date_str, max_rows=cfg.daily_max_rows)
        text, buttons = await build_code_menu(context, date_str)
        await query.answer()
        prefix = "↩️ Удалил последнюю запись.\n\n" if removed else "Нет записей для удаления.\n\n"
        await query.edit_message_text(
            f"{prefix}{text}",
            reply_markup=build_keyboard(buttons, cols=1, back=("⬅️ Назад", "menu:study")),
        )
        return

    if data == "code:clear":
        await query.answer()
        context.user_data["pending_code_clear"] = True
        await query.edit_message_text(
            "Удалить все записи кода за сегодня?",
            reply_markup=build_keyboard([("✅ Да", "code_clear:yes"), ("↩️ Нет", "code_clear:no")], cols=2, back=("⬅️ Назад", "menu:study")),
        )
        return

    if data.startswith("code_clear:"):
        await query.answer()
        if data == "code_clear:yes":
            sheets.clear_sessions(date_str, category="Код")
            sync_code_fields(sheets, date_str, max_rows=cfg.daily_max_rows)
            context.user_data.pop("pending_code_clear", None)
            text, buttons = await build_code_menu(context, date_str)
            await query.edit_message_text(
                f"🗑 Очистил записи.\n\n{text}",
                reply_markup=build_keyboard(buttons, cols=1, back=("⬅️ Назад", "menu:study")),
            )
            return
        if data == "code_clear:no":
            context.user_data.pop("pending_code_clear", None)
            text, buttons = await build_code_menu(context, date_str)
            await query.edit_message_text(
                text,
                reply_markup=build_keyboard(buttons, cols=1, back=("⬅️ Назад", "menu:study")),
            )
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
    if data == "leisure:anti":
        await query.answer()
        text, buttons = await build_anti_menu(context, date_str)
        await query.edit_message_text(
            text,
            reply_markup=build_keyboard(buttons, cols=2, back=("⬅️ Назад", "menu:leisure")),
        )
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
    if data == "food:oils":
        await show_menu(query, "Еда: масла", FOOD_OIL_OPTIONS, back_to="menu:food", cols=2)
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
        if field_key in FIELD_HEADERS:
            daily = get_daily_data(context, date_str)
            current = daily.get(FIELD_HEADERS[field_key])
            if normalize_choice(current) and normalize_choice(current) != normalize_choice(value):
                next_menu = None
                return_menu = "menu:main"
                if field_key in {"training", "cardio", "steps"}:
                    return_menu = "sport"
                elif field_key in {"english", "code_mode", "code_topic", "reading"}:
                    return_menu = "study"
                elif field_key in {"rest_time", "rest_type", "sleep_bed", "sleep_hours", "sleep_regime", "productivity"}:
                    return_menu = "leisure"
                elif field_key in {"mood", "energy"}:
                    return_menu = "morale"
                if field_key == "code_mode":
                    next_menu = "code_topic"
                elif field_key == "rest_time":
                    next_menu = "rest_type"
                elif field_key == "sleep_bed":
                    next_menu = "sleep_hours"
                elif field_key == "sleep_hours":
                    next_menu = "sleep_regime"
                await confirm_override(
                    context,
                    query,
                    field_key=field_key,
                    current_value=current,
                    new_value=value,
                    return_menu=return_menu,
                    next_menu=next_menu,
                )
                return
        if field_key == "code_mode":
            sheets.update_daily_fields(date_str, {COLUMN_MAP["code_mode"]: value}, max_rows=cfg.daily_max_rows)
            daily = get_daily_data(context, date_str)
            current_topic = daily.get("Код_тема")
            await show_menu(query, "Код: тема", mark_set_buttons(CODE_TOPIC_OPTIONS, current_topic), back_to="menu:study", cols=2)
            return
        if field_key == "code_topic":
            sheets.update_daily_fields(date_str, {COLUMN_MAP["code_topic"]: value}, max_rows=cfg.daily_max_rows)
            await show_study_menu(query, context, date_str)
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
                await show_study_menu(query, context, date_str)
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

    if expect == "habit_add":
        added = sheets.add_habit(text)
        context.user_data.clear()
        if added:
            await update.message.reply_text("✅ Привычка добавлена.")
        else:
            await update.message.reply_text("ℹ️ Такая привычка уже есть.")
        text_menu, buttons = await build_habits_menu(context, date_str)
        await update.message.reply_text(text_menu, reply_markup=build_keyboard(buttons, cols=1, back=("⬅️ Назад", "menu:main")))
        return

    if expect == "anti_custom":
        reason = text
        sheets.add_session(date_str, time_str(cfg.timezone), "Анти", reason, 0, "")
        context.user_data.clear()
        await update.message.reply_text("✅ Записал.")
        text_menu, buttons = await build_anti_menu(context, date_str)
        await update.message.reply_text(text_menu, reply_markup=build_keyboard(buttons, cols=2, back=("⬅️ Назад", "menu:leisure")))
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
    if ensure_daily_formulas(context, row.row_index):
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
    code_sessions = sheets.get_sessions(date_str, category="Код")
    if code_sessions:
        labels = [s.get("subcategory") for s in code_sessions if s.get("subcategory")]
        preview = ", ".join(labels[:2])
        if len(labels) > 2:
            preview = f"{preview} +{len(labels) - 2}"
        study_parts.append(f"код {preview}")
    reading_value = data.get("Чтение_стр")
    if reading_is_set(reading_value):
        label = "не читал" if normalize_choice(reading_value) in {"0", "0.0"} else f"{reading_value} стр"
        study_parts.append(f"чтение {label}")
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

    anti_sessions = sheets.get_sessions(date_str, category="Анти")
    if anti_sessions:
        reasons = [s.get("subcategory") for s in anti_sessions if s.get("subcategory")]
        preview = ", ".join(reasons[:3])
        if len(reasons) > 3:
            preview = f"{preview} +{len(reasons) - 3}"
        lines.append(f"🧯 Анти‑прокраст.: {preview}")

    if data.get("Вес"):
        lines.append(f"⚖️ Вес: {data.get('Вес')}")
    if data.get("О_чем_жалею"):
        lines.append(f"📝 О чем жалею: {data.get('О_чем_жалею')}")
    if data.get("Отзыв_о_дне"):
        lines.append(f"🗒 Отзыв: {data.get('Отзыв_о_дне')}")
    habits_value = data.get("Привычки")
    habits_list = parse_habits_value(habits_value)
    if habits_list:
        try:
            total_habits = len(sheets.get_habits())
            if total_habits:
                lines.append(f"🧠 Привычки: {len(habits_list)}/{total_habits}")
            else:
                lines.append(f"🧠 Привычки: {', '.join(habits_list)}")
        except Exception:
            lines.append(f"🧠 Привычки: {', '.join(habits_list)}")

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
    if ensure_daily_formulas(context, row.row_index):
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
    portion_rows = sheets.get_values("Portions!A2:D")
    food_items_rows = sheets.get_values("FoodItems!A2:E")
    portions = compute_portions(portion_rows, food_items_rows)
    portion_map: dict[str, dict] = {p["code"]: p for p in portions}

    eaten: dict[str, dict[str, float]] = {}
    eaten_products: set[str] = set()
    for row_item in food_rows:
        if not row_item or len(row_item) < 4:
            continue
        if row_item[0] != date_str:
            continue
        code = str(row_item[2])
        qty = parse_sheet_number(row_item[3])
        grams = parse_sheet_number(row_item[4]) if len(row_item) > 4 else 0.0
        portion = portion_map.get(code)
        label = portion["label"] if portion else code
        if portion:
            eaten_products.add(portion["product"])
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

    target_mid = {
        "kcal": (kcal_min + kcal_max) / 2,
        "protein": (p_min + p_max) / 2,
        "fat": (f_min + f_max) / 2,
        "carb": (c_min + c_max) / 2,
    }
    current_vec = {"kcal": kcal, "protein": protein, "fat": fat, "carb": carbs}
    recommendations = recommend_portions(
        current_vec,
        target_mid,
        portions,
        eaten_products=eaten_products,
        max_items=3,
    )
    if recommendations:
        lines.append("")
        lines.append("🤖 Что лучше добрать сейчас:")
        for item in recommendations:
            m = item["macros"]
            lines.append(
                f"• {item['label']} — +{fmt_num(m['kcal'])} ккал, Б {fmt_num(m['protein'],1)}, Ж {fmt_num(m['fat'],1)}, У {fmt_num(m['carb'],1)}"
            )

    plan = build_plan(current_vec, target_mid, portions, eaten_products=eaten_products, max_steps=4)
    if plan:
        lines.append("")
        lines.append("🍱 Черновик рациона на остаток дня:")
        for item in plan:
            lines.append(f"• {item['label']}")

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
    app.add_error_handler(handle_error)

    LOGGER.info("Bot started")
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    app.run_polling()


if __name__ == "__main__":
    main()
