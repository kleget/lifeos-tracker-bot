from __future__ import annotations

from typing import Iterable

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def build_keyboard(
    buttons: Iterable[tuple[str, str]],
    *,
    cols: int = 2,
    back: tuple[str, str] | None = None,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for label, data in buttons:
        row.append(InlineKeyboardButton(label, callback_data=data))
        if len(row) >= cols:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    if back:
        rows.append([InlineKeyboardButton(back[0], callback_data=back[1])])
    return InlineKeyboardMarkup(rows)


MAIN_MENU = [
    ("🏋️ Спорт", "menu:sport"),
    ("📚 Учеба", "menu:study"),
    ("🌤 Досуг", "menu:leisure"),
    ("🙂 Моралька", "menu:morale"),
    ("🧠 Привычки", "menu:habits"),
]

SPORT_MENU = [
    ("Тренировка", "sport:training"),
    ("Отдых", "sport:rest"),
    ("Пропуск", "sport:skip"),
    ("Кардио", "sport:cardio"),
]

TRAINING_OPTIONS = [
    ("Верх", "set:training:Верх"),
    ("Низ", "set:training:Ноги"),
    ("Фулл", "set:training:Фулл"),
]

CARDIO_OPTIONS = [
    ("0", "set:cardio:0"),
    ("10", "set:cardio:10"),
    ("20", "set:cardio:20"),
    ("30", "set:cardio:30"),
    ("40", "set:cardio:40"),
]

STEPS_OPTIONS = [
    ("<5k", "set:steps:<5k"),
    ("5-7k", "set:steps:5-7k"),
    ("7-10k", "set:steps:7-10k"),
    ("10-12k", "set:steps:10-12k"),
    ("12-15k", "set:steps:12-15k"),
    ("15k+", "set:steps:15k+"),
]

STUDY_MENU = [
    ("Английский", "study:english"),
    ("ML", "study:ml"),
    ("Алгосы", "study:algos"),
    ("ВУЗ", "study:uni"),
    ("Чтение", "study:reading"),
]

ENGLISH_OPTIONS = [
    ("15м", "set:english:15"),
    ("30м", "set:english:30"),
    ("45м", "set:english:45"),
    ("1ч", "set:english:60"),
    ("1.5ч", "set:english:90"),
    ("2ч", "set:english:120"),
]

ML_OPTIONS = [
    ("30м", "set:ml:30"),
    ("1ч", "set:ml:60"),
    ("1.5ч", "set:ml:90"),
    ("2ч", "set:ml:120"),
    ("2.5ч", "set:ml:150"),
    ("3ч", "set:ml:180"),
]

ALGOS_OPTIONS = [
    ("30м", "set:algos:30"),
    ("1ч", "set:algos:60"),
    ("1.5ч", "set:algos:90"),
    ("2ч", "set:algos:120"),
    ("2.5ч", "set:algos:150"),
    ("3ч", "set:algos:180"),
]

UNI_OPTIONS = [
    ("30м", "set:uni:30"),
    ("1ч", "set:uni:60"),
    ("1.5ч", "set:uni:90"),
    ("2ч", "set:uni:120"),
    ("2.5ч", "set:uni:150"),
    ("3ч", "set:uni:180"),
]

CODE_MODE_OPTIONS = [
    ("Сам", "code_mode:Сам"),
    ("С помощью", "code_mode:С помощью"),
    ("Вайб код", "code_mode:Вайб код"),
]

CODE_TOPIC_OPTIONS = [
    ("МЛ", "code_topic:МЛ"),
    ("Алгосы", "code_topic:Алгосы"),
    ("ВУЗ", "code_topic:ВУЗ"),
    ("Веб", "code_topic:Веб"),
]

READING_OPTIONS = [("Не читал", "set:reading:0")] + [
    (f"{n} стр", f"set:reading:{n}") for n in range(10, 101, 10)
]

LEISURE_MENU = [
    ("Отдых", "leisure:rest"),
    ("Продуктивность", "leisure:productivity"),
    ("Дневной сон", "leisure:nap"),
    ("🧯 Анти‑прокраст.", "leisure:anti"),
]

NAP_OPTIONS = [
    ("0", "set:nap:0"),
    ("30м", "set:nap:0.5"),
    ("1ч", "set:nap:1"),
    ("1.5ч", "set:nap:1.5"),
    ("2ч", "set:nap:2"),
    ("2.5ч", "set:nap:2.5"),
    ("3ч", "set:nap:3"),
    ("Другое", "leisure:nap_custom"),
]

REST_TIME_OPTIONS = [
    ("0ч", "set:rest_time:0ч"),
    ("1-3ч", "set:rest_time:1-3ч"),
    ("3-6ч", "set:rest_time:3-6ч"),
    ("пол дня", "set:rest_time:пол дня"),
    ("весь день", "set:rest_time:весь день"),
]

REST_TYPE_OPTIONS = [
    ("гулял", "set:rest_type:гулял"),
    ("кафовал", "set:rest_type:кафовал"),
    ("с кентами", "set:rest_type:с кентами"),
    ("в егорлыке", "set:rest_type:в егорлыке"),
]

SLEEP_BEDTIME_OPTIONS = [(str(n), f"set:sleep_bed:{n}") for n in [10, 11, 12, 1, 2, 3, 4, 5, 6]]
SLEEP_HOURS_OPTIONS = [
    ("<6", "set:sleep_hours:<6"),
    ("6-8", "set:sleep_hours:6-8"),
    (">8", "set:sleep_hours:>8"),
]
SLEEP_REGIME_OPTIONS = [
    ("сбит", "set:sleep_regime:сбит"),
    ("не сбит", "set:sleep_regime:не сбит"),
]

PRODUCTIVITY_OPTIONS = [
    ("0%", "set:productivity:0"),
    ("25%", "set:productivity:25"),
    ("50%", "set:productivity:50"),
    ("75%", "set:productivity:75"),
    ("100%", "set:productivity:100"),
]

PROCRASTINATION_OPTIONS = [
    ("Соцсети", "anti:Соцсети"),
    ("YouTube/сериалы", "anti:YouTube/сериалы"),
    ("Игры", "anti:Игры"),
    ("Нет ясной цели", "anti:Нет ясной цели"),
    ("Усталость", "anti:Усталость"),
    ("Тревога/стресс", "anti:Тревога/стресс"),
]

FOOD_MENU = [
    ("Белковое", "food:protein"),
    ("Гарнир", "food:garnish"),
    ("Сладкое", "food:sweet"),
    ("Масла", "food:oils"),
    ("Другое", "food:custom"),
]

FOOD_PROTEIN_OPTIONS = [
    ("Творог 180 г", "food_item:CURD_180"),
    ("Творог 300 г", "food_item:CURD_300"),
    ("Яйца C2", "food_item:EGG_C2_1"),
    ("Яйца C1", "food_item:EGG_C1_1"),
    ("Яйца C0", "food_item:EGG_C0_1"),
    ("Грудка 100 г", "food_item:CHICK_100"),
    ("Грудка 150 г", "food_item:CHICK_150"),
    ("Грудка 200 г", "food_item:CHICK_200"),
    ("Грудка 250 г", "food_item:CHICK_250"),
    ("Грудка 300 г", "food_item:CHICK_300"),
    ("Грудка 350 г", "food_item:CHICK_350"),
]

FOOD_GARNISH_OPTIONS = [
    ("Рис 50 г", "food_item:RICE_50"),
    ("Рис 100 г", "food_item:RICE_100"),
    ("Овсянка 50 г", "food_item:OAT_50"),
    ("Овсянка 100 г", "food_item:OAT_100"),
    ("Картоха 100 г", "food_item:POT_100"),
    ("Кукуруза 50 г", "food_item:CORN_50"),
    ("Гречка 50 г", "food_item:BCKW_50"),
    ("Гречка 100 г", "food_item:BCKW_100"),
]

FOOD_SWEET_OPTIONS = [
    ("Банан 1 шт", "food_item:BANANA_1"),
    ("Зефир 1 шт", "food_item:MARSH_1"),
    ("Сгущенка 20 г", "food_item:COND_20"),
    ("Греческий йогурт 140 г", "food_item:GREEK_140"),
    ("Греческий йогурт 250 г", "food_item:GREEK_250"),
    ("Обезжир. йогурт 260 г", "food_item:FATFREE_260"),
    ("Йогурт чудо 100 г", "food_item:CHUDO_100"),
    ("Йогурт чудо 140 г", "food_item:CHUDO_140"),
    ("Йогурт чудо 260 г", "food_item:CHUDO_260"),
    ("Йогурт чудо 300 г", "food_item:CHUDO_300"),
    ("Булочка венская", "food_item:BUN_1"),
    ("Печенье америк. (1 шт)", "food_item:COOKIE_1"),
]

FOOD_OIL_OPTIONS = [
    ("Оливковое 1 ч.л.", "food_item:OIL_OLIVE_TSP"),
    ("Подсолнечное 1 ч.л.", "food_item:OIL_SUN_TSP"),
]

MORALE_MENU = [
    ("Настроение", "morale:mood"),
    ("Энергия", "morale:energy"),
    ("О чем жалею", "morale:regret"),
    ("Отзыв о дне", "morale:review"),
]

MOOD_OPTIONS = [
    ("Отличное", "set:mood:Отличное"),
    ("Веселый", "set:mood:Веселый"),
    ("Обычное", "set:mood:Обычное"),
    ("Серьезный", "set:mood:Серьезный"),
    ("Раздраженный", "set:mood:Раздраженный"),
    ("Беспокойный", "set:mood:Беспокойный"),
    ("Злой", "set:mood:Злой"),
]

ENERGY_OPTIONS = [
    ("нет", "set:energy:нет"),
    ("мало", "set:energy:мало"),
    ("есть", "set:energy:есть"),
    ("я живчик", "set:energy:я живчик"),
]

HABITS_MENU = [
    ("Добавить привычки", "habits:text"),
]


def quantity_keyboard(portion_code: str) -> InlineKeyboardMarkup:
    buttons = [(str(n), f"food_qty:{portion_code}:{n}") for n in range(1, 11)]
    return build_keyboard(buttons, cols=5, back=("⬅️ Назад", "menu:food"))
