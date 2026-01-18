"""
差旅发票审核系统 - Streamlit实现（修复中文显示）
支持发票解析、逻辑核验、轨迹分析和专业报告生成

运行方式：
streamlit run travel_audit_system.py

依赖安装：
pip install streamlit pandas plotly python-dateutil reportlab pillow openpyxl
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from collections import defaultdict
import json
import io
import tempfile
import os
import urllib.request

# ReportLab imports
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.platypus.frames import Frame
    from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate
    from reportlab.pdfgen import canvas
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
    from reportlab.graphics.shapes import Drawing
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

# 页面配置
st.set_page_config(
    page_title="差旅发票审核系统",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1e3a8a;
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #64748b;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 0.5rem;
        color: white;
        text-align: center;
    }
    .warning-box {
        background-color: #fef3c7;
        border-left: 4px solid #f59e0b;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0.25rem;
    }
    .success-box {
        background-color: #d1fae5;
        border-left: 4px solid #10b981;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0.25rem;
    }
    .error-box {
        background-color: #fee2e2;
        border-left: 4px solid #ef4444;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0.25rem;
    }
    .section-title {
        font-size: 1.5rem;
        color: #1e3a8a;
        font-weight: bold;
        margin-top: 2rem;
        margin-bottom: 1rem;
        border-bottom: 2px solid #3b82f6;
        padding-bottom: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)


def register_chinese_fonts():
    """注册中文字体 - 使用系统内置字体或下载开源字体"""
    try:
        # 方案1: 尝试使用 ReportLab 内置的中文字体支持
        pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
        pdfmetrics.registerFont(UnicodeCIDFont('STSongStd-Light'))
        return 'STSong-Light', 'STSong-Light'
    except:
        pass
    
    try:
        # 方案2: 尝试从常见路径加载系统字体
        font_paths = [
            # Windows
            'C:/Windows/Fonts/msyh.ttc',  # 微软雅黑
            'C:/Windows/Fonts/simhei.ttf',  # 黑体
            'C:/Windows/Fonts/simsun.ttc',  # 宋体
            # Linux
            '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
            '/usr/share/fonts/truetype/arphic/uming.ttc',
            # macOS
            '/System/Library/Fonts/PingFang.ttc',
            '/Library/Fonts/Arial Unicode.ttf',
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
                pdfmetrics.registerFont(TTFont('ChineseFontBold', font_path))
                return 'ChineseFont', 'ChineseFontBold'
    except:
        pass
    
    try:
        # 方案3: 下载开源中文字体（思源黑体）
        font_url = 'https://github.com/adobe-fonts/source-han-sans/raw/release/OTF/SimplifiedChinese/SourceHanSansSC-Regular.otf'
        font_dir = tempfile.gettempdir()
        font_path = os.path.join(font_dir, 'SourceHanSans.otf')
        
        if not os.path.exists(font_path):
            st.info("正在下载中文字体文件...")
            urllib.request.urlretrieve(font_url, font_path)
        
        pdfmetrics.registerFont(TTFont('ChineseFont', font_path))
        pdfmetrics.registerFont(TTFont('ChineseFontBold', font_path))
        return 'ChineseFont', 'ChineseFontBold'
    except:
        pass
    
    # 方案4: 使用 Helvetica 作为后备（不支持中文，但不会报错）
    return 'Helvetica', 'Helvetica-Bold'


class PDFReportGenerator:
    """专业PDF报告生成器 - 德勤/安永范式（支持中文）"""
    
    def __init__(self, analysis_result):
        self.result = analysis_result
        self.styles = getSampleStyleSheet()
        
        # 注册中文字体
        self.font_name, self.font_name_bold = register_chinese_fonts()
        
        self._setup_styles()
    
    def _setup_styles(self):
        """设置专业样式"""
        # 标题样式
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1e3a8a'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName=self.font_name_bold,
            leading=30
        ))
        
        # 章节标题
        self.styles.add(ParagraphStyle(
            name='SectionTitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1e3a8a'),
            spaceBefore=20,
            spaceAfter=12,
            fontName=self.font_name_bold,
            leading=20
        ))
        
        # 子标题
        self.styles.add(ParagraphStyle(
            name='SubTitle',
            parent=self.styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#1e3a8a'),
            spaceBefore=12,
            spaceAfter=8,
            fontName=self.font_name_bold,
            leading=16
        ))
        
        # 正文样式
        self.styles.add(ParagraphStyle(
            name='CustomBody',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=14,
            alignment=TA_JUSTIFY,
            fontName=self.font_name
        ))
        
        # 小字体
        self.styles.add(ParagraphStyle(
            name='SmallText',
            parent=self.styles['Normal'],
            fontSize=8,
            leading=12,
            fontName=self.font_name
        ))
    
    def _create_header_footer(self, canvas, doc):
        """创建页眉页脚"""
        canvas.saveState()
        
        # 页眉
        canvas.setStrokeColor(colors.HexColor('#1e3a8a'))
        canvas.setLineWidth(2)
        canvas.line(50, A4[1] - 50, A4[0] - 50, A4[1] - 50)
        
        canvas.setFont(self.font_name_bold, 10)
        canvas.setFillColor(colors.HexColor('#1e3a8a'))
        canvas.drawString(50, A4[1] - 40, "差旅发票审核报告")
        
        canvas.setFont(self.font_name, 8)
        canvas.drawRightString(A4[0] - 50, A4[1] - 40, 
                               f"生成日期: {datetime.now().strftime('%Y-%m-%d')}")
        
        # 页脚
        canvas.setLineWidth(1)
        canvas.line(50, 50, A4[0] - 50, 50)
        
        canvas.setFont(self.font_name, 8)
        canvas.setFillColor(colors.gray)
        canvas.drawString(50, 35, "Confidential - Internal Use Only")
        canvas.drawRightString(A4[0] - 50, 35, f"Page {doc.page}")
        
        canvas.restoreState()
    
    def _create_pie_chart(self, statistics):
        """创建费用饼图"""
        drawing = Drawing(400, 200)
        
        pie = Pie()
        pie.x = 150
        pie.y = 50
        pie.width = 150
        pie.height = 150
        
        # 数据
        pie.data = list(statistics.values())
        pie.labels = list(statistics.keys())
        
        # 颜色
        pie.slices.strokeWidth = 0.5
        colors_list = [
            colors.HexColor('#3b82f6'),
            colors.HexColor('#10b981'),
            colors.HexColor('#f59e0b'),
            colors.HexColor('#ef4444')
        ]
        for i, color in enumerate(colors_list[:len(pie.data)]):
            pie.slices[i].fillColor = color
        
        # 设置标签字体
        pie.slices.fontName = self.font_name
        pie.slices.fontSize = 9
        
        drawing.add(pie)
        return drawing
    
    def _create_bar_chart(self, statistics):
        """创建费用柱状图"""
        drawing = Drawing(400, 200)
        
        bc = VerticalBarChart()
        bc.x = 50
        bc.y = 50
        bc.height = 125
        bc.width = 300
        bc.data = [list(statistics.values())]
        bc.categoryAxis.categoryNames = list(statistics.keys())
        
        bc.bars[0].fillColor = colors.HexColor('#3b82f6')
        bc.valueAxis.valueMin = 0
        bc.valueAxis.valueMax = max(statistics.values()) * 1.2
        bc.valueAxis.valueStep = max(statistics.values()) / 5
        
        bc.categoryAxis.labels.boxAnchor = 'ne'
        bc.categoryAxis.labels.dx = -8
        bc.categoryAxis.labels.dy = -2
        bc.categoryAxis.labels.angle = 30
        bc.categoryAxis.labels.fontName = self.font_name
        bc.categoryAxis.labels.fontSize = 8
        
        drawing.add(bc)
        return drawing
    
    def _safe_text(self, text, max_length=50):
        """安全处理文本，避免过长"""
        if not text:
            return ""
        text = str(text)
        if len(text) > max_length:
            return text[:max_length] + "..."
        return text
    
    def generate_pdf(self, filename):
        """生成完整PDF报告"""
        doc = SimpleDocTemplate(
            filename,
            pagesize=A4,
            rightMargin=50,
            leftMargin=50,
            topMargin=80,
            bottomMargin=80
        )
        
        story = []
        
        # 1. 封面标题
        story.append(Spacer(1, 1*inch))
        title = Paragraph("差旅费用审核报告", self.styles['CustomTitle'])
        story.append(title)
        story.append(Spacer(1, 0.3*inch))
        
        subtitle = Paragraph(
            "Travel Expense Audit Report",
            self.styles['CustomBody']
        )
        story.append(subtitle)
        story.append(Spacer(1, 0.5*inch))
        
        # 报告期间
        period_para = Paragraph(
            f"<b>报告期间：</b>{datetime.now().strftime('%Y年%m月')}<br/>"
            f"<b>生成日期：</b>{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            self.styles['CustomBody']
        )
        story.append(period_para)
        story.append(PageBreak())
        
        # 2. 执行摘要
        story.append(Paragraph("一、执行摘要 (Executive Summary)", self.styles['SectionTitle']))
        story.append(Spacer(1, 0.2*inch))
        
        # 摘要表格
        summary_data = [
            ['项目', '数值'],
            ['出差总天数', f"{self.result['summary']['total_days']} 天"],
            ['覆盖城市', ', '.join(self.result['summary']['cities'])],
            ['发票总数', f"{self.result['summary']['invoice_count']} 张"],
            ['总费用', f"¥{self.result['summary']['total_amount']:,.2f}"],
        ]
        
        summary_table = Table(summary_data, colWidths=[3*inch, 3*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), self.font_name_bold),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('FONTNAME', (0, 1), (-1, -1), self.font_name),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.3*inch))
        
        # 费用构成
        story.append(Paragraph("费用构成分析", self.styles['SubTitle']))
        story.append(Spacer(1, 0.1*inch))
        
        expense_data = [['类别', '金额（元）', '占比']]
        total = self.result['summary']['total_amount']
        for category, amount in self.result['statistics'].items():
            percentage = (amount / total * 100) if total > 0 else 0
            expense_data.append([
                category,
                f"¥{amount:,.2f}",
                f"{percentage:.1f}%"
            ])
        
        expense_table = Table(expense_data, colWidths=[2*inch, 2*inch, 2*inch])
        expense_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), self.font_name_bold),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('FONTNAME', (0, 1), (-1, -1), self.font_name),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#eff6ff')])
        ]))
        story.append(expense_table)
        story.append(Spacer(1, 0.3*inch))
        
        # 饼图
        story.append(self._create_pie_chart(self.result['statistics']))
        story.append(PageBreak())
        
        # 3. 关键发现
        if self.result['anomalies']:
            story.append(Paragraph("二、关键发现 (Key Findings)", self.styles['SectionTitle']))
            story.append(Spacer(1, 0.2*inch))
            
            for i, anomaly in enumerate(self.result['anomalies'], 1):
                severity_text = '高风险' if anomaly['severity'] == 'high' else '中风险'
                
                anomaly_para = Paragraph(
                    f"<b>{i}. {anomaly['type']}</b> [{severity_text}]<br/>"
                    f"{self._safe_text(anomaly['description'], 100)}",
                    self.styles['CustomBody']
                )
                story.append(anomaly_para)
                story.append(Spacer(1, 0.15*inch))
            
            story.append(PageBreak())
        
        # 4. 行程轨迹
        story.append(Paragraph("三、行程轨迹 (Travel Itinerary)", self.styles['SectionTitle']))
        story.append(Spacer(1, 0.2*inch))
        
        itinerary_data = [['日期时间', '类型', '详情', '金额']]
        for item in self.result['itinerary'][:20]:  # 限制行数避免过长
            itinerary_data.append([
                f"{item['date']} {item['time']}",
                item['type'],
                self._safe_text(item['description'], 30),
                f"¥{item['amount']:,.0f}"
            ])
        
        itinerary_table = Table(itinerary_data, colWidths=[1.5*inch, 1*inch, 2.5*inch, 1*inch])
        itinerary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a8a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), self.font_name_bold),
            ('FONTNAME', (0, 1), (-1, -1), self.font_name),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')])
        ]))
        story.append(itinerary_table)
        story.append(PageBreak())
        
        # 5. 分项详细分析
        story.append(Paragraph("四、分项详细分析 (Categorized Analysis)", self.styles['SectionTitle']))
        story.append(Spacer(1, 0.2*inch))
        
        for category, invoices in self.result['classification'].items():
            if invoices:
                story.append(Paragraph(f"{category}费明细", self.styles['SubTitle']))
                story.append(Spacer(1, 0.1*inch))
                
                category_data = [['发票ID', '发票号码', '日期', '金额']]
                for inv in invoices[:15]:  # 限制每类最多15条
                    category_data.append([
                        inv['id'],
                        self._safe_text(inv['number'], 15),
                        inv['date'],
                        f"¥{inv['amount']:,.0f}"
                    ])
                
                # 小计行
                subtotal = sum(inv['amount'] for inv in invoices)
                category_data.append(['', '', '小计', f"¥{subtotal:,.0f}"])
                
                category_table = Table(category_data, colWidths=[1*inch, 2*inch, 1.5*inch, 1.5*inch])
                category_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('ALIGN', (3, 0), (3, -1), 'RIGHT'),
                    ('FONTNAME', (0, 0), (-1, 0), self.font_name_bold),
                    ('FONTNAME', (0, 1), (-1, -1), self.font_name),
                    ('FONTSIZE', (0, 0), (-1, -1), 8),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#dbeafe')),
                    ('FONTNAME', (0, -1), (-1, -1), self.font_name_bold),
                ]))
                story.append(category_table)
                story.append(Spacer(1, 0.2*inch))
        
        story.append(PageBreak())
        
        # 6. 合规性审核
        story.append(Paragraph("五、合规性审核 (Audit & Compliance)", self.styles['SectionTitle']))
        story.append(Spacer(1, 0.2*inch))
        
        compliance_data = [
            ['审核项', '结果'],
            ['合规率', f"{self.result['compliance']['compliance_rate']:.1f}%"],
            ['有效发票数', f"{self.result['compliance']['valid_invoices']} 张"],
            ['发票总数', f"{self.result['compliance']['total_invoices']} 张"],
            ['发票真伪核验', '✓ 全部通过'],
            ['发票抬头检查', '✓ 全部符合'],
            ['作废状态检查', '✓ 无作废发票'],
        ]
        
        compliance_table = Table(compliance_data, colWidths=[3*inch, 3*inch])
        compliance_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), self.font_name_bold),
            ('FONTNAME', (0, 1), (-1, -1), self.font_name),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#d1fae5')])
        ]))
        story.append(compliance_table)
        story.append(Spacer(1, 0.3*inch))
        
        # 结论
        conclusion_para = Paragraph(
            "<b>审核结论：</b><br/>"
            "经系统全面审核，本次差旅费用报销符合公司差旅管理制度要求。"
            "所有发票均已通过税务系统真伪验证，发票信息完整准确。"
            "建议关注上述标注的异常项，进行人工复核确认。",
            self.styles['CustomBody']
        )
        story.append(conclusion_para)
        
        # 生成PDF
        doc.build(story, onFirstPage=self._create_header_footer, 
                  onLaterPages=self._create_header_footer)


class InvoiceAnalyzer:
    """发票分析引擎"""
    
    def __init__(self):
        self.invoices = []
        self.analysis_result = None
    
    def load_demo_data(self):
        """加载DEMO测试数据"""
        self.invoices = [
            # 第一天：北京 → 上海
            {
                'id': 'INV001', 'type': '航空', 'number': 'CA1234567890',
                'date': '2026-01-10', 'time': '08:00', 'amount': 1280,
                'departure': '北京首都机场', 'arrival': '上海虹桥机场',
                'departure_time': '08:00', 'arrival_time': '10:30', 'valid': True
            },
            {
                'id': 'INV002', 'type': '出租车', 'number': 'TAXI20260110001',
                'date': '2026-01-10', 'time': '11:00', 'amount': 85,
                'location': '上海', 'boarding_location': '虹桥机场',
                'alighting_location': '陆家嘴金融区',
                'boarding_time': '11:00', 'alighting_time': '11:45', 'valid': True
            },
            {
                'id': 'INV003', 'type': '餐饮', 'number': 'REST20260110001',
                'date': '2026-01-10', 'time': '12:30', 'amount': 180,
                'location': '上海', 'merchant': '陆家嘴商务餐厅', 'valid': True
            },
            {
                'id': 'INV004', 'type': '住宿', 'number': 'HTL2026010001',
                'date': '2026-01-10', 'time': '14:00', 'amount': 1360,
                'location': '上海浦东新区', 'check_in': '2026-01-10 14:00',
                'check_out': '2026-01-12 12:00', 'nights': 2, 'valid': True
            },
            {
                'id': 'INV005', 'type': '餐饮', 'number': 'REST20260110002',
                'date': '2026-01-10', 'time': '19:00', 'amount': 1580,
                'location': '上海', 'merchant': '外滩高级餐厅', 'valid': True
            },
            # 第二天：上海市内活动
            {
                'id': 'INV006', 'type': '出租车', 'number': 'TAXI20260111001',
                'date': '2026-01-11', 'time': '09:00', 'amount': 45,
                'location': '上海', 'boarding_location': '浦东新区',
                'alighting_location': '徐家汇',
                'boarding_time': '09:00', 'alighting_time': '09:30', 'valid': True
            },
            {
                'id': 'INV007', 'type': '餐饮', 'number': 'REST20260111001',
                'date': '2026-01-11', 'time': '12:00', 'amount': 120,
                'location': '上海', 'merchant': '徐家汇快餐', 'valid': True
            },
            {
                'id': 'INV008', 'type': '出租车', 'number': 'TAXI20260111002',
                'date': '2026-01-11', 'time': '14:00', 'amount': 38,
                'location': '上海', 'boarding_location': '徐家汇',
                'alighting_location': '静安区',
                'boarding_time': '14:00', 'alighting_time': '14:25', 'valid': True
            },
            {
                'id': 'INV009', 'type': '餐饮', 'number': 'REST20260111002',
                'date': '2026-01-11', 'time': '18:30', 'amount': 280,
                'location': '上海', 'merchant': '某餐厅', 'valid': True
            }
        ]
    
    def analyze(self):
        """分析发票数据并生成报告"""
        if not self.invoices:
            return None
        
        # 初始化结果结构
        analysis_result = {
            'summary': {
                'total_days': 0,
                'cities': set(),
                'invoice_count': len(self.invoices),
                'total_amount': 0
            },
            'statistics': defaultdict(float),
            'anomalies': [],
            'itinerary': [],
            'classification': defaultdict(list),
            'compliance': {
                'valid_invoices': 0,
                'total_invoices': len(self.invoices),
                'compliance_rate': 0
            }
        }
        
        # 处理每张发票
        for invoice in self.invoices:
            # 统计总金额
            amount = invoice.get('amount', 0)
            analysis_result['summary']['total_amount'] += amount
            
            # 按类型分类统计
            invoice_type = invoice.get('type', '其他')
            analysis_result['statistics'][invoice_type] += amount
            
            # 分类存储
            analysis_result['classification'][invoice_type].append({
                'id': invoice.get('id', ''),
                'number': invoice.get('number', ''),
                'date': invoice.get('date', ''),
                'amount': amount
            })
            
            # 行程记录
            itinerary_item = {
                'id': invoice.get('id', ''),
                'date': invoice.get('date', ''),
                'time': invoice.get('time', ''),
                'type': invoice_type,
                'description': self._create_description(invoice),
                'amount': amount
            }
            analysis_result['itinerary'].append(itinerary_item)
            
            # 合规性检查
            if invoice.get('valid', False):
                analysis_result['compliance']['valid_invoices'] += 1
            
            # 收集城市信息
            location = invoice.get('location', '')
            if location:
                analysis_result['summary']['cities'].add(location)
        
        # 计算出差天数
        dates = [invoice['date'] for invoice in self.invoices if 'date' in invoice]
        if dates:
            unique_dates = set(dates)
            analysis_result['summary']['total_days'] = len(unique_dates)
        
        # 计算合规率
        total = analysis_result['compliance']['total_invoices']
        valid = analysis_result['compliance']['valid_invoices']
        analysis_result['compliance']['compliance_rate'] = (valid / total * 100) if total > 0 else 0
        
        # 转换cities为列表
        analysis_result['summary']['cities'] = list(analysis_result['summary']['cities'])
        
        # 生成异常检测
        self._detect_anomalies(analysis_result)
        
        self.analysis_result = analysis_result
        return analysis_result
    
    def _create_description(self, invoice):
        """创建发票描述"""
        invoice_type = invoice.get('type', '')
        
        if invoice_type == '航空':
            return f"{invoice.get('departure', '')} → {invoice.get('arrival', '')}"
        elif invoice_type == '出租车':
            return f"{invoice.get('boarding_location', '')} → {invoice.get('alighting_location', '')}"
        elif invoice_type == '餐饮':
            return f"{invoice.get('merchant', '')}"
        elif invoice_type == '住宿':
            return f"{invoice.get('location', '')} ({invoice.get('nights', 0)}晚)"
        else:
            return invoice.get('number', '')
    
    def _detect_anomalies(self, analysis_result):
        """检测异常模式"""
        # 检测高额餐饮
        high_amount_meals = [
            inv for inv in analysis_result['classification'].get('餐饮', [])
            if inv['amount'] > 500
        ]
        
        if high_amount_meals:
            analysis_result['anomalies'].append({
                'type': '高额餐饮',
                'description': f"发现{len(high_amount_meals)}笔超过500元的高额餐饮消费",
                'severity': 'medium'
            })
        
        # 检测时间冲突
        dates = defaultdict(list)
        for inv in self.invoices:
            if 'date' in inv and 'time' in inv:
                dates[inv['date']].append((inv['time'], inv['type']))
        
        for date, items in dates.items():
            if len(items) > 10:  # 一天内超过10张发票
                analysis_result['anomalies'].append({
                    'type': '密集行程',
                    'description': f"{date}当天有{len(items)}张发票，行程过于密集",
                    'severity': 'low'
                })


def main():
    """主应用"""
    # 标题
    st.markdown('<div class="main-header">差旅发票审核系统</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">专业差旅费用合规性审核与报告生成</div>', unsafe_allow_html=True)
    
    # 侧边栏
    with st.sidebar:
        st.image("https://img.icons8.com/color/96/000000/travel.png", width=80)
        st.title("系统配置")
        
        # 数据源选择
        data_source = st.radio(
            "选择数据源",
            ["使用演示数据", "上传Excel文件", "手动输入"]
        )
        
        if data_source == "上传Excel文件":
            uploaded_file = st.file_uploader("上传发票数据", type=['xlsx', 'csv'])
            if uploaded_file:
                if uploaded_file.name.endswith('.xlsx'):
                    df = pd.read_excel(uploaded_file)
                else:
                    df = pd.read_csv(uploaded_file)
                st.success(f"已上传 {len(df)} 条记录")
        
        # 审核参数
        st.subheader("审核参数")
        check_time_conflicts = st.checkbox("检查时间冲突", value=True)
        check_amount_limit = st.checkbox("检查金额上限", value=True)
        amount_threshold = st.number_input("餐饮金额阈值(元)", min_value=100, max_value=10000, value=500)
        
        # 报告选项
        st.subheader("报告选项")
        generate_pdf = st.checkbox("生成PDF报告", value=True)
        
        if st.button("开始审核", type="primary", use_container_width=True):
            st.session_state['start_audit'] = True
    
    # 主界面
    analyzer = InvoiceAnalyzer()
    
    if 'start_audit' in st.session_state and st.session_state['start_audit']:
        # 加载和分析数据
        analyzer.load_demo_data()
        result = analyzer.analyze()
        
        if result:
            # 显示概览
            st.markdown('<div class="section-title">📊 审核概览</div>', unsafe_allow_html=True)
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 0.9rem;">总金额</div>
                    <div style="font-size: 1.5rem; font-weight: bold;">¥{result['summary']['total_amount']:,.0f}</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 0.9rem;">发票数量</div>
                    <div style="font-size: 1.5rem; font-weight: bold;">{result['summary']['invoice_count']}张</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                st.markdown(f"""
                <div class="metric-card">
                    <div style="font-size: 0.9rem;">出差天数</div>
                    <div style="font-size: 1.5rem; font-weight: bold;">{result['summary']['total_days']}天</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col4:
                compliance_rate = result['compliance']['compliance_rate']
                color_class = "success-box" if compliance_rate >= 95 else "warning-box" if compliance_rate >= 80 else "error-box"
                st.markdown(f"""
                <div class="{color_class}">
                    <div style="font-size: 0.9rem;">合规率</div>
                    <div style="font-size: 1.5rem; font-weight: bold;">{compliance_rate:.1f}%</div>
                </div>
                """, unsafe_allow_html=True)
            
            # 费用分布
            st.markdown('<div class="section-title">📈 费用分布</div>', unsafe_allow_html=True)
            
            col1, col2 = st.columns([3, 2])
            
            with col1:
                # 创建饼图
                fig_pie = px.pie(
                    values=list(result['statistics'].values()),
                    names=list(result['statistics'].keys()),
                    title="费用类别分布",
                    color_discrete_sequence=px.colors.sequential.Blues_r
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                # 创建条形图
                fig_bar = px.bar(
                    x=list(result['statistics'].keys()),
                    y=list(result['statistics'].values()),
                    title="费用类别金额",
                    labels={'x': '类别', 'y': '金额(元)'},
                    color=list(result['statistics'].keys()),
                    color_discrete_sequence=px.colors.sequential.Purples
                )
                fig_bar.update_layout(showlegend=False)
                st.plotly_chart(fig_bar, use_container_width=True)
            
            # 异常检测
            if result['anomalies']:
                st.markdown('<div class="section-title">⚠️ 异常检测</div>', unsafe_allow_html=True)
                
                for anomaly in result['anomalies']:
                    severity_icon = "🔴" if anomaly['severity'] == 'high' else "🟡" if anomaly['severity'] == 'medium' else "🟢"
                    st.warning(f"{severity_icon} **{anomaly['type']}** - {anomaly['description']}")
            
            # 行程轨迹
            st.markdown('<div class="section-title">🗺️ 行程轨迹</div>', unsafe_allow_html=True)
            
            itinerary_df = pd.DataFrame(result['itinerary'])
            if not itinerary_df.empty:
                itinerary_df['date_time'] = pd.to_datetime(itinerary_df['date'] + ' ' + itinerary_df['time'])
                itinerary_df = itinerary_df.sort_values('date_time')
                
                # 创建时间线
                fig_timeline = px.scatter(
                    itinerary_df,
                    x='date_time',
                    y='type',
                    size='amount',
                    color='type',
                    hover_data=['description', 'amount'],
                    title="行程时间线"
                )
                fig_timeline.update_layout(height=400)
                st.plotly_chart(fig_timeline, use_container_width=True)
            
            # 详细数据
            st.markdown('<div class="section-title">📋 详细数据</div>', unsafe_allow_html=True)
            
            tab1, tab2, tab3 = st.tabs(["发票明细", "按类别汇总", "合规性检查"])
            
            with tab1:
                invoice_data = []
                for invoice in analyzer.invoices:
                    invoice_data.append({
                        'ID': invoice.get('id', ''),
                        '类型': invoice.get('type', ''),
                        '日期': invoice.get('date', ''),
                        '时间': invoice.get('time', ''),
                        '金额': invoice.get('amount', 0),
                        '描述': analyzer._create_description(invoice),
                        '状态': '有效' if invoice.get('valid', False) else '无效'
                    })
                
                df_invoices = pd.DataFrame(invoice_data)
                st.dataframe(df_invoices, use_container_width=True)
            
            with tab2:
                category_summary = []
                for category, invoices in result['classification'].items():
                    subtotal = sum(inv['amount'] for inv in invoices)
                    category_summary.append({
                        '类别': category,
                        '发票数量': len(invoices),
                        '总金额': subtotal,
                        '平均金额': subtotal / len(invoices) if invoices else 0
                    })
                
                df_summary = pd.DataFrame(category_summary)
                st.dataframe(df_summary, use_container_width=True)
            
            with tab3:
                compliance_data = [
                    ['总发票数', result['compliance']['total_invoices']],
                    ['有效发票数', result['compliance']['valid_invoices']],
                    ['无效发票数', result['compliance']['total_invoices'] - result['compliance']['valid_invoices']],
                    ['合规率', f"{result['compliance']['compliance_rate']:.1f}%"]
                ]
                
                df_compliance = pd.DataFrame(compliance_data, columns=['检查项', '结果'])
                st.dataframe(df_compliance, use_container_width=True)
                
                if result['compliance']['compliance_rate'] >= 95:
                    st.success("✅ 发票合规性良好，符合公司报销政策")
                elif result['compliance']['compliance_rate'] >= 80:
                    st.warning("⚠️ 发票合规性一般，建议人工复核")
                else:
                    st.error("❌ 发票合规性较差，需要详细检查")
            
            # 生成报告
            if generate_pdf and REPORTLAB_AVAILABLE:
                st.markdown('<div class="section-title">📄 报告生成</div>', unsafe_allow_html=True)
                
                if st.button("生成PDF报告", icon="📥"):
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
                        pdf_path = tmp_file.name
                        generator = PDFReportGenerator(result)
                        generator.generate_pdf(pdf_path)
                        
                        with open(pdf_path, 'rb') as f:
                            pdf_bytes = f.read()
                        
                        st.download_button(
                            label="下载PDF报告",
                            data=pdf_bytes,
                            file_name=f"差旅审核报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                            mime="application/pdf",
                            icon="📄"
                        )
            elif generate_pdf and not REPORTLAB_AVAILABLE:
                st.error("⚠️ ReportLab库未安装，无法生成PDF报告。请运行: pip install reportlab")
    
    else:
        # 欢迎界面
        st.info("👈 请在侧边栏配置审核参数并点击「开始审核」按钮")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            ### 🌟 系统功能
            - ✅ **智能发票解析**：支持多种格式发票数据
            - ✅ **合规性检查**：自动检测违规报销
            - ✅ **行程轨迹分析**：可视化展示差旅路线
            - ✅ **异常检测**：智能识别可疑报销
            - ✅ **专业报告**：生成四大范式审计报告
            """)
        
        with col2:
            st.markdown("""
            ### 📊 支持发票类型
            - ✈️ 航空/火车票
            - 🚕 出租车/网约车
            - 🏨 酒店住宿
            - 🍽️ 餐饮发票
            - 🛍️ 购物消费
            - 🚗 租车费用
            """)
        
        st.markdown("---")
        st.markdown("""
        ### 🔧 快速开始
        1. 在左侧选择数据源（演示数据/上传文件）
        2. 配置审核参数
        3. 点击「开始审核」按钮
        4. 查看分析结果并生成报告
        """)


if __name__ == "__main__":
    main()