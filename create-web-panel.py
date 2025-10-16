# 保存为 app.py 并运行: streamlit run app.py

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta

def create_streamlit_dashboard():
    st.set_page_config(page_title="销售分析仪表板", layout="wide")
    
    # 标题
    st.title("📊 销售分析仪表板")
    
    # 生成示例数据
    @st.cache_data
    def load_data():
        dates = pd.date_range('2023-01-01', periods=180, freq='D')
        data = {
            'date': dates,
            'sales': np.random.randint(1000, 5000, 180) + np.sin(np.arange(180)*0.1) * 1000,
            'profit': np.random.randint(200, 1000, 180),
            'region': np.random.choice(['华北', '华东', '华南', '西部'], 180),
            'product': np.random.choice(['产品A', '产品B', '产品C', '产品D'], 180)
        }
        return pd.DataFrame(data)
    
    df = load_data()
    
    # 侧边栏过滤器
    st.sidebar.header("筛选条件")
    
    region_filter = st.sidebar.multiselect(
        "选择区域",
        options=df['region'].unique(),
        default=df['region'].unique()
    )
    
    product_filter = st.sidebar.multiselect(
        "选择产品",
        options=df['product'].unique(),
        default=df['product'].unique()
    )
    
    date_range = st.sidebar.date_input(
        "选择日期范围",
        value=(df['date'].min(), df['date'].max()),
        min_value=df['date'].min(),
        max_value=df['date'].max()
    )
    
    # 应用筛选
    filtered_df = df[
        (df['region'].isin(region_filter)) &
        (df['product'].isin(product_filter)) &
        (df['date'] >= pd.to_datetime(date_range[0])) &
        (df['date'] <= pd.to_datetime(date_range[1]))
    ]
    
    # KPI指标卡
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_sales = filtered_df['sales'].sum()
        st.metric("总销售额", f"¥{total_sales:,.0f}")
    
    with col2:
        avg_daily_sales = filtered_df['sales'].mean()
        st.metric("日均销售额", f"¥{avg_daily_sales:,.0f}")
    
    with col3:
        total_profit = filtered_df['profit'].sum()
        st.metric("总利润", f"¥{total_profit:,.0f}")
    
    with col4:
        profit_margin = (total_profit / total_sales * 100) if total_sales > 0 else 0
        st.metric("利润率", f"{profit_margin:.1f}%")
    
    # 图表区域
    col1, col2 = st.columns(2)
    
    with col1:
        # 销售趋势图
        daily_sales = filtered_df.groupby('date')['sales'].sum().reset_index()
        fig1 = px.line(daily_sales, x='date', y='sales', 
                      title="销售趋势")
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        # 区域销售分布
        region_sales = filtered_df.groupby('region')['sales'].sum().reset_index()
        fig2 = px.pie(region_sales, values='sales', names='region',
                     title="区域销售分布")
        st.plotly_chart(fig2, use_container_width=True)
    
    # 产品分析
    st.subheader("产品分析")
    
    col3, col4 = st.columns(2)
    
    with col3:
        # 产品销售排行
        product_sales = filtered_df.groupby('product').agg({
            'sales': 'sum',
            'profit': 'sum'
        }).reset_index()
        
        fig3 = px.bar(product_sales, x='product', y='sales',
                     title="产品销售排行")
        st.plotly_chart(fig3, use_container_width=True)
    
    with col4:
        # 散点图：销售额 vs 利润
        fig4 = px.scatter(product_sales, x='sales', y='profit', 
                         text='product', size='sales',
                         title="销售额 vs 利润")
        st.plotly_chart(fig4, use_container_width=True)
    
    # 数据表格
    st.subheader("详细数据")
    st.dataframe(filtered_df, use_container_width=True)

if __name__ == "__main__":
    create_streamlit_dashboard()