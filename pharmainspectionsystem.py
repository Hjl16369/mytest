import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json

# 页面配置
st.set_page_config(
    page_title="正掌讯医药市场稽查管理系统",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS样式
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #4F46E5 0%, #4338CA 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .stat-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: bold;
        margin: 0.5rem 0;
    }
    .alert-card {
        border-left: 4px solid #EF4444;
        padding: 1rem;
        background: #FEF2F2;
        border-radius: 5px;
        margin: 0.5rem 0;
    }
    .case-card {
        border: 1px solid #E5E7EB;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
        background: white;
    }
    .blacklist-card {
        border: 2px solid #FCA5A5;
        background: #FEF2F2;
        padding: 1.5rem;
        border-radius: 10px;
        margin: 1rem 0;
    }
    .progress-bar {
        background: #E5E7EB;
        border-radius: 10px;
        height: 10px;
        overflow: hidden;
    }
    .progress-fill {
        background: linear-gradient(90deg, #6366F1 0%, #4F46E5 100%);
        height: 100%;
        border-radius: 10px;
    }
    .approval-card {
        border: 2px solid #C7D2FE;
        border-radius: 10px;
        padding: 2rem;
        background: linear-gradient(135deg, white 0%, #EEF2FF 100%);
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# 初始化session state
if 'active_module' not in st.session_state:
    st.session_state.active_module = 'dashboard'
if 'date_range' not in st.session_state:
    st.session_state.date_range = '30days'
if 'selected_region' not in st.session_state:
    st.session_state.selected_region = 'all'

# 模拟数据
dashboard_stats = {
    'active_alerts': 23,
    'pending_cases': 15,
    'investigating': 8,
    'this_month_cases': 42,
    'resolved_rate': 87.5,
    'avg_response_time': 4.2,
    'blacklist_count': 12,
    'total_penalty': 2580000
}

recent_alerts = [
    {
        'id': 'A001',
        'type': 'divert',
        'severity': 'high',
        'product': '阿莫西林胶囊 0.5g×24粒',
        'distributor': '华东医药商业有限公司',
        'source_region': '上海市',
        'target_region': '江苏省南京市',
        'amount': 580,
        'detected_time': '2024-11-14 09:23',
        'status': 'pending',
        'risk_score': 92
    },
    {
        'id': 'A002',
        'type': 'price',
        'severity': 'high',
        'product': '布洛芬缓释胶囊 0.3g×20粒',
        'distributor': '江苏康泽医药有限公司',
        'region': '江苏省',
        'price_deviation': -27.5,
        'amount': 320,
        'detected_time': '2024-11-14 08:45',
        'status': 'pending',
        'risk_score': 88
    },
    {
        'id': 'A003',
        'type': 'divert',
        'severity': 'medium',
        'product': '头孢克肟分散片',
        'distributor': '广州德信医药有限公司',
        'source_region': '广东省',
        'target_region': '湖南省',
        'amount': 420,
        'detected_time': '2024-11-13 15:42',
        'status': 'assigned',
        'risk_score': 75
    }
]

cases = [
    {
        'id': 'C2024110001',
        'title': '上海华东医药严重窜货案',
        'type': 'divert',
        'severity': 'high',
        'distributor': '华东医药商业有限公司',
        'region': '华东区',
        'created_date': '2024-11-10',
        'assignee': '张伟',
        'status': 'investigating',
        'progress': 60,
        'estimated_loss': 125000,
        'deadline': '2024-11-20'
    },
    {
        'id': 'C2024110002',
        'title': '江苏康泽恶意低价倾销',
        'type': 'price',
        'severity': 'high',
        'distributor': '江苏康泽医药有限公司',
        'region': '华东区',
        'created_date': '2024-11-11',
        'assignee': '李娜',
        'status': 'evidence-collection',
        'progress': 45,
        'estimated_loss': 89000,
        'deadline': '2024-11-21'
    },
    {
        'id': 'C2024110003',
        'title': '广东德信跨区域销售',
        'type': 'divert',
        'severity': 'medium',
        'distributor': '广州德信医药有限公司',
        'region': '华南区',
        'created_date': '2024-11-12',
        'assignee': '王强',
        'status': 'pending-approval',
        'progress': 85,
        'estimated_loss': 56000,
        'deadline': '2024-11-18'
    }
]

blacklist = [
    {
        'id': 'BL001',
        'name': '上海某医药贸易公司',
        'type': '经销商',
        'violations': 3,
        'total_penalty': 450000,
        'status': 'blacklisted',
        'added_date': '2024-09-15',
        'expiry_date': '2025-09-15',
        'last_violation': '严重窜货'
    },
    {
        'id': 'BL002',
        'name': '江苏某药业有限公司',
        'type': '经销商',
        'violations': 2,
        'total_penalty': 280000,
        'status': 'suspended',
        'added_date': '2024-10-20',
        'expiry_date': '2025-04-20',
        'last_violation': '恶意低价'
    }
]

# 趋势数据
trend_data = pd.DataFrame({
    'month': ['5月', '6月', '7月', '8月', '9月', '10月', '11月'],
    'divert': [12, 15, 18, 14, 20, 25, 28],
    'price': [8, 10, 12, 9, 15, 18, 14],
    'mixed': [2, 3, 4, 2, 5, 6, 4],
    'resolved': [18, 22, 28, 20, 32, 38, 42]
})

region_data = pd.DataFrame({
    'region': ['华东区', '华南区', '华北区', '西南区', '华中区', '东北区', '西北区'],
    'cases': [45, 38, 32, 28, 25, 18, 12],
    'penalty': [1250000, 980000, 850000, 720000, 650000, 450000, 320000],
    'rate': [88, 85, 90, 82, 86, 92, 89]
})

case_type_data = pd.DataFrame({
    'name': ['窜货案件', '乱价案件', '混合违规'],
    'value': [128, 56, 14],
    'color': ['#EF4444', '#F59E0B', '#8B5CF6']
})

# 辅助函数
def get_severity_badge(severity):
    colors = {
        'high': ('🔴', '高风险', '#FEE2E2', '#991B1B'),
        'medium': ('🟡', '中风险', '#FEF3C7', '#92400E'),
        'low': ('🔵', '低风险', '#DBEAFE', '#1E40AF')
    }
    icon, text, bg, fg = colors.get(severity, ('⚪', '未知', '#F3F4F6', '#374151'))
    return f'<span style="background:{bg}; color:{fg}; padding:4px 12px; border-radius:12px; font-size:0.85rem; font-weight:600;">{icon} {text}</span>'

def get_status_badge(status):
    status_map = {
        'pending': ('⏳', '待处理', '#FEE2E2', '#991B1B'),
        'assigned': ('📋', '已分配', '#DBEAFE', '#1E40AF'),
        'investigating': ('🔍', '调查中', '#E9D5FF', '#6B21A8'),
        'evidence-collection': ('📸', '取证中', '#E0E7FF', '#3730A3'),
        'pending-approval': ('📝', '待审批', '#FEF3C7', '#92400E'),
        'approved': ('✅', '已审批', '#D1FAE5', '#065F46'),
        'executing': ('⚙️', '执行中', '#CCFBF1', '#115E59'),
        'closed': ('✔️', '已结案', '#F3F4F6', '#374151'),
        'blacklisted': ('🚫', '黑名单', '#FEE2E2', '#991B1B'),
        'suspended': ('⏸️', '暂停合作', '#FED7AA', '#9A3412')
    }
    icon, text, bg, fg = status_map.get(status, ('⚪', '未知', '#F3F4F6', '#374151'))
    return f'<span style="background:{bg}; color:{fg}; padding:4px 12px; border-radius:12px; font-size:0.85rem; font-weight:600;">{icon} {text}</span>'

# 顶部导航栏
st.markdown("""
<div class="main-header">
    <div style="display: flex; justify-content: space-between; align-items: center;">
        <div>
            <h1 style="margin:0; font-size:1.8rem;">🛡️ 正掌讯医药市场稽查管理系统</h1>
            <p style="margin:0.5rem 0 0 0; opacity:0.9; font-size:0.9rem;">Pharmaceutical Market Inspection Management System</p>
        </div>
        <div style="display: flex; gap: 2rem; align-items: center;">
            <div style="text-align: center;">
                <div style="font-size: 0.75rem; opacity: 0.8;">今日报警</div>
                <div style="font-size: 1.5rem; font-weight: bold;">8</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 0.75rem; opacity: 0.8;">待处理</div>
                <div style="font-size: 1.5rem; font-weight: bold;">15</div>
            </div>
            <div style="text-align: center;">
                <div style="font-size: 0.75rem; opacity: 0.8;">本月结案</div>
                <div style="font-size: 1.5rem; font-weight: bold;">42</div>
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# 侧边栏导航
with st.sidebar:
    st.markdown("### 📊 系统导航")
    
    modules = {
        'dashboard': ('📈', '监控驾驶舱'),
        'cases': ('📋', f'案件管理 ({len(cases)})'),
        'investigation': ('🔍', '调查取证'),
        'approval': ('✅', '审批决策'),
        'blacklist': ('🚫', f'黑名单管理 ({len(blacklist)})'),
        'analysis': ('📊', '数据分析')
    }
    
    for key, (icon, label) in modules.items():
        if st.button(f"{icon} {label}", key=f"nav_{key}", use_container_width=True):
            st.session_state.active_module = key
            st.rerun()
    
    st.markdown("---")
    st.markdown("### 📅 本月概览")
    st.metric("新增案件", "42")
    st.metric("已结案", "38", delta="6", delta_color="normal")
    st.metric("处罚金额", "¥258万", delta="¥42万", delta_color="inverse")
    
    st.markdown("---")
    st.markdown("**当前用户**")
    st.info("👤 张伟 - 华东区经理")

# 主内容区域
if st.session_state.active_module == 'dashboard':
    st.markdown("## 📈 监控驾驶舱")
    
    # 关键指标卡片
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #EF4444 0%, #DC2626 100%); padding: 1.5rem; border-radius: 10px; color: white;">
            <div style="font-size: 2.5rem; font-weight: bold;">{dashboard_stats['active_alerts']}</div>
            <div style="font-size: 1.1rem; margin-top: 0.5rem;">活跃报警</div>
            <div style="font-size: 0.85rem; opacity: 0.9; margin-top: 0.3rem;">需要立即关注处理</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%); padding: 1.5rem; border-radius: 10px; color: white;">
            <div style="font-size: 2.5rem; font-weight: bold;">{dashboard_stats['pending_cases']}</div>
            <div style="font-size: 1.1rem; margin-top: 0.5rem;">待处理案件</div>
            <div style="font-size: 0.85rem; opacity: 0.9; margin-top: 0.3rem;">本月新增 {dashboard_stats['this_month_cases']} 件</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #8B5CF6 0%, #7C3AED 100%); padding: 1.5rem; border-radius: 10px; color: white;">
            <div style="font-size: 2.5rem; font-weight: bold;">{dashboard_stats['investigating']}</div>
            <div style="font-size: 1.1rem; margin-top: 0.5rem;">调查中案件</div>
            <div style="font-size: 0.85rem; opacity: 0.9; margin-top: 0.3rem;">平均 {dashboard_stats['avg_response_time']} 天响应</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col4:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #10B981 0%, #059669 100%); padding: 1.5rem; border-radius: 10px; color: white;">
            <div style="font-size: 2.5rem; font-weight: bold;">{dashboard_stats['resolved_rate']}%</div>
            <div style="font-size: 1.1rem; margin-top: 0.5rem;">结案率</div>
            <div style="font-size: 0.85rem; opacity: 0.9; margin-top: 0.3rem;">处罚金额 ¥{dashboard_stats['total_penalty']//10000}万</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # 实时报警和统计
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.markdown("### 🚨 实时报警监控")
        for alert in recent_alerts[:3]:
            severity_badge = get_severity_badge(alert['severity'])
            status_badge = get_status_badge(alert['status'])
            alert_type = '窜货' if alert['type'] == 'divert' else '乱价'
            
            st.markdown(f"""
            <div class="alert-card">
                <div style="display: flex; justify-content: space-between; align-items: start;">
                    <div style="flex: 1;">
                        <div style="margin-bottom: 0.5rem;">
                            {severity_badge} {status_badge}
                            <span style="color: #6B7280; font-size: 0.85rem; margin-left: 0.5rem;">{alert['detected_time']}</span>
                        </div>
                        <div style="font-weight: 600; font-size: 1.05rem; margin-bottom: 0.3rem;">{alert['product']}</div>
                        <div style="color: #4B5563; font-size: 0.9rem; margin-bottom: 0.3rem;">{alert['distributor']}</div>
                        <div style="color: #6B7280; font-size: 0.85rem;">
                            {'📍 ' + alert['source_region'] + ' → ' + alert['target_region'] if alert['type'] == 'divert' else '💰 价格偏离 ' + str(alert.get('price_deviation', 0)) + '%'}
                        </div>
                    </div>
                    <div style="background: #FEE2E2; padding: 1rem; border-radius: 8px; text-align: center; margin-left: 1rem;">
                        <div style="font-size: 0.75rem; color: #6B7280;">风险评分</div>
                        <div style="font-size: 1.8rem; font-weight: bold; color: #DC2626;">{alert['risk_score']}</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    with col_right:
        st.markdown("### 📊 案件类型分布")
        st.markdown("""
        <div style="background: white; padding: 1rem; border-radius: 10px;">
            <div style="margin-bottom: 1rem;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 0.3rem;">
                    <span style="font-size: 0.9rem;">窜货案件</span>
                    <span style="font-weight: 600;">65%</span>
                </div>
                <div style="background: #E5E7EB; border-radius: 10px; height: 8px; overflow: hidden;">
                    <div style="background: #EF4444; width: 65%; height: 100%;"></div>
                </div>
            </div>
            <div style="margin-bottom: 1rem;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 0.3rem;">
                    <span style="font-size: 0.9rem;">乱价案件</span>
                    <span style="font-weight: 600;">28%</span>
                </div>
                <div style="background: #E5E7EB; border-radius: 10px; height: 8px; overflow: hidden;">
                    <div style="background: #F59E0B; width: 28%; height: 100%;"></div>
                </div>
            </div>
            <div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 0.3rem;">
                    <span style="font-size: 0.9rem;">混合违规</span>
                    <span style="font-weight: 600;">7%</span>
                </div>
                <div style="background: #E5E7EB; border-radius: 10px; height: 8px; overflow: hidden;">
                    <div style="background: #8B5CF6; width: 7%; height: 100%;"></div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### 📍 高发区域TOP5")
        regions = ['华东区', '华南区', '华北区', '西南区', '华中区']
        counts = [15, 13, 11, 9, 7]
        for i, (region, count) in enumerate(zip(regions, counts)):
            medal = '🥇' if i == 0 else '🥈' if i == 1 else '🥉' if i == 2 else '  '
            st.markdown(f"{medal} **{region}**: {count} 件")

elif st.session_state.active_module == 'cases':
    st.markdown("## 📋 案件管理")
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        status_filter = st.selectbox("案件状态", ["全部状态", "待处理", "调查中", "待审批"])
    with col2:
        region_filter = st.selectbox("所属区域", ["全部区域", "华东区", "华南区", "华北区"])
    with col3:
        st.markdown("<div style='margin-top: 1.8rem;'></div>", unsafe_allow_html=True)
        if st.button("📥 导出报表", use_container_width=True):
            st.success("报表导出成功!")
    
    st.markdown("---")
    
    for case in cases:
        severity_badge = get_severity_badge(case['severity'])
        status_badge = get_status_badge(case['status'])
        
        st.markdown(f"""
        <div class="case-card">
            <div style="margin-bottom: 1rem;">
                <span style="background: #F3F4F6; padding: 4px 12px; border-radius: 12px; font-size: 0.85rem; font-weight: 600; margin-right: 0.5rem;">{case['id']}</span>
                {severity_badge}
                {status_badge}
            </div>
            <h3 style="margin: 0.5rem 0; font-size: 1.2rem;">{case['title']}</h3>
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.5rem; margin: 1rem 0;">
                <div>
                    <div style="color: #6B7280; font-size: 0.85rem;">涉及主体</div>
                    <div style="font-weight: 600; margin-top: 0.3rem;">{case['distributor']}</div>
                </div>
                <div>
                    <div style="color: #6B7280; font-size: 0.85rem;">所属区域</div>
                    <div style="font-weight: 600; margin-top: 0.3rem;">{case['region']}</div>
                </div>
                <div>
                    <div style="color: #6B7280; font-size: 0.85rem;">调查人员</div>
                    <div style="font-weight: 600; margin-top: 0.3rem;">{case['assignee']}</div>
                </div>
                <div>
                    <div style="color: #6B7280; font-size: 0.85rem;">预估损失</div>
                    <div style="font-weight: 600; color: #DC2626; font-size: 1.1rem; margin-top: 0.3rem;">¥{case['estimated_loss']:,}</div>
                </div>
            </div>
            <div style="border-top: 1px solid #E5E7EB; padding-top: 1rem; margin-top: 1rem;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                    <span style="font-size: 0.9rem; font-weight: 500;">调查进度</span>
                    <span style="font-weight: 600;">{case['progress']}%</span>
                </div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: {case['progress']}%;"></div>
                </div>
                <div style="display: flex; justify-content: space-between; margin-top: 0.5rem; font-size: 0.75rem; color: #6B7280;">
                    <span>立案日期: {case['created_date']}</span>
                    <span>截止日期: {case['deadline']}</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

elif st.session_state.active_module == 'investigation':
    st.markdown("## 🔍 调查取证工作台")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div style="border: 2px solid #C7D2FE; border-radius: 10px; padding: 1.5rem; background: white;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h3 style="margin: 0; font-size: 1.1rem;">📄 在线证据</h3>
            </div>
            <ul style="list-style: none; padding: 0;">
                <li style="margin: 0.8rem 0;">✅ 流向数据记录 (23条)</li>
                <li style="margin: 0.8rem 0;">✅ 批次追踪信息 (8批次)</li>
                <li style="margin: 0.8rem 0;">✅ 价格变动记录 (15条)</li>
                <li style="margin: 0.8rem 0;">✅ 供应链关系图</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        if st.button("查看详情", key="evidence_detail", use_container_width=True):
            st.info("证据详情查看")
    
    with col2:
        st.markdown("""
        <div style="border: 2px solid #DDD6FE; border-radius: 10px; padding: 1.5rem; background: white;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h3 style="margin: 0; font-size: 1.1rem;">📸 现场调查</h3>
            </div>
            <ul style="list-style: none; padding: 0;">
                <li style="margin: 0.8rem 0;">📷 现场照片 (12张)</li>
                <li style="margin: 0.8rem 0;">🎙️ 访谈录音 (3段)</li>
                <li style="margin: 0.8rem 0;">📝 调查笔录 (5份)</li>
                <li style="margin: 0.8rem 0;">📍 GPS定位记录</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        if st.button("上传证据", key="upload_evidence", use_container_width=True):
            st.info("证据上传功能")
    
    with col3:
        st.markdown("""
        <div style="border: 2px solid #BBF7D0; border-radius: 10px; padding: 1.5rem; background: white;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <h3 style="margin: 0; font-size: 1.1rem;">🛡️ 证据链校验</h3>
            </div>
            <div style="margin: 1rem 0;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 0.5rem;">
                    <span>完整性评分</span>
                    <span style="font-weight: bold; color: #10B981; font-size: 1.3rem;">95%</span>
                </div>
                <div class="progress-bar">
                    <div style="background: #10B981; width: 95%; height: 100%; border-radius: 10px;"></div>
                </div>
            </div>
            <ul style="list-style: none; padding: 0; font-size: 0.9rem;">
                <li style="margin: 0.5rem 0;">✅ 时间线完整</li>
                <li style="margin: 0.5rem 0;">✅ 证据可追溯</li>
                <li style="margin: 0.5rem 0;">⚠️ 待补充：终端验证</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        if st.button("生成报告", key="generate_report", use_container_width=True):
            st.success("报告已生成!")
    
    st.markdown("---")
    
    # 供应链追溯图谱
    st.markdown("### 🔗 供应链追溯图谱")
    st.markdown("""
    <div style="background: linear-gradient(135deg, #F9FAFB 0%, #EFF6FF 100%); border: 2px solid #E5E7EB; border-radius: 10px; padding: 2rem;">
        <div style="display: flex; justify-content: space-around; align-items: center;">
            <div style="text-align: center;">
                <div style="width: 80px; height: 80px; background: linear-gradient(135deg, #3B82F6, #2563EB); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; margin: 0 auto 0.5rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">厂家</div>
                <div style="font-weight: 600;">华东制药</div>
            </div>
            <div style="font-size: 2rem; color: #9CA3AF;">→</div>
            <div style="text-align: center;">
                <div style="width: 80px; height: 80px; background: linear-gradient(135deg, #F59E0B, #D97706); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; margin: 0 auto 0.5rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">一级</div>
                <div style="font-weight: 600;">华东医药</div>
                <div style="color: #DC2626; font-size: 0.8rem; font-weight: 600;">授权：上海</div>
            </div>
            <div style="font-size: 2rem; color: #9CA3AF;">→</div>
            <div style="text-align: center;">
                <div style="width: 80px; height: 80px; background: linear-gradient(135deg, #F97316, #EA580C); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; margin: 0 auto 0.5rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">二级</div>
                <div style="font-weight: 600;">江苏康泽</div>
                <div style="color: #DC2626; font-size: 0.8rem; font-weight: 600;">违规：南京</div>
            </div>
            <div style="font-size: 2rem; color: #9CA3AF;">→</div>
            <div style="text-align: center;">
                <div style="width: 80px; height: 80px; background: linear-gradient(135deg, #EF4444, #DC2626); border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; margin: 0 auto 0.5rem; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">终端</div>
                <div style="font-weight: 600;">某医院</div>
                <div style="color: #DC2626; font-size: 0.8rem; font-weight: 600;">检出地</div>
            </div>
        </div>
        <div style="background: #FEE2E2; border: 2px solid #FCA5A5; border-radius: 8px; padding: 1rem; margin-top: 1.5rem;">
            <strong style="color: #991B1B;">违规行为：</strong>
            <span style="color: #991B1B;">华东医药将授权在上海销售的产品通过江苏康泽流向南京市场，跨区域销售构成窜货</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

elif st.session_state.active_module == 'approval':
    st.markdown("## ✅ 处罚决策审批")
    
    # 审批卡片
    st.markdown("""
    <div class="approval-card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem;">
            <div>
                <h3 style="margin: 0; font-size: 1.3rem;">案件：C2024110001</h3>
                <p style="margin: 0.5rem 0 0 0; color: #6B7280;">上海华东医药严重窜货案</p>
            </div>
            <span style="background: #FEF3C7; color: #92400E; padding: 8px 20px; border-radius: 20px; font-weight: 600; border: 2px solid #FCD34D;">⏳ 待审批</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # 违规事实认定
    st.markdown("""
    <div style="background: white; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; border: 1px solid #E5E7EB;">
        <h4 style="margin: 0 0 1rem 0; font-weight: 600;">📋 违规事实认定</h4>
        <ul style="margin: 0; padding-left: 1.5rem; line-height: 1.8;">
            <li>将授权在上海地区销售的阿莫西林胶囊580盒，通过江苏康泽医药流向南京市场</li>
            <li>批次号20241015可追溯，证据链完整</li>
            <li>造成区域市场价格混乱，预估损失12.5万元</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # 处罚建议
    st.markdown("""
    <div style="background: #FEF2F2; border-radius: 8px; padding: 1.5rem; margin-bottom: 1.5rem; border: 1px solid #FCA5A5;">
        <h4 style="margin: 0 0 1rem 0; font-weight: 600;">⚖️ 处罚建议</h4>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-bottom: 1rem;">
            <div style="background: white; padding: 1rem; border-radius: 8px; border-left: 4px solid #EF4444;">
                <div style="font-size: 0.75rem; color: #6B7280; margin-bottom: 0.3rem;">经济处罚</div>
                <div style="font-size: 1.8rem; font-weight: bold; color: #DC2626;">¥150,000</div>
            </div>
            <div style="background: white; padding: 1rem; border-radius: 8px; border-left: 4px solid #F97316;">
                <div style="font-size: 0.75rem; color: #6B7280; margin-bottom: 0.3rem;">暂停供货</div>
                <div style="font-size: 1.8rem; font-weight: bold; color: #EA580C;">6个月</div>
            </div>
        </div>
        <p style="margin: 0; font-size: 0.9rem;">建议对华东医药处以罚款15万元，并暂停供货资格6个月，要求提交整改方案</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 审批流程
    st.markdown("""
    <div style="border-top: 2px solid #E5E7EB; padding-top: 1.5rem; margin-bottom: 1.5rem;">
        <h4 style="margin: 0 0 1.5rem 0; font-weight: 600;">🔄 审批流程</h4>
    </div>
    """, unsafe_allow_html=True)
    
    # 审批步骤
    approval_steps = [
        ('✅', '区域经理审核', '张伟 - 2024-11-14 10:30 已通过', '#10B981'),
        ('✅', '大区总监审批', '李娜 - 2024-11-14 14:20 已通过', '#10B981'),
        ('⏳', '总部审批', '等待审批中...', '#F59E0B'),
        ('⏸️', '法务审核', '待前序审批完成', '#9CA3AF')
    ]
    
    for icon, title, desc, color in approval_steps:
        st.markdown(f"""
        <div style="display: flex; align-items: center; margin-bottom: 1.5rem;">
            <div style="width: 40px; height: 40px; background: {color}; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: white; font-size: 1.2rem; flex-shrink: 0;">{icon}</div>
            <div style="margin-left: 1rem;">
                <div style="font-weight: 600; font-size: 0.95rem;">{title}</div>
                <div style="font-size: 0.85rem; color: #6B7280; margin-top: 0.2rem;">{desc}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # 操作按钮
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("✅ 批准处罚", use_container_width=True, type="primary"):
            st.success("✅ 处罚决策已批准!")
    with col2:
        if st.button("❌ 驳回重审", use_container_width=True):
            st.warning("⚠️ 已驳回，需要重新审核")
    with col3:
        if st.button("📝 补充调查", use_container_width=True):
            st.info("📋 已要求补充调查材料")

elif st.session_state.active_module == 'blacklist':
    st.markdown("## 🚫 违规主体黑名单")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        search_term = st.text_input("🔍 搜索企业名称...", placeholder="输入企业名称进行搜索")
    with col2:
        st.markdown("<div style='margin-top: 1.8rem;'></div>", unsafe_allow_html=True)
        if st.button("🚫 添加黑名单", use_container_width=True):
            st.info("添加黑名单功能")
    
    st.markdown("---")
    
    for item in blacklist:
        status_badge = get_status_badge(item['status'])
        
        st.markdown(f"""
        <div class="blacklist-card">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <div style="flex: 1;">
                    <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                        <div style="font-size: 1.5rem; margin-right: 0.5rem;">🚫</div>
                        <h3 style="margin: 0; font-size: 1.2rem;">{item['name']}</h3>
                        <div style="margin-left: 1rem;">{status_badge}</div>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 1.5rem;">
                        <div>
                            <div style="color: #6B7280; font-size: 0.85rem;">主体类型</div>
                            <div style="font-weight: 600; margin-top: 0.3rem;">{item['type']}</div>
                        </div>
                        <div>
                            <div style="color: #6B7280; font-size: 0.85rem;">违规次数</div>
                            <div style="font-weight: 600; color: #DC2626; font-size: 1.1rem; margin-top: 0.3rem;">{item['violations']} 次</div>
                        </div>
                        <div>
                            <div style="color: #6B7280; font-size: 0.85rem;">累计处罚</div>
                            <div style="font-weight: 600; color: #DC2626; font-size: 1.1rem; margin-top: 0.3rem;">¥{item['total_penalty']:,}</div>
                        </div>
                        <div>
                            <div style="color: #6B7280; font-size: 0.85rem;">最近违规</div>
                            <div style="font-weight: 600; margin-top: 0.3rem;">{item['last_violation']}</div>
                        </div>
                    </div>
                    <div style="margin-top: 1rem; padding-top: 1rem; border-top: 1px solid #FCA5A5; display: flex; justify-content: space-between; font-size: 0.85rem; color: #6B7280;">
                        <span>加入日期: {item['added_date']}</span>
                        <span>到期日期: {item['expiry_date']}</span>
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button(f"查看详情 - {item['id']}", key=f"view_{item['id']}", use_container_width=True):
                st.info(f"查看 {item['name']} 详情")
        with col2:
            if st.button(f"解除限制 - {item['id']}", key=f"remove_{item['id']}", use_container_width=True):
                st.success(f"已解除 {item['name']} 的限制")
    
    st.markdown("---")
    st.markdown("### 📋 处罚措施说明")
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div style="border: 2px solid #FCD34D; background: #FFFBEB; padding: 1.5rem; border-radius: 10px;">
            <div style="display: flex; align-items: center; margin-bottom: 0.8rem;">
                <span style="font-size: 1.5rem; margin-right: 0.5rem;">⚠️</span>
                <h4 style="margin: 0;">暂停合作（6个月）</h4>
            </div>
            <p style="margin: 0; font-size: 0.9rem; color: #92400E;">首次或轻微违规，暂停供货资格，整改后可恢复</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style="border: 2px solid #FCA5A5; background: #FEF2F2; padding: 1.5rem; border-radius: 10px;">
            <div style="display: flex; align-items: center; margin-bottom: 0.8rem;">
                <span style="font-size: 1.5rem; margin-right: 0.5rem;">🚫</span>
                <h4 style="margin: 0;">永久黑名单</h4>
            </div>
            <p style="margin: 0; font-size: 0.9rem; color: #991B1B;">严重或多次违规，永久取消合作资格</p>
        </div>
        """, unsafe_allow_html=True)

elif st.session_state.active_module == 'analysis':
    st.markdown("## 📊 数据分析中心")
    
    # 筛选控制栏
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        date_range = st.selectbox("时间范围", ["近7天", "近30天", "近90天", "本年度"])
    with col2:
        region = st.selectbox("区域选择", ["全部区域", "华东区", "华南区", "华北区"])
    with col3:
        st.markdown("<div style='margin-top: 1.8rem;'></div>", unsafe_allow_html=True)
        if st.button("📥 导出分析报告", use_container_width=True):
            st.success("分析报告已导出!")
    
    st.markdown("---")
    
    # 案件趋势分析
    st.markdown("### 📈 案件趋势分析")
    fig_trend = go.Figure()
    fig_trend.add_trace(go.Scatter(
        x=trend_data['month'], 
        y=trend_data['divert'],
        mode='lines+markers',
        name='窜货案件',
        line=dict(color='#EF4444', width=3),
        fill='tozeroy',
        fillcolor='rgba(239, 68, 68, 0.2)'
    ))
    fig_trend.add_trace(go.Scatter(
        x=trend_data['month'], 
        y=trend_data['price'],
        mode='lines+markers',
        name='乱价案件',
        line=dict(color='#F59E0B', width=3),
        fill='tozeroy',
        fillcolor='rgba(245, 158, 11, 0.2)'
    ))
    fig_trend.add_trace(go.Scatter(
        x=trend_data['month'], 
        y=trend_data['resolved'],
        mode='lines+markers',
        name='已结案',
        line=dict(color='#10B981', width=3),
        fill='tozeroy',
        fillcolor='rgba(16, 185, 129, 0.2)'
    ))
    fig_trend.update_layout(
        height=400,
        hovermode='x unified',
        plot_bgcolor='white',
        paper_bgcolor='white',
        font=dict(family="Arial, sans-serif", size=12),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_trend, use_container_width=True)
    
    # 区域对比分析
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📍 区域案件分布")
        fig_region = px.bar(
            region_data, 
            x='region', 
            y='cases',
            color='cases',
            color_continuous_scale=['#DBEAFE', '#3B82F6', '#1E40AF'],
            labels={'cases': '案件数', 'region': '区域'}
        )
        fig_region.update_layout(height=350, showlegend=False, plot_bgcolor='white')
        st.plotly_chart(fig_region, use_container_width=True)
    
    with col2:
        st.markdown("### 💰 区域处罚金额")
        fig_penalty = px.bar(
            region_data, 
            x='region', 
            y='penalty',
            color='penalty',
            color_continuous_scale=['#FEE2E2', '#EF4444', '#991B1B'],
            labels={'penalty': '处罚金额', 'region': '区域'}
        )
        fig_penalty.update_layout(height=350, showlegend=False, plot_bgcolor='white')
        st.plotly_chart(fig_penalty, use_container_width=True)
    
    # 案件类型和响应时间
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📊 案件类型统计")
        fig_pie = px.pie(
            case_type_data, 
            values='value', 
            names='name',
            color='name',
            color_discrete_map={'窜货案件': '#EF4444', '乱价案件': '#F59E0B', '混合违规': '#8B5CF6'},
            hole=0.4
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        fig_pie.update_layout(height=350, showlegend=True)
        st.plotly_chart(fig_pie, use_container_width=True)
    
    with col2:
        st.markdown("### ⏱️ 平均响应时间（天）")
        response_time_data = pd.DataFrame({
            'type': ['立案响应', '调查完成', '审批决策', '处罚执行'],
            'time': [2.3, 8.5, 3.2, 12.8],
            'target': [4, 10, 5, 15]
        })
        fig_response = go.Figure()
        fig_response.add_trace(go.Bar(
            name='实际时间',
            x=response_time_data['type'],
            y=response_time_data['time'],
            marker_color='#3B82F6'
        ))
        fig_response.add_trace(go.Bar(
            name='目标时间',
            x=response_time_data['type'],
            y=response_time_data['target'],
            marker_color='#D1D5DB'
        ))
        fig_response.update_layout(height=350, barmode='group', plot_bgcolor='white')
        st.plotly_chart(fig_response, use_container_width=True)
    
    # 关键数据洞察
    st.markdown("---")
    st.markdown("### 💡 关键数据洞察")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div style="background: white; border-radius: 10px; padding: 1.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem;">
                <span style="font-size: 2rem;">📉</span>
                <span style="font-size: 2rem; font-weight: bold; color: #10B981;">-32%</span>
            </div>
            <div style="font-weight: 600; margin-bottom: 0.3rem;">违规案件环比</div>
            <div style="font-size: 0.85rem; color: #6B7280;">相比上季度下降32%，稽查效果显著</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style="background: white; border-radius: 10px; padding: 1.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem;">
                <span style="font-size: 2rem;">⏱️</span>
                <span style="font-size: 2rem; font-weight: bold; color: #3B82F6;">4.2天</span>
            </div>
            <div style="font-weight: 600; margin-bottom: 0.3rem;">平均响应时间</div>
            <div style="font-size: 0.85rem; color: #6B7280;">快于行业平均水平6.5天</div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div style="background: white; border-radius: 10px; padding: 1.5rem; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.8rem;">
                <span style="font-size: 2rem;">🎯</span>
                <span style="font-size: 2rem; font-weight: bold; color: #8B5CF6;">87.5%</span>
            </div>
            <div style="font-weight: 600; margin-bottom: 0.3rem;">结案率</div>
            <div style="font-size: 0.85rem; color: #6B7280;">高于目标85%，处理效率优秀</div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.warning("⚠️ **重点关注**：华东区窜货案件占比65%，建议加强该区域监控力度")
    with col2:
        st.success("✅ **积极信号**：黑名单制度实施后，违规重复率从18%降至5%")

# 页脚
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #6B7280; font-size: 0.85rem; padding: 2rem 0;">
    <p style="margin: 0;">正掌讯医药市场稽查管理系统 v2.0</p>
    <p style="margin: 0.5rem 0 0 0;">© 2025 All Rights Reserved | 技术支持：西安正讯软件有限公司</p>
</div>
""", unsafe_allow_html=True)