"""
咽部图像筛查系统 - Streamlit Web应用版本（PDF报告）
运行命令: streamlit run pharynx_screening_app.py

部署说明:
1. 上传此文件到 Streamlit Cloud
2. 同时上传 requirements.txt 文件
3. 同时上传 packages.txt 文件
"""

import streamlit as st
import numpy as np
from PIL import Image
from datetime import datetime
import traceback
from io import BytesIO
import sys

# 尝试导入 opencv，使用 headless 版本
try:
    import cv2
    print("✓ OpenCV 导入成功")
except ImportError as e:
    st.error("❌ OpenCV 导入失败，请检查 requirements.txt 配置")
    st.stop()

# PDF生成库
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    print("✓ ReportLab 导入成功")
except ImportError as e:
    st.error("❌ ReportLab 导入失败，请检查 requirements.txt 配置")
    st.stop()

print("=" * 60)
print("咽部筛查系统启动...")
print(f"Python 版本: {sys.version}")
print(f"OpenCV 版本: {cv2.__version__}")
print("=" * 60)

# 设置页面配置
try:
    st.set_page_config(
        page_title="正掌讯咽部健康筛查AI系统",
        page_icon="🏥",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    print("✓ 页面配置成功")
except Exception as e:
    print(f"✗ 页面配置失败: {e}")


class PharynxImageAnalyzer:
    """咽部图像分析器"""
    
    def __init__(self):
        self.img_size = (224, 224)
        print("✓ PharynxImageAnalyzer 初始化成功")
    
    def preprocess_image(self, img_array):
        """预处理图像"""
        try:
            print(f"  - 输入图像 shape: {img_array.shape}")
            
            # 确保是3通道RGB图像
            if len(img_array.shape) == 2:
                img_rgb = cv2.cvtColor(img_array, cv2.COLOR_GRAY2RGB)
            elif img_array.shape[2] == 4:
                img_rgb = cv2.cvtColor(img_array, cv2.COLOR_RGBA2RGB)
            else:
                img_rgb = img_array.copy()
            
            # 调整大小
            img_resized = cv2.resize(img_rgb, self.img_size)
            
            print(f"  - 预处理后 shape: {img_resized.shape}")
            return img_rgb, img_resized
            
        except Exception as e:
            print(f"✗ 预处理失败: {e}")
            raise
    
    def analyze_color_features(self, img):
        """分析颜色特征"""
        try:
            print("  - 开始颜色特征分析...")
            
            # 转换到HSV色彩空间
            hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
            
            # 红色区域检测（炎症）
            lower_red1 = np.array([0, 50, 50])
            upper_red1 = np.array([10, 255, 255])
            lower_red2 = np.array([170, 50, 50])
            upper_red2 = np.array([180, 255, 255])
            
            mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
            mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
            red_mask = cv2.bitwise_or(mask1, mask2)
            
            total_pixels = img.shape[0] * img.shape[1]
            red_ratio = np.sum(red_mask > 0) / total_pixels
            
            # 白色区域检测（脓点）
            lower_white = np.array([0, 0, 200])
            upper_white = np.array([180, 30, 255])
            white_mask = cv2.inRange(hsv, lower_white, upper_white)
            white_ratio = np.sum(white_mask > 0) / total_pixels
            
            # 计算平均值
            avg_brightness = float(np.mean(hsv[:, :, 2]))
            avg_saturation = float(np.mean(hsv[:, :, 1]))
            
            print(f"    红色比例: {red_ratio:.4f}, 白色比例: {white_ratio:.4f}")
            
            return {
                'red_ratio': float(red_ratio),
                'white_ratio': float(white_ratio),
                'avg_brightness': avg_brightness,
                'avg_saturation': avg_saturation,
                'red_mask': red_mask,
                'white_mask': white_mask
            }
            
        except Exception as e:
            print(f"✗ 颜色特征分析失败: {e}")
            raise
    
    def analyze_texture_features(self, img):
        """分析纹理特征"""
        try:
            print("  - 开始纹理特征分析...")
            
            # 转换为灰度图
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            
            # 边缘检测
            edges = cv2.Canny(gray, 50, 150)
            edge_density = float(np.sum(edges > 0) / edges.size)
            
            # 纹理方差
            texture_variance = float(np.std(gray))
            
            # Laplacian变换
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            laplacian_variance = float(np.var(laplacian))
            
            print(f"    边缘密度: {edge_density:.4f}, 纹理方差: {texture_variance:.2f}")
            
            return {
                'edge_density': edge_density,
                'texture_variance': texture_variance,
                'laplacian_variance': laplacian_variance,
                'edges': edges
            }
            
        except Exception as e:
            print(f"✗ 纹理特征分析失败: {e}")
            raise


class DiseaseClassifier:
    """疾病分类器"""
    
    def __init__(self):
        self.disease_patterns = {
            'healthy': {
                'name': '健康',
                'name_en': 'Healthy',
                'red_ratio': (0.0, 0.1),
                'white_ratio': (0.0, 0.03),
                'texture_variance': (15, 40),
                'severity': 'none',
                'severity_cn': '无异常',
                'symptoms': ['咽部状态正常', '无明显不适'],
                'color': '🟢',
                'priority': 4
            },
            'chronic_pharyngitis': {
                'name': '慢性咽炎',
                'name_en': 'Chronic Pharyngitis',
                'red_ratio': (0.1, 0.25),
                'white_ratio': (0.0, 0.1),
                'texture_variance': (20, 60),
                'severity': 'low',
                'severity_cn': '轻度',
                'symptoms': ['咽干', '咽痒', '异物感', '轻微不适'],
                'color': '🟠',
                'priority': 3
            },
            'acute_pharyngitis': {
                'name': '急性咽炎',
                'name_en': 'Acute Pharyngitis',
                'red_ratio': (0.15, 0.5),
                'white_ratio': (0.0, 0.05),
                'texture_variance': (30, 80),
                'severity': 'medium',
                'severity_cn': '中度',
                'symptoms': ['咽痛', '吞咽困难', '咽部充血', '发热可能'],
                'color': '🟡',
                'priority': 2
            },
            'tonsillitis': {
                'name': '扁桃体炎',
                'name_en': 'Tonsillitis',
                'red_ratio': (0.2, 1.0),
                'white_ratio': (0.05, 0.3),
                'texture_variance': (40, 100),
                'severity': 'high',
                'severity_cn': '较重',
                'symptoms': ['扁桃体肿大', '白色脓点', '高热', '吞咽剧痛'],
                'color': '🔴',
                'priority': 1
            }
        }
        print("✓ DiseaseClassifier 初始化成功")
    
    def classify(self, color_features, texture_features):
        """疾病分类"""
        try:
            print("  - 开始疾病分类...")
            
            scores = {}
            
            for disease_id, pattern in self.disease_patterns.items():
                score = 0
                
                # 红色区域匹配
                red_min, red_max = pattern['red_ratio']
                if red_min <= color_features['red_ratio'] <= red_max:
                    score += 30
                elif color_features['red_ratio'] > red_max:
                    score += 15
                
                # 白色区域匹配
                white_min, white_max = pattern['white_ratio']
                if white_min <= color_features['white_ratio'] <= white_max:
                    score += 25
                elif color_features['white_ratio'] > white_max:
                    score += 15
                
                # 纹理匹配
                texture_min, texture_max = pattern['texture_variance']
                if texture_min <= texture_features['texture_variance'] <= texture_max:
                    score += 25
                
                # 边缘密度
                if texture_features['edge_density'] > 0.1:
                    if disease_id != 'healthy':
                        score += 20
                else:
                    if disease_id == 'healthy':
                        score += 20
                
                scores[disease_id] = score
            
            # 找到最高分
            best_match = max(scores.items(), key=lambda x: x[1])
            disease_id, confidence = best_match
            pattern = self.disease_patterns[disease_id]
            
            print(f"    分类结果: {pattern['name']}, 置信度: {confidence}")
            
            return {
                'disease_id': disease_id,
                'disease_name': pattern['name'],
                'disease_name_en': pattern['name_en'],
                'confidence': min(confidence, 100),
                'severity': pattern['severity'],
                'severity_cn': pattern['severity_cn'],
                'symptoms': pattern['symptoms'],
                'color': pattern['color'],
                'priority': pattern['priority'],
                'all_scores': scores
            }
            
        except Exception as e:
            print(f"✗ 分类失败: {e}")
            raise
    
    def get_recommendations(self, classification):
        """获取健康建议"""
        disease_id = classification['disease_id']
        
        recommendations = {
            'healthy': [
                '咽部状态良好，请继续保持',
                '建议：保持良好的口腔卫生习惯',
                '建议：多喝温水，保持咽部湿润',
                '建议：定期进行健康检查',
                '建议：避免过度用嗓'
            ],
            'chronic_pharyngitis': [
                '检测到慢性咽炎迹象',
                '建议：戒烟戒酒，避免刺激性食物',
                '建议：多饮温水，保持咽部湿润',
                '建议：避免粉尘和有害气体',
                '建议：加强锻炼，提高免疫力',
                '建议：如症状持续加重，请就医咨询'
            ],
            'acute_pharyngitis': [
                '检测到急性咽炎迹象',
                '建议：及时就医，明确诊断',
                '建议：充足休息，避免劳累',
                '建议：多喝温水，清淡饮食',
                '建议：避免辛辣、油腻食物',
                '建议：遵医嘱用药，不要自行用药',
                '注意：观察体温变化'
            ],
            'tonsillitis': [
                '检测到扁桃体炎迹象',
                '重要：请立即就医检查',
                '可能需要：抗生素治疗（遵医嘱）',
                '建议：卧床休息，避免活动',
                '建议：流质或半流质饮食',
                '建议：多喝水，注意退热',
                '警惕：高热不退、呼吸困难请急诊'
            ]
        }
        
        return recommendations.get(disease_id, ['请咨询专业医生'])


class PDFReportGenerator:
    """PDF报告生成器"""
    
    def __init__(self):
        # 注册中文字体
        self.setup_chinese_font()
        print("✓ PDFReportGenerator 初始化成功")
    
    def setup_chinese_font(self):
        """设置中文字体支持"""
        try:
            # 尝试注册系统中文字体
            import platform
            import os
            
            system = platform.system()
            font_registered = False
            
            # 首先尝试 Streamlit Cloud 常见路径
            streamlit_cloud_fonts = [
                "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
                "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            ]
            
            for font_path in streamlit_cloud_fonts:
                if os.path.exists(font_path):
                    try:
                        pdfmetrics.registerFont(TTFont('Chinese', font_path))
                        font_registered = True
                        print(f"  ✓ 已注册中文字体: {font_path}")
                        self.font_name = 'Chinese'
                        return
                    except Exception as e:
                        print(f"  - 尝试 {font_path} 失败: {e}")
                        continue
            
            # Windows系统
            if system == "Windows":
                font_paths = [
                    "C:/Windows/Fonts/msyh.ttc",  # 微软雅黑
                    "C:/Windows/Fonts/simhei.ttf",  # 黑体
                    "C:/Windows/Fonts/simsun.ttc",  # 宋体
                ]
                for font_path in font_paths:
                    if os.path.exists(font_path):
                        try:
                            pdfmetrics.registerFont(TTFont('Chinese', font_path))
                            font_registered = True
                            print(f"  ✓ 已注册中文字体: {font_path}")
                            self.font_name = 'Chinese'
                            return
                        except:
                            continue
            
            # macOS系统
            elif system == "Darwin":
                font_paths = [
                    "/System/Library/Fonts/PingFang.ttc",  # 苹方
                    "/System/Library/Fonts/STHeiti Light.ttc",  # 华文黑体
                    "/Library/Fonts/Songti.ttc",  # 宋体
                ]
                for font_path in font_paths:
                    if os.path.exists(font_path):
                        try:
                            pdfmetrics.registerFont(TTFont('Chinese', font_path))
                            font_registered = True
                            print(f"  ✓ 已注册中文字体: {font_path}")
                            self.font_name = 'Chinese'
                            return
                        except:
                            continue
            
            # Linux系统 - 其他路径
            else:
                font_paths = [
                    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
                    "/usr/share/fonts/truetype/arphic/uming.ttc",
                    "/usr/share/fonts/truetype/arphic/ukai.ttc",
                ]
                for font_path in font_paths:
                    if os.path.exists(font_path):
                        try:
                            pdfmetrics.registerFont(TTFont('Chinese', font_path))
                            font_registered = True
                            print(f"  ✓ 已注册中文字体: {font_path}")
                            self.font_name = 'Chinese'
                            return
                        except:
                            continue
            
            # 如果都没找到，使用 Helvetica
            if not font_registered:
                print("  ⚠ 警告: 未找到系统中文字体，将使用默认字体（可能无法显示中文）")
                print(f"  - 当前系统: {system}")
                print("  - 建议: 在 packages.txt 中添加 fonts-noto-cjk")
                self.font_name = 'Helvetica'
                
        except Exception as e:
            print(f"  ⚠ 字体设置警告: {e}")
            print(traceback.format_exc())
            self.font_name = 'Helvetica'
    
    def generate_report(self, result_data, original_image):
        """生成PDF报告"""
        try:
            print("  - 开始生成PDF报告...")
            
            # 创建BytesIO对象
            buffer = BytesIO()
            
            # 创建PDF文档
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=2*cm,
                leftMargin=2*cm,
                topMargin=2*cm,
                bottomMargin=2*cm
            )
            
            # 准备内容
            story = []
            styles = getSampleStyleSheet()
            
            # 创建自定义样式（使用中文字体）
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontName=self.font_name,
                fontSize=24,
                textColor=colors.HexColor('#2E86AB'),
                spaceAfter=30,
                alignment=TA_CENTER
            )
            
            heading_style = ParagraphStyle(
                'CustomHeading',
                parent=styles['Heading2'],
                fontName=self.font_name,
                fontSize=16,
                textColor=colors.HexColor('#333333'),
                spaceAfter=12,
                spaceBefore=12
            )
            
            normal_style = ParagraphStyle(
                'CustomNormal',
                parent=styles['Normal'],
                fontName=self.font_name,
                fontSize=11,
                leading=16
            )
            
            subtitle_style = ParagraphStyle(
                'CustomSubtitle',
                parent=styles['Normal'],
                fontName=self.font_name,
                fontSize=12,
                textColor=colors.grey,
                alignment=TA_CENTER,
                spaceAfter=10
            )
            
            # 标题
            story.append(Paragraph("咽部健康筛查AI分析报告", title_style))
            story.append(Paragraph("Pharynx Health Screening Report", subtitle_style))
            story.append(Spacer(1, 0.5*cm))
            
            # 基本信息表格
            classification = result_data['classification']
            
            basic_info = [
                ['报告生成时间', result_data['timestamp']],
                ['诊断结果', f"{classification['disease_name']} ({classification['disease_name_en']})"],
                ['置信度', f"{classification['confidence']}%"],
                ['严重程度', classification['severity_cn']]
            ]
            
            basic_table = Table(basic_info, colWidths=[5*cm, 12*cm])
            basic_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E8F4F8')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), self.font_name),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ('TOPPADDING', (0, 0), (-1, -1), 12),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ]))
            
            story.append(basic_table)
            story.append(Spacer(1, 0.8*cm))
            
            # 添加原始图像
            story.append(Paragraph("原始咽部图像", heading_style))
            
            # 将numpy数组转换为PIL Image
            pil_image = Image.fromarray(original_image)
            img_buffer = BytesIO()
            pil_image.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            # 添加到PDF
            img = RLImage(img_buffer, width=8*cm, height=6*cm)
            story.append(img)
            story.append(Spacer(1, 0.8*cm))
            
            # 特征分析
            story.append(Paragraph("特征分析", heading_style))
            
            color_features = result_data['color_features']
            texture_features = result_data['texture_features']
            
            features_data = [
                ['特征类型', '特征名称', '数值'],
                ['颜色特征', '红色区域占比', f"{color_features['red_ratio']:.2%}"],
                ['', '白色区域占比', f"{color_features['white_ratio']:.2%}"],
                ['', '平均亮度', f"{color_features['avg_brightness']:.1f}"],
                ['', '平均饱和度', f"{color_features['avg_saturation']:.1f}"],
                ['纹理特征', '边缘密度', f"{texture_features['edge_density']:.2%}"],
                ['', '纹理方差', f"{texture_features['texture_variance']:.1f}"],
                ['', '拉普拉斯方差', f"{texture_features['laplacian_variance']:.1f}"]
            ]
            
            features_table = Table(features_data, colWidths=[4*cm, 6*cm, 7*cm])
            features_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), self.font_name),
                ('FONTSIZE', (0, 0), (-1, 0), 11),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#E8F4F8')),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 10),
                ('TOPPADDING', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
            ]))
            
            story.append(features_table)
            story.append(Spacer(1, 0.8*cm))
            
            # 可能症状
            story.append(Paragraph("可能症状", heading_style))
            
            for symptom in classification['symptoms']:
                story.append(Paragraph(f"• {symptom}", normal_style))
            
            story.append(Spacer(1, 0.5*cm))
            
            # 健康建议
            story.append(Paragraph("健康建议", heading_style))
            
            for rec in result_data['recommendations']:
                story.append(Paragraph(f"• {rec}", normal_style))
            
            story.append(Spacer(1, 1*cm))
            
            # 免责声明
            disclaimer_style = ParagraphStyle(
                'Disclaimer',
                parent=styles['Normal'],
                fontName=self.font_name,
                fontSize=9,
                textColor=colors.grey,
                alignment=TA_CENTER
            )
            
            story.append(Paragraph("=" * 80, disclaimer_style))
            story.append(Spacer(1, 0.3*cm))
            story.append(Paragraph("免责声明", disclaimer_style))
            story.append(Paragraph(
                "本报告由AI系统自动生成，仅供健康筛查参考，不能替代专业医疗诊断。",
                disclaimer_style
            ))
            story.append(Paragraph(
                "如有不适症状，请及时就医咨询专业医生。",
                disclaimer_style
            ))
            story.append(Spacer(1, 0.3*cm))
            story.append(Paragraph(
                "© 2025 咽部健康筛查AI系统 | Powered by 正掌讯软件",
                disclaimer_style
            ))
            
            # 生成PDF
            doc.build(story)
            
            # 获取PDF数据
            pdf_data = buffer.getvalue()
            buffer.close()
            
            print("  ✓ PDF报告生成成功")
            return pdf_data
            
        except Exception as e:
            print(f"  ✗ PDF生成失败: {e}")
            print(traceback.format_exc())
            raise


def create_visualization(img_rgb, color_features, texture_features):
    """创建特征可视化"""
    try:
        print("  - 创建可视化图像...")
        
        # 调整图像大小
        display_size = (300, 300)
        img_display = cv2.resize(img_rgb, display_size)
        
        # 创建红色热图
        red_mask = color_features['red_mask']
        red_mask_resized = cv2.resize(red_mask, display_size)
        red_heatmap = cv2.applyColorMap(red_mask_resized, cv2.COLORMAP_HOT)
        red_heatmap_rgb = cv2.cvtColor(red_heatmap, cv2.COLOR_BGR2RGB)
        
        # 创建边缘图
        edges = texture_features['edges']
        edges_resized = cv2.resize(edges, display_size)
        edges_rgb = cv2.cvtColor(edges_resized, cv2.COLOR_GRAY2RGB)
        
        print("  ✓ 可视化创建成功")
        return img_display, red_heatmap_rgb, edges_rgb
        
    except Exception as e:
        print(f"  ✗ 可视化创建失败: {e}")
        return None, None, None


def init_session_state():
    """初始化会话状态"""
    if 'analyzer' not in st.session_state:
        st.session_state.analyzer = PharynxImageAnalyzer()
    if 'classifier' not in st.session_state:
        st.session_state.classifier = DiseaseClassifier()
    if 'pdf_generator' not in st.session_state:
        st.session_state.pdf_generator = PDFReportGenerator()
    if 'history' not in st.session_state:
        st.session_state.history = []
    if 'current_result' not in st.session_state:
        st.session_state.current_result = None


def main():
    """主应用"""
    
    print("\n" + "=" * 60)
    print("开始渲染 Streamlit 应用...")
    print("=" * 60)
    
    try:
        # 初始化
        init_session_state()
        print("✓ 会话状态初始化成功")
        
        # 侧边栏
        with st.sidebar:
            st.markdown("# 🏥 咽部健康筛查")
            st.markdown("---")
            
            st.markdown("""
            ### 📱 使用说明
            1. 📤 上传咽部照片
            2. 🔍 点击开始分析
            3. 📊 查看筛查结果
            4. 📄 下载PDF报告
            
            ### ⚠️ 重要提示
            - 本系统仅供参考
            - 不能替代医生诊断
            - 严重症状请就医
            
            ### 📸 拍照建议
            - ✅ 光线充足
            - ✅ 正对咽部
            - ✅ 保持稳定
            - ✅ 焦距清晰
            """)
            
            st.markdown("---")
            
            if st.session_state.history:
                st.markdown(f"### 📜 历史记录 ({len(st.session_state.history)})")
                if st.button("🗑️ 清除历史", use_container_width=True):
                    st.session_state.history = []
                    st.session_state.current_result = None
                    st.rerun()
        
        # 主标题
        st.markdown("""
        <div style='text-align: center;'>
            <h1 style='color: #2E86AB;'>🏥 正掌讯咽部图像智能筛查系统</h1>
            <p style='color: #666; font-size: 18px;'>
                Pharynx Health Screening System
            </p>
            <p style='color: #888;'>AI辅助上呼吸道健康评估</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # 文件上传区
        st.markdown("### 📤 上传咽部照片")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            uploaded_file = st.file_uploader(
                "选择图片文件",
                type=['jpg', 'jpeg', 'png', 'bmp'],
                help="支持 JPG、PNG、BMP 格式，建议分辨率 640x480 以上",
                label_visibility="collapsed"
            )
        
        if uploaded_file is not None:
            print(f"\n收到上传文件: {uploaded_file.name}")
            
            try:
                # 读取图像
                file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
                img_bgr = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                
                if img_bgr is None:
                    st.error("❌ 无法读取图像，请检查文件格式")
                    return
                
                img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
                print(f"图像读取成功: shape={img_rgb.shape}")
                
                # 显示原图
                st.markdown("### 📷 上传的图像")
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    st.image(img_rgb, caption="原始咽部图像", use_container_width=True)
                
                # 分析按钮
                col1, col2, col3 = st.columns([1, 1, 1])
                with col2:
                    if st.button("🔍 开始智能分析", type="primary", use_container_width=True):
                        print("\n点击分析按钮，开始处理...")
                        
                        with st.spinner("🤖 AI正在分析中，请稍候..."):
                            try:
                                # 预处理
                                print("步骤 1/5: 预处理图像")
                                img_rgb_processed, img_resized = st.session_state.analyzer.preprocess_image(img_rgb)
                                
                                # 特征提取
                                print("步骤 2/5: 提取颜色特征")
                                color_features = st.session_state.analyzer.analyze_color_features(img_resized)
                                
                                print("步骤 3/5: 提取纹理特征")
                                texture_features = st.session_state.analyzer.analyze_texture_features(img_resized)
                                
                                # 分类
                                print("步骤 4/5: 进行疾病分类")
                                classification = st.session_state.classifier.classify(color_features, texture_features)
                                
                                print("步骤 5/5: 生成建议")
                                recommendations = st.session_state.classifier.get_recommendations(classification)
                                
                                # 保存结果
                                st.session_state.current_result = {
                                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'classification': classification,
                                    'recommendations': recommendations,
                                    'color_features': {k: v for k, v in color_features.items() if not isinstance(v, np.ndarray)},
                                    'texture_features': {k: v for k, v in texture_features.items() if not isinstance(v, np.ndarray)},
                                    'img_rgb': img_rgb,
                                    'color_features_full': color_features,
                                    'texture_features_full': texture_features
                                }
                                
                                st.session_state.history.append(st.session_state.current_result)
                                
                                print("✓ 分析完成！")
                                st.success("✅ 分析完成！")
                                st.rerun()
                                
                            except Exception as e:
                                error_msg = f"分析过程出错: {str(e)}"
                                print(f"✗ {error_msg}")
                                print(traceback.format_exc())
                                st.error(f"❌ {error_msg}")
                                st.exception(e)
                
                # 显示结果
                if st.session_state.current_result:
                    result = st.session_state.current_result
                    classification = result['classification']
                    recommendations = result['recommendations']
                    color_features = result['color_features']
                    texture_features = result['texture_features']
                    
                    st.markdown("---")
                    st.markdown("## 📊 筛查结果")
                    
                    # 结果卡片
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric(
                            label="诊断结果",
                            value=classification['disease_name']
                        )
                        st.markdown(f"<h1 style='text-align: center; font-size: 60px;'>{classification['color']}</h1>", unsafe_allow_html=True)
                    
                    with col2:
                        st.metric(
                            label="置信度",
                            value=f"{classification['confidence']}%"
                        )
                        st.progress(classification['confidence'] / 100)
                    
                    with col3:
                        st.metric(
                            label="严重程度",
                            value=classification['severity_cn']
                        )
                    
                    with col4:
                        st.metric(
                            label="分析时间",
                            value=result['timestamp'].split()[1]
                        )
                    
                    # 详细特征
                    st.markdown("### 🔬 详细特征分析")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("#### 🎨 颜色特征")
                        st.write(f"🔴 红色区域占比: **{color_features['red_ratio']:.2%}**")
                        st.progress(min(color_features['red_ratio'] * 5, 1.0))
                        
                        st.write(f"⚪ 白色区域占比: **{color_features['white_ratio']:.2%}**")
                        st.progress(min(color_features['white_ratio'] * 10, 1.0))
                        
                        st.write(f"💡 平均亮度: **{color_features['avg_brightness']:.1f}**")
                        st.write(f"🌈 平均饱和度: **{color_features['avg_saturation']:.1f}**")
                    
                    with col2:
                        st.markdown("#### 📐 纹理特征")
                        st.write(f"📊 边缘密度: **{texture_features['edge_density']:.2%}**")
                        st.progress(min(texture_features['edge_density'] * 5, 1.0))
                        
                        st.write(f"📈 纹理方差: **{texture_features['texture_variance']:.1f}**")
                        st.write(f"🔍 拉普拉斯方差: **{texture_features['laplacian_variance']:.1f}**")
                    
                    # 可视化
                    st.markdown("### 🎨 可视化分析")
                    img_vis, red_heat, edges_vis = create_visualization(
                        result['img_rgb'],
                        result['color_features_full'],
                        result['texture_features_full']
                    )
                    
                    if img_vis is not None:
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.image(img_vis, caption="原始图像", use_container_width=True)
                        with col2:
                            st.image(red_heat, caption="炎症热图", use_container_width=True)
                        with col3:
                            st.image(edges_vis, caption="纹理分析", use_container_width=True)
                    
                    # 症状和建议
                    st.markdown("---")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("### 🩺 可能症状")
                        for symptom in classification['symptoms']:
                            st.markdown(f"- {symptom}")
                    
                    with col2:
                        st.markdown("### 💊 健康建议")
                        for rec in recommendations:
                            st.markdown(f"- {rec}")
                    
                    # 下载PDF报告
                    st.markdown("---")
                    st.markdown("### 📄 下载分析报告")
                    
                    col1, col2, col3 = st.columns([1, 1, 1])
                    with col2:
                        try:
                            # 生成PDF
                            pdf_data = st.session_state.pdf_generator.generate_report(
                                result, 
                                result['img_rgb']
                            )
                            
                            # 下载按钮
                            st.download_button(
                                label="📥 下载PDF报告",
                                data=pdf_data,
                                file_name=f"pharynx_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                                type="primary"
                            )
                        except Exception as e:
                            st.error(f"PDF生成失败: {str(e)}")
                            print(f"PDF生成错误: {e}")
                            print(traceback.format_exc())
            
            except Exception as e:
                error_msg = f"处理图像时出错: {str(e)}"
                print(f"✗ {error_msg}")
                print(traceback.format_exc())
                st.error(f"❌ {error_msg}")
        
        else:
            # 显示说明
            st.info("👆 请上传咽部图像开始筛查")
        
        # 历史记录
        if st.session_state.history and len(st.session_state.history) > 1:
            st.markdown("---")
            st.markdown("## 📜 历史记录")
            
            for idx, record in enumerate(reversed(st.session_state.history[-5:])):
                with st.expander(f"{record['timestamp']} - {record['classification']['disease_name']} {record['classification']['color']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**诊断**: {record['classification']['disease_name']}")
                        st.write(f"**置信度**: {record['classification']['confidence']}%")
                    with col2:
                        st.write(f"**严重程度**: {record['classification']['severity_cn']}")
        
        # 页脚
        st.markdown("---")
        st.markdown("""
        <div style='text-align: center; color: #888; padding: 20px;'>
            <p>⚠️ <strong>免责声明</strong>：本系统仅供健康筛查参考，不能替代专业医疗诊断</p>
            <p>如有不适症状，请及时就医咨询专业医生</p>
            <p style='margin-top: 10px; font-size: 12px;'>© 2025 咽部健康筛查AI系统 | Powered by AI & 正掌讯软件</p>
        </div>
        """, unsafe_allow_html=True)
        
        print("✓ 页面渲染完成")
    
    except Exception as e:
        print(f"\n✗✗✗ 主程序异常: {e}")
        print(traceback.format_exc())
        st.error(f"❌ 系统错误: {str(e)}")
        st.exception(e)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("程序入口: __main__")
    print("=" * 60)
    main()