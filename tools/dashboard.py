"""
dashboard.py - Classroom & Exam Monitoring Analytics Dashboard
Loads CSV session logs and shows visual analytics.

Usage:
    streamlit run tools/dashboard.py
"""

import os
import sys
import glob

try:
    import streamlit as st
    import pandas as pd
    import matplotlib.pyplot as plt
except ImportError as e:
    print(f"ERROR: Missing dashboard dependency ({e}).")
    print("Please install the required libraries with:")
    print("    pip install streamlit pandas matplotlib")
    sys.exit(1)


def load_session(csv_path):
    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


def get_session_files(log_dir="logs"):
    if not os.path.exists(log_dir):
        return []
    files = sorted(glob.glob(os.path.join(log_dir, "session_*.csv")), reverse=True)
    return files


def plot_class_counts(df):
    counts = df["class_name"].value_counts()
    colors = {
        "attentive": "#2ecc71",
        "hand_raised": "#3498db",
        "inattentive": "#e74c3c",
    }

    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar(counts.index, counts.values,
                  color=[colors.get(c, "#95a5a6") for c in counts.index])

    for bar, val in zip(bars, counts.values):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 5,
                str(val), ha="center", fontweight="bold", fontsize=11)

    ax.set_title("Tổng Số Lần Nhận Diện Theo Phân Lớp", fontsize=14, fontweight="bold")
    ax.set_ylabel("Số lượng phát hiện")
    ax.set_xlabel("Hành vi")
    st.pyplot(fig)


def plot_timeline(df):
    df_copy = df.copy()
    df_copy["minute"] = df_copy["timestamp"].dt.floor("min")

    timeline = df_copy.groupby(["minute", "class_name"]).size().unstack(fill_value=0)
    colors = {
        "attentive": "#2ecc71",
        "hand_raised": "#3498db",
        "inattentive": "#e74c3c",
    }

    fig, ax = plt.subplots(figsize=(10, 4))
    for col in timeline.columns:
        ax.plot(timeline.index, timeline[col], label=col,
                color=colors.get(col, "#95a5a6"), linewidth=2, marker="o", markersize=4)

    ax.set_title("Dòng Thời Gian Phát Hiện Hành Vi (Mỗi Phút)", fontsize=14, fontweight="bold")
    ax.set_xlabel("Thời gian")
    ax.set_ylabel("Số lượng")
    ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    st.pyplot(fig)


def main():
    st.set_page_config(page_title="VisionGuard Analytics", page_icon="📊", layout="wide")
    st.title("📊 VisionGuard AI — Phân Tích Dữ Liệu Hành Vi Phòng Thi")

    session_files = get_session_files()

    if not session_files:
        st.info("Chưa có phiên log nào trong thư mục `logs/`. Hãy chạy `python tools/detect.py` để tạo dữ liệu.")
        return

    selected_file = st.selectbox("Chọn phiên giám sát:", session_files)

    if selected_file:
        df = load_session(selected_file)

        total_detections = len(df)
        attentive_count = len(df[df["class_name"] == "attentive"])
        inattentive_count = len(df[df["class_name"] == "inattentive"])
        hand_count = len(df[df["class_name"] == "hand_raised"])

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Tổng phát hiện", total_detections)
        col2.metric("Tập trung (Attentive)", f"{attentive_count} ({attentive_count/max(1, total_detections)*100:.1f}%)")
        col3.metric("Mất tập trung (Inattentive)", f"{inattentive_count} ({inattentive_count/max(1, total_detections)*100:.1f}%)")
        col4.metric("Giơ tay (Hand Raised)", hand_count)

        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            plot_class_counts(df)
        with c2:
            plot_timeline(df)

        with st.expander("Xem bảng dữ liệu chi tiết"):
            st.dataframe(df)


if __name__ == "__main__":
    main()
