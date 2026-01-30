from __future__ import annotations

from dataclasses import dataclass
import random
import ssl
import time
from typing import Iterable, Optional

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from httplib2 import HttpLib2Error


@dataclass
class DailyRow:
    row_index: int
    values: list[str]


class SheetsClient:
    def __init__(self, spreadsheet_id: str, service_account_file: str):
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(service_account_file, scopes=scopes)
        self._service = build("sheets", "v4", credentials=creds)
        self._sheet_id = spreadsheet_id

    def get_values(
        self,
        range_a1: str,
        *,
        value_render_option: str = "FORMATTED_VALUE",
        date_time_render_option: str = "FORMATTED_STRING",
    ) -> list[list[str]]:
        result = self._execute_with_retry(
            lambda: self._service.spreadsheets()
            .values()
            .get(
                spreadsheetId=self._sheet_id,
                range=range_a1,
                valueRenderOption=value_render_option,
                dateTimeRenderOption=date_time_render_option,
            )
            .execute()
        )
        return result.get("values", [])

    def update_values(
        self,
        range_a1: str,
        values: list[list[object]],
        *,
        value_input_option: str = "USER_ENTERED",
    ) -> None:
        body = {"values": values}
        self._execute_with_retry(
            lambda: self._service.spreadsheets()
            .values()
            .update(
                spreadsheetId=self._sheet_id,
                range=range_a1,
                valueInputOption=value_input_option,
                body=body,
            )
            .execute()
        )

    def batch_update_values(
        self,
        updates: Iterable[dict],
        *,
        value_input_option: str = "USER_ENTERED",
    ) -> None:
        body = {"valueInputOption": value_input_option, "data": list(updates)}
        self._execute_with_retry(
            lambda: self._service.spreadsheets()
            .values()
            .batchUpdate(spreadsheetId=self._sheet_id, body=body)
            .execute()
        )

    def ensure_sheet(self, title: str, headers: list[str] | None = None) -> None:
        result = self._execute_with_retry(
            lambda: self._service.spreadsheets()
            .get(spreadsheetId=self._sheet_id, fields="sheets.properties.title")
            .execute()
        )
        titles = {sheet["properties"]["title"] for sheet in result.get("sheets", [])}
        if title in titles:
            return
        body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
        self._execute_with_retry(
            lambda: self._service.spreadsheets()
            .batchUpdate(spreadsheetId=self._sheet_id, body=body)
            .execute()
        )
        if headers:
            self.update_values(f"{title}!A1:{chr(64 + len(headers))}1", [headers])

    def _execute_with_retry(self, func, attempts: int = 3):
        last_err: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return func()
            except HttpError as exc:
                status = getattr(exc, "status_code", None)
                if status is None and hasattr(exc, "resp"):
                    status = getattr(exc.resp, "status", None)
                if status in (429, 500, 502, 503, 504):
                    last_err = exc
                else:
                    raise
            except (ssl.SSLError, HttpLib2Error, ConnectionError, OSError) as exc:
                last_err = exc
            if attempt < attempts:
                time.sleep(0.5 * (2 ** (attempt - 1)) + random.uniform(0, 0.2))
        if last_err:
            raise last_err
        return func()

    def find_first_empty_row(
        self,
        sheet: str,
        column: str,
        start_row: int,
        max_rows: int,
    ) -> int:
        range_a1 = f"{sheet}!{column}{start_row}:{column}{start_row + max_rows - 1}"
        values = self.get_values(range_a1)
        for idx in range(max_rows):
            if idx >= len(values):
                return start_row + idx
            row = values[idx]
            if not row or row[0] == "":
                return start_row + idx
        return start_row + max_rows

    def find_daily_row(self, date_str: str, *, max_rows: int = 400) -> Optional[int]:
        values = self.get_values(f"Daily!A2:A{max_rows + 1}")
        for idx, row in enumerate(values, start=2):
            if row and row[0] == date_str:
                return idx
        return None

    def ensure_daily_row(self, date_str: str, *, max_rows: int = 400) -> int:
        row = self.find_daily_row(date_str, max_rows=max_rows)
        if row:
            return row
        row = self.find_first_empty_row("Daily", "A", 2, max_rows)
        self.update_values(f"Daily!A{row}:A{row}", [[date_str]])
        return row

    def update_daily_fields(
        self,
        date_str: str,
        fields: dict[str, object],
        *,
        max_rows: int = 400,
    ) -> int:
        row = self.ensure_daily_row(date_str, max_rows=max_rows)
        updates = [
            {"range": f"Daily!{col}{row}", "values": [[value]]}
            for col, value in fields.items()
        ]
        if updates:
            self.batch_update_values(updates)
        return row

    def get_daily_row(self, date_str: str, *, max_rows: int = 400) -> Optional[DailyRow]:
        row = self.find_daily_row(date_str, max_rows=max_rows)
        if not row:
            return None
        values = self.get_values(f"Daily!A{row}:Z{row}")
        if not values:
            return None
        return DailyRow(row_index=row, values=values[0])

    def add_food_log(
        self,
        date_str: str,
        time_str: str,
        portion_code: str,
        quantity: int,
        comment: str = "",
        *,
        max_rows: int = 2000,
    ) -> int:
        row = self.find_first_empty_row("FoodLog", "A", 2, max_rows)
        self.update_values(
            f"FoodLog!A{row}:D{row}",
            [[date_str, time_str, portion_code, quantity]],
        )
        if comment:
            self.update_values(f"FoodLog!J{row}:J{row}", [[comment]])
        return row

    def ensure_food_item(
        self,
        name: str,
        proteins: float,
        fats: float,
        carbs: float,
        kcal: float,
        *,
        max_rows: int = 500,
    ) -> None:
        values = self.get_values(f"FoodItems!A2:A{max_rows + 1}")
        for row in values:
            if row and row[0].strip().lower() == name.strip().lower():
                return
        row = self.find_first_empty_row("FoodItems", "A", 2, max_rows)
        self.update_values(
            f"FoodItems!A{row}:E{row}",
            [[name, proteins, fats, carbs, kcal]],
        )

    def ensure_portion(
        self,
        code: str,
        product_name: str,
        description: str,
        grams: float,
        *,
        max_rows: int = 500,
    ) -> None:
        values = self.get_values(f"Portions!A2:A{max_rows + 1}")
        for row in values:
            if row and row[0] == code:
                return
        row = self.find_first_empty_row("Portions", "A", 2, max_rows)
        self.update_values(
            f"Portions!A{row}:D{row}",
            [[code, product_name, description, grams]],
        )

    def add_session(
        self,
        date_str: str,
        time_str: str,
        category: str,
        subcategory: str,
        minutes: int = 0,
        comment: str = "",
        *,
        max_rows: int = 2000,
    ) -> int:
        row = self.find_first_empty_row("SessionLog", "A", 2, max_rows)
        self.update_values(
            f"SessionLog!A{row}:F{row}",
            [[date_str, time_str, category, subcategory, minutes, comment]],
        )
        return row

    def get_sessions(
        self,
        date_str: str,
        *,
        category: str | None = None,
        max_rows: int = 2000,
    ) -> list[dict]:
        values = self.get_values(f"SessionLog!A2:F{max_rows + 1}")
        sessions = []
        for idx, row in enumerate(values, start=2):
            if not row or len(row) < 3:
                continue
            if row[0] != date_str:
                continue
            if category and len(row) >= 3 and row[2] != category:
                continue
            sessions.append(
                {
                    "row": idx,
                    "date": row[0] if len(row) > 0 else "",
                    "time": row[1] if len(row) > 1 else "",
                    "category": row[2] if len(row) > 2 else "",
                    "subcategory": row[3] if len(row) > 3 else "",
                    "minutes": row[4] if len(row) > 4 else "",
                    "comment": row[5] if len(row) > 5 else "",
                }
            )
        return sessions

    def delete_last_session(
        self,
        date_str: str,
        *,
        category: str | None = None,
        max_rows: int = 2000,
    ) -> bool:
        sessions = self.get_sessions(date_str, category=category, max_rows=max_rows)
        if not sessions:
            return False
        last = sessions[-1]
        row = last["row"]
        self.update_values(f"SessionLog!A{row}:F{row}", [["", "", "", "", "", ""]])
        return True

    def clear_sessions(
        self,
        date_str: str,
        *,
        category: str | None = None,
        max_rows: int = 2000,
    ) -> int:
        sessions = self.get_sessions(date_str, category=category, max_rows=max_rows)
        if not sessions:
            return 0
        updates = []
        for item in sessions:
            row = item["row"]
            updates.append({"range": f"SessionLog!A{row}:F{row}", "values": [["", "", "", "", "", ""]]})
        self.batch_update_values(updates)
        return len(sessions)

    def ensure_habits_sheet(self) -> None:
        self.ensure_sheet("Habits", headers=["Привычка", "Активна"])

    def get_habits(self, *, max_rows: int = 500) -> list[str]:
        self.ensure_habits_sheet()
        values = self.get_values(f"Habits!A2:A{max_rows + 1}")
        habits = []
        for row in values:
            if row and row[0]:
                habits.append(str(row[0]).strip())
        return habits

    def add_habit(self, name: str, *, max_rows: int = 500) -> bool:
        self.ensure_habits_sheet()
        habits = self.get_habits(max_rows=max_rows)
        normalized = name.strip().lower()
        for existing in habits:
            if existing.strip().lower() == normalized:
                return False
        row = self.find_first_empty_row("Habits", "A", 2, max_rows)
        self.update_values(f"Habits!A{row}:B{row}", [[name.strip(), "TRUE"]])
        return True
