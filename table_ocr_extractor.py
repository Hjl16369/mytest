"""
图片表格识别并转换为Excel文件 - Streamlit版本
支持JPG、PNG、PDF格式
使用OCR技术提取表格数据
运行命令: streamlit run ocr_xls.py
"""

import streamlit as st
from PIL import Image
import pandas as pd
from io import BytesIO
import re

# 尝试导入OCR相关库
try:
    import pytesseract
    import cv2
    import numpy as np
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

try:
    from pdf2image import convert_from_bytes
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


def check_dependencies():
    """检查并显示依赖信息"""
    if not OCR_AVAILABLE:
        st.error("""
        ⚠️ **缺少OCR依赖库!**
        
        请安装以下库:
        ```bash
        pip install pytesseract opencv-python numpy
        ```
        
        并安装Tesseract OCR引擎:
        - **Windows**: https://github.com/UB-Mannheim/tesseract/wiki
        - **Linux**: `sudo apt-get install tesseract-ocr tesseract-ocr-chi-sim`
        - **Mac**: `brew install tesseract`
        """)
        return False
    
    if not PDF_AVAILABLE:
        st.warning("💡 提示: 安装 `pdf2image` 和 `poppler` 以支持PDF文件")
    
    return True


def preprocess_image(image_array):
    """图像预处理"""
    # 转换为灰度图
    if len(image_array.shape) == 3:
        gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
    else:
        gray = image_array
    
    # 二值化
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    
    # 去噪
    kernel = np.ones((1, 1), np.uint8)
    opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel, iterations=1)
    
    return opening


def ocr_recognize(image_array):
    """OCR识别"""
    try:
        # 预处理
        processed = preprocess_image(image_array)
        
        # OCR识别
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(
            processed, 
            config=custom_config, 
            lang='chi_sim+eng'
        )
        
        return text
    except Exception as e:
        st.error(f"OCR识别失败: {str(e)}")
        return ""


def parse_table_text(text):
    """解析文本为表格数据"""
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    if not lines:
        return pd.DataFrame()
    
    data = []
    for line in lines:
        # 尝试多种分隔符
        if '|' in line:
            row = [cell.strip() for cell in line.split('|') if cell.strip()]
        elif '\t' in line:
            row = [cell.strip() for cell in line.split('\t') if cell.strip()]
        elif '  ' in line:  # 多个空格
            row = [cell.strip() for cell in re.split(r'\s{2,}', line) if cell.strip()]
        else:
            # 尝试识别中文标点或特殊字符作为分隔符
            if any(sep in line for sep in ['，', '、', ';', ':']):
                row = re.split(r'[，、;:]\s*', line)
            else:
                row = [line]
        
        if row:
            data.append(row)
    
    if not data:
        return pd.DataFrame()
    
    # 创建DataFrame
    max_cols = max(len(row) for row in data)
    
    # 补齐列数
    for row in data:
        while len(row) < max_cols:
            row.append('')
    
    # 第一行作为表头
    if len(data) > 1:
        df = pd.DataFrame(data[1:], columns=data[0])
    else:
        df = pd.DataFrame(data)
    
    return df


def convert_df_to_excel(df):
    """将DataFrame转换为Excel字节流"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='提取的表格')
    return output.getvalue()


def main():
    # 页面配置
    st.set_page_config(
        page_title="图片表格识别工具",
        page_icon="📊",
        layout="wide"
    )
    
    # 标题
    st.markdown("""
    <h1 style='text-align: center; color: #2c3e50;'>
        📊 图片表格识别转Excel工具
    </h1>
    <p style='text-align: center; color: #7f8c8d;'>
        支持 JPG、PNG、PDF 格式 | 自动识别表格并生成Excel文件
    </p>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # 检查依赖
    if not check_dependencies():
        st.stop()
    
    # 侧边栏说明
    with st.sidebar:
        st.header("📖 使用说明")
        st.markdown("""
        **操作步骤:**
        1. 上传图片文件 (JPG/PNG/PDF)
        2. 点击"开始识别"按钮
        3. 查看识别结果
        4. 下载生成的Excel文件
        
        **最佳实践:**
        - 📸 使用清晰的图片
        - 📐 表格结构要规整
        - 🔤 字体大小适中
        - 🌟 避免过多干扰元素
        """)
        
        st.markdown("---")
        st.info("💡 支持中英文混合识别")
    
    # 文件上传
    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded_file = st.file_uploader(
            "📁 选择图片文件",
            type=['jpg', 'jpeg', 'png', 'pdf'],
            help="支持JPG、PNG、PDF格式"
        )
    
    if uploaded_file is not None:
        # 显示文件信息
        with col2:
            st.info(f"""
            **文件信息:**
            - 文件名: {uploaded_file.name}
            - 大小: {uploaded_file.size / 1024:.2f} KB
            - 类型: {uploaded_file.type}
            """)
        
        # 显示图片预览
        st.subheader("🖼️ 图片预览")
        
        try:
            if uploaded_file.type == 'application/pdf':
                if not PDF_AVAILABLE:
                    st.error("需要安装 pdf2image 库来处理PDF文件")
                    st.stop()
                
                # 转换PDF
                images = convert_from_bytes(uploaded_file.read())
                image = images[0]
                image_array = np.array(image)
            else:
                image = Image.open(uploaded_file)
                image_array = np.array(image)
            
            # 显示预览
            st.image(image, use_column_width=True, caption="上传的图片")
            
            # 识别按钮
            st.markdown("---")
            col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 2])
            
            with col_btn1:
                recognize_btn = st.button("🔍 开始识别", type="primary", use_container_width=True)
            
            # 识别处理
            if recognize_btn:
                with st.spinner("🔄 正在识别中，请稍候..."):
                    # OCR识别
                    text = ocr_recognize(image_array)
                    
                    if text:
                        # 解析表格
                        df = parse_table_text(text)
                        
                        # 存储到session state
                        st.session_state['extracted_data'] = df
                        st.session_state['raw_text'] = text
                        st.session_state['filename'] = uploaded_file.name
                        
                        st.success("✅ 识别完成!")
            
            # 显示识别结果
            if 'extracted_data' in st.session_state:
                st.markdown("---")
                st.subheader("📊 识别概要")
                
                df = st.session_state['extracted_data']
                raw_text = st.session_state['raw_text']
                
                # 统计信息
                col_stat1, col_stat2, col_stat3 = st.columns(3)
                with col_stat1:
                    st.metric("识别行数", len(df))
                with col_stat2:
                    st.metric("识别列数", len(df.columns) if not df.empty else 0)
                with col_stat3:
                    st.metric("字符总数", len(raw_text))
                
                # 数据预览
                if not df.empty:
                    st.markdown("#### 📋 数据预览")
                    st.dataframe(df, use_container_width=True, height=300)
                    
                    # 下载按钮
                    excel_data = convert_df_to_excel(df)
                    
                    filename = st.session_state.get('filename', 'image')
                    output_filename = f"extracted_{filename.rsplit('.', 1)[0]}.xlsx"
                    
                    with col_btn2:
                        st.download_button(
                            label="💾 下载Excel",
                            data=excel_data,
                            file_name=output_filename,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            type="secondary",
                            use_container_width=True
                        )
                else:
                    st.warning("⚠️ 未能识别到表格数据，请检查图片质量")
                
                # 原始文本
                with st.expander("📄 查看原始识别文本"):
                    st.text_area("识别的原始文本", raw_text, height=200)
        
        except Exception as e:
            st.error(f"处理失败: {str(e)}")
    
    else:
        # 未上传文件时的提示
        st.info("👆 请上传图片文件开始识别")
        
        # 示例展示
        st.markdown("---")
        st.subheader("💡 使用示例")
        st.markdown("""
        **适用场景:**
        - 📸 扫描的纸质表格
        - 📊 截图的电子表格
        - 📄 PDF文档中的表格
        - 🖼️ 图片中的数据表
        
        **识别效果:**
        - ✅ 结构清晰的表格效果最佳
        - ⚠️ 复杂格式可能需要手动调整
        - 🔧 支持中英文混合识别
        """)


if __name__ == "__main__":
    main()
