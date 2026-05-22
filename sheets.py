import gspread
from google.oauth2.service_account import Credentials
import streamlit as st
import pandas as pd
from datetime import datetime
import uuid

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
HEADERS = ["id", "タイトル", "内容", "期日", "完了", "作成日時", "優先度", "タグ"]


class SheetsManager:
    def __init__(self):
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=SCOPES
        )
        client = gspread.authorize(creds)
        self.sheet = client.open(st.secrets["spreadsheet_name"]).sheet1
        self._ensure_headers()

    def _ensure_headers(self):
        existing = self.sheet.row_values(1)
        if not existing:
            self.sheet.append_row(HEADERS)
            return
        for col in ["優先度", "タグ"]:
            if col not in existing:
                self.sheet.update_cell(1, len(existing) + 1, col)
                existing.append(col)

    def get_all_tasks(self) -> pd.DataFrame:
        records = self.sheet.get_all_records()
        if not records:
            return pd.DataFrame(columns=HEADERS)
        df = pd.DataFrame(records)
        df["完了"] = df["完了"].map(lambda x: str(x).upper() == "TRUE")
        df["期日"] = pd.to_datetime(df["期日"], errors="coerce")
        if "優先度" not in df.columns:
            df["優先度"] = ""
        if "タグ" not in df.columns:
            df["タグ"] = ""
        return df

    def add_task(self, title: str, content: str, due_date, priority: str = "", tags: str = "") -> None:
        row = [
            str(uuid.uuid4())[:8],
            title,
            content,
            due_date.strftime("%Y-%m-%d") if due_date else "",
            "FALSE",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            priority,
            tags,
        ]
        self.sheet.append_row(row)

    def _find_row(self, task_id: str) -> int:
        ids = self.sheet.col_values(1)
        for i, v in enumerate(ids):
            if v == task_id:
                return i + 1
        return -1

    def update_task(self, task_id: str, title: str, content: str, due_date, priority: str = "", tags: str = "") -> None:
        row = self._find_row(task_id)
        if row > 0:
            self.sheet.update(
                f"B{row}:D{row}",
                [[title, content, due_date.strftime("%Y-%m-%d") if due_date else ""]],
            )
            self.sheet.update(f"G{row}:H{row}", [[priority, tags]])

    def toggle_complete(self, task_id: str, completed: bool) -> None:
        row = self._find_row(task_id)
        if row > 0:
            self.sheet.update_cell(row, 5, "TRUE" if completed else "FALSE")

    def delete_task(self, task_id: str) -> None:
        row = self._find_row(task_id)
        if row > 0:
            self.sheet.delete_rows(row)
