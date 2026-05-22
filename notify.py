"""
毎朝 GitHub Actions から実行される LINE 通知スクリプト。
環境変数:
  GCP_SERVICE_ACCOUNT_JSON  - サービスアカウントの JSON 文字列
  SPREADSHEET_NAME          - スプレッドシート名
  LINE_CHANNEL_ACCESS_TOKEN - LINE チャネルアクセストークン
  LINE_USER_ID              - 通知先の LINE ユーザー ID
"""

import os
import json
import requests
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import date, timedelta

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
PRIORITY_ICON = {"高": "🔴", "中": "🟡", "低": "🟢"}


def get_tasks(service_account_info: dict, spreadsheet_name: str) -> pd.DataFrame:
    creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
    client = gspread.authorize(creds)
    sheet = client.open(spreadsheet_name).sheet1
    records = sheet.get_all_records()
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    df["完了"] = df["完了"].map(lambda x: str(x).upper() == "TRUE")
    df["期日"] = pd.to_datetime(df["期日"], errors="coerce")
    if "優先度" not in df.columns:
        df["優先度"] = ""
    if "タグ" not in df.columns:
        df["タグ"] = ""
    return df


def build_message(df: pd.DataFrame, today: date, days_before: int = 3) -> str:
    upcoming = df[
        ~df["完了"]
        & df["期日"].notna()
        & (df["期日"].dt.date >= today)
        & (df["期日"].dt.date <= today + timedelta(days=days_before))
    ].sort_values("期日")

    overdue = df[
        ~df["完了"]
        & df["期日"].notna()
        & (df["期日"].dt.date < today)
    ]

    lines = ["📋 タスクリマインダー\n"]

    if not upcoming.empty:
        lines.append(f"⏰ 期日{days_before}日以内（{len(upcoming)}件）")
        for _, t in upcoming.iterrows():
            d = t["期日"].date()
            diff = (d - today).days
            due_label = "今日" if diff == 0 else f"あと{diff}日"
            icon = PRIORITY_ICON.get(str(t.get("優先度", "")), "・")
            lines.append(f"{icon} {t['タイトル']}（{d.strftime('%m/%d')} {due_label}）")

    if not overdue.empty:
        lines.append(f"\n🚨 期限切れ（{len(overdue)}件）")
        for _, t in overdue.iterrows():
            d = t["期日"].date()
            diff = (today - d).days
            lines.append(f"  ・{t['タイトル']}（{diff}日超過）")

    if upcoming.empty and overdue.empty:
        return ""

    return "\n".join(lines)


def send_line_notification(token: str, user_id: str, message: str) -> bool:
    resp = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"to": user_id, "messages": [{"type": "text", "text": message}]},
        timeout=10,
    )
    return resp.status_code == 200


def run(service_account_info: dict, spreadsheet_name: str, line_token: str, line_user_id: str):
    today = date.today()
    df = get_tasks(service_account_info, spreadsheet_name)

    if df.empty:
        print("タスクがありません")
        return

    message = build_message(df, today)
    if not message:
        print("通知対象のタスクがありません")
        return

    success = send_line_notification(line_token, line_user_id, message)
    if success:
        print("LINE通知を送信しました")
    else:
        print("LINE通知の送信に失敗しました")
        raise RuntimeError("LINE API returned non-200 status")


if __name__ == "__main__":
    info = json.loads(os.environ["GCP_SERVICE_ACCOUNT_JSON"])
    run(
        info,
        os.environ["SPREADSHEET_NAME"],
        os.environ["LINE_CHANNEL_ACCESS_TOKEN"],
        os.environ["LINE_USER_ID"],
    )
