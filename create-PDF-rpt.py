from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import inch
import pandas as pd
import numpy as np
from datetime import datetime

def create_pdf_report():
    # 创建示例数据
    np.random.seed(42)
    months = ['1月', '2月', '3月', '4月', '5月', '6月']
    data = {
        '月份': months,
        '收入': np.random.randint(50000, 100000, 6),
        '成本': np.random.randint(30000, 60000, 6),
        '利润': np.random.randint(15000, 40000, 6),
        '增长率': np.random.uniform(0.05, 0.15, 6)
    }
    df = pd.DataFrame(data)
    
    # 创建PDF
    filename = "business_report.pdf"
    doc = SimpleDocTemplate(filename, pagesize=A4)
    story = []
    styles = getSampleStyleSheet()
    
    # 标题
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        spaceAfter=30,
        alignment=1  # 居中
    )
    title = Paragraph("企业业务报表", title_style)
    story.append(title)
    
    # 生成日期
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=2  # 右对齐
    )
    date_text = Paragraph(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}", date_style)
    story.append(date_text)
    story.append(Spacer(1, 20))
    
    # 汇总数据表格
    headers = list(df.columns)
    data = [headers] + df.values.tolist()
    
    # 创建表格
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    story.append(table)
    story.append(Spacer(1, 30))
    
    # 添加总结段落
    summary_style = ParagraphStyle(
        'SummaryStyle',
        parent=styles['Normal'],
        fontSize=12,
        leading=16
    )
    
    total_revenue = df['收入'].sum()
    total_profit = df['利润'].sum()
    avg_growth = df['增长率'].mean()
    
    summary_text = f"""
    <b>业绩总结:</b><br/>
    上半年总收入: ¥{total_revenue:,.0f}<br/>
    总利润: ¥{total_profit:,.0f}<br/>
    平均增长率: {avg_growth:.1%}<br/>
    <br/>
    根据数据分析，公司业务保持稳定增长态势，建议继续关注成本控制，优化产品结构。
    """
    
    summary = Paragraph(summary_text, summary_style)
    story.append(summary)
    
    # 生成PDF
    doc.build(story)
    print(f"PDF报表已生成: {filename}")

# 生成PDF报表
create_pdf_report()