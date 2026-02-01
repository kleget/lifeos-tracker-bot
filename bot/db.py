from __future__ import annotations

import csv
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


@dataclass
class DailyRow:
    values: list[object]


class Database:
    def __init__(self, db_path: str):
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.execute("PRAGMA synchronous = NORMAL")

    def close(self) -> None:
        self._conn.close()

    def init_schema(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.executescript(
                """
                CREATE TABLE IF NOT EXISTS daily (
                    date TEXT PRIMARY KEY,
                    training TEXT,
                    cardio_min INTEGER,
                    steps_category TEXT,
                    steps_count INTEGER,
                    english_min INTEGER,
                    ml_min INTEGER,
                    code_mode TEXT,
                    code_topic TEXT,
                    reading_pages INTEGER,
                    rest_time TEXT,
                    rest_type TEXT,
                    sleep_bed TEXT,
                    sleep_hours TEXT,
                    sleep_regime TEXT,
                    productivity INTEGER,
                    mood TEXT,
                    energy TEXT,
                    weight REAL,
                    regret TEXT,
                    review TEXT,
                    habits TEXT,
                    active_kcal REAL,
                    food_tracked INTEGER,
                    food_kcal REAL,
                    food_protein REAL,
                    food_fat REAL,
                    food_carb REAL,
                    food_source TEXT
                );

                CREATE TABLE IF NOT EXISTS food_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    protein_100 REAL NOT NULL,
                    fat_100 REAL NOT NULL,
                    carb_100 REAL NOT NULL,
                    kcal_100 REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS portions (
                    code TEXT PRIMARY KEY,
                    item_id INTEGER NOT NULL REFERENCES food_items(id) ON DELETE CASCADE,
                    description TEXT,
                    grams REAL NOT NULL
                );

                CREATE TABLE IF NOT EXISTS food_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    time TEXT NOT NULL,
                    portion_code TEXT NOT NULL REFERENCES portions(code) ON DELETE RESTRICT,
                    quantity REAL NOT NULL,
                    comment TEXT
                );

                CREATE TABLE IF NOT EXISTS session_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    time TEXT NOT NULL,
                    category TEXT NOT NULL,
                    subcategory TEXT,
                    minutes INTEGER,
                    comment TEXT
                );

                CREATE TABLE IF NOT EXISTS habits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    active INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS habit_log (
                    date TEXT NOT NULL,
                    habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
                    done INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (date, habit_id)
                );
                """
            )
            self._conn.commit()
            self._ensure_columns(
                "daily",
                {
                    "steps_count": "INTEGER",
                    "ml_min": "INTEGER",
                    "active_kcal": "REAL",
                    "food_tracked": "INTEGER",
                    "food_kcal": "REAL",
                    "food_protein": "REAL",
                    "food_fat": "REAL",
                    "food_carb": "REAL",
                    "food_source": "TEXT",
                },
            )

    def _ensure_columns(self, table: str, columns: dict[str, str]) -> None:
        cur = self._conn.execute(f"PRAGMA table_info({table})")
        existing = {row["name"] for row in cur.fetchall()}
        to_add = [(name, col_type) for name, col_type in columns.items() if name not in existing]
        if not to_add:
            return
        for name, col_type in to_add:
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {col_type}")
        self._conn.commit()

    def seed_from_csv(self, food_items_csv: str, portions_csv: str) -> None:
        food_items_csv_path = Path(food_items_csv)
        portions_csv_path = Path(portions_csv)
        if not food_items_csv_path.exists() or not portions_csv_path.exists():
            return
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT COUNT(*) FROM food_items")
            count = cur.fetchone()[0]
            if count:
                return
            with food_items_csv_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    cur.execute(
                        "INSERT INTO food_items (name, protein_100, fat_100, carb_100, kcal_100) VALUES (?,?,?,?,?)",
                        (
                            row["name"],
                            float(row["protein_100"]),
                            float(row["fat_100"]),
                            float(row["carb_100"]),
                            float(row["kcal_100"]),
                        ),
                    )
            self._conn.commit()

            # build name -> id map
            cur.execute("SELECT id, name FROM food_items")
            item_map = {row["name"]: row["id"] for row in cur.fetchall()}

            with portions_csv_path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    item_id = item_map.get(row["product"])
                    if not item_id:
                        continue
                    cur.execute(
                        "INSERT INTO portions (code, item_id, description, grams) VALUES (?,?,?,?)",
                        (
                            row["code"],
                            item_id,
                            row["description"],
                            float(row["grams"]),
                        ),
                    )
            self._conn.commit()

    def ensure_daily_row(self, date_str: str) -> None:
        with self._lock:
            self._conn.execute("INSERT OR IGNORE INTO daily (date) VALUES (?)", (date_str,))
            self._conn.commit()

    def update_daily_fields(self, date_str: str, fields: dict[str, object]) -> None:
        if not fields:
            return
        self.ensure_daily_row(date_str)
        columns = ", ".join([f"{col}=?" for col in fields.keys()])
        values = list(fields.values()) + [date_str]
        with self._lock:
            self._conn.execute(f"UPDATE daily SET {columns} WHERE date=?", values)
            self._conn.commit()

    def get_daily_row(self, date_str: str) -> Optional[dict]:
        with self._lock:
            cur = self._conn.execute("SELECT * FROM daily WHERE date=?", (date_str,))
            row = cur.fetchone()
            if not row:
                return None
            return dict(row)

    def get_daily_dates(self) -> list[str]:
        with self._lock:
            cur = self._conn.execute("SELECT date FROM daily ORDER BY date")
            return [row["date"] for row in cur.fetchall()]

    def add_food_log(
        self,
        date_str: str,
        time_str: str,
        portion_code: str,
        quantity: int,
        comment: str = "",
    ) -> int:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO food_log (date, time, portion_code, quantity, comment) VALUES (?,?,?,?,?)",
                (date_str, time_str, portion_code, quantity, comment),
            )
            self._conn.commit()
            return cur.lastrowid

    def ensure_food_item(
        self,
        name: str,
        proteins: float,
        fats: float,
        carbs: float,
        kcal: float,
    ) -> int:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT id FROM food_items WHERE lower(name)=lower(?)", (name,))
            row = cur.fetchone()
            if row:
                return row["id"]
            cur.execute(
                "INSERT INTO food_items (name, protein_100, fat_100, carb_100, kcal_100) VALUES (?,?,?,?,?)",
                (name, proteins, fats, carbs, kcal),
            )
            self._conn.commit()
            return cur.lastrowid

    def ensure_portion(
        self,
        code: str,
        product_name: str,
        description: str,
        grams: float,
    ) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute("SELECT code FROM portions WHERE code=?", (code,))
            if cur.fetchone():
                return
            cur.execute("SELECT id FROM food_items WHERE lower(name)=lower(?)", (product_name,))
            row = cur.fetchone()
            if not row:
                raise ValueError(f"Food item not found: {product_name}")
            cur.execute(
                "INSERT INTO portions (code, item_id, description, grams) VALUES (?,?,?,?)",
                (code, row["id"], description, grams),
            )
            self._conn.commit()

    def list_portions(self) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT p.code, p.description, p.grams, fi.name AS product,
                       fi.protein_100, fi.fat_100, fi.carb_100, fi.kcal_100
                FROM portions p
                JOIN food_items fi ON fi.id = p.item_id
                ORDER BY p.code
                """
            )
            rows = cur.fetchall()
        portions = []
        for row in rows:
            grams = row["grams"]
            macros = {
                "kcal": grams / 100 * row["kcal_100"],
                "protein": grams / 100 * row["protein_100"],
                "fat": grams / 100 * row["fat_100"],
                "carb": grams / 100 * row["carb_100"],
            }
            label = f"{row['product']} ({row['description']})" if row["description"] else row["product"]
            portions.append(
                {
                    "code": row["code"],
                    "product": row["product"],
                    "label": label,
                    "grams": grams,
                    "macros": macros,
                }
            )
        return portions

    def get_food_log(self, date_str: str) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT fl.id, fl.date, fl.time, fl.portion_code, fl.quantity, fl.comment,
                       p.grams, p.description, fi.name AS product
                FROM food_log fl
                LEFT JOIN portions p ON p.code = fl.portion_code
                LEFT JOIN food_items fi ON fi.id = p.item_id
                WHERE fl.date = ?
                ORDER BY fl.id
                """,
                (date_str,),
            )
            rows = cur.fetchall()
        result = []
        for row in rows:
            grams = row["grams"] or 0
            total_grams = grams * (row["quantity"] or 0)
            label = row["portion_code"]
            if row["product"]:
                label = (
                    f"{row['product']} ({row['description']})" if row["description"] else row["product"]
                )
            result.append(
                {
                    "id": row["id"],
                    "date": row["date"],
                    "time": row["time"],
                    "code": row["portion_code"],
                    "quantity": row["quantity"],
                    "comment": row["comment"],
                    "product": row["product"],
                    "label": label,
                    "grams": total_grams,
                }
            )
        return result

    def get_daily_macros(self, date_str: str) -> Optional[dict]:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT
                    SUM(fl.quantity * p.grams * fi.kcal_100 / 100.0) AS kcal,
                    SUM(fl.quantity * p.grams * fi.protein_100 / 100.0) AS protein,
                    SUM(fl.quantity * p.grams * fi.fat_100 / 100.0) AS fat,
                    SUM(fl.quantity * p.grams * fi.carb_100 / 100.0) AS carb,
                    COUNT(fl.id) AS cnt
                FROM food_log fl
                JOIN portions p ON p.code = fl.portion_code
                JOIN food_items fi ON fi.id = p.item_id
                WHERE fl.date = ?
                """,
                (date_str,),
            )
            row = cur.fetchone()
        if not row or row["cnt"] == 0:
            return None
        return {
            "kcal": row["kcal"] or 0.0,
            "protein": row["protein"] or 0.0,
            "fat": row["fat"] or 0.0,
            "carb": row["carb"] or 0.0,
        }

    def add_session(
        self,
        date_str: str,
        time_str: str,
        category: str,
        subcategory: str,
        minutes: int = 0,
        comment: str = "",
    ) -> int:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                "INSERT INTO session_log (date, time, category, subcategory, minutes, comment) VALUES (?,?,?,?,?,?)",
                (date_str, time_str, category, subcategory, minutes, comment),
            )
            self._conn.commit()
            return cur.lastrowid

    def get_sessions(self, date_str: str, *, category: str | None = None) -> list[dict]:
        params = [date_str]
        sql = "SELECT * FROM session_log WHERE date=?"
        if category:
            sql += " AND category=?"
            params.append(category)
        sql += " ORDER BY id"
        with self._lock:
            cur = self._conn.execute(sql, params)
            rows = cur.fetchall()
        sessions = []
        for row in rows:
            sessions.append(
                {
                    "row": row["id"],
                    "date": row["date"],
                    "time": row["time"],
                    "category": row["category"],
                    "subcategory": row["subcategory"],
                    "minutes": row["minutes"],
                    "comment": row["comment"],
                }
            )
        return sessions

    def delete_last_session(self, date_str: str, *, category: str | None = None) -> bool:
        sessions = self.get_sessions(date_str, category=category)
        if not sessions:
            return False
        last_id = sessions[-1]["row"]
        with self._lock:
            self._conn.execute("DELETE FROM session_log WHERE id=?", (last_id,))
            self._conn.commit()
        return True

    def clear_sessions(self, date_str: str, *, category: str | None = None) -> int:
        sessions = self.get_sessions(date_str, category=category)
        if not sessions:
            return 0
        ids = [s["row"] for s in sessions]
        with self._lock:
            self._conn.executemany("DELETE FROM session_log WHERE id=?", [(i,) for i in ids])
            self._conn.commit()
        return len(ids)

    def get_habits(self) -> list[str]:
        with self._lock:
            cur = self._conn.execute("SELECT name FROM habits WHERE active=1 ORDER BY id")
            return [row["name"] for row in cur.fetchall()]

    def add_habit(self, name: str) -> bool:
        normalized = name.strip()
        if not normalized:
            return False
        with self._lock:
            cur = self._conn.execute("SELECT id FROM habits WHERE lower(name)=lower(?)", (normalized,))
            if cur.fetchone():
                return False
            self._conn.execute("INSERT INTO habits (name, active) VALUES (?,1)", (normalized,))
            self._conn.commit()
        return True

    def set_habit_done(self, date_str: str, habit_name: str, done: bool) -> None:
        with self._lock:
            cur = self._conn.execute("SELECT id FROM habits WHERE lower(name)=lower(?)", (habit_name,))
            row = cur.fetchone()
            if not row:
                return
            habit_id = row["id"]
            if done:
                self._conn.execute(
                    "INSERT OR REPLACE INTO habit_log (date, habit_id, done) VALUES (?,?,1)",
                    (date_str, habit_id),
                )
            else:
                self._conn.execute(
                    "DELETE FROM habit_log WHERE date=? AND habit_id=?",
                    (date_str, habit_id),
                )
            self._conn.commit()

    def clear_habits_for_date(self, date_str: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM habit_log WHERE date=?", (date_str,))
            self._conn.commit()

    def get_habits_done(self, date_str: str) -> list[str]:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT h.name FROM habit_log hl
                JOIN habits h ON h.id = hl.habit_id
                WHERE hl.date=?
                ORDER BY h.id
                """,
                (date_str,),
            )
            return [row["name"] for row in cur.fetchall()]

    def list_food_items(self) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT name, protein_100, fat_100, carb_100, kcal_100 FROM food_items ORDER BY name"
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    def list_portions_raw(self) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT p.code, fi.name AS product, p.description, p.grams
                FROM portions p
                JOIN food_items fi ON fi.id = p.item_id
                ORDER BY p.code
                """
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    def list_food_log_all(self) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT fl.date, fl.time, fl.portion_code, fl.quantity, fl.comment
                FROM food_log fl
                ORDER BY fl.id
                """
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    def list_session_log_all(self) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT date, time, category, subcategory, minutes, comment
                FROM session_log
                ORDER BY id
                """
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    def list_habits_raw(self) -> list[dict]:
        with self._lock:
            cur = self._conn.execute("SELECT id, name, active FROM habits ORDER BY id")
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    def list_habit_log_all(self) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT hl.date, h.name AS habit, hl.done
                FROM habit_log hl
                JOIN habits h ON h.id = hl.habit_id
                ORDER BY hl.date, h.id
                """
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]
