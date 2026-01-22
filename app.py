import streamlit as st
import pydicom
import pandas as pd
import re
import os
from pypinyin import pinyin, Style
from datetime import datetime

# --- 1. 页面基本配置 ---
st.set_page_config(page_title="DICOM 信息提取与校正", page_icon="🦷", layout="wide")

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

# --- 3. 动态 CSS 注入 (重点：强制文字替换与色彩同步) ---
MAIN_BLUE = "#1565C0"
BG_BLUE = "#E3F2FD"

# 动态计算主框高度
uploader_key = "main_dcm_uploader"
is_uploaded = st.session_state.get(uploader_key) is not None and len(st.session_state.get(uploader_key, [])) > 0
main_padding = "20px" if is_uploaded else "80px"

st.markdown(f"""
<style>
    /* 标题颜色 */
    .main-header {{ font-size: 2.5rem; color: {MAIN_BLUE}; text-align: center; margin-bottom: 30px; font-weight: bold; }}
    
    /* 隐藏所有原生按钮和默认文字 */
    div[data-testid="stFileUploader"] section button {{ display: none !important; }}
    div[data-testid="stFileUploader"] section div {{ font-size: 0 !important; color: transparent !important; }}

    /* 【修正1】主页面上传框：显示正确文字 */
    div:not([data-testid="stSidebar"]) div[data-testid="stFileUploader"] section {{
        border: 2px dashed {MAIN_BLUE};
        border-radius: 15px;
        padding: {main_padding} !important;
        background-color: {BG_BLUE};
        text-align: center;
        transition: all 0.3s ease;
    }}
    div:not([data-testid="stSidebar"]) div[data-testid="stFileUploader"] section::before {{
        content: "📂 请将文件夹或.dcm文件拖入框内";
        color: {MAIN_BLUE};
        font-size: 1.3rem !important;
        font-weight: bold;
        visibility: visible;
    }}

    /* 【修正2】侧边栏上传框：彻底抹除误导文字，改为“图片说明” */
    div[data-testid="stSidebar"] div[data-testid="stFileUploader"] section {{
        border: 1px dashed {MAIN_BLUE} !important;
        border-radius: 8px;
        padding: 15px !important;
        background-color: #FFFFFF !important;
        text-align: center;
    }}
    div[data-testid="stSidebar"] div[data-testid="stFileUploader"] section::before {{
        content: "🖼️ 图片说明 (非必须)";
        color: {MAIN_BLUE};
        font-size: 0.9rem !important;
        font-weight: normal;
        visibility: visible;
    }}

    /* 【修正3】侧边栏布局：底部吸附逻辑 */
    [data-testid="stSidebar"] > div:first-child {{
        display: flex;
        flex-direction: column;
        height: 100vh;
    }}
    .sidebar-spacer {{
        flex-grow: 1;
    }}
</style>
""", unsafe_allow_html=True)

st.markdown(f'<div class="main-header">🩺 DICOM 信息提取与校正</div>', unsafe_allow_html=True)

# --- 4. 侧边栏布局 ---
with st.sidebar:
    st.header("⚙️ 辅助设置")
    manual_chinese = st.text_input("当前批次汉字姓名补全", placeholder="输入汉字以校正拼音...")
    st.divider()
    st.info("💡 提示：本工具支持自动去重，一个患者只生成一行记录。")
    
    # 占位符将反馈推向底部
    st.markdown('<div class="sidebar-spacer"></div>', unsafe_allow_html=True)
    
    with st.expander("💬 问题反馈"):
        feedback_text = st.text_area("问题或建议：", placeholder="请描述遇到的异常...", height=100)
        # 侧边栏图片上传
        feedback_file = st.file_uploader("", type=['png', 'jpg', 'jpeg'], key="sidebar_feedback_img")
        
        if st.button("提交反馈", type="primary", use_container_width=True):
            if feedback_text:
                if not os.path.exists("feedback_images"): os.makedirs("feedback_images")
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                img_path = "无"
                if feedback_file:
                    img_path = f"feedback_images/{datetime.now().strftime('%Y%m%d_%H%M%S')}_{feedback_file.name}"
                    with open(img_path, "wb") as f:
                        f.write(feedback_file.getbuffer())
                
                new_data = pd.DataFrame([[timestamp, feedback_text, img_path]], columns=["时间", "内容", "截图路径"])
                file_exists = os.path.isfile("feedback_log.csv")
                new_data.to_csv("feedback_log.csv", mode='a', index=False, header=not file_exists, encoding='utf-8-sig')
                st.success("✅ 提交成功！")
            else:
                st.warning("请填写描述")

# --- 5. 主处理流程 ---
uploaded_files = st.file_uploader("", type=['dcm'], accept_multiple_files=True, key=uploader_key)

if uploaded_files:
    processed_studies = {}
    with st.status("🚀 正在提取数据...", expanded=True) as status:
        for file in uploaded_files:
            try:
                ds = pydicom.dcmread(file, stop_before_pixels=True)
                study_id = str(ds.get('StudyInstanceUID', 'None'))
                if study_id not in processed_studies:
                    name = get_final_name(ds, manual_chinese)
                    age = str(ds.get('PatientAge', ''))
                    if not age:
                        try:
                            birth, study = ds.get('PatientBirthDate', ''), ds.get('StudyDate', '')
                            b, s = datetime.strptime(birth, "%Y%m%d"), datetime.strptime(study, "%Y%m%d")
                            age = f"{s.year - b.year - ((study.month, study.day) < (birth.month, birth.day))}岁"
                        except: age = "未知"
                    else: age = age.replace('Y', '岁').lstrip('0')

                    processed_studies[study_id] = {
                        "姓名": name,
                        "性别": str(ds.get('PatientSex', '未知')),
                        "年龄": age,
                        "检查日期": str(ds.get('StudyDate', '未知')),
                        "代表文件名": file.name
                    }
            except: continue
        status.update(label="✅ 提取完毕", state="complete", expanded=False)

    if processed_studies:
        df = pd.DataFrame(list(processed_studies.values()))
        df.index = range(1, len(df) + 1) # 序号从 1 开始
        st.subheader(f"📊 提取清单 (共计 {len(df)} 位患者)")
        st.dataframe(df, use_container_width=True)
        
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 导出结果 (Excel)", data=csv, file_name=f"DICOM_Report_{datetime.now().strftime('%m%d')}.csv", type="primary")