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
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ---------------------------
# 页面配置
# ---------------------------
st.set_page_config(
    page_title="动态安全库存优化系统", 
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📦 供应链安全库存动态优化系统")
st.markdown("""
该系统用于在**船期不固定**、**运输周期不确定**的条件下，
自动计算最优的安全库存（Safety Stock）和再订货点（Reorder Point），
以实现**不断货且库存最小化**。
""")

# ---------------------------
# 侧边栏配置
# ---------------------------
with st.sidebar:
    st.header("⚙️ 系统配置")
    service = st.slider(
        "目标服务水平（Service Level）", 
        0.80, 0.999, 0.95, 0.01,
        help="服务水平越高，安全库存越大，断货风险越低"
    )
    st.write(f"**当前服务水平：{service:.2%}**")
    
    st.divider()
    
    show_advanced = st.checkbox("显示高级选项", value=False)
    if show_advanced:
        use_custom_leadtime = st.checkbox("使用自定义运输周期", value=False)
        if use_custom_leadtime:
            custom_mu_l = st.number_input("平均运输周期（天）", 0.0, 365.0, 30.0, 1.0)
            custom_sigma_l = st.number_input("运输周期标准差（天）", 0.0, 100.0, 5.0, 0.5)
    else:
        use_custom_leadtime = False
        custom_mu_l = None
        custom_sigma_l = None
    
    st.divider()
    st.caption("© 2025 sisley供应链智能分析实验室")

# ---------------------------
# 数据读取函数（优化版）
# ---------------------------
@st.cache_data(show_spinner=False)
def read_data(uploaded_file):
    """读取并标准化上传的数据文件"""
    try:
        if uploaded_file is None:
            return None
        
        # 根据文件类型读取
        if uploaded_file.name.endswith(".xlsx"):
            df = pd.read_excel(uploaded_file, engine='openpyxl')
        elif uploaded_file.name.endswith(".xls"):
            df = pd.read_excel(uploaded_file, engine='xlrd')
        else:
            # 尝试不同编码读取CSV
            try:
                df = pd.read_csv(uploaded_file, encoding='utf-8')
            except:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding='gbk')
        
        # 标准化列名
        df.columns = [c.lower().strip().replace(' ', '_') for c in df.columns]
        
        return df
    
    except Exception as e:
        st.error(f"❌ 文件读取失败：{str(e)}")
        return None

# ---------------------------
# 数据验证函数
# ---------------------------
def validate_ship_schedule(df):
    """验证船期表格式"""
    if df is None:
        return False, "数据为空"
    
    required_cols = ['date']
    missing = [col for col in required_cols if col not in df.columns]
    
    if missing:
        return False, f"缺少必需列：{', '.join(missing)}"
    
    try:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        if df['date'].isna().all():
            return False, "date列无法解析为日期格式"
    except:
        return False, "date列格式错误"
    
    return True, f"✅ 成功读取 {len(df)} 条船期记录"

def validate_sales_history(df):
    """验证销售记录格式"""
    if df is None:
        return False, "数据为空"
    
    required_cols = ['date', 'sku', 'quantity']
    missing = [col for col in required_cols if col not in df.columns]
    
    if missing:
        return False, f"缺少必需列：{', '.join(missing)}"
    
    try:
        df['date'] = pd.to_datetime(df['date'], errors='coerce')
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce')
        
        if df['date'].isna().all():
            return False, "date列无法解析为日期格式"
        if df['quantity'].isna().all():
            return False, "quantity列无法解析为数值格式"
        
        # 统计信息
        n_skus = df['sku'].nunique()
        date_range = f"{df['date'].min().date()} 至 {df['date'].max().date()}"
        
    except Exception as e:
        return False, f"数据格式错误：{str(e)}"
    
    return True, f"✅ 成功读取 {len(df)} 条销售记录，涵盖 {n_skus} 个SKU，时间范围：{date_range}"

def validate_leadtime_history(df):
    """验证运输周期记录格式"""
    if df is None:
        return True, "未上传运输周期记录（可选）"
    
    has_leadtime_col = 'lead_time_days' in df.columns
    has_date_cols = 'order_date' in df.columns and 'arrival_date' in df.columns
    
    if not (has_leadtime_col or has_date_cols):
        return False, "需要包含 'lead_time_days' 或 ('order_date' + 'arrival_date') 列"
    
    try:
        if has_leadtime_col:
            df['lead_time_days'] = pd.to_numeric(df['lead_time_days'], errors='coerce')
            if df['lead_time_days'].isna().all():
                return False, "lead_time_days列无法解析为数值"
        else:
            df['order_date'] = pd.to_datetime(df['order_date'], errors='coerce')
            df['arrival_date'] = pd.to_datetime(df['arrival_date'], errors='coerce')
            if df['order_date'].isna().all() or df['arrival_date'].isna().all():
                return False, "日期列无法解析"
    except Exception as e:
        return False, f"数据格式错误：{str(e)}"
    
    return True, f"✅ 成功读取 {len(df)} 条运输周期记录"

# ---------------------------
# 上传数据区域
# ---------------------------
st.header("📁 数据上传")

col1, col2, col3 = st.columns(3)

with col1:
    ship_file = st.file_uploader(
        "① 上传船期表（Ship Schedule）", 
        type=["csv", "xlsx", "xls"],
        help="必需：包含船期出发日期信息"
    )
    if ship_file:
        ship_df = read_data(ship_file)
        valid, msg = validate_ship_schedule(ship_df)
        if valid:
            st.success(msg)
            ship_df['date'] = pd.to_datetime(ship_df['date'])
        else:
            st.error(msg)
            ship_df = None

with col2:
    sales_file = st.file_uploader(
        "② 上传销售记录（Sales History）", 
        type=["csv", "xlsx", "xls"],
        help="必需：包含日期、SKU、销量信息"
    )
    if sales_file:
        sales_df = read_data(sales_file)
        valid, msg = validate_sales_history(sales_df)
        if valid:
            st.success(msg)
            sales_df['date'] = pd.to_datetime(sales_df['date'])
            sales_df['quantity'] = pd.to_numeric(sales_df['quantity'])
        else:
            st.error(msg)
            sales_df = None

with col3:
    leadtime_file = st.file_uploader(
        "③ 上传运输周期记录（可选）", 
        type=["csv", "xlsx", "xls"],
        help="可选：包含订单日期和到货日期或运输天数"
    )
    if leadtime_file:
        lead_df = read_data(leadtime_file)
        valid, msg = validate_leadtime_history(lead_df)
        if valid:
            st.success(msg)
        else:
            st.error(msg)
            lead_df = None
    else:
        lead_df = None

# ---------------------------
# 分析函数定义（优化版）
# ---------------------------
def compute_demand_stats(sales_df, sku=None):
    """计算需求统计量"""
    df = sales_df.copy()
    
    # 筛选SKU
    if sku is not None:
        df = df[df["sku"] == sku]
    
    if len(df) == 0:
        return 0, 0, 0
    
    # 创建完整日期范围并填充缺失值
    date_range = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
    daily = df.groupby("date")["quantity"].sum().reindex(date_range, fill_value=0)
    
    mu_d = daily.mean()
    sigma_d = daily.std(ddof=1) if len(daily) > 1 else 0
    
    # 计算需求变异系数（CV）作为需求波动的衡量指标
    cv = (sigma_d / mu_d * 100) if mu_d > 0 else 0
    
    return mu_d, sigma_d, cv

def derive_leadtime_from_schedule(schedule_df):
    """从船期推算运输周期"""
    dates = schedule_df["date"].sort_values().reset_index(drop=True)
    intervals = dates.diff().dt.days.dropna()
    
    if len(intervals) == 0:
        return 30, 5  # 默认值
    
    # 船期间隔的平均值和标准差
    avg_interval = intervals.mean()
    std_interval = intervals.std(ddof=1) if len(intervals) > 1 else 0
    
    # 等待船期的平均时间（假设均匀分布）
    mu_w = avg_interval / 2
    # 等待时间的标准差（均匀分布）
    sigma_w = avg_interval / np.sqrt(12)
    
    # 假设固定运输时间30天
    fixed_transit = 30
    
    # 总运输周期 = 固定运输 + 平均等待
    mu_l = fixed_transit + mu_w
    # 运输周期波动主要来自等待时间波动
    sigma_l = sigma_w
    
    return mu_l, sigma_l

def derive_leadtime_from_history(lead_df):
    """从历史记录计算运输周期"""
    if "lead_time_days" in lead_df.columns:
        lt = pd.to_numeric(lead_df["lead_time_days"], errors="coerce").dropna()
    else:
        lt = (pd.to_datetime(lead_df["arrival_date"]) - 
              pd.to_datetime(lead_df["order_date"])).dt.days
        lt = lt.dropna()
    
    if len(lt) == 0:
        return 30, 5
    
    mu_l = lt.mean()
    sigma_l = lt.std(ddof=1) if len(lt) > 1 else 0
    
    return mu_l, sigma_l

def safety_stock(mu_d, sigma_d, mu_l, sigma_l, service):
    """计算安全库存和再订货点"""
    if mu_d <= 0:
        return 0, 0
    
    # 服务水平对应的z值
    z = norm.ppf(service)
    
    # 方差公式：Var = L*σ_d² + μ_d²*σ_L²
    var = mu_l * (sigma_d ** 2) + (mu_d ** 2) * (sigma_l ** 2)
    
    # 安全库存
    ss = z * np.sqrt(var) if var > 0 else 0
    
    # 再订货点 = 平均需求 + 安全库存
    rop = mu_d * mu_l + ss
    
    return ss, rop

# ---------------------------
# 主计算流程
# ---------------------------
if ship_file and sales_file and ship_df is not None and sales_df is not None:
    
    st.divider()
    
    # 计算运输周期参数
    if use_custom_leadtime:
        mu_l = custom_mu_l
        sigma_l = custom_sigma_l
        st.info(f"📌 使用自定义运输周期：平均 {mu_l:.2f} 天，波动 {sigma_l:.2f} 天")
    elif lead_df is not None:
        mu_l, sigma_l = derive_leadtime_from_history(lead_df)
        st.success(f"✅ 使用运输周期历史记录：平均 {mu_l:.2f} 天，波动 {sigma_l:.2f} 天")
    else:
        mu_l, sigma_l = derive_leadtime_from_schedule(ship_df)
        st.info(f"📊 根据船期推算：平均运输周期 {mu_l:.2f} 天，波动 {sigma_l:.2f} 天")
    
    # SKU 列表
    sku_list = sorted(sales_df["sku"].unique())
    
    # 添加进度条
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    result_list = []
    
    for idx, sku in enumerate(sku_list):
        status_text.text(f"正在计算 {sku}... ({idx+1}/{len(sku_list)})")
        progress_bar.progress((idx + 1) / len(sku_list))
        
        mu_d, sigma_d, cv = compute_demand_stats(sales_df, sku)
        ss, rop = safety_stock(mu_d, sigma_d, mu_l, sigma_l, service)
        
        # 计算周转天数
        turnover_days = (ss / mu_d) if mu_d > 0 else 0
        
        result_list.append({
            "SKU": sku,
            "平均日销量": round(mu_d, 2),
            "日销量标准差": round(sigma_d, 2),
            "需求变异系数CV%": round(cv, 2),
            "平均运输周期(天)": round(mu_l, 2),
            "运输周期标准差(天)": round(sigma_l, 2),
            "安全库存": round(ss, 2),
            "再订货点": round(rop, 2),
            "安全库存周转天数": round(turnover_days, 1),
            "服务水平": f"{service:.2%}"
        })
    
    progress_bar.empty()
    status_text.empty()
    
    result_df = pd.DataFrame(result_list)
    
    # ---------------------------
    # 结果展示
    # ---------------------------
    st.header("📊 计算结果")
    
    # 关键指标卡片
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("SKU总数", len(result_df))
    with col2:
        st.metric("总安全库存", f"{result_df['安全库存'].sum():,.0f}")
    with col3:
        st.metric("平均服务水平", f"{service:.1%}")
    with col4:
        avg_turnover = result_df['安全库存周转天数'].mean()
        st.metric("平均周转天数", f"{avg_turnover:.1f}")
    
    st.divider()
    
    # 结果表格（可排序、可筛选）
    st.subheader("📋 详细计算结果")
    
    # 筛选器
    col1, col2 = st.columns([1, 3])
    with col1:
        filter_option = st.selectbox(
            "筛选条件",
            ["显示全部", "高需求波动(CV>50%)", "低需求波动(CV<30%)", "高安全库存(>1000)"]
        )
    
    # 应用筛选
    filtered_df = result_df.copy()
    if filter_option == "高需求波动(CV>50%)":
        filtered_df = filtered_df[filtered_df["需求变异系数CV%"] > 50]
    elif filter_option == "低需求波动(CV<30%)":
        filtered_df = filtered_df[filtered_df["需求变异系数CV%"] < 30]
    elif filter_option == "高安全库存(>1000)":
        filtered_df = filtered_df[filtered_df["安全库存"] > 1000]
    
    st.dataframe(
        filtered_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "SKU": st.column_config.TextColumn("SKU", width="small"),
            "平均日销量": st.column_config.NumberColumn("平均日销量", format="%.2f"),
            "需求变异系数CV%": st.column_config.NumberColumn("需求CV%", format="%.2f%%"),
            "安全库存": st.column_config.NumberColumn("安全库存", format="%.0f"),
            "再订货点": st.column_config.NumberColumn("再订货点", format="%.0f"),
        }
    )
    
    # 下载按钮
    output = BytesIO()
    result_df.to_excel(output, index=False, engine='openpyxl')
    st.download_button(
        label="📥 下载Excel结果",
        data=output.getvalue(),
        file_name=f"safety_stock_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
    # ---------------------------
    # 可视化分析
    # ---------------------------
    st.divider()
    st.header("📈 数据可视化分析")
    
    tab1, tab2, tab3, tab4 = st.tabs(["销售趋势", "安全库存分布", "需求波动分析", "船期分析"])
    
    with tab1:
        st.subheader("SKU销售趋势")
        sku_selected = st.selectbox("选择SKU", sku_list, key="trend_sku")
        
        df_sku = sales_df[sales_df["sku"] == sku_selected].copy()
        daily_sales = df_sku.groupby("date")["quantity"].sum().reset_index()
        
        fig = px.line(
            daily_sales, 
            x="date", 
            y="quantity",
            title=f"{sku_selected} 日销量趋势",
            labels={"date": "日期", "quantity": "销量"}
        )
        
        # 添加移动平均线
        daily_sales['MA7'] = daily_sales['quantity'].rolling(window=7, min_periods=1).mean()
        fig.add_scatter(
            x=daily_sales['date'], 
            y=daily_sales['MA7'], 
            mode='lines',
            name='7日移动平均',
            line=dict(dash='dash')
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.subheader("安全库存分布")
        
        fig = px.bar(
            result_df.sort_values("安全库存", ascending=False).head(20),
            x="SKU",
            y="安全库存",
            title="TOP 20 安全库存需求SKU",
            labels={"安全库存": "安全库存数量", "SKU": "SKU编号"},
            color="安全库存",
            color_continuous_scale="Blues"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with tab3:
        st.subheader("需求波动性分析")
        
        fig = px.scatter(
            result_df,
            x="平均日销量",
            y="需求变异系数CV%",
            size="安全库存",
            color="安全库存周转天数",
            hover_data=["SKU"],
            title="需求特征散点图（气泡大小=安全库存）",
            labels={
                "平均日销量": "平均日销量",
                "需求变异系数CV%": "需求变异系数 CV%",
                "安全库存周转天数": "周转天数"
            },
            color_continuous_scale="Viridis"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with tab4:
        st.subheader("船期时间间隔分析")
        
        dates = ship_df["date"].sort_values().reset_index(drop=True)
        intervals = dates.diff().dt.days.dropna()
        
        if len(intervals) > 0:
            fig = go.Figure()
            fig.add_trace(go.Histogram(
                x=intervals,
                nbinsx=20,
                name="船期间隔分布",
                marker_color='lightblue'
            ))
            fig.update_layout(
                title="船期时间间隔分布（天）",
                xaxis_title="天数",
                yaxis_title="频次",
                showlegend=True
            )
            st.plotly_chart(fig, use_container_width=True)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("平均间隔", f"{intervals.mean():.1f} 天")
            with col2:
                st.metric("最小间隔", f"{intervals.min():.0f} 天")
            with col3:
                st.metric("最大间隔", f"{intervals.max():.0f} 天")

else:
    st.warning("⚠️ 请至少上传**船期表**与**销售记录**后再运行计算")
    
    # ---------------------------
    # 示例数据下载
    # ---------------------------
    with st.expander("📘 查看数据格式说明和示例"):
        st.markdown("""
        ### 数据格式要求
        
        #### 1. 船期表 (ship_schedule.csv/xlsx)
        | 列名 | 类型 | 说明 | 示例 |
        |------|------|------|------|
        | date | 日期 | 船期出发日期 | 2025-08-01 |
        | voyage_id | 文本(可选) | 航次编号 | V001 |
        | route | 文本(可选) | 航线 | R1 |
        
        #### 2. 销售记录 (sales_history.csv/xlsx)
        | 列名 | 类型 | 说明 | 示例 |
        |------|------|------|------|
        | date | 日期 | 销售日期 | 2025-09-01 |
        | sku | 文本 | 产品SKU编号 | SKU-001 |
        | quantity | 数值 | 销售数量 | 120 |
        
        #### 3. 运输周期记录 (leadtime_history.csv/xlsx, 可选)
        
        **方式A：包含运输天数列**
        | 列名 | 类型 | 说明 | 示例 |
        |------|------|------|------|
        | sku | 文本(可选) | 产品SKU | SKU-001 |
        | lead_time_days | 数值 | 运输天数 | 37 |
        
        **方式B：包含订单和到货日期**
        | 列名 | 类型 | 说明 | 示例 |
        |------|------|------|------|
        | order_date | 日期 | 订单日期 | 2025-07-01 |
        | arrival_date | 日期 | 到货日期 | 2025-08-07 |
        | sku | 文本(可选) | 产品SKU | SKU-001 |
        
        ### 计算方法说明
        
        **安全库存公式：**
        ```
        SS = Z × √(L × σ_d² + μ_d² × σ_L²)
        ```
        其中：
        - Z: 服务水平对应的标准正态分布分位数
        - L: 平均运输周期
        - σ_d: 日需求标准差
        - μ_d: 平均日需求
        - σ_L: 运输周期标准差
        
        **再订货点：**
        ```
        ROP = μ_d × L + SS
        ```
        """)
        
        # 生成示例数据
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # 示例船期数据
            sample_ship = pd.DataFrame({
                'date': pd.date_range('2025-08-01', periods=12, freq='15D'),
                'voyage_id': [f'V{str(i).zfill(3)}' for i in range(1, 13)],
                'route': ['R1'] * 12
            })
            output_ship = BytesIO()
            sample_ship.to_csv(output_ship, index=False)
            st.download_button(
                "📥 下载船期示例",
                data=output_ship.getvalue(),
                file_name="sample_ship_schedule.csv",
                mime="text/csv"
            )
        
        with col2:
            # 示例销售数据
            dates = pd.date_range('2025-09-01', '2025-10-31', freq='D')
            sample_sales = pd.DataFrame({
                'date': np.tile(dates, 3),
                'sku': np.repeat(['SKU-001', 'SKU-002', 'SKU-003'], len(dates)),
                'quantity': np.random.poisson(100, len(dates) * 3)
            })
            output_sales = BytesIO()
            sample_sales.to_csv(output_sales, index=False)
            st.download_button(
                "📥 下载销售示例",
                data=output_sales.getvalue(),
                file_name="sample_sales_history.csv",
                mime="text/csv"
            )
        
        with col3:
            # 示例运输周期数据
            sample_leadtime = pd.DataFrame({
                'order_date': pd.date_range('2025-07-01', periods=10, freq='7D'),
                'arrival_date': pd.date_range('2025-08-07', periods=10, freq='7D'),
                'sku': [f'SKU-{str(i % 3 + 1).zfill(3)}' for i in range(10)],
                'lead_time_days': np.random.normal(37, 5, 10).astype(int)
            })
            output_lead = BytesIO()
            sample_leadtime.to_csv(output_lead, index=False)
            st.download_button(
                "📥 下载运输周期示例",
                data=output_lead.getvalue(),
                file_name="sample_leadtime_history.csv",
                mime="text/csv"
            )
