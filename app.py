import streamlit as st
import pandas as pd
from datetime import date, timedelta
import calendar
import requests

from sheets import SheetsManager

# ── ページ設定 ────────────────────────────────────────────────
st.set_page_config(page_title="TODOリスト", page_icon="📝", layout="wide")

# ── パスワード認証 ────────────────────────────────────────────
def check_password():
    if st.session_state.get("authenticated"):
        return True
    st.title("🔒 TODOリスト")
    pw = st.text_input("パスワードを入力してください", type="password")
    if st.button("ログイン", type="primary"):
        if pw == st.secrets.get("app_password", ""):
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("パスワードが違います")
    return False

if not check_password():
    st.stop()

st.markdown("""
<style>
div[data-testid="stHorizontalBlock"] > div { padding: 1px !important; }
div[data-testid="stHorizontalBlock"] button {
    font-size: 13px !important;
    padding: 6px 2px !important;
    min-height: 48px !important;
    line-height: 1.4;
}
.task-card {
    border-radius: 8px;
    padding: 12px 16px;
    margin-bottom: 10px;
    background: #fafafa;
}
.task-overdue  { border-left: 5px solid #e74c3c; background: #fff5f5; }
.task-today    { border-left: 5px solid #e74c3c; background: #fff5f5; }
.task-soon     { border-left: 5px solid #f39c12; background: #fffdf0; }
.task-normal   { border-left: 5px solid #27ae60; background: #f0fff4; }
.task-done     { border-left: 5px solid #bdc3c7; background: #f8f9fa; opacity: 0.65; }
.task-nodate   { border-left: 5px solid #3498db; background: #f0f8ff; }
.task-title    { font-size: 15px; font-weight: 600; margin-bottom: 4px; }
.task-content  { color: #555; font-size: 13px; margin-bottom: 6px; white-space: pre-wrap; }
.task-badge    { font-size: 12px; color: #666; }
.tag-chip {
    display: inline-block;
    background: #e8f0fe;
    border-radius: 4px;
    padding: 1px 7px;
    font-size: 11px;
    margin-right: 4px;
    color: #3d5a99;
}
</style>
""", unsafe_allow_html=True)

PRIORITY_ICON = {"高": "🔴", "中": "🟡", "低": "🟢"}


# ── セッション初期化 ──────────────────────────────────────────
def _init():
    today = date.today()
    defaults = {
        "cal_year": today.year,
        "cal_month": today.month,
        "selected_date": today,
        "show_form": False,
        "editing_id": None,
        "confirm_delete": None,
        "tasks": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init()


# ── Sheets 接続・タスク読み込み ──────────────────────────────
@st.cache_resource
def get_sm():
    return SheetsManager()


def refresh():
    sm = get_sm()
    st.session_state.tasks = sm.get_all_tasks()


if st.session_state.tasks is None:
    refresh()

df: pd.DataFrame = st.session_state.tasks


# ── カレンダー描画 ────────────────────────────────────────────
def _date_status(df: pd.DataFrame, today: date) -> dict:
    status_map = {}
    priority = {"overdue": 5, "today": 4, "soon": 3, "normal": 2, "done": 1}
    if df.empty:
        return status_map
    for _, t in df.iterrows():
        if not pd.notna(t.get("期日")):
            continue
        d = t["期日"].date()
        done = bool(t["完了"])
        if done:
            s = "done"
        else:
            diff = (d - today).days
            if diff < 0:
                s = "overdue"
            elif diff == 0:
                s = "today"
            elif diff <= 3:
                s = "soon"
            else:
                s = "normal"
        if priority.get(s, 0) > priority.get(status_map.get(d), 0):
            status_map[d] = s
    return status_map


DOT = {"overdue": "🔴", "today": "🔴", "soon": "🟡", "normal": "🟢", "done": "⚪"}


def render_calendar(df: pd.DataFrame):
    today = date.today()
    year = st.session_state.cal_year
    month = st.session_state.cal_month
    status_map = _date_status(df, today)

    nav_l, nav_c, nav_r = st.columns([1, 3, 1])
    with nav_l:
        if st.button("◀ 前月", use_container_width=True):
            if month == 1:
                st.session_state.cal_year -= 1
                st.session_state.cal_month = 12
            else:
                st.session_state.cal_month -= 1
            st.rerun()
    with nav_c:
        st.markdown(
            f"<h3 style='text-align:center;margin:0'>{year}年{month}月</h3>",
            unsafe_allow_html=True,
        )
    with nav_r:
        if st.button("次月 ▶", use_container_width=True):
            if month == 12:
                st.session_state.cal_year += 1
                st.session_state.cal_month = 1
            else:
                st.session_state.cal_month += 1
            st.rerun()

    st.write("")

    header_cols = st.columns(7)
    for i, h in enumerate(["月", "火", "水", "木", "金", "土", "日"]):
        color = "#e74c3c" if i == 6 else ("#3498db" if i == 5 else "#444")
        header_cols[i].markdown(
            f"<p style='text-align:center;font-weight:bold;color:{color};margin:4px 0'>{h}</p>",
            unsafe_allow_html=True,
        )

    for week in calendar.monthcalendar(year, month):
        cols = st.columns(7)
        for i, day in enumerate(week):
            with cols[i]:
                if day == 0:
                    st.write(" ")
                    continue
                d = date(year, month, day)
                dot = DOT.get(status_map.get(d), "")
                is_today = d == today
                is_sel = d == st.session_state.selected_date
                label = f"**{day}**\n{dot}" if is_today else f"{day}\n{dot}"
                btn_type = "primary" if is_sel else "secondary"
                if st.button(
                    label,
                    key=f"cal_{year}_{month}_{day:02d}",
                    use_container_width=True,
                    type=btn_type,
                ):
                    st.session_state.selected_date = d
                    st.session_state.editing_id = None
                    st.session_state.show_form = False
                    st.rerun()

    st.markdown(
        "<div style='font-size:12px;color:#888;margin-top:6px'>"
        "🔴 期限切れ/当日 &nbsp; 🟡 3日以内 &nbsp; 🟢 余裕あり &nbsp; ⚪ 完了済み</div>",
        unsafe_allow_html=True,
    )


# ── タスクカード ──────────────────────────────────────────────
def _card_class(task, today: date) -> str:
    if task["完了"]:
        return "task-done"
    if not pd.notna(task.get("期日")):
        return "task-nodate"
    diff = (task["期日"].date() - today).days
    if diff < 0:
        return "task-overdue"
    if diff == 0:
        return "task-today"
    if diff <= 3:
        return "task-soon"
    return "task-normal"


def _badge(task, today: date) -> str:
    if not pd.notna(task.get("期日")):
        return "📅 期日なし"
    d = task["期日"].date()
    date_str = d.strftime("%Y/%m/%d")
    if task["完了"]:
        return f"📅 {date_str} ✅ 完了"
    diff = (d - today).days
    if diff < 0:
        return f"📅 {date_str} 🔴 {-diff}日超過"
    if diff == 0:
        return f"📅 {date_str} 🔴 今日まで"
    if diff <= 3:
        return f"📅 {date_str} 🟡 あと{diff}日"
    return f"📅 {date_str} 🟢 あと{diff}日"


def _priority_html(priority: str) -> str:
    icon = PRIORITY_ICON.get(priority, "")
    if not icon:
        return ""
    return f'<span style="font-size:12px;margin-right:8px">{icon} {priority}優先</span>'


def _tags_html(tags_str: str) -> str:
    tags = [t.strip() for t in str(tags_str).split(",") if t.strip()]
    if not tags:
        return ""
    chips = "".join(f'<span class="tag-chip">#{t}</span>' for t in tags)
    return f'<div style="margin-top:4px">{chips}</div>'


def render_task_card(task, sm: SheetsManager):
    today = date.today()
    tid = task["id"]
    completed = bool(task["完了"])
    card_cls = _card_class(task, today)
    badge = _badge(task, today)
    content_preview = str(task["内容"])[:100] + ("…" if len(str(task["内容"])) > 100 else "")
    title_style = "text-decoration:line-through;color:#999" if completed else ""
    priority_html = _priority_html(str(task.get("優先度", "")))
    tags_html = _tags_html(str(task.get("タグ", "")))

    if st.session_state.confirm_delete == tid:
        st.warning(f"「{task['タイトル']}」を削除しますか？")
        c1, c2 = st.columns(2)
        if c1.button("はい、削除する", key=f"del_ok_{tid}", type="primary", use_container_width=True):
            sm.delete_task(tid)
            st.session_state.confirm_delete = None
            refresh()
            st.rerun()
        if c2.button("キャンセル", key=f"del_cancel_{tid}", use_container_width=True):
            st.session_state.confirm_delete = None
            st.rerun()
        return

    col_chk, col_body, col_actions = st.columns([0.5, 7, 2.5])

    with col_chk:
        new_val = st.checkbox("", value=completed, key=f"chk_{tid}")
        if new_val != completed:
            sm.toggle_complete(tid, new_val)
            refresh()
            st.rerun()

    with col_body:
        st.markdown(f"""
        <div class="task-card {card_cls}">
          <div class="task-title" style="{title_style}">{task['タイトル']}</div>
          <div class="task-content">{content_preview}</div>
          <div class="task-badge">{priority_html}{badge}</div>
          {tags_html}
        </div>
        """, unsafe_allow_html=True)

    with col_actions:
        st.write("")
        if st.button("✏️ 編集", key=f"edit_{tid}", use_container_width=True):
            st.session_state.editing_id = tid
            st.session_state.show_form = True
            st.rerun()
        if st.button("🗑️ 削除", key=f"del_{tid}", use_container_width=True):
            st.session_state.confirm_delete = tid
            st.rerun()


# ── LINE通知 ─────────────────────────────────────────────────
def _build_line_message(tasks_df: pd.DataFrame, today: date) -> str:
    upcoming = tasks_df[
        ~tasks_df["完了"]
        & tasks_df["期日"].notna()
        & (tasks_df["期日"].dt.date >= today)
        & (tasks_df["期日"].dt.date <= today + timedelta(days=3))
    ].sort_values("期日")

    overdue = tasks_df[
        ~tasks_df["完了"]
        & tasks_df["期日"].notna()
        & (tasks_df["期日"].dt.date < today)
    ]

    lines = ["📋 タスクリマインダー\n"]

    if not upcoming.empty:
        lines.append(f"⏰ 期日3日以内（{len(upcoming)}件）")
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

    return "\n".join(lines)


def _send_line(token: str, user_id: str, message: str) -> bool:
    resp = requests.post(
        "https://api.line.me/v2/bot/message/push",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"to": user_id, "messages": [{"type": "text", "text": message}]},
        timeout=10,
    )
    return resp.status_code == 200


# ── サイドバー ────────────────────────────────────────────────
def render_sidebar(df: pd.DataFrame, sm: SheetsManager):
    with st.sidebar:
        st.title("📝 TODOリスト")

        total = len(df)
        done = int(df["完了"].sum()) if not df.empty else 0
        today = date.today()
        overdue = 0
        if not df.empty:
            mask = ~df["完了"] & df["期日"].notna() & (df["期日"].dt.date < today)
            overdue = int(mask.sum())
        st.markdown(f"""
        <div style='background:#f0f2f6;border-radius:8px;padding:12px;margin-bottom:12px'>
        📊 全タスク: <b>{total}</b> &nbsp;|&nbsp; ✅ 完了: <b>{done}</b><br>
        {"🔴 期限切れ: <b>" + str(overdue) + "件</b>" if overdue else ""}
        </div>
        """, unsafe_allow_html=True)

        if st.button("＋ 新しいタスクを追加", use_container_width=True, type="primary"):
            st.session_state.show_form = True
            st.session_state.editing_id = None

        if st.session_state.show_form:
            eid = st.session_state.editing_id
            is_edit = eid is not None
            existing = {}
            if is_edit and not df.empty:
                rows = df[df["id"] == eid]
                if not rows.empty:
                    existing = rows.iloc[0].to_dict()

            st.divider()
            st.subheader("✏️ 編集" if is_edit else "＋ タスク追加")

            with st.form("task_form", clear_on_submit=True):
                title = st.text_input(
                    "タイトル *",
                    value=existing.get("タイトル", ""),
                    placeholder="タスクのタイトル",
                )
                content = st.text_area(
                    "内容",
                    value=existing.get("内容", ""),
                    placeholder="詳細を入力（任意）",
                    height=100,
                )
                default_due = None
                if existing.get("期日") and pd.notna(existing["期日"]):
                    default_due = existing["期日"].date()
                due_date = st.date_input("期日", value=default_due, format="YYYY/MM/DD")

                priority = st.selectbox(
                    "優先度",
                    ["", "高", "中", "低"],
                    index=["", "高", "中", "低"].index(existing.get("優先度", "") or ""),
                    format_func=lambda x: {"": "なし", "高": "🔴 高", "中": "🟡 中", "低": "🟢 低"}.get(x, x),
                )
                tags = st.text_input(
                    "タグ",
                    value=existing.get("タグ", "") or "",
                    placeholder="仕事, 勉強, 生活（カンマ区切り）",
                )

                submitted = st.form_submit_button(
                    "更新する" if is_edit else "追加する",
                    use_container_width=True,
                    type="primary",
                )
                if submitted:
                    if not title.strip():
                        st.error("タイトルは必須です")
                    else:
                        if is_edit:
                            sm.update_task(eid, title.strip(), content.strip(), due_date, priority, tags.strip())
                        else:
                            sm.add_task(title.strip(), content.strip(), due_date, priority, tags.strip())
                        st.session_state.show_form = False
                        st.session_state.editing_id = None
                        refresh()
                        st.rerun()

            if st.button("キャンセル", use_container_width=True):
                st.session_state.show_form = False
                st.session_state.editing_id = None
                st.rerun()

        st.divider()
        st.session_state.view_mode = st.radio(
            "表示モード",
            ["📅 カレンダー", "📋 全タスク一覧"],
            index=0 if st.session_state.get("view_mode", "📅 カレンダー") == "📅 カレンダー" else 1,
        )

        # ── LINE通知テスト
        line_token = st.secrets.get("line_channel_access_token", "")
        line_user_id = st.secrets.get("line_user_id", "")
        if line_token and line_user_id:
            st.divider()
            if st.button("📱 LINE通知テスト", use_container_width=True):
                msg = _build_line_message(df, date.today())
                if _send_line(line_token, line_user_id, msg):
                    st.success("通知を送信しました")
                else:
                    st.error("送信に失敗しました。トークンを確認してください")


# ── メインコンテンツ ──────────────────────────────────────────
def main():
    try:
        sm = get_sm()
    except Exception as e:
        st.error("Google Sheetsへの接続に失敗しました。`.streamlit/secrets.toml` の設定を確認してください。")
        st.exception(e)
        return

    render_sidebar(df, sm)

    view = st.session_state.get("view_mode", "📅 カレンダー")

    if view == "📅 カレンダー":
        col_cal, col_tasks = st.columns([1, 1])

        with col_cal:
            st.subheader("カレンダー")
            render_calendar(df)
            if st.button("📍 今月に戻る", use_container_width=True):
                today = date.today()
                st.session_state.cal_year = today.year
                st.session_state.cal_month = today.month
                st.session_state.selected_date = today
                st.rerun()

        with col_tasks:
            sel = st.session_state.selected_date
            st.subheader(f"{sel.strftime('%Y年%-m月%-d日')} のタスク")

            day_tasks = df[
                df["期日"].notna() & (df["期日"].dt.date == sel)
            ] if not df.empty else pd.DataFrame()

            if day_tasks.empty:
                st.info("この日のタスクはありません。サイドバーから追加できます。")
            else:
                for _, task in day_tasks.iterrows():
                    render_task_card(task, sm)

    else:
        st.subheader("📋 全タスク一覧")

        # タグ一覧を収集
        all_tags = set()
        if not df.empty and "タグ" in df.columns:
            for tags_str in df["タグ"].dropna():
                for tag in str(tags_str).split(","):
                    tag = tag.strip()
                    if tag:
                        all_tags.add(tag)
        all_tags = sorted(all_tags)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            filter_opt = st.selectbox("状態", ["全て", "未完了のみ", "完了のみ", "期限切れ"])
        with col2:
            priority_filter = st.selectbox(
                "優先度",
                ["全て", "高", "中", "低"],
                format_func=lambda x: {"全て": "全て", "高": "🔴 高", "中": "🟡 中", "低": "🟢 低"}.get(x, x),
            )
        with col3:
            tag_filter = st.selectbox("タグ", ["全て"] + all_tags)
        with col4:
            sort_opt = st.selectbox("並び順", ["期日が近い順", "期日が遠い順", "作成日が新しい順"])

        filtered = df.copy() if not df.empty else df
        today = date.today()

        if filter_opt == "未完了のみ":
            filtered = filtered[~filtered["完了"]]
        elif filter_opt == "完了のみ":
            filtered = filtered[filtered["完了"]]
        elif filter_opt == "期限切れ":
            filtered = filtered[~filtered["完了"] & filtered["期日"].notna() & (filtered["期日"].dt.date < today)]

        if priority_filter != "全て":
            filtered = filtered[filtered["優先度"] == priority_filter]

        if tag_filter != "全て":
            filtered = filtered[filtered["タグ"].apply(
                lambda x: tag_filter in [t.strip() for t in str(x).split(",") if t.strip()]
            )]

        if not filtered.empty:
            if sort_opt == "期日が近い順":
                filtered = filtered.sort_values("期日", ascending=True, na_position="last")
            elif sort_opt == "期日が遠い順":
                filtered = filtered.sort_values("期日", ascending=False, na_position="last")
            elif sort_opt == "作成日が新しい順":
                filtered = filtered.sort_values("作成日時", ascending=False)

            for _, task in filtered.iterrows():
                render_task_card(task, sm)
        else:
            st.info("該当するタスクがありません。")


main()
