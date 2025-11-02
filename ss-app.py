# ------------------------------------------------------------
# 文件名：safety_stock_app.py
# 功能：基于船期、销售与运输周期波动的动态安全库存计算系统
# 运行方式：streamlit run safety_stock_app.py
# ------------------------------------------------------------

import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from scipy.stats import norm

# ---------------------------
# 页面配置
# ---------------------------
st.set_page_config(page_title="动态安全库存优化系统", layout="wide")
st.title("📦 供应链安全库存动态优化系统")
st.markdown("""
该系统用于在**船期不固定**、**运输周期不确定**的条件下，
自动计算最优的安全库存（Safety Stock）和再订货点（Reorder Point），
以实现**不断货且库存最小化**。
""")

# ---------------------------
# 上传数据
# ---------------------------
st.header("📁 数据上传")

col1, col2, col3 = st.columns(3)
with col1:
    ship_file = st.file_uploader("① 上传船期表（Ship Schedule）", type=["csv", "xlsx"])
with col2:
    sales_file = st.file_uploader("② 上传销售记录（Sales History）", type=["csv", "xlsx"])
with col3:
    leadtime_file = st.file_uploader("③ 上传运输周期记录（Lead Time History，可选）", type=["csv", "xlsx"])

st.markdown("""
**格式要求**：
- 船期表：需包含列 `date`（出发日期）
- 销售记录：需包含列 `date`, `sku`, `quantity`
- 运输周期记录（可选）：包含列 `order_date`, `arrival_date` 或 `lead_time_days`
""")

# ---------------------------
# 数据读取函数
# ---------------------------
@st.cache_data
def read_data(uploaded_file):
    if uploaded_file is None:
        return None
    if uploaded_file.name.endswith(".xlsx"):
        df = pd.read_excel(uploaded_file)
    else:
        df = pd.read_csv(uploaded_file)
    df.columns = [c.lower().strip() for c in df.columns]
    return df

# ---------------------------
# 分析函数定义
# ---------------------------
def compute_demand_stats(sales_df, sku=None):
    df = sales_df.copy()
    if sku is not None:
        df = df[df["sku"] == sku]
    daily = df.groupby("date")["quantity"].sum().reindex(
        pd.date_range(df["date"].min(), df["date"].max(), freq="D"), fill_value=0
    )
    mu_d = daily.mean()
    sigma_d = daily.std(ddof=1)
    return mu_d, sigma_d

def derive_leadtime_from_schedule(schedule_df):
    dates = schedule_df["date"].sort_values().reset_index(drop=True)
    intervals = dates.diff().dt.days.dropna()
    if len(intervals) == 0:
        return 30, 0
    mu_w = intervals.mean() / 2
    sigma_w = np.sqrt((intervals.pow(2).mean()) / 12)
    mu_l = 30 + mu_w
    sigma_l = sigma_w
    return mu_l, sigma_l

def derive_leadtime_from_history(lead_df):
    if "lead_time_days" in lead_df.columns:
        lt = pd.to_numeric(lead_df["lead_time_days"], errors="coerce").dropna()
    else:
        lt = (pd.to_datetime(lead_df["arrival_date"]) - pd.to_datetime(lead_df["order_date"])).dt.days
    mu_l = lt.mean()
    sigma_l = lt.std(ddof=1)
    return mu_l, sigma_l

def safety_stock(mu_d, sigma_d, mu_l, sigma_l, service):
    z = norm.ppf(service)
    var = mu_l * (sigma_d ** 2) + (mu_d ** 2) * (sigma_l ** 2)
    ss = z * np.sqrt(var)
    rop = mu_d * mu_l + ss
    return ss, rop

# ---------------------------
# 主计算流程
# ---------------------------
if ship_file and sales_file:
    # 读取数据
    ship_df = read_data(ship_file)
    sales_df = read_data(sales_file)
    lead_df = read_data(leadtime_file) if leadtime_file else None

    # 数据预处理
    if "date" in ship_df.columns:
        ship_df["date"] = pd.to_datetime(ship_df["date"])
    sales_df["date"] = pd.to_datetime(sales_df["date"])

    service = st.slider("目标服务水平（Service Level）", 0.80, 0.999, 0.95, 0.01)
    st.write(f"当前服务水平：{service:.2%}")

    # 计算运输周期参数
    if lead_df is not None:
        mu_l, sigma_l = derive_leadtime_from_history(lead_df)
        st.success(f"使用运输周期记录计算得：平均运输周期 {mu_l:.2f} 天，波动 {sigma_l:.2f} 天")
    else:
        mu_l, sigma_l = derive_leadtime_from_schedule(ship_df)
        st.info(f"根据船期推算：平均运输周期 {mu_l:.2f} 天，波动 {sigma_l:.2f} 天")

    # SKU 列表
    sku_list = sorted(sales_df["sku"].unique())
    result_list = []

    for sku in sku_list:
        mu_d, sigma_d = compute_demand_stats(sales_df, sku)
        ss, rop = safety_stock(mu_d, sigma_d, mu_l, sigma_l, service)
        result_list.append({
            "SKU": sku,
            "平均日销量": round(mu_d, 2),
            "日销量波动": round(sigma_d, 2),
            "平均运输周期": round(mu_l, 2),
            "运输波动": round(sigma_l, 2),
            "安全库存": round(ss, 2),
            "再订货点": round(rop, 2),
            "服务水平": f"{service:.2%}"
        })

    result_df = pd.DataFrame(result_list)

    # ---------------------------
    # 结果展示
    # ---------------------------
    st.header("📊 计算结果")
    st.dataframe(result_df, use_container_width=True)

    # 可下载结果
    output = BytesIO()
    result_df.to_csv(output, index=False, encoding="utf-8-sig")
    st.download_button(
        label="📥 下载计算结果 CSV",
        data=output.getvalue(),
        file_name="safety_stock_results.csv",
        mime="text/csv"
    )

    # 可视化
    st.subheader("趋势可视化")
    sku_selected = st.selectbox("选择SKU查看销售趋势", sku_list)
    df_sku = sales_df[sales_df["sku"] == sku_selected]
    daily_sales = df_sku.groupby("date")["quantity"].sum()
    st.line_chart(daily_sales)

else:
    st.warning("请至少上传船期表与销售记录后再运行计算。")

# ---------------------------
# 示例数据下载
# ---------------------------
with st.expander("📘 下载示例数据格式"):
    st.markdown("""
    **示例文件内容说明：**
    - ship_schedule.csv  
      ```
      date,voyage_id,route
      2025-08-01,V001,R1
      2025-08-15,V002,R1
      2025-09-01,V003,R1
      ```
    - sales_history.csv  
      ```
      date,sku,quantity
      2025-09-01,SKU-001,120
      2025-09-02,SKU-001,110
      ```
    - leadtime_history.csv  
      ```
      order_date,arrival_date,sku,lead_time_days
      2025-07-01,2025-08-07,SKU-001,37
      ```
    """)

st.caption("© 2025 sisley供应链智能分析实验室  |  技术方案示例版")
