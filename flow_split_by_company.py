import streamlit as st
import pandas as pd
import zipfile
from io import BytesIO

st.set_page_config(page_title="流向自动分拆工具", layout="centered")
st.title("汇总流向按【配送企业】自动分拆")

st.write("### 操作流程")
st.write("1. 上传【汇总流向表】文件")
st.write("2. 点击【开始分拆】")
st.write("3. 点击【下载分拆结果压缩包】")

flow_file = st.file_uploader("请上传：汇总流向表（Excel）", type=["xlsx"])

output_files = {}

if st.button("开始分拆"):
    if flow_file is None:
        st.error("请先上传汇总流向文件")
    else:
        flow_df = pd.read_excel(flow_file)

        if "配送企业" not in flow_df.columns:
            st.error("文件中不存在字段：配送企业")
            st.stop()

        # 获取所有配送企业
        companies = flow_df["配送企业"].dropna().astype(str).unique()
        st.write(f"识别到配送企业数量：{len(companies)}")

        output_files.clear()

        for company in companies:
            sub_df = flow_df[flow_df["配送企业"].astype(str) == company]
            if len(sub_df) > 0:
                buffer = BytesIO()
                sub_df.to_excel(buffer, index=False)
                output_files[f"{company}.xlsx"] = buffer.getvalue()

        st.success(f"分拆完成，共生成 {len(output_files)} 个文件")

if len(output_files) > 0:
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for fname, content in output_files.items():
            zipf.writestr(fname, content)
    zip_buffer.seek(0)

    st.download_button(
        label="下载分拆后的流向文件压缩包",
        data=zip_buffer,
        file_name="按配送企业分拆结果.zip",
        mime="application/zip"
    )
