"""
图片表格识别并转换为Excel文件
支持JPG、PNG、PDF格式
使用OCR技术提取表格数据
"""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import pandas as pd
from pathlib import Path
import io
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
    from pdf2image import convert_from_path
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False


class TableExtractorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("图片表格识别转Excel工具")
        self.root.geometry("900x700")
        
        self.image_path = None
        self.extracted_data = None
        self.preview_image = None
        
        self.setup_ui()
        self.check_dependencies()
    
    def check_dependencies(self):
        """检查依赖库"""
        if not OCR_AVAILABLE:
            messagebox.showwarning(
                "缺少依赖",
                "未检测到OCR库！\n\n请安装以下库：\n"
                "pip install pytesseract opencv-python numpy\n\n"
                "并安装Tesseract OCR引擎：\n"
                "Windows: https://github.com/UB-Mannheim/tesseract/wiki\n"
                "Linux: sudo apt-get install tesseract-ocr\n"
                "Mac: brew install tesseract"
            )
        
        if not PDF_AVAILABLE:
            self.info_label.config(
                text="提示：安装 pdf2image 和 poppler 以支持PDF文件\n"
                     "pip install pdf2image"
            )
    
    def setup_ui(self):
        """设置用户界面"""
        # 标题
        title_frame = tk.Frame(self.root, bg="#2c3e50", height=60)
        title_frame.pack(fill=tk.X)
        title_frame.pack_propagate(False)
        
        title_label = tk.Label(
            title_frame,
            text="📊正讯 图片表格识别转Excel工具",
            font=("Arial", 18, "bold"),
            bg="#2c3e50",
            fg="white"
        )
        title_label.pack(pady=15)
        
        # 信息提示
        self.info_label = tk.Label(
            self.root,
            text="支持格式：JPG、PNG、PDF\n点击下方按钮上传图片",
            font=("Arial", 10),
            fg="#7f8c8d"
        )
        self.info_label.pack(pady=10)
        
        # 按钮区域
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=10)
        
        self.upload_btn = tk.Button(
            button_frame,
            text="📁 上传图片",
            command=self.upload_image,
            font=("Arial", 12, "bold"),
            bg="#3498db",
            fg="white",
            padx=20,
            pady=10,
            cursor="hand2"
        )
        self.upload_btn.grid(row=0, column=0, padx=10)
        
        self.recognize_btn = tk.Button(
            button_frame,
            text="🔍 开始识别",
            command=self.recognize_table,
            font=("Arial", 12, "bold"),
            bg="#2ecc71",
            fg="white",
            padx=20,
            pady=10,
            cursor="hand2",
            state=tk.DISABLED
        )
        self.recognize_btn.grid(row=0, column=1, padx=10)
        
        self.download_btn = tk.Button(
            button_frame,
            text="💾 下载Excel",
            command=self.download_excel,
            font=("Arial", 12, "bold"),
            bg="#e74c3c",
            fg="white",
            padx=20,
            pady=10,
            cursor="hand2",
            state=tk.DISABLED
        )
        self.download_btn.grid(row=0, column=2, padx=10)
        
        # 图片预览区域
        preview_frame = tk.LabelFrame(
            self.root,
            text="图片预览",
            font=("Arial", 11, "bold"),
            padx=10,
            pady=10
        )
        preview_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        self.preview_label = tk.Label(
            preview_frame,
            text="暂无图片",
            bg="#ecf0f1",
            font=("Arial", 10),
            fg="#95a5a6"
        )
        self.preview_label.pack(fill=tk.BOTH, expand=True)
        
        # 识别结果区域
        result_frame = tk.LabelFrame(
            self.root,
            text="识别概要",
            font=("Arial", 11, "bold"),
            padx=10,
            pady=10
        )
        result_frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)
        
        # 添加滚动条
        scrollbar = tk.Scrollbar(result_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.result_text = tk.Text(
            result_frame,
            height=10,
            font=("Courier", 9),
            yscrollcommand=scrollbar.set,
            wrap=tk.WORD,
            bg="#f8f9fa"
        )
        self.result_text.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.result_text.yview)
        
        # 进度条
        self.progress = ttk.Progressbar(
            self.root,
            mode='indeterminate',
            length=300
        )
        
        # 状态栏
        self.status_label = tk.Label(
            self.root,
            text="就绪",
            font=("Arial", 9),
            bg="#34495e",
            fg="white",
            anchor=tk.W,
            padx=10
        )
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
    
    def upload_image(self):
        """上传图片"""
        file_types = [
            ("图片文件", "*.jpg *.jpeg *.png"),
            ("所有文件", "*.*")
        ]
        
        if PDF_AVAILABLE:
            file_types.insert(0, ("PDF文件", "*.pdf"))
        
        file_path = filedialog.askopenfilename(
            title="选择图片文件",
            filetypes=file_types
        )
        
        if file_path:
            self.image_path = file_path
            self.display_image(file_path)
            self.recognize_btn.config(state=tk.NORMAL)
            self.status_label.config(text=f"已加载: {Path(file_path).name}")
            self.result_text.delete(1.0, tk.END)
            self.download_btn.config(state=tk.DISABLED)
    
    def display_image(self, image_path):
        """显示图片预览"""
        try:
            if image_path.lower().endswith('.pdf'):
                if not PDF_AVAILABLE:
                    messagebox.showerror("错误", "需要安装 pdf2image 库来处理PDF文件")
                    return
                # 转换PDF第一页
                images = convert_from_path(image_path, first_page=1, last_page=1)
                img = images[0]
            else:
                img = Image.open(image_path)
            
            # 调整大小以适应预览区域
            max_width = 500
            max_height = 300
            img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            
            photo = ImageTk.PhotoImage(img)
            self.preview_image = photo  # 保持引用
            
            self.preview_label.config(image=photo, text="")
            self.preview_label.image = photo
        except Exception as e:
            messagebox.showerror("错误", f"无法加载图片：{str(e)}")
    
    def recognize_table(self):
        """识别表格"""
        if not self.image_path:
            messagebox.showwarning("警告", "请先上传图片！")
            return
        
        if not OCR_AVAILABLE:
            messagebox.showerror("错误", "OCR库未安装，无法识别表格")
            return
        
        self.status_label.config(text="正在识别中...")
        self.progress.pack(pady=10)
        self.progress.start()
        self.root.update()
        
        try:
            # 处理图片
            if self.image_path.lower().endswith('.pdf'):
                if not PDF_AVAILABLE:
                    raise Exception("需要安装 pdf2image 库")
                images = convert_from_path(self.image_path, first_page=1, last_page=1)
                image = np.array(images[0])
            else:
                image = cv2.imread(self.image_path)
            
            # 图像预处理
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
            
            # OCR识别
            custom_config = r'--oem 3 --psm 6'
            text = pytesseract.image_to_string(thresh, config=custom_config, lang='chi_sim+eng')
            
            # 解析表格数据
            self.extracted_data = self.parse_table_text(text)
            
            # 显示结果
            self.display_results(text, self.extracted_data)
            
            self.download_btn.config(state=tk.NORMAL)
            self.status_label.config(text="识别完成！")
            
        except Exception as e:
            messagebox.showerror("识别错误", f"识别失败：{str(e)}\n\n"
                                             f"提示：\n1. 确保已安装Tesseract OCR\n"
                                             f"2. 图片清晰度足够\n3. 表格结构明确")
            self.status_label.config(text="识别失败")
        
        finally:
            self.progress.stop()
            self.progress.pack_forget()
    
    def parse_table_text(self, text):
        """解析文本为表格数据"""
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        
        if not lines:
            return pd.DataFrame()
        
        # 尝试识别分隔符
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
        
        df = pd.DataFrame(data)
        return df
    
    def display_results(self, raw_text, df):
        """显示识别结果"""
        self.result_text.delete(1.0, tk.END)
        
        summary = f"{'='*60}\n"
        summary += f"识别概要\n"
        summary += f"{'='*60}\n\n"
        summary += f"📄 文件: {Path(self.image_path).name}\n"
        summary += f"📊 识别到的行数: {len(df)}\n"
        summary += f"📊 识别到的列数: {len(df.columns) if not df.empty else 0}\n\n"
        
        if not df.empty:
            summary += f"数据预览 (前5行):\n"
            summary += f"{'-'*60}\n"
            summary += df.head(5).to_string(index=False)
            summary += f"\n{'-'*60}\n\n"
        
        summary += f"原始识别文本:\n"
        summary += f"{'-'*60}\n"
        summary += raw_text[:500]  # 只显示前500个字符
        if len(raw_text) > 500:
            summary += "\n... (文本过长，已截断)"
        
        self.result_text.insert(1.0, summary)
    
    def download_excel(self):
        """下载Excel文件"""
        if self.extracted_data is None or self.extracted_data.empty:
            messagebox.showwarning("警告", "没有可导出的数据！")
            return
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")],
            initialfile="extracted_table.xlsx"
        )
        
        if file_path:
            try:
                # 保存为Excel
                self.extracted_data.to_excel(file_path, index=False, engine='openpyxl')
                messagebox.showinfo("成功", f"Excel文件已保存至:\n{file_path}")
                self.status_label.config(text=f"已保存: {Path(file_path).name}")
            except Exception as e:
                messagebox.showerror("错误", f"保存失败：{str(e)}")


def main():
    """主函数"""
    root = tk.Tk()
    app = TableExtractorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
