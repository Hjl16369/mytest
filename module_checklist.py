"""
软件开发模块自查表生成系统 - Streamlit版
功能：填写自查表并生成PDF确认单
运行方式：streamlit run zx_checklist.py
"""

import streamlit as st
from datetime import datetime, date
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import cm
import os
import io

# 页面配置
st.set_page_config(
    page_title="软件开发模块功能自查表",
    page_icon="✅",
    layout="wide"
)

# 初始化session_state
if 'checkbox_state' not in st.session_state:
    st.session_state.checkbox_state = {}

def setup_fonts():
    """设置中文字体 - 使用reportlab内置字体"""
    try:
        # 尝试使用reportlab的内置中文字体支持
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
        return 'STSong-Light'
    except:
        pass
    
    # 备选方案：尝试系统字体
    font_paths = [
        "C:/Windows/Fonts/simhei.ttf",  # Windows 黑体
        "C:/Windows/Fonts/simsun.ttc",  # Windows 宋体
        "/System/Library/Fonts/PingFang.ttc",  # macOS
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",  # Linux
        "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",  # Linux
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",  # Linux Noto
    ]
    
    for font_path in font_paths:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont('Chinese', font_path))
                return 'Chinese'
            except:
                continue
    
    return None

def get_checklist_items():
    """获取自查项目数据"""
    return {
        "一、数据填报类功能自查": {
            "1. 数据校验自查": [
                "A. 输入数量、单价的地方不允许输入非法字符；若错误有提醒",
                "B. 金额类自动计算，对应的数量或单价变化自动更新",
                "C. 输入类金额保留小数点后两位；单价保留小数点后两位（含税价）",
                "D. 选择输入的内容，若内容条目较多（大于5个），已加上模糊筛查功能",
                "E. 与数据库字段长度匹配，对页面输入的内容长度要限制，超出已提醒",
                "F. 日期类输入项目已给出日期默认值",
                "G. 输入数字量时，只呈现数字键盘"
            ],
            "2. 操作留痕自查": [
                "数据修改已保留修改记录",
                "数据删除已保留删除记录"
            ],
            "3. 功能完整实现自查": [
                "数据新增功能已实现",
                "数据删除功能已实现",
                "数据修改功能已实现",
                "数据查询实现，列表中每个字段都可筛查",
                "管理列表数据导出已实现",
                "管理列表每项数据都可筛查"
            ],
            "4. 流程功能自查": [
                "流程业务已能实现回退或撤消功能"
            ],
            "5. 数据参数化自查": [
                "利用数据字典实现内容参数化，没有在代码中将参数写死"
            ],
            "6. 页面内容禁止直接用数据库table/混合SQL自查": [
                "页面中列表、下拉内容采用存储过程传参调用方式实现内容获取"
            ],
            "7. 事务实现保障数据一致性自查": [
                "数据新增、删除、更新已采用事务机制保障数据一致性"
            ],
            "8. 数据权限限制功能自查": [
                "页面及管理列表数据呈现已实现权限设置"
            ]
        },
        "二、报表呈现功能自查": {
            "1. 报表数据提取方式自查": [
                "报表数据呈现利用存储过程实现，没有直接利用组合SQL实现"
            ],
            "2. 金额合计呈现自查": [
                "所有金额列最后一行呈现金额合计（不是当前页面合计）"
            ],
            "3. 单价列显示自查": [
                "含税单价保留小数点后两位，不含税单价保留小数点后四位，右对齐"
            ],
            "4. 金额列显示自查": [
                "含税金额保留小数点后两位，不含税金额保留小数点后四位，右对齐"
            ],
            "5. 报表列查询功能自查": [
                "各个列已实现查询功能（筛选、分组）（不是当前页面合计）"
            ],
            "6. 报表导出功能自查": [
                "报表显示列数据可以导出电子表格"
            ]
        }
    }

def create_pdf(module_name, developer, start_date, end_date, checkbox_state):
    """创建PDF文档"""
    # 创建内存中的PDF
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    
    # 设置字体
    font_name = setup_fonts()
    
    # 如果没有中文字体，使用Helvetica但提示用户
    if not font_name:
        font_name = 'Helvetica'
        st.warning("⚠️ 系统未找到中文字体，PDF中的中文可能无法正常显示。建议在本地环境运行。")
    
    # 标题
    c.setFont(font_name, 18)
    title = "软件开发模块功能自查确认单"
    c.drawCentredString(width/2, height - 2*cm, title)
    
    c.setFont(font_name, 13)
    
    # 基本信息
    y = height - 3.5*cm
    c.drawString(2*cm, y, f"模块名: {module_name}")
    y -= 0.7*cm
    c.drawString(2*cm, y, f"开发人: {developer}")
    y -= 0.7*cm
    c.drawString(2*cm, y, f"开始时间: {start_date.strftime('%Y-%m-%d')}")
    y -= 0.7*cm
    c.drawString(2*cm, y, f"完成时间: {end_date.strftime('%Y-%m-%d')}")
    y -= 1*cm
    
    # 绘制分隔线
    c.line(2*cm, y, width - 2*cm, y)
    y -= 0.8*cm
    
    c.setFont(font_name, 12)
    
    # 自查项目
    checklist_items = get_checklist_items()
    for category, subcategories in checklist_items.items():
        # 检查是否需要新页面
        if y < 3*cm:
            c.showPage()
            c.setFont(font_name, 12)
            y = height - 2*cm
        
        # 大类标题
        c.setFont(font_name, 13)
        c.drawString(2*cm, y, category)
        c.setFont(font_name, 11)
        y -= 0.7*cm
        
        for subcat, items in subcategories.items():
            if y < 3*cm:
                c.showPage()
                c.setFont(font_name, 11)
                y = height - 2*cm
            
            # 子类标题
            c.drawString(2.5*cm, y, subcat)
            y -= 0.6*cm
            
            for item in items:
                if y < 3*cm:
                    c.showPage()
                    c.setFont(font_name, 11)
                    y = height - 2*cm
                
                # 复选框
                checked = checkbox_state.get(item, False)
                checkbox = "[√]" if checked else "[ ]"
                
                # 处理长文本换行
                text = f"{checkbox} {item}"
                max_width = width - 5*cm
                
                text_width = c.stringWidth(text, font_name, 11)
                
                if text_width > max_width:
                    # 简单换行处理
                    words = text.split()
                    line = ""
                    for word in words:
                        test_line = f"{line} {word}".strip()
                        test_width = c.stringWidth(test_line, font_name, 11)
                        
                        if test_width > max_width and line:
                            c.drawString(3*cm, y, line)
                            y -= 0.5*cm
                            line = word
                        else:
                            line = test_line
                    if line:
                        c.drawString(3*cm, y, line)
                        y -= 0.5*cm
                else:
                    c.drawString(3*cm, y, text)
                    y -= 0.5*cm
        
        y -= 0.3*cm
    
    # 确认信息
    if y < 5*cm:
        c.showPage()
        y = height - 2*cm
    
    y -= 1*cm
    c.line(2*cm, y, width - 2*cm, y)
    y -= 1*cm
    
    c.setFont(font_name, 13)
    c.drawString(2*cm, y, "三、开发人确认")
    y -= 0.8*cm
    
    c.setFont(font_name, 12)
    c.drawString(2*cm, y, "我确认上述功能自查都已完成、实现。")
    y -= 1*cm
    
    c.drawString(2*cm, y, f"确认人: {developer}")
    y -= 0.7*cm
    c.drawString(2*cm, y, f"确认日期: {datetime.now().strftime('%Y-%m-%d')}")
    
    # 统计信息
    total_items = sum(len(items) for subcats in checklist_items.values() for items in subcats.values())
    checked_items = sum(1 for v in checkbox_state.values() if v)
    y -= 1*cm
    completion_rate = (checked_items * 100 // total_items) if total_items > 0 else 0
    c.drawString(2*cm, y, f"自查完成率: {checked_items}/{total_items} 项 ({completion_rate}%)")
    
    c.save()
    buffer.seek(0)
    return buffer

def main():
    # 标题
    st.title("📋 软件开发模块功能自查表")
    st.markdown("---")
    
    # 基本信息区域
    st.header("📝 基本信息")
    col1, col2 = st.columns(2)
    
    with col1:
        module_name = st.text_input("模块名", placeholder="请输入模块名称")
        start_date = st.date_input("开始时间", value=date.today())
    
    with col2:
        developer = st.text_input("开发人", placeholder="请输入开发人姓名")
        end_date = st.date_input("完成时间", value=date.today())
    
    st.markdown("---")
    
    # 自查项目区域
    st.header("✓ 自查项目")
    
    # 快捷操作按钮
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        if st.button("✅ 全选", use_container_width=True):
            checklist_items = get_checklist_items()
            for category, subcategories in checklist_items.items():
                for subcat, items in subcategories.items():
                    for item in items:
                        st.session_state.checkbox_state[item] = True
            st.rerun()
    
    with col2:
        if st.button("⬜ 取消全选", use_container_width=True):
            st.session_state.checkbox_state = {}
            st.rerun()
    
    st.markdown("")
    
    # 显示自查项目
    checklist_items = get_checklist_items()
    
    for category, subcategories in checklist_items.items():
        st.subheader(category)
        
        for subcat, items in subcategories.items():
            st.markdown(f"**{subcat}**")
            
            for item in items:
                # 使用session_state存储复选框状态
                key = f"checkbox_{item}"
                checked = st.checkbox(
                    item,
                    value=st.session_state.checkbox_state.get(item, False),
                    key=key
                )
                st.session_state.checkbox_state[item] = checked
        
        st.markdown("")
    
    st.markdown("---")
    
    # 生成PDF按钮
    st.header("📄 生成确认单")
    
    col1, col2, col3 = st.columns([2, 1, 2])
    with col2:
        if st.button("🎯 生成PDF确认单", type="primary", use_container_width=True):
            # 验证基本信息
            if not module_name:
                st.error("❌ 请填写模块名！")
            elif not developer:
                st.error("❌ 请填写开发人！")
            else:
                # 检查未勾选项
                total_items = sum(len(items) for subcats in checklist_items.values() for items in subcats.values())
                checked_items = sum(1 for v in st.session_state.checkbox_state.values() if v)
                unchecked = total_items - checked_items
                
                if unchecked > 0:
                    st.warning(f"⚠️ 还有 {unchecked} 项未勾选")
                
                # 生成PDF
                with st.spinner("正在生成PDF..."):
                    try:
                        pdf_buffer = create_pdf(
                            module_name,
                            developer,
                            start_date,
                            end_date,
                            st.session_state.checkbox_state
                        )
                        
                        # 提供下载
                        filename = f"{module_name}_{developer}_自查确认单_{datetime.now().strftime('%Y%m%d')}.pdf"
                        st.download_button(
                            label="📥 下载PDF确认单",
                            data=pdf_buffer,
                            file_name=filename,
                            mime="application/pdf",
                            use_container_width=True
                        )
                        
                        st.success("✅ PDF确认单已生成！点击上方按钮下载")
                        
                        # 显示统计信息
                        completion_rate = (checked_items * 100 // total_items) if total_items > 0 else 0
                        st.info(f"📊 自查完成率: {checked_items}/{total_items} 项 ({completion_rate}%)")
                        
                    except Exception as e:
                        st.error(f"❌ 生成PDF失败: {str(e)}")

if __name__ == "__main__":
    main()
