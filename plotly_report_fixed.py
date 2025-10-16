import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

def create_interactive_report():
    # 创建示例数据
    np.random.seed(42)
    months = pd.date_range('2023-01-01', periods=12, freq='M')
    data = {
        'month': months,
        'revenue': np.random.randint(50000, 100000, 12),
        'customers': np.random.randint(1000, 5000, 12),
        'conversion_rate': np.random.uniform(0.02, 0.08, 12),
        'category': np.random.choice(['电子产品', '服装', '食品', '家居'], 12)
    }
    df = pd.DataFrame(data)
    
    # 创建仪表板
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('月度收入趋势', '客户数量 vs 转化率', '收入按类别分布', '关键指标'),
        specs=[[{"type": "scatter"}, {"type": "scatter"}],
               [{"type": "pie"}, {"type": "indicator"}]]
    )
    
    # 1. 收入趋势
    fig.add_trace(
        go.Scatter(x=df['month'], y=df['revenue'], name='收入', 
                   line=dict(color='#1f77b4', width=3)),
        row=1, col=1
    )
    
    # 2. 客户数量
    fig.add_trace(
        go.Scatter(x=df['month'], y=df['customers'], name='客户数',
                   line=dict(color='#ff7f0e', width=3)),
        row=1, col=2
    )
    
    # 3. 饼图
    category_revenue = df.groupby('category')['revenue'].sum()
    fig.add_trace(
        go.Pie(labels=category_revenue.index, values=category_revenue.values,
               hole=0.3),
        row=2, col=1
    )
    
    # 4. 指标卡
    fig.add_trace(
        go.Indicator(
            mode="number+delta",
            value=df['revenue'].sum(),
            title={"text": "总收入"},
            delta={'reference': df['revenue'].sum() * 0.9, 'relative': True},
            number={'prefix': "¥", 'valueformat': ',.0f'}
        ),
        row=2, col=2
    )
    
    fig.update_layout(
        height=800, 
        showlegend=True, 
        title_text="业务仪表板",
        title_font_size=24
    )
    
    return fig

# Streamlit 页面配置
st.set_page_config(page_title="业务仪表板", layout="wide")

# 页面标题
st.title("📊 交互式业务仪表板")

# 生成并显示图表
fig = create_interactive_report()
st.plotly_chart(fig, use_container_width=True)

# 添加说明
st.markdown("---")
st.markdown("""
### 仪表板说明
- **左上**: 月度收入趋势
- **右上**: 客户数量变化
- **左下**: 收入按类别分布
- **右下**: 总收入关键指标
""")