import streamlit as st
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

# ページ設定（SNS映えを意識してワイドレイアウトに）
st.set_page_config(page_title="ゴルフ練習記録", page_icon="⛳", layout="wide")

# スプレッドシートのシート名
WORKSHEET_NAME = "Sheet1"

# 各項目の定義（ラベル名と単位）
MULTI_FIELDS = {
    "Putter_1Y": ("パター 1ヤード", "球"),
    "Putter_2Y": ("パター 2ヤード", "球"),
    "Putter_3Y": ("パター 3ヤード", "球"),
    "Approach_5Y": ("ウレタンボールアプローチ 5ヤード", "球"),
    "Wall_Drill": ("壁ケツドリル", "回"),
    "Swing_Stick": ("素振り棒", "回"),
}

SINGLE_FIELDS = {
    "Indoor_Golf": ("インドアゴルフ", "h"),
    "Driving_Range": ("打ちっぱなし", "h"),
    "Round_Half": ("ラウンド ハーフ", "回"),
    "Round_Full": ("ラウンド フル", "回"),
}

def parse_multi_entry(entry: str):
    """ '20, 30 50' のような入力をパースして、カンマ区切り文字列と合計値を返す """
    if not entry.strip():
        return "", 0
    # カンマをスペースに置換して分割
    parts = entry.replace(',', ' ').split()
    total = 0
    valid_parts = []
    for p in parts:
        try:
            val = int(p)
            total += val
            valid_parts.append(str(val))
        except ValueError:
            pass
    return ", ".join(valid_parts), total

def create_empty_df():
    cols = ['Date']
    for k in MULTI_FIELDS.keys():
        cols.extend([f"{k}_sets", f"{k}_total"])
    for k in SINGLE_FIELDS.keys():
        cols.append(k)
    return pd.DataFrame(columns=cols)

def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        df = conn.read(worksheet=WORKSHEET_NAME)
        # 空のシートやNaNだけのシートの場合は空のDataFrameを返す
        if df is None or df.empty or df.dropna(how='all').empty:
            return create_empty_df()
        return df
    except Exception as e:
        # シートが存在しない、またはまだデータがない場合は空のDataFrameを作成
        return create_empty_df()

def save_data(new_row_df):
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = load_data()
    # 既存のデータと新しいデータを結合
    if not df.empty and not df.dropna(how='all').empty:
        updated_df = pd.concat([df, new_row_df], ignore_index=True)
    else:
        updated_df = new_row_df
    
    # スプレッドシートを更新（上書き）
    conn.update(worksheet=WORKSHEET_NAME, data=updated_df)

def main():
    st.title("⛳ ゴルフ練習記録ダッシュボード")
    
    # --- サイドバー (入力フォーム) ---
    st.sidebar.header("📝 記録入力")
    
    record_date = st.sidebar.date_input("日付", datetime.date.today())
    
    st.sidebar.markdown("### 複数セット記録")
    st.sidebar.caption("例: 「20, 30, 50」または「20 30 50」")
    
    multi_inputs = {}
    for k, (name, unit) in MULTI_FIELDS.items():
        multi_inputs[k] = st.sidebar.text_input(f"{name}（{unit}）", value="")
        
    st.sidebar.markdown("### 単一数値記録")
    single_inputs = {}
    for k, (name, unit) in SINGLE_FIELDS.items():
        if unit == "h":
            single_inputs[k] = st.sidebar.number_input(f"{name}（{unit}）", min_value=0.0, value=0.0, step=0.5, format="%.1f")
        else:
            single_inputs[k] = st.sidebar.number_input(f"{name}（{unit}）", min_value=0, value=0, step=1)
            
    if st.sidebar.button("記録する", use_container_width=True, type="primary"):
        row_data = {'Date': record_date.strftime("%Y-%m-%d")}
        
        has_input = False
        for k in MULTI_FIELDS.keys():
            sets_str, total_val = parse_multi_entry(multi_inputs[k])
            row_data[f"{k}_sets"] = sets_str
            row_data[f"{k}_total"] = total_val
            if total_val > 0: has_input = True
            
        for k in SINGLE_FIELDS.keys():
            row_data[k] = single_inputs[k]
            if single_inputs[k] > 0: has_input = True
            
        if has_input:
            new_df = pd.DataFrame([row_data])
            save_data(new_df)
            st.sidebar.success("✅ 記録を保存しました！")
            st.rerun()
        else:
            st.sidebar.warning("⚠️ 記録する値がありません。")

    st.sidebar.divider()
    with st.sidebar.expander("⚙️ 管理メニュー（記録の取り消し）"):
        st.caption("※間違えて記録してしまった場合、直前の1件を削除します。")
        if st.button("直前の記録を取り消す", use_container_width=True):
            df_current = load_data()
            if not df_current.empty and not df_current.dropna(how='all').empty:
                df_current = df_current.iloc[:-1]
                if df_current.empty:
                    df_current = create_empty_df()
                conn = st.connection("gsheets", type=GSheetsConnection)
                conn.update(worksheet=WORKSHEET_NAME, data=df_current)
                st.rerun()
            else:
                st.warning("⚠️ 取り消す記録がありません。")

    # --- メイン画面 (ダッシュボード) ---
    df = load_data()
    
    st.markdown("## 🎯 本日の記録")
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    
    if not df.empty:
        today_df = df[df['Date'] == today_str]
    else:
        today_df = pd.DataFrame()
        
    if not today_df.empty:
        st.markdown("#### セット項目")
        cols = st.columns(3)
        col_idx = 0
        for k, (name, unit) in MULTI_FIELDS.items():
            total = today_df[f"{k}_total"].sum()
            if total > 0:
                # 本日複数回送信した場合の対応
                sets_list = [str(s) for s in today_df[f"{k}_sets"].dropna() if str(s).strip()]
                sets_display = " / ".join(sets_list)
                with cols[col_idx % 3]:
                    st.metric(label=name, value=f"{total} {unit}", delta=f"内訳: [{sets_display}]", delta_color="off")
                col_idx += 1
                
        st.markdown("#### その他")
        cols2 = st.columns(4)
        col_idx2 = 0
        for k, (name, unit) in SINGLE_FIELDS.items():
            total = today_df[k].sum()
            if total > 0:
                with cols2[col_idx2 % 4]:
                    if unit == "h":
                        st.metric(label=name, value=f"{total:.1f} {unit}")
                    else:
                        st.metric(label=name, value=f"{total} {unit}")
                col_idx2 += 1
                
        if col_idx == 0 and col_idx2 == 0:
            st.info("本日の記録はありますが、全て0です。")
    else:
        st.info("本日の記録はまだありません。左のメニューから入力してください。")
        
    st.divider()
    
    st.markdown("## 🏆 これまでの累計")
    if not df.empty:
        st.markdown("#### セット項目")
        c_cols = st.columns(3)
        c_idx = 0
        for k, (name, unit) in MULTI_FIELDS.items():
            cum_total = df[f"{k}_total"].sum()
            if cum_total > 0:
                with c_cols[c_idx % 3]:
                    st.metric(label=name, value=f"{cum_total} {unit}")
                c_idx += 1
                
        st.markdown("#### その他")
        c_cols2 = st.columns(4)
        c_idx2 = 0
        for k, (name, unit) in SINGLE_FIELDS.items():
            cum_total = df[k].sum()
            if cum_total > 0:
                with c_cols2[c_idx2 % 4]:
                    if unit == "h":
                        st.metric(label=name, value=f"{cum_total:.1f} {unit}")
                    else:
                        st.metric(label=name, value=f"{cum_total} {unit}")
                c_idx2 += 1
                
        if c_idx == 0 and c_idx2 == 0:
            st.info("累計データがありません。")
            
    else:
        st.info("まだデータがありません。")

if __name__ == "__main__":
    main()
