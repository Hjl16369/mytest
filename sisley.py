import streamlit as st
import pandas as pd

st.title("Sisley 补货与物流方式判定系统")

# 上传文件
uploaded_file_main = st.file_uploader("上传文件: restock_final_sold_vs_sold.xlsx", type=["xlsx"])

if uploaded_file_main:
    # 读取文件
    df_main = pd.read_excel(uploaded_file_main)
    
    # 判断逻辑
    logistics = []
    for _, row in df_main.iterrows():
        final_restock = row["最终补货量"]
        daily_sales = row["日均销量"]
        growth = row["增长系数"]
        stock = row["当前库存"]

        if final_restock <= 0:
            logistics.append("不补货")
            continue

        # 未来10天累计销量
        sales_10_days = sum([daily_sales * ((1 + growth) ** i) for i in range(1, 11)])
        sales_3_days = sum([daily_sales * ((1 + growth) ** i) for i in range(1, 4)])

        if sales_10_days >= stock:
            if sales_3_days >= stock:
                logistics.append("空运")
            else:
                logistics.append("海运")
        else:
            logistics.append("不补货")

    df_main["补货物流方式"] = logistics

    # 定义样式函数
    def highlight_logistics(val):
        if val == "空运":
            return "color: red; font-weight: bold;"
        elif val == "海运":
            return "color: blue; font-weight: bold;"
        return ""

    # 应用样式
    styled_df = df_main.style.applymap(highlight_logistics, subset=["补货物流方式"])

    st.write("处理后的数据（带颜色标记）:")
    st.write(styled_df.to_html(), unsafe_allow_html=True)

    # 保存并下载
    output_path = "updated_restock_final_sold_vs_sold.xlsx"
    df_main.to_excel(output_path, index=False)
    with open(output_path, "rb") as f:
        st.download_button("下载更新后的表格", f, file_name=output_path)
else:
    st.info("请上传Excel文件以开始处理")