"""
图片表格识别并转换为Excel文件 - Streamlit Cloud 版本
支持JPG、PNG、PDF格式
使用OCR技术提取表格数据

文件说明:
- app.py (本文件): 主程序
- requirements.txt: Python依赖包
- packages.txt: Linux系统包
- .streamlit/config.toml: Streamlit配置

作者: OCR Table Extractor
版本: 2.0 (Cloud Optimized)
"""

import streamlit as st
from PIL import Image
import pandas as pd
from io import BytesIO
import re
import sys
import os

# 尝试导入OCR相关库
try:
    import pytesseract
    import cv2
    import numpy as np
    OCR_AVAILABLE = True
    
    # Streamlit Cloud 环境下 tesseract 路径配置
    if os.path.exists('/usr/bin/tesseract'):
        pytesseract.pytesseract.tesseract_cmd = '/usr/bin/tesseract'
    
except ImportError as e:
    OCR_AVAILABLE = False
    OCR_ERROR = str(e)

try:
    from pdf2image import convert_from_bytes
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


def show_setup_instructions():
    """显示部署说明"""
    st.error("⚠️ OCR 依赖未正确安装")
    
    with st.expander("📖 Streamlit Cloud 部署指南", expanded=True):
        st.markdown("""
        ### 🚀 部署步骤
        
        #### 1️⃣ 创建 GitHub 仓库
        在 GitHub 上创建新仓库，上传以下文件：
        
        #### 2️⃣ 必需文件清单
        
        **📄 requirements.txt**
        ```txt
        streamlit==1.31.0
        pillow==10.2.0
        pandas==2.2.0
        openpyxl==3.1.2
        pytesseract==0.3.10
        opencv-python-headless==4.9.0.80
        numpy==1.26.3
        pdf2image==1.17.0
        ```
        
        **📄 packages.txt**
        ```txt
        tesseract-ocr
        tesseract-ocr-chi-sim
        tesseract-ocr-eng
        poppler-utils
        libgl1
        ```
        
        **📄 .streamlit/config.toml**
        ```toml
        [theme]
        primaryColor = "#3498db"
        backgroundColor = "#ffffff"
        secondaryBackgroundColor = "#f0f2f6"
        textColor = "#262730"
        font = "sans serif"
        
        [server]
        maxUploadSize = 200
        enableXsrfProtection = false
        ```
        
        #### 3️⃣ 部署到 Streamlit Cloud
        1. 访问 https://streamlit.io/cloud
        2. 点击 "New app"
        3. 连接你的 GitHub 仓库
        4. 选择分支和主文件 (app.py)
        5. 点击 "Deploy"
        
        #### 4️⃣ 等待部署完成
        - 首次部署需要 5-10 分钟安装依赖
        - 部署完成后会自动运行
        
        ---
        
        ### 🔧 本地测试命令
        ```bash
        # 安装依赖
        pip install -r requirements.txt
        
        # Linux 安装系统包
        sudo apt-get install tesseract-ocr tesseract-ocr-chi-sim poppler-utils
        
        # 运行应用
        streamlit run app.py
        ```
        """)
    
    st.info("💡 如果您已经部署但仍看到此消息，请检查 packages.txt 文件是否正确配置")


def preprocess_image(image_array):
    """图像预处理 - 优化版"""
    try:
        # 转换为灰度图
        if len(image_array.shape) == 3:
            gray = cv2.cvtColor(image_array, cv2.COLOR_RGB2GRAY)
        else:
            gray = image_array
        
        # 自适应阈值二值化
        binary = cv2.adaptiveThreshold(
            gray, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # 降噪
        denoised = cv2.fastNlMeansDenoising(binary)
        
        return denoised
    except Exception as e:
        st.warning(f"预处理警告: {str(e)}, 使用原图")
        return image_array


def ocr_recognize(image_array, lang='chi_sim+eng'):
    """OCR识别 - 增强版"""
    try:
        # 预处理
        processed = preprocess_image(image_array)
        
        # OCR配置 - 优化识别率
        custom_config = r'--oem 3 --psm 6 -c preserve_interword_spaces=1'
        
        # 执行OCR
        text = pytesseract.image_to_string(
            processed, 
            config=custom_config, 
            lang=lang
        )
        
        return text.strip()
    
    except pytesseract.TesseractNotFoundError:
        st.error("❌ Tesseract OCR 引擎未找到！请检查 packages.txt 配置")
        return ""
    except Exception as e:
        st.error(f"❌ OCR识别失败: {str(e)}")
        return ""


def smart_parse_table(text):
    """智能解析表格 - 增强版"""
    if not text or not text.strip():
        return pd.DataFrame()
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    if not lines:
        return pd.DataFrame()
    
    data = []
    
    for line in lines:
        # 多种分隔符识别
        if '|' in line:
            # 表格线分隔
            row = [cell.strip() for cell in line.split('|') if cell.strip()]
        elif '\t' in line:
            # 制表符分隔
            row = [cell.strip() for cell in line.split('\t')]
        elif re.search(r'\s{3,}', line):
            # 多个空格分隔
            row = [cell.strip() for cell in re.split(r'\s{3,}', line)]
        elif re.search(r'[,，]', line):
            # 逗号分隔
            row = [cell.strip() for cell in re.split(r'[,，]', line)]
        else:
            # 单行数据
            row = [line]
        
        if row and any(cell for cell in row):  # 过滤空行
            data.append(row)
    
    if not data:
        return pd.DataFrame()
    
    # 统一列数
    max_cols = max(len(row) for row in data)
    
    for row in data:
        while len(row) < max_cols:
            row.append('')
    
    # 智能判断是否有表头
    if len(data) > 1 and max_cols > 1:
        # 如果第一行看起来像表头（文字较短，无数字）
        first_row_is_header = all(
            not any(char.isdigit() for char in str(cell)) 
            for cell in data[0]
        )
        
        if first_row_is_header:
            df = pd.DataFrame(data[1:], columns=data[0])
        else:
            df = pd.DataFrame(data)
    else:
        df = pd.DataFrame(data)
    
    return df


def convert_df_to_excel(df):
    """转换为Excel"""
    output = BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='识别表格')
        
        # 自动调整列宽
        worksheet = writer.sheets['识别表格']
        for idx, col in enumerate(df.columns):
            max_length = max(
                df[col].astype(str).apply(len).max(),
                len(str(col))
            )
            worksheet.column_dimensions[chr(65 + idx)].width = min(max_length + 2, 50)
    
    return output.getvalue()


def main():
    """主程序"""
    
    # 页面配置
    st.set_page_config(
        page_title="正讯OCR表格识别工具",
        page_icon="📊",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # 自定义CSS
    st.markdown("""
    <style>
    .main-header {
        text-align: center;
        padding: 2rem 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border-radius: 10px;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #667eea;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # 标题
    st.markdown("""
    <div class="main-header">
        <h1>📊 正讯图片表格识别转Excel工具</h1>
        <p>支持 JPG | PNG | PDF | 自动识别 | 一键导出</p>
    </div>
    """, unsafe_allow_html=True)
    
    # 检查依赖
    if not OCR_AVAILABLE:
        show_setup_instructions()
        st.stop()
    
    # 侧边栏
    with st.sidebar:
        st.header("⚙️ 配置选项")
        
        # OCR语言选择
        ocr_lang = st.selectbox(
            "识别语言",
            options=[
                ("中英文混合", "chi_sim+eng"),
                ("仅中文", "chi_sim"),
                ("仅英文", "eng")
            ],
            format_func=lambda x: x[0],
            index=0
        )
        
        st.markdown("---")
        
        # 使用说明
        st.header("📖 使用指南")
        st.markdown("""
        **操作流程:**
        1. 📤 上传图片文件
        2. 👀 预览图片内容
        3. 🔍 点击开始识别
        4. 📊 查看识别结果
        5. 💾 下载Excel文件
        
        **最佳实践:**
        - ✅ 图片清晰、对比度高
        - ✅ 表格边界明确
        - ✅ 文字大小适中（≥12号）
        - ✅ 避免倾斜或扭曲
        
        **支持格式:**
        - 📸 JPG / JPEG
        - 🖼️ PNG
        - 📄 PDF (仅第一页)
        """)
        
        st.markdown("---")
        
        # 系统信息
        with st.expander("🔧 系统信息"):
            st.code(f"""
Python: {sys.version.split()[0]}
OCR: {'✅ 可用' if OCR_AVAILABLE else '❌ 不可用'}
PDF: {'✅ 支持' if PDF_AVAILABLE else '❌ 不支持'}
Tesseract: {pytesseract.get_tesseract_version() if OCR_AVAILABLE else 'N/A'}
            """)
    
    # 主界面
    tab1, tab2 = st.tabs(["📤 上传识别", "❓ 帮助"])
    
    with tab1:
        # 文件上传
        uploaded_file = st.file_uploader(
            "选择图片文件",
            type=['jpg', 'jpeg', 'png', 'pdf'],
            help="支持 JPG、PNG、PDF 格式，文件大小限制 200MB"
        )
        
        if uploaded_file:
            col1, col2 = st.columns([3, 2])
            
            with col1:
                st.subheader("🖼️ 图片预览")
                
                try:
                    # 处理文件
                    if uploaded_file.type == 'application/pdf':
                        if not PDF_AVAILABLE:
                            st.error("❌ PDF支持未启用，请检查 pdf2image 依赖")
                            st.stop()
                        
                        with st.spinner("正在转换PDF..."):
                            images = convert_from_bytes(uploaded_file.read(), dpi=200)
                            image = images[0]
                            image_array = np.array(image)
                    else:
                        image = Image.open(uploaded_file)
                        image_array = np.array(image)
                    
                    # 显示预览
                    st.image(image, use_column_width=True, caption=uploaded_file.name)
                    
                except Exception as e:
                    st.error(f"❌ 文件加载失败: {str(e)}")
                    st.stop()
            
            with col2:
                st.subheader("📋 文件信息")
                
                file_info = f"""
                **文件名:** {uploaded_file.name}  
                **大小:** {uploaded_file.size / 1024:.2f} KB  
                **类型:** {uploaded_file.type}  
                **尺寸:** {image.size[0]} × {image.size[1]} px
                """
                st.markdown(file_info)
                
                st.markdown("---")
                
                # 识别按钮
                if st.button("🔍 开始识别", type="primary", use_container_width=True):
                    
                    with st.spinner("🔄 正在识别中，请稍候..."):
                        # 进度提示
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        # OCR识别
                        status_text.text("⏳ 正在预处理图片...")
                        progress_bar.progress(30)
                        
                        status_text.text("⏳ 正在OCR识别...")
                        progress_bar.progress(60)
                        
                        text = ocr_recognize(image_array, ocr_lang[1])
                        
                        status_text.text("⏳ 正在解析表格...")
                        progress_bar.progress(90)
                        
                        if text:
                            # 解析表格
                            df = smart_parse_table(text)
                            
                            # 保存到session
                            st.session_state['extracted_data'] = df
                            st.session_state['raw_text'] = text
                            st.session_state['filename'] = uploaded_file.name
                            
                            progress_bar.progress(100)
                            status_text.text("✅ 识别完成!")
                            
                            st.success("✅ 识别成功！请查看下方结果")
                        else:
                            st.error("❌ 未能识别到文本，请检查图片质量")
            
            # 显示识别结果
            if 'extracted_data' in st.session_state:
                st.markdown("---")
                st.subheader("📊 识别结果")
                
                df = st.session_state['extracted_data']
                raw_text = st.session_state['raw_text']
                
                # 统计卡片
                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                
                with col_m1:
                    st.metric("📝 总行数", len(df))
                with col_m2:
                    st.metric("📊 总列数", len(df.columns) if not df.empty else 0)
                with col_m3:
                    st.metric("🔤 字符数", len(raw_text))
                with col_m4:
                    st.metric("💾 数据单元", len(df) * len(df.columns) if not df.empty else 0)
                
                # 数据表格
                if not df.empty:
                    st.markdown("#### 📋 识别的表格数据")
                    st.dataframe(
                        df, 
                        use_container_width=True, 
                        height=400,
                        hide_index=True
                    )
                    
                    # 下载按钮
                    excel_data = convert_df_to_excel(df)
                    filename = st.session_state.get('filename', 'table')
                    output_name = f"提取表格_{filename.rsplit('.', 1)[0]}.xlsx"
                    
                    col_d1, col_d2, col_d3 = st.columns([1, 1, 2])
                    with col_d1:
                        st.download_button(
                            label="💾 下载 Excel",
                            data=excel_data,
                            file_name=output_name,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            type="primary",
                            use_container_width=True
                        )
                    
                    with col_d2:
                        csv_data = df.to_csv(index=False).encode('utf-8-sig')
                        st.download_button(
                            label="📄 下载 CSV",
                            data=csv_data,
                            file_name=output_name.replace('.xlsx', '.csv'),
                            mime="text/csv",
                            use_container_width=True
                        )
                else:
                    st.warning("⚠️ 未能解析出表格结构，请查看原始文本")
                
                # 原始文本
                with st.expander("📄 查看原始识别文本"):
                    st.text_area(
                        "OCR识别的完整文本",
                        raw_text,
                        height=300,
                        disabled=True
                    )
        else:
            # 空状态提示
            st.info("👆 请上传图片文件开始识别")
    
    with tab2:
        st.markdown("""
        ## ❓ 常见问题
        
        ### Q1: 识别准确率低怎么办？
        - 确保图片清晰、光线充足
        - 调整图片对比度
        - 尽量使图片中的表格水平对齐
        - 选择正确的识别语言
        
        ### Q2: 支持哪些文件格式？
        - ✅ JPG/JPEG 图片
        - ✅ PNG 图片
        - ✅ PDF 文档（仅识别第一页）
        
        ### Q3: 文件大小有限制吗？
        - 单个文件最大 200MB
        - 建议图片分辨率在 1000-3000px 之间
        
        ### Q4: 如何提高识别速度？
        - 压缩图片大小（保持清晰度）
        - 裁剪掉不需要的区域
        - 转换为PNG格式
        
        ### Q5: 表格格式混乱怎么办？
        - 下载Excel后手动调整
        - 使用CSV格式可能更准确
        - 检查原始文本进行对比
        
        ---
        
        ## 📧 反馈与支持
        
        如有问题或建议，欢迎反馈！
        """)
    
    # 页脚
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #7f8c8d; padding: 1rem;'>
        <p>📊 正讯OCR 表格识别工具 | Powered by Tesseract OCR & Streamlit</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
