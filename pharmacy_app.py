import streamlit as st
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import io, smtplib, ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# ══════════════════════════════════════════════════════
# 页面配置
# ══════════════════════════════════════════════════════
st.set_page_config(
    page_title="正掌讯 · 零售药店潜力评估系统",
    page_icon="💊",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════════════
# 全局 CSS
# ══════════════════════════════════════════════════════
st.markdown("""
<style>
html, body, .stApp { background:#F0F4FA !important; font-size:15px; }
.block-container { max-width:860px !important; padding:16px 20px 40px !important; }
* { box-sizing:border-box; }
.stApp { overflow-x:hidden !important; }

.hero {
  background:linear-gradient(135deg,#1565C0,#0D47A1,#1A237E);
  border-radius:14px; padding:20px 28px; margin-bottom:16px;
  box-shadow:0 6px 24px rgba(21,101,192,.28);
}
.hero h1 { font-size:24px; font-weight:900; color:#fff; margin:0; letter-spacing:2px; }
.hero p  { font-size:13px; color:rgba(255,255,255,.75); margin:4px 0 0; }

.card {
  background:#fff; border-radius:12px; border-left:5px solid #1565C0;
  padding:14px 18px; margin-bottom:14px;
  box-shadow:0 2px 10px rgba(0,0,0,.06);
}
.card-title { font-size:16px; font-weight:800; color:#1565C0; margin-bottom:2px; }
.card-badge {
  display:inline-block; background:#E3F2FD; color:#1565C0;
  border-radius:20px; padding:2px 10px; font-size:12px; font-weight:600;
  margin-bottom:10px;
}

.dash {
  background:linear-gradient(135deg,#0D47A1,#1565C0);
  border-radius:14px; padding:22px; text-align:center; color:#fff;
  margin:18px 0; box-shadow:0 6px 22px rgba(21,101,192,.3);
}
.dash .num  { font-size:68px; font-weight:900; line-height:1; }
.dash .lbl  { font-size:13px; opacity:.8; margin-top:4px; }
.dash .lvl  { font-size:20px; font-weight:800; margin-top:8px; color:#FFD54F; }
.dash .prio { font-size:13px; opacity:.85; margin-top:6px; }

.dim-grid {
  display:grid; grid-template-columns:repeat(4,1fr);
  gap:10px; margin:12px 0;
}
.dim-box { border-radius:10px; padding:12px 8px; text-align:center; color:#fff; }
.dim-box .dname { font-size:11px; opacity:.85; margin-bottom:4px; }
.dim-box .dval  { font-size:36px; font-weight:900; line-height:1; }
.dim-box .dwt   { font-size:11px; opacity:.75; margin-top:4px; }

.pbar-wrap { margin:6px 0 10px; }
.pbar-row  { display:flex; justify-content:space-between;
             font-size:13px; font-weight:600; color:#444; margin-bottom:3px; }
.pbar-bg   { height:9px; background:#E8EAF6; border-radius:5px; }
.pbar-fill { height:9px; border-radius:5px; }

.strategy { background:#fff; border:1px solid #DDEEFF; border-radius:10px;
            padding:16px 20px; margin-top:12px; }
.strategy h4 { font-size:15px; font-weight:800; color:#1565C0; margin:0 0 8px; }
.strategy li { font-size:14px; color:#333; line-height:1.9; }

.tip  { background:#FFF8E1; border-left:4px solid #FFC107; border-radius:8px;
        padding:10px 14px; font-size:13px; color:#6D4C41; margin-top:10px; }
.tip2 { background:#E8F5E9; border-left:4px solid #4CAF50; border-radius:8px;
        padding:10px 14px; font-size:13px; color:#2E7D32; margin-top:10px; }

label,
.stTextInput label, .stSelectbox label,
.stSlider label, .stNumberInput label,
.stRadio label, .stCheckbox label,
.stDateInput label {
  font-size:14px !important; font-weight:600 !important; color:#222 !important;
}
.stTextInput input, .stNumberInput input { font-size:14px !important; }
.streamlit-expanderHeader { font-size:14px !important; font-weight:700 !important; }
.stSelectbox > div > div, .stRadio > div { font-size:14px !important; }

.stButton > button {
  background:linear-gradient(135deg,#1565C0,#0D47A1) !important;
  color:#fff !important; border:none !important; border-radius:10px !important;
  padding:13px 0 !important; font-size:15px !important; font-weight:800 !important;
  width:100% !important; letter-spacing:1px !important;
  box-shadow:0 4px 14px rgba(21,101,192,.35) !important;
}
.stDownloadButton > button {
  background:linear-gradient(135deg,#00695C,#00897B) !important;
  color:#fff !important; border:none !important; border-radius:10px !important;
  padding:12px 0 !important; font-size:14px !important; font-weight:700 !important;
  width:100% !important;
}
hr { border-color:#DDEEFF !important; margin:14px 0 !important; }
#MainMenu, footer, header { visibility:hidden !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# 工具函数
# ══════════════════════════════════════════════════════
def xscore(text: str, default=50) -> int:
    try:
        return int(text.split("(")[1].split("分")[0])
    except Exception:
        return default

def bar(label, val, color="#1565C0"):
    st.markdown(f"""
    <div class="pbar-wrap">
      <div class="pbar-row"><span>{label}</span><span>{val:.1f}</span></div>
      <div class="pbar-bg">
        <div class="pbar-fill" style="width:{min(val,100):.0f}%;background:{color};"></div>
      </div>
    </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# Hero 标题
# ══════════════════════════════════════════════════════
st.markdown("""
<div class="hero">
  <h1>💊 零售药店潜力量化评估系统</h1>
  <p>正掌讯营销管理咨询中心 · 医药行业精准营销数字化决策工具 v2.1</p>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# 调研基本信息
# ══════════════════════════════════════════════════════
st.markdown('<div class="card"><div class="card-title">📋 调研基本信息</div>'
            '<div class="card-badge">必填项 *</div>', unsafe_allow_html=True)

c1, c2 = st.columns(2)
with c1:
    researcher     = st.text_input("调研人员姓名 *", placeholder="请输入姓名")
    researcher_tel = st.text_input("调研人员手机号 *", placeholder="如：138xxxxxxxx")
    company        = st.text_input("所属企业/团队", placeholder="如：XX医药销售团队")
with c2:
    pharmacy_name  = st.text_input("目标药店名称 *", placeholder="如：XX连锁旗舰店")
    target_drug    = st.text_input("被评估药品名称 *", placeholder="如：XX牌降压片")
    city           = st.text_input("所在城市", placeholder="如：西安市")

c3, c4 = st.columns(2)
with c3:
    survey_date = st.date_input("调研日期 *", datetime.now())
with c4:
    reporter_email = st.text_input("调研人邮箱", placeholder="用于接收报告副本（选填）")

st.markdown('</div>', unsafe_allow_html=True)
st.markdown("---")

# ══════════════════════════════════════════════════════
# 维度一：基础实力 10%
# ══════════════════════════════════════════════════════
st.markdown('<div class="card"><div class="card-title">① 基础实力 S_Basic</div>'
            '<div class="card-badge">权重 10% · 硬件与政策底盘</div>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    chain_type = st.selectbox("🏪 药店连锁背景", [
        "全国/省级龙头连锁 (100分)",
        "地方中型连锁 (70分)",
        "单体药店 (40分)",
    ])
    insurance_type = st.selectbox("🏥 医保/统筹资质", [
        "门诊统筹＋双通道定点 (100分)",
        "基础医保定点 (80分)",
        "无医保/纯自费 (40分)",
    ])
with c2:
    location_type = st.selectbox("📍 地理区位", [
        "三甲医院门口 ≤200米 (100分)",
        "三甲医院附近 200-500米 (85分)",
        "大型社区核心位置 (70分)",
        "普通商业/住宅区 (50分)",
        "偏僻/次级位置 (30分)",
    ])
    store_grade = st.selectbox("🏬 门店等级", [
        "旗舰店 (100分)",
        "A类店 (80分)",
        "B类店 (60分)",
        "C类店 (40分)",
    ])
st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# 维度二：需求潜力 45%
# ══════════════════════════════════════════════════════
RX_MAP = {
    "三甲医院门口 ≤200米 (100分)":    ("A级 <200米，加成 ×1.5", 1.5),
    "三甲医院附近 200-500米 (85分)":  ("B级 200-500米，加成 ×1.2", 1.2),
    "大型社区核心位置 (70分)":        ("C级 社区店，系数 ×1.0", 1.0),
    "普通商业/住宅区 (50分)":         ("C级 社区店，系数 ×1.0", 1.0),
    "偏僻/次级位置 (30分)":           ("C级 社区店，系数 ×1.0", 1.0),
}
rx_lbl, rx_factor = RX_MAP[location_type]

st.markdown('<div class="card"><div class="card-title">② 需求潜力 S_Demand</div>'
            '<div class="card-badge">权重 45% · 患者流量天花板（最核心）</div>', unsafe_allow_html=True)

with st.expander("📖 数据采集指引（点击展开）"):
    st.markdown("""
    - **日均进店人数**：POS系统年度总订单 ÷ 365 ÷ 平均成交率(30-50%)；或早/中/晚三时段各计数30分钟取均值。
    - **品类转化率**：目标品类订单数 / 门店总订单数，从POS后台提取。
    - **处方外流加成**：根据距医院位置自动联动（A级×1.5，B级×1.2，C级×1.0）。
    """)

c1, c2 = st.columns(2)
with c1:
    daily_traffic = st.number_input("🚶 日均进店人数（人/日）", 0, 5000, 200, 10,
        help="以城市/区域最高值500人为参照进行归一化")
    cat_conv = st.slider("🔄 目标品类转化率（%）", 0, 100, 15,
        help="进店人群中购买目标品类的比例")
    tgt_pen  = st.slider("🎯 目标适应症渗透率（%）", 0, 100, 30,
        help="该品类购买者中属于目标适应症患者的比例")
with c2:
    st.info(f"📋 处方外流加成：{rx_lbl}（与区位联动）")
    has_rx = st.radio("💊 是否有慢病管理区/处方柜台", ["是 (+5分)", "否 (0分)"])
    rx_vol = st.number_input("📄 目标科室处方承接量（份/日）", 0, 500, 0, 5,
        help="每日来自医院/诊所的处方承接数量，无则填0")
st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# 维度三：增长潜力 25%
# ══════════════════════════════════════════════════════
st.markdown('<div class="card"><div class="card-title">③ 增长潜力 S_Growth</div>'
            '<div class="card-badge">权重 25% · 动销势头与会员扩张</div>', unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    cagr = st.slider("📈 近两年销售额复合增长率 CAGR（%）", -30, 100, 15,
        help=">25% 为满分参照；负增长自动触发风险提示")
    member_growth = st.slider("📊 慢病会员月增长率（%）", 0, 50, 5,
        help=">10%/月为满分，慢病会员LTV高")
with c2:
    growth_trend = st.selectbox("📉 近三年销售整体趋势", [
        "持续增长 >20% (100分)",
        "稳步增长 10-20% (80分)",
        "基本持平 (60分)",
        "略有下滑 (30分)",
        "持续下滑 (10分)",
    ])
    o2o = st.selectbox("🛵 O2O/社区活动能力", [
        "美团/饿了么活跃＋患教频繁 (100分)",
        "有O2O但活动较少 (70分)",
        "仅线下，无O2O (40分)",
    ])
st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# 维度四：竞争与推荐 20%
# ══════════════════════════════════════════════════════
st.markdown('<div class="card"><div class="card-title">④ 竞争与推荐 S_Competition</div>'
            '<div class="card-badge">权重 20% · 竞争格局与拦截能力</div>', unsafe_allow_html=True)

with st.expander("🕵️ 神秘顾客测试话术（点击查看）"):
    st.markdown("""
    **话术**：进店询问：「我有点**（目标适应症症状）**，您有什么推荐？」  
    观察：① 是否主动首推本品？ ② 是否推荐竞品？ ③ 是否"洗方"（改推高毛利品）？
    """)

c1, c2 = st.columns(2)
with c1:
    display_pos = st.selectbox("🏷️ 本品货架陈列位置", [
        "黄金视线位（端架/第一二排正面）(100分)",
        "普通货架中层，正视可见 (70分)",
        "侧柜/底层/偏僻位置 (40分)",
        "无陈列/缺货 (10分)",
    ])
    brand_share = st.slider("📦 本品占同通用名品总销售额（%）", 0, 100, 20,
        help="低份额+高总潜力 = 巨大抢夺空间")
with c2:
    rec_level = st.selectbox("🗣️ 店员推介意愿（神秘顾客评级）", [
        "主动首选推荐本品 (100分)",
        "询问后推荐本品，未推竞品 (80分)",
        "本品与竞品同时推荐 (60分)",
        "询问后才提及，倾向竞品 (40分)",
        "主动拦截/洗方推竞品 (10分)",
    ])
    comp_rebate = st.radio("💰 竞品返利是否显著高于本品",
        ["是（风险，推介分下调）", "否（本品有竞争力）"])
st.markdown('</div>', unsafe_allow_html=True)

# ── 补充信息 ──────────────────────────────────────────
with st.expander("➕ 补充信息（可选，辅助策略判断）"):
    cc1, cc2 = st.columns(2)
    with cc1:
        nearby_competitors = st.number_input("周边500米内同类竞品门店数", 0, 50, 2)
        new_hospital = st.radio("周边是否有新院区即将/已开业", ["是", "否"])
    with cc2:
        visit_gap = st.selectbox("上次代表拜访/SKT培训距今", [
            "1个月内", "1-3个月", "3-6个月", "超过6个月", "从未拜访"
        ])
        notes = st.text_area("现场补充备注", placeholder="如：店长态度、竞品动态...", height=80)

st.markdown("---")

# ══════════════════════════════════════════════════════
# 邮件配置
# ══════════════════════════════════════════════════════
with st.expander("📧 邮件发送配置（可选 · 自动推送评测报告）"):
    st.markdown("""
    <div class="tip">
    💡 配置后点击"提交评估"，系统将自动把报告PDF和调研人信息发送至指定邮箱。<br>
    推荐使用 <b>Gmail应用密码</b> 或 <b>QQ邮箱授权码</b>。
    </div>
    """, unsafe_allow_html=True)
    ec1, ec2 = st.columns(2)
    with ec1:
        smtp_host  = st.text_input("SMTP服务器", placeholder="smtp.gmail.com 或 smtp.qq.com")
        smtp_port  = st.number_input("SMTP端口", value=465, min_value=1, max_value=65535)
        smtp_user  = st.text_input("发件人邮箱", placeholder="your@email.com")
        smtp_pass  = st.text_input("邮箱密码/应用密码", type="password", placeholder="16位应用密码")
    with ec2:
        to_emails_str = st.text_area(
            "收件人邮箱（多个用英文逗号分隔）",
            placeholder="manager@company.com,\nboss@company.com",
            height=80,
            help="收件人将收到包含调研人姓名电话、药店信息、评分及PDF附件的完整报告"
        )
        send_copy = st.checkbox("同时发送副本至调研人邮箱", value=True)
        email_enabled = st.checkbox("✅ 启用自动邮件发送", value=False)

# ══════════════════════════════════════════════════════
# 核心计算
# ══════════════════════════════════════════════════════
def calc():
    s_basic = (xscore(chain_type)*0.30 + xscore(insurance_type)*0.30 +
               xscore(location_type)*0.20 + xscore(store_grade)*0.20)

    traffic_n  = min(daily_traffic / 500 * 100, 100)
    demand_raw = traffic_n * (cat_conv/100) * (tgt_pen/100) * rx_factor * 100
    s_demand   = min(demand_raw, 100)
    if "是" in has_rx:  s_demand = min(s_demand + 5, 100)
    s_demand = min(s_demand + min(rx_vol/10*2, 10), 100)

    cagr_s = min(max(cagr,0)/25*100, 100)
    if cagr < 0: cagr_s = max(50+cagr*2, 0)
    mem_s  = min(member_growth/10*100, 100)
    s_growth = (cagr_s*0.6 + mem_s*0.4)*0.75 + xscore(growth_trend)*0.15 + xscore(o2o)*0.10
    s_growth = min(s_growth, 100)

    rec_s  = xscore(rec_level)
    if "是" in comp_rebate: rec_s = max(rec_s-15, 10)
    s_comp = rec_s*0.50 + xscore(display_pos)*0.30 + min(brand_share,100)*0.20
    s_comp = min(s_comp, 100)

    total = s_demand*0.45 + s_growth*0.25 + s_comp*0.20 + s_basic*0.10
    return dict(
        total=round(total,1), s_basic=round(s_basic,1),
        s_demand=round(s_demand,1), s_growth=round(s_growth,1), s_comp=round(s_comp,1),
        traffic_n=round(traffic_n,1), demand_raw=round(demand_raw,1),
        cagr_s=round(cagr_s,1), mem_s=round(mem_s,1), rec_s=round(rec_s,1),
    )

def level_info(score):
    if score >= 80:
        return ("战略堡垒店 A+","🏆","#D32F2F","⭐⭐⭐⭐⭐ 最高优先级·全力资源倾斜",[
            "派驻驻店促销员（PTA），全时段覆盖关键客流",
            "签署独家/优先陈列协议，锁定黄金货架资源",
            "建立高层战略伙伴关系，开展年度合作规划",
            "开展VIP慢病患者专项沙龙，提升患者LTV",
            "设置专属库存配额，保障长期供应稳定性",
            "季度重点投入：SKT专业培训 + 社区患教义诊",
        ])
    elif score >= 60:
        return ("重点进攻店 A","🎯","#F57C00","⭐⭐⭐⭐ 高优先级·核心增长阵地",[
            "每月至少2次店员专业技能培训（SKT），提升首推率",
            "定期神秘顾客测试，持续监控推介质量",
            "申请改善陈列位置，争取中层以上黄金货架",
            "开展社区患教义诊，导入精准患者流量",
            "评估O2O引流合作（美团/饿了么），拓展线上入口",
        ])
    elif score >= 40:
        return ("资源观察店 B","👀","#1976D2","⭐⭐⭐ 中优先级·维持覆盖观察",[
            "侧重渠道覆盖（B2B供货），维持基础库存",
            "保持基础陈列，季度检查一次货架状态",
            "低成本O2O引流，评估线上单量增长潜力",
            "每季度拜访一次，动态观察是否升级",
            "如O2O数据或处方量改善，立即升级资源投入",
        ])
    else:
        return ("自然销售店 C","📦","#757575","⭐⭐ 低优先级·自然维护",[
            "仅保持基本物流配送，确保不断货",
            "不建议投入额外学术/营销预算",
            "每半年复核一次，关注区位变化（如新医院开业）",
            "若评分显著提升则重新归级",
        ])

# ══════════════════════════════════════════════════════
# PDF 生成
# ══════════════════════════════════════════════════════
def make_pdf(sc, lvl_tuple) -> bytes:
    level, badge, lc, prio, strategies = lvl_tuple
    buf = io.BytesIO()
    p   = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    def hdr():
        p.setFillColorRGB(0.086, 0.282, 0.753)
        p.rect(0, H-64, W, 64, fill=1, stroke=0)
        p.setFillColorRGB(1, 1, 1)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(22, H-28, "Zhengzhangxun Marketing Management Consulting Center")
        p.setFont("Helvetica", 10)
        p.drawString(22, H-46, "Retail Pharmacy Potential Evaluation Report")
        p.drawRightString(W-22, H-46, f"Date: {survey_date}")

    def ftr(n):
        p.setFillColorRGB(0.5, 0.5, 0.5)
        p.setFont("Helvetica", 8)
        p.drawString(22, 16, "(C) 2026 Zhengzhangxun (Xi'an Zhengxun Software)  |  Confidential")
        p.drawRightString(W-22, 16, f"Page {n}")
        p.setStrokeColorRGB(0.086, 0.282, 0.753)
        p.line(22, 26, W-22, 26)

    def sec(title, y):
        p.setFillColorRGB(0.086, 0.282, 0.753)
        p.rect(22, y-2, 4, 15, fill=1, stroke=0)
        p.setFillColorRGB(0.086, 0.282, 0.753)
        p.setFont("Helvetica-Bold", 11)
        p.drawString(30, y, title)
        return y-22

    def irow(lbl, val, y, bold=False):
        p.setFillColorRGB(0.5, 0.5, 0.5)
        p.setFont("Helvetica", 9)
        p.drawString(36, y, lbl)
        p.setFillColorRGB(0.1, 0.1, 0.1)
        p.setFont("Helvetica-Bold" if bold else "Helvetica", 10)
        p.drawString(210, y, str(val))
        return y-15

    hdr()
    y = H - 80

    # 基本信息
    y = sec("Basic Information & Surveyor Details", y)
    for lbl, val in [
        ("Pharmacy Name",     pharmacy_name or "N/A"),
        ("Target Drug",       target_drug or "N/A"),
        ("City",              city or "N/A"),
        ("Researcher Name",   researcher or "N/A"),
        ("Researcher Tel",    researcher_tel or "N/A"),
        ("Researcher Email",  reporter_email or "N/A"),
        ("Company / Team",    company or "N/A"),
        ("Survey Date",       str(survey_date)),
    ]:
        y = irow(lbl, val, y)
    y -= 6

    # 总分大框
    p.setFillColorRGB(0.086, 0.282, 0.753)
    p.roundRect(22, y-78, W-44, 86, 8, fill=1, stroke=0)
    p.setFillColorRGB(1, 1, 1)
    p.setFont("Helvetica-Bold", 52)
    p.drawCentredString(W/2, y-50, f"{sc['total']}")
    p.setFont("Helvetica-Bold", 13)
    p.drawCentredString(W/2, y-65, level)
    p.setFont("Helvetica", 9)
    p.drawCentredString(W/2, y-78, prio.replace("⭐","*"))
    y -= 94

    # 四维格
    y -= 6
    bw = (W-44-9)/4
    dims = [
        (f"S_Demand  {sc['s_demand']}", "Demand 45%",  (0.086,0.282,0.753)),
        (f"S_Growth  {sc['s_growth']}", "Growth 25%",  (0.0,0.537,0.482)),
        (f"S_Comp    {sc['s_comp']}",   "Comp 20%",    (0.961,0.49,0.0)),
        (f"S_Basic   {sc['s_basic']}",  "Basic 10%",   (0.557,0.141,0.667)),
    ]
    for i, (title, wlbl, col) in enumerate(dims):
        bx = 22 + i*(bw+3)
        p.setFillColorRGB(*col)
        p.roundRect(bx, y-46, bw, 52, 6, fill=1, stroke=0)
        p.setFillColorRGB(1, 1, 1)
        parts = title.split("  ")
        p.setFont("Helvetica-Bold", 9)
        p.drawCentredString(bx+bw/2, y-12, parts[0])
        p.setFont("Helvetica-Bold", 20)
        p.drawCentredString(bx+bw/2, y-32, parts[1])
        p.setFont("Helvetica", 8)
        p.drawCentredString(bx+bw/2, y-44, wlbl)
    y -= 60

    # 细项得分表
    y = sec("Score Breakdown", y-4)
    tdata = [
        ["Dimension", "Sub-Indicator", "Score"],
        ["Demand (45%)", "Traffic Normalized",   str(sc["traffic_n"])],
        ["",             "Rx Outflow Factor",    f"x{rx_factor}"],
        ["",             "Final S_Demand",       str(sc["s_demand"])],
        ["Growth (25%)", "CAGR Score",           str(sc["cagr_s"])],
        ["",             "Member Growth Score",  str(sc["mem_s"])],
        ["",             "Final S_Growth",       str(sc["s_growth"])],
        ["Comp (20%)",   "Display Score",        str(xscore(display_pos))],
        ["",             "Recommendation (adj)", str(sc["rec_s"])],
        ["",             "Final S_Competition",  str(sc["s_comp"])],
        ["Basic (10%)",  "Chain Type",           str(xscore(chain_type))],
        ["",             "Insurance Level",      str(xscore(insurance_type))],
        ["",             "Location",             str(xscore(location_type))],
        ["",             "Final S_Basic",        str(sc["s_basic"])],
        ["TOTAL SCORE",  "",                     str(sc["total"])],
    ]
    cw = [(W-44)*0.38, (W-44)*0.40, (W-44)*0.22]
    rh = 13
    for ri, rrow in enumerate(tdata):
        if ri == 0:              bg = (0.086,0.282,0.753)
        elif ri == len(tdata)-1: bg = (1,0.95,0.82)
        elif ri%2 == 0:          bg = (0.95,0.97,1.0)
        else:                    bg = (1,1,1)
        p.setFillColorRGB(*bg)
        p.rect(22, y-rh+2, W-44, rh, fill=1, stroke=0)
        tx = 22
        for ci, cell in enumerate(rrow):
            if ri == 0:              p.setFillColorRGB(1,1,1)
            elif ri == len(tdata)-1: p.setFillColorRGB(0.6,0.2,0.0)
            else:                    p.setFillColorRGB(0.15,0.15,0.15)
            is_bold = (ri==0 or ri==len(tdata)-1 or ci==2)
            p.setFont("Helvetica-Bold" if is_bold else "Helvetica", 8)
            p.drawString(tx+4, y-rh+4, cell)
            tx += cw[ci]
        y -= rh
        if y < 80:
            ftr(1); p.showPage(); hdr(); y = H-80

    # 策略建议
    y -= 10
    y = sec("Strategic Action Plan", y)
    for s in strategies:
        txt = s[:82]+"..." if len(s) > 82 else s
        p.setFillColorRGB(0.2, 0.2, 0.2)
        p.setFont("Helvetica", 9)
        p.drawString(34, y, f"* {txt}")
        y -= 13
        if y < 60:
            ftr(1); p.showPage(); hdr(); y = H-80

    # 备注
    if notes.strip():
        y -= 4
        y = sec("Field Notes", y)
        for ln in notes.split("\n"):
            p.setFont("Helvetica", 9)
            p.setFillColorRGB(0.3, 0.3, 0.3)
            p.drawString(34, y, ln[:90])
            y -= 13

    ftr(1)
    p.showPage()
    p.save()
    buf.seek(0)
    return buf.read()

# ══════════════════════════════════════════════════════
# 邮件发送
# ══════════════════════════════════════════════════════
def send_email(pdf_bytes, sc, lvl_tuple):
    level, badge, lc, prio, strategies = lvl_tuple
    to_list = [e.strip() for e in to_emails_str.split(",") if e.strip()]
    if send_copy and reporter_email.strip():
        if reporter_email.strip() not in to_list:
            to_list.append(reporter_email.strip())
    if not to_list:
        return False, "未填写收件人邮箱"

    subject = f"【正掌讯评测报告】{pharmacy_name} - {survey_date} - {level}"
    body = f"""正掌讯零售药店潜力评估报告

━━━━━ 调研人员信息 ━━━━━
调研人：{researcher}
手  机：{researcher_tel}
邮  箱：{reporter_email}
企业/团队：{company}

━━━━━ 药店信息 ━━━━━
药店名称：{pharmacy_name}
目标药品：{target_drug}
城    市：{city}
调研日期：{survey_date}

━━━━━ 评估结果 ━━━━━
综合得分：{sc['total']} 分
评估等级：{badge} {level}
优先级：{prio}

各维度得分：
  需求潜力（45%）：{sc['s_demand']}
  增长潜力（25%）：{sc['s_growth']}
  竞争推荐（20%）：{sc['s_comp']}
  基础实力（10%）：{sc['s_basic']}

━━━━━ 策略建议 ━━━━━
""" + "\n".join(f"  * {s}" for s in strategies) + """

--
本邮件由正掌讯评估系统自动发送
© 2026 正掌讯（西安正讯软件有限公司）
"""
    try:
        msg = MIMEMultipart()
        msg["From"]    = smtp_user
        msg["To"]      = ", ".join(to_list)
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        att = MIMEBase("application", "octet-stream")
        att.set_payload(pdf_bytes)
        encoders.encode_base64(att)
        fn = f"Report_{pharmacy_name}_{survey_date}.pdf"
        att.add_header("Content-Disposition", "attachment",
                       filename=("utf-8", "", fn))
        msg.attach(att)

        ctx = ssl.create_default_context()
        if smtp_port == 465:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, context=ctx) as srv:
                srv.login(smtp_user, smtp_pass)
                srv.sendmail(smtp_user, to_list, msg.as_bytes())
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as srv:
                srv.ehlo(); srv.starttls(context=ctx); srv.ehlo()
                srv.login(smtp_user, smtp_pass)
                srv.sendmail(smtp_user, to_list, msg.as_bytes())
        return True, f"已发送至：{', '.join(to_list)}"
    except Exception as e:
        return False, str(e)

# ══════════════════════════════════════════════════════
# 提交按钮
# ══════════════════════════════════════════════════════
submit = st.button("🚀  提 交 评 估 · 生 成 数 字 化 报 告")

if submit:
    missing = []
    if not researcher.strip():     missing.append("调研人员姓名")
    if not researcher_tel.strip(): missing.append("调研人员手机号")
    if not pharmacy_name.strip():  missing.append("目标药店名称")
    if not target_drug.strip():    missing.append("被评估药品名称")
    if missing:
        missing_str = "、".join(missing)
        st.error(f"⚠️ 以下必填项尚未填写：{missing_str}")
        st.stop()

    sc  = calc()
    lvl = level_info(sc["total"])
    level, badge, lc, prio, strategies = lvl

    # 总分仪表盘
    st.markdown(f"""
    <div class="dash">
      <div class="lbl">综合潜力评分 · {pharmacy_name}</div>
      <div class="num">{sc['total']}</div>
      <div style="font-size:12px;opacity:.65;margin-top:3px;">满分 100 分</div>
      <div class="lvl">{badge} {level}</div>
      <div class="prio">{prio}</div>
    </div>
    """, unsafe_allow_html=True)

    # 四维格
    st.markdown(f"""
    <div class="dim-grid">
      <div class="dim-box" style="background:#1565C0;">
        <div class="dname">需求潜力</div>
        <div class="dval">{sc['s_demand']}</div>
        <div class="dwt">权重 45%</div>
      </div>
      <div class="dim-box" style="background:#00897B;">
        <div class="dname">增长潜力</div>
        <div class="dval">{sc['s_growth']}</div>
        <div class="dwt">权重 25%</div>
      </div>
      <div class="dim-box" style="background:#F57C00;">
        <div class="dname">竞争推荐</div>
        <div class="dval">{sc['s_comp']}</div>
        <div class="dwt">权重 20%</div>
      </div>
      <div class="dim-box" style="background:#8E24AA;">
        <div class="dname">基础实力</div>
        <div class="dval">{sc['s_basic']}</div>
        <div class="dwt">权重 10%</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # 进度条
    st.markdown("**📊 各维度得分**")
    bar("需求潜力  S_Demand",      sc["s_demand"], "#1565C0")
    bar("增长潜力  S_Growth",      sc["s_growth"], "#00897B")
    bar("竞争推荐  S_Competition", sc["s_comp"],   "#F57C00")
    bar("基础实力  S_Basic",       sc["s_basic"],  "#8E24AA")

    # 细项明细
    with st.expander("🔍 细项得分明细"):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"""
**需求潜力**
- 客流归一化：**{sc['traffic_n']}**
- 处方外流系数：**×{rx_factor}**
- 最终 S_Demand：**{sc['s_demand']}**

**基础实力**
- 连锁背景：**{xscore(chain_type)}**
- 医保资质：**{xscore(insurance_type)}**
- 地理区位：**{xscore(location_type)}**
- 门店等级：**{xscore(store_grade)}**
""")
        with c2:
            st.markdown(f"""
**增长潜力**
- CAGR评分：**{sc['cagr_s']}**
- 会员增长：**{sc['mem_s']}**
- 最终 S_Growth：**{sc['s_growth']}**

**竞争推荐**
- 陈列位置：**{xscore(display_pos)}**
- 推介意愿（含竞品修正）：**{sc['rec_s']}**
- 本品份额贡献：**{brand_share}**
- 最终 S_Competition：**{sc['s_comp']}**
""")

    # 策略建议
    items_html = "".join(f"<li>{s}</li>" for s in strategies)
    st.markdown(f"""
    <div class="strategy">
      <h4>{badge} {level} · 精准经营策略</h4>
      <ul>{items_html}</ul>
    </div>
    """, unsafe_allow_html=True)

    # 风险/机会提示
    risks = []
    if cagr < 0:               risks.append("⚠️ 近两年销售负增长，请关注集采或竞店影响")
    if "拦截" in rec_level:     risks.append("⚠️ 店员存在主动拦截行为，建议优先SKT培训并优化返利政策")
    if "是" in comp_rebate:     risks.append("⚠️ 竞品返利更高，店员推介意愿受压，需评估价差政策")
    if "无陈列" in display_pos: risks.append("🚨 本品无陈列/缺货，需立即跟进补货及陈列谈判")
    if new_hospital == "是":    risks.append("✅ 周边有新院区，处方外流潜力将快速提升，建议提前锁定")
    if visit_gap in ["3-6个月","超过6个月","从未拜访"]:
        risks.append("⚠️ 拜访频率过低，建议立即安排拜访维护客情")
    if risks:
        st.markdown('<div class="tip"><b>🔔 风险与机会提示：</b><br>' +
                    "<br>".join(risks) + '</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="tip2">
    📌 <b>顾问提示：</b>建议<b>每季度</b>更新一次评分数据。
    拥有门诊统筹资质的药店应赋予更高加权；美团/饿了么线上单量高的药店可作为额外流量入口加分。
    </div>
    """, unsafe_allow_html=True)

    # PDF 下载
    pdf_bytes = make_pdf(sc, lvl)
    st.markdown("<br>", unsafe_allow_html=True)
    st.download_button(
        "📄  下载完整PDF评估报告",
        data=pdf_bytes,
        file_name=f"正掌讯评估报告_{pharmacy_name}_{survey_date}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

    # 邮件发送
    if email_enabled:
        with st.spinner("📤 正在发送邮件，请稍候..."):
            ok, msg_out = send_email(pdf_bytes, sc, lvl)
        if ok:
            st.success(f"✅ 邮件发送成功！{msg_out}")
        else:
            st.error(f"❌ 邮件发送失败：{msg_out}")
            st.markdown("""
            <div class="tip">
            🔧 <b>排查建议：</b><br>
            · Gmail：账户设置 → 安全 → 应用专用密码（16位）<br>
            · QQ邮箱：设置 → 账户 → 开启SMTP → 获取授权码，端口465<br>
            · 企业邮箱：请联系IT获取SMTP地址与端口
            </div>
            """, unsafe_allow_html=True)
    elif to_emails_str.strip() and not email_enabled:
        st.info("💡 已填写收件人邮箱，勾选「启用自动邮件发送」后重新提交即可自动推送。")

    st.markdown(f"""
    <div style="text-align:center;font-size:12px;color:#999;margin-top:12px;">
    生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')} ·
    调研人：{researcher}（{researcher_tel}）· {pharmacy_name}
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# 页脚
# ══════════════════════════════════════════════════════
st.markdown("---")
st.markdown("""
<div style="text-align:center;font-size:12px;color:#999;padding:6px 0 20px;">
© 2026 正掌讯（西安正讯软件有限公司）· 医药行业精准营销管理数字化工具<br>
<b>评分模型：</b>流量决定上限 · 增速代表趋势 · 推荐决定份额 · 资质保障基础
</div>
""", unsafe_allow_html=True)
