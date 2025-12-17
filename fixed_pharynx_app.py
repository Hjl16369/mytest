"""
咽部图像筛查系统 - Streamlit Web应用版本(PDF报告)
运行命令: streamlit run fixed_pharynx_app.py
"""

import streamlit as st
import cv2
import numpy as np
from PIL import Image
from datetime import datetime
import traceback
from io import BytesIO
import sys
import os

# PDF 生成库
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, Image as RLImage
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER

# ================= 页面配置 =================
st.set_page_config(
    page_title="正掌讯咽部健康筛查AI系统",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================= 图像分析器 =================
class PharynxImageAnalyzer:

    def __init__(self):
        self.img_size = (224, 224)

    def preprocess_image(self, img_array):
        if len(img_array.shape) == 2:
            img_rgb = cv2.cvtColor(img_array, cv2.COLOR_GRAY2RGB)
        elif img_array.shape[2] == 4:
            img_rgb = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
        else:
            img_rgb = img_array.copy()

        img_resized = cv2.resize(img_rgb, self.img_size)
        return img_rgb, img_resized

    def analyze_color_features(self, img):
        hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)

        lower_red1 = np.array([0, 50, 50])
        upper_red1 = np.array([10, 255, 255])
        lower_red2 = np.array([170, 50, 50])
        upper_red2 = np.array([180, 255, 255])

        mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
        mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
        red_mask = cv2.bitwise_or(mask1, mask2)

        lower_white = np.array([0, 0, 200])
        upper_white = np.array([180, 30, 255])
        white_mask = cv2.inRange(hsv, lower_white, upper_white)

        total_pixels = img.shape[0] * img.shape[1]

        return {
            "red_ratio": float(np.sum(red_mask > 0) / total_pixels),
            "white_ratio": float(np.sum(white_mask > 0) / total_pixels),
            "avg_brightness": float(np.mean(hsv[:, :, 2])),
            "avg_saturation": float(np.mean(hsv[:, :, 1])),
            "red_mask": red_mask,
            "white_mask": white_mask,
        }

    def analyze_texture_features(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        edges = cv2.Canny(gray, 50, 150)

        return {
            "edge_density": float(np.sum(edges > 0) / edges.size),
            "texture_variance": float(np.std(gray)),
            "laplacian_variance": float(np.var(cv2.Laplacian(gray, cv2.CV_64F))),
            "edges": edges,
        }

# ================= 疾病分类器 =================
class DiseaseClassifier:

    def __init__(self):
        self.patterns = {
            "healthy": ("健康", "🟢", 4),
            "chronic": ("慢性咽炎", "🟠", 3),
            "acute": ("急性咽炎", "🟡", 2),
            "tonsil": ("扁桃体炎", "🔴", 1),
        }

    def classify(self, color, texture):
        if color["white_ratio"] > 0.05:
            return self.patterns["tonsil"]
        if color["red_ratio"] > 0.2:
            return self.patterns["acute"]
        if color["red_ratio"] > 0.1:
            return self.patterns["chronic"]
        return self.patterns["healthy"]

# ================= PDF 报告 =================
class PDFReportGenerator:

    def __init__(self):
        self.font_name = "Helvetica"

    def generate_report(self, result, image):
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()

        story = []
        story.append(Paragraph("Pharynx Health Screening Report", styles["Title"]))
        story.append(Spacer(1, 12))

        pil_img = Image.fromarray(image)
        img_buf = BytesIO()
        pil_img.save(img_buf, format="PNG")
        img_buf.seek(0)

        story.append(RLImage(img_buf, width=10 * cm, height=7 * cm))
        story.append(Spacer(1, 12))

        story.append(Paragraph(f"诊断结果：{result[0]} {result[1]}", styles["Normal"]))

        doc.build(story)
        pdf = buffer.getvalue()
        buffer.close()
        return pdf

# ================= Session 初始化 =================
def init_session():
    if "analyzer" not in st.session_state:
        st.session_state.analyzer = PharynxImageAnalyzer()
    if "classifier" not in st.session_state:
        st.session_state.classifier = DiseaseClassifier()
    if "pdf" not in st.session_state:
        st.session_state.pdf = PDFReportGenerator()
    if "result" not in st.session_state:
        st.session_state.result = None

# ================= 主程序 =================
def main():

    init_session()

    # ---------- Sidebar ----------
    with st.sidebar:
        st.markdown("# 🏥 咽部健康筛查")
        st.markdown("---")
        st.markdown("""
        ### 📱 使用说明
        1. 上传咽部照片  
        2. 点击开始分析  
        3. 查看筛查结果  
        4. 下载 PDF 报告  

        ⚠️ 本系统仅供健康筛查参考，不能替代医生诊断
        """)

    # ---------- 主界面 ----------
    st.markdown("## 📤 上传咽部照片")
    file = st.file_uploader("选择图片", type=["jpg", "png", "jpeg"])

    if file:
        img = cv2.imdecode(np.frombuffer(file.read(), np.uint8), 1)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        st.image(img, caption="原始图像", use_container_width=True)

        if st.button("🔍 开始分析", type="primary"):
            _, resized = st.session_state.analyzer.preprocess_image(img)
            color = st.session_state.analyzer.analyze_color_features(resized)
            texture = st.session_state.analyzer.analyze_texture_features(resized)
            result = st.session_state.classifier.classify(color, texture)

            st.session_state.result = result

    if st.session_state.result:
        name, icon, _ = st.session_state.result
        st.success(f"诊断结果：{name} {icon}")

        pdf = st.session_state.pdf.generate_report(
            st.session_state.result, img
        )

        st.download_button(
            "📄 下载 PDF 报告",
            data=pdf,
            file_name="pharynx_report.pdf",
            mime="application/pdf",
        )

    st.markdown("---")
    st.markdown(
        "<div style='text-align:center;color:#888'>© 2025 咽部健康筛查 AI 系统</div>",
        unsafe_allow_html=True,
    )

# ================= 程序入口 =================
if __name__ == "__main__":
    main()
