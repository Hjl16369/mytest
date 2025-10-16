import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

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
        go.Scatter(x=df['month'], y=df['revenue'], name='收入'),
        row=1, col=1
    )
    
    # 2. 双Y轴图
    fig.add_trace(
        go.Scatter(x=df['month'], y=df['customers'], name='客户数'),
        row=1, col=2
    )
    fig.add_trace(
        go.Scatter(x=df['month'], y=df['conversion_rate']*1000, 
                  name='转化率(x1000)', yaxis='y2'),
        row=1, col=2
    )
    
    # 3. 饼图
    category_revenue = df.groupby('category')['revenue'].sum()
    fig.add_trace(
        go.Pie(labels=category_revenue.index, values=category_revenue.values),
        row=2, col=1
    )
    
    # 4. 指标卡
    fig.add_trace(
        go.Indicator(
            mode = "number+delta",
            value = df['revenue'].sum(),
            title = {"text": "总收入"},
            delta = {'reference': df['revenue'].sum() * 0.9},
        ),
        row=2, col=2
    )
    
    fig.update_layout(height=800, showlegend=True, 
                     title_text="业务仪表板")
    fig.show()
    
    return fig

# 生成交互式报表
fig = create_interactive_report()