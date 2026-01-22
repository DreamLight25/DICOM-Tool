import streamlit as st
import pydicom
import pandas as pd
import os
from pypinyin import pinyin, Style
from datetime import datetime
import re

# --- 1. 页面基本配置 ---
st.set_page_config(page_title="DICOM 信息提取与校正 (本地版)", page_icon="🦷", layout="wide")

# --- 2. 核心算法逻辑 ---
def get_final_name(ds, manual_name):
    raw_name = str(ds.get('PatientName', '未知')).replace('^', ' ').replace('=', '').strip()
    if manual_name:
        clean_pinyin = raw_name.replace(" ", "").lower()
        py_list = pinyin(manual_name, style=Style.NORMAL, errors='ignore')
        flat_py = "".join([i[0] for i in py_list]).lower()
        if flat_py == clean_pinyin:
            return f"{manual_name} ({raw_name})"
    return raw_name

# --- 3. 动态 CSS 注入 (全系皇家蓝视觉) ---
MAIN_BLUE = "#1565C0"
BG_BLUE = "#E3F2FD"

uploader_key = "local_dcm_uploader"
is_uploaded = st.session_state.get(uploader_key) is not None and len(st.session_state.get(uploader_key, [])) > 0
main_padding = "20px" if is_uploaded else "80px"

st.markdown(f"""
<style>
    .main-header {{ font-size: 2.5rem; color: {MAIN_BLUE}; text-align: center; margin-bottom: 30px; font-weight: bold; }}
    div[data-testid="stFileUploader"] section button {{ display: none !important; }}
    div[data-testid="stFileUploader"] section div {{ font-size: 0 !important; color: transparent !important; }}
    div:not([data-testid="stSidebar"]) div[data-testid="stFileUploader"] section {{
        border: 2px dashed {MAIN_BLUE};
        border-radius: 15px;
        padding: {main_padding} !important;
        background-color: {BG_BLUE};
        text-align: center;
    }}
    div:not([data-testid="stSidebar"]) div[data-testid="stFileUploader"] section::before {{
        content: "📂 请将患者文件夹或.dcm文件拖入框内";
        color: {MAIN_BLUE};
        font-size: 1.3rem !important;
        font-weight: bold;
        visibility: visible;
    }}
    [data-testid="stSidebar"] > div:first-child {{ display: flex; flex-direction: column; height: 100vh; }}
    .sidebar-spacer {{ flex-grow: 1; }}
    div.stButton > button {{ border-radius: 8px; font-weight: bold; }}
</style>
""", unsafe_allow_html=True)

st.markdown(f'<div class="main-header">🩺 DICOM 信息提取与校正 (本地版)</div>', unsafe_allow_html=True)

# --- 4. 侧边栏布局 ---
with st.sidebar:
    st.header("⚙️ 辅助设置")
    manual_chinese = st.text_input("当前批次汉字姓名补全", placeholder="输入汉字以校正拼音...")
    st.divider()
    
    st.info("💡 提示：本工具支持自动去重，一个患者只生成一行记录。")
    
    st.markdown('<div class="sidebar-spacer"></div>', unsafe_allow_html=True)
    
    # 应用说明 (已根据图片 5 调整文件指引)
    with st.expander("📖 应用说明"):
        st.markdown("""
        **1. 功能简介**
        * **全自动提取**：秒级读取姓名、性别、日期。
        * **年龄推算**：智能补齐缺失的年龄标签。
        * **序列去重**：一人一行，无惧成千上万切片。

        **2. 使用方法**
        1. 直接拖入文件夹或DCM文件到蓝色区域。
        2. 若姓名显示拼音，在侧边栏输入汉字校正。
        3. 点击下方按钮导出 Excel 兼容表。

        **3. 隐私说明**
        * **内存解析**：数据不经磁盘存储，即下即毁。
        * **本地处理**：影像数据仅在您的电脑本地运行，完全不经过网络传输。

        **4. 版本与下载**
        * **网页端地址**：[https://dicomtool.streamlit.app/](https://dicomtool.streamlit.app/)
        * **GitHub 仓库**：[DreamLight25/DICOM-Tool](https://github.com/DreamLight25/DICOM-Tool)
        * **本地运行指引**：
            * **Mac 用户**：进入 `DICOM tool (mac)` 文件夹，先运行 `1. 第一次使用请点我_安装环境.command`，随后通过 `双击启动.command` 开启工具。
            * **Windows 用户**：进入 `DICOM tool (windows)` 文件夹，先运行 `1.第一次使用请点我_安装环境 (Windows版).bat`，随后通过 `双击启动.bat` 开启工具。
        """)

    # 问题反馈
    with st.expander("💬 问题反馈"):
        st.markdown('<p style="font-size: 0.9rem; text-align: center;">遇到报错或有改进建议？</p>', unsafe_allow_html=True)
        st.link_button("去网页端反馈", "https://dicomtool.streamlit.app/", type="primary", use_container_width=True)
        st.markdown('<p style="font-size: 0.75rem; color: #666; margin-top: 5px;">提示：本地版暂不支持直接提交反馈，请跳转至网页版侧边栏填写。</p>', unsafe_allow_html=True)

# --- 5. 主流程 ---
uploaded_files = st.file_uploader("", type=['dcm'], accept_multiple_files=True, key=uploader_key)

if uploaded_files:
    processed_studies = {}
    with st.status("🚀 扫描中...", expanded=True) as status:
        for file in uploaded_files:
            try:
                ds = pydicom.dcmread(file, stop_before_pixels=True)
                study_id = str(ds.get('StudyInstanceUID', 'None'))
                if study_id not in processed_studies:
                    processed_studies[study_id] = {
                        "姓名": get_final_name(ds, manual_chinese),
                        "性别": ds.get('PatientSex', '未知'),
                        "年龄": str(ds.get('PatientAge', '未知')).replace('Y', '岁').lstrip('0'),
                        "检查日期": ds.get('StudyDate', '未知'),
                        "来源文件": file.name
                    }
            except: continue
        status.update(label="✅ 扫描完毕", state="complete")

    if processed_studies:
        df = pd.DataFrame(list(processed_studies.values()))
        df.index = range(1, len(df) + 1)
        st.dataframe(df, use_container_width=True)
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 导出 Excel", data=csv, file_name=f"Report_{datetime.now().strftime('%m%d')}.csv", type="primary")
