import streamlit as st
import pandas as pd
import pdfplumber
import re
from io import BytesIO

st.set_page_config(page_title="📦 拣货单PDF智能提取工具", layout="centered")
st.title("📦 拣货单PDF智能提取工具")
st.caption("自动识别并提取PDF中的 Product name / Seller SKU / Qty 三列数据，生成Excel文件下载。")

uploaded_file = st.file_uploader("请上传PDF格式拣货单文件", type=["pdf"])

def normalize_column_name(name: str):
    """标准化列名"""
    name = name.lower().strip().replace(" ", "")
    if any(k in name for k in ["product", "name", "商品", "品名"]):
        return "Product name"
    elif any(k in name for k in ["sku", "seller"]):
        return "Seller SKU"
    elif any(k in name for k in ["qty", "数量", "数", "pcs"]):
        return "Qty"
    else:
        return None

def try_extract_from_table(table):
    """尝试从 pdfplumber 提取的表格中匹配三列"""
    df = pd.DataFrame(table)
    if df.empty or df.shape[1] < 2:
        return None
    # 尝试识别列名
    first_row = [str(x).strip() for x in df.iloc[0].tolist()]
    col_map = {}
    for i, c in enumerate(first_row):
        col_type = normalize_column_name(c)
        if col_type:
            col_map[col_type] = i

    if len(col_map) >= 2:
        df.columns = first_row
        df = df.drop(0).reset_index(drop=True)
        selected_cols = [df.columns[i] for i in col_map.values()]
        df = df[selected_cols]
        df.columns = col_map.keys()
        return df
    return None

def try_extract_from_text(page):
    """当表格识别失败时，从文字行中用正则提取"""
    text = page.extract_text()
    if not text:
        return None

    # 匹配模式：SKU 和 数量
    pattern = re.compile(r"(.+?)\s+([A-Z0-9\-]+)\s+(\d+)\b")
    matches = pattern.findall(text)
    if matches:
        df = pd.DataFrame(matches, columns=["Product name", "Seller SKU", "Qty"])
        return df
    return None


if uploaded_file is not None:
    st.success("✅ 文件上传成功，正在智能解析中...")
    extracted_frames = []

    with pdfplumber.open(uploaded_file) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            # 先尝试表格提取
            tables = page.extract_tables()
            page_data = None
            for t in tables:
                df_table = try_extract_from_table(t)
                if df_table is not None:
                    page_data = df_table
                    break
            # 如果表格失败，尝试正则提取
            if page_data is None:
                df_text = try_extract_from_text(page)
                if df_text is not None:
                    page_data = df_text

            if page_data is not None and not page_data.empty:
                page_data["Page"] = page_num
                extracted_frames.append(page_data)

    if extracted_frames:
        final_df = pd.concat(extracted_frames, ignore_index=True)

        # 清洗数据
        final_df["Qty"] = pd.to_numeric(final_df["Qty"], errors="coerce").fillna(0).astype(int)
        final_df = final_df[["Product name", "Seller SKU", "Qty"]]

        st.success(f"✅ 成功提取 {len(final_df)} 条记录！")
        st.dataframe(final_df.head(20))

        # 生成Excel下载
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            final_df.to_excel(writer, index=False, sheet_name="PickList")

        st.download_button(
            label="📥 下载提取后的Excel文件",
            data=output.getvalue(),
            file_name="picklist_extracted.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    else:
        st.error("⚠️ 未能在PDF中识别出有效的表格或内容，请检查文件结构是否为扫描图片或纯图像格式。")
