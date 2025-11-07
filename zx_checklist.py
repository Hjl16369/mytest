"""
软件开发模块自查表生成系统
功能：填写自查表并生成PDF确认单
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkcalendar import DateEntry
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import cm
import os

class ModuleChecklistApp:
    def __init__(self, root):
        self.root = root
        self.root.title("软件开发模块功能自查表")
        self.root.geometry("900x700")
        
        # 存储复选框变量（必须先初始化）
        self.checkbox_vars = {}
        
        # 配置样式
        self.setup_styles()
        
        # 注册中文字体（使用系统自带字体）
        self.setup_fonts()
        
        # 创建主框架
        main_frame = ttk.Frame(root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # 配置网格权重
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # 基本信息区域
        self.create_basic_info_section(main_frame)
        
        # 自查项目区域
        self.create_checklist_section(main_frame)
        
        # 按钮区域
        self.create_button_section(main_frame)
    
    def setup_styles(self):
        """配置界面样式"""
        style = ttk.Style()
        # 配置复选框字体大小
        style.configure('Large.TCheckbutton', font=('Microsoft YaHei', 12))
        
    def setup_fonts(self):
        """设置中文字体"""
        # 尝试使用系统中文字体
        font_paths = [
            "C:/Windows/Fonts/simhei.ttf",  # Windows 黑体
            "C:/Windows/Fonts/simsun.ttc",  # Windows 宋体
            "/System/Library/Fonts/PingFang.ttc",  # macOS
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",  # Linux
        ]
        
        self.font_registered = False
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont('Chinese', font_path))
                    self.font_registered = True
                    break
                except:
                    continue
    
    def create_basic_info_section(self, parent):
        """创建基本信息输入区域"""
        info_frame = ttk.LabelFrame(parent, text="基本信息", padding="10")
        info_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=5)
        
        # 模块名
        ttk.Label(info_frame, text="模块名:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.module_name = ttk.Entry(info_frame, width=40)
        self.module_name.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        # 开发人
        ttk.Label(info_frame, text="开发人:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.developer = ttk.Entry(info_frame, width=40)
        self.developer.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        # 开始时间（使用日期选择控件）
        ttk.Label(info_frame, text="开始时间:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.start_date = DateEntry(
            info_frame, 
            width=37,
            background='darkblue',
            foreground='white',
            borderwidth=2,
            date_pattern='yyyy-mm-dd',
            locale='zh_CN'
        )
        self.start_date.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        # 完成时间（使用日期选择控件）
        ttk.Label(info_frame, text="完成时间:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.end_date = DateEntry(
            info_frame,
            width=37,
            background='darkblue',
            foreground='white',
            borderwidth=2,
            date_pattern='yyyy-mm-dd',
            locale='zh_CN'
        )
        self.end_date.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5, padx=5)
        
        info_frame.columnconfigure(1, weight=1)
    
    def create_checklist_section(self, parent):
        """创建自查项目区域"""
        # 创建滚动区域
        canvas_frame = ttk.Frame(parent)
        canvas_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        
        # 创建Canvas和Scrollbar
        canvas = tk.Canvas(canvas_frame, height=400)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 自查项目数据
        self.checklist_items = {
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
        
        # 创建复选框
        row = 0
        for category, subcategories in self.checklist_items.items():
            # 大类标题
            label = ttk.Label(scrollable_frame, text=category, font=('Microsoft YaHei', 14, 'bold'))
            label.grid(row=row, column=0, sticky=tk.W, pady=(10, 5), padx=5)
            row += 1
            
            for subcat, items in subcategories.items():
                # 子类标题
                label = ttk.Label(scrollable_frame, text=subcat, font=('Microsoft YaHei', 13))
                label.grid(row=row, column=0, sticky=tk.W, pady=(5, 2), padx=20)
                row += 1
                
                # 检查项
                for item in items:
                    var = tk.BooleanVar()
                    self.checkbox_vars[item] = var
                    cb = ttk.Checkbutton(scrollable_frame, text=item, variable=var)
                    # 设置复选框字体大小
                    cb.configure(style='Large.TCheckbutton')
                    cb.grid(row=row, column=0, sticky=tk.W, pady=2, padx=40)
                    row += 1
        
        parent.rowconfigure(1, weight=1)
    
    def create_button_section(self, parent):
        """创建按钮区域"""
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=2, column=0, columnspan=2, pady=10)
        
        ttk.Button(button_frame, text="全选", command=self.select_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="取消全选", command=self.deselect_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="生成PDF确认单", command=self.generate_pdf).pack(side=tk.LEFT, padx=5)
    
    def select_all(self):
        """全选所有复选框"""
        for var in self.checkbox_vars.values():
            var.set(True)
    
    def deselect_all(self):
        """取消所有复选框"""
        for var in self.checkbox_vars.values():
            var.set(False)
    
    def generate_pdf(self):
        """生成PDF确认单"""
        # 验证基本信息
        if not self.module_name.get():
            messagebox.showerror("错误", "请填写模块名！")
            return
        if not self.developer.get():
            messagebox.showerror("错误", "请填写开发人！")
            return
        
        # 检查是否有未勾选项
        unchecked = [item for item, var in self.checkbox_vars.items() if not var.get()]
        if unchecked:
            result = messagebox.askyesno(
                "提醒", 
                f"还有 {len(unchecked)} 项未勾选，是否继续生成PDF？"
            )
            if not result:
                return
        
        # 选择保存路径（文件名包含开发人员名字）
        filename = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialfile=f"{self.module_name.get()}_{self.developer.get()}_自查确认单_{datetime.now().strftime('%Y%m%d')}.pdf"
        )
        
        if not filename:
            return
        
        try:
            self.create_pdf(filename)
            messagebox.showinfo("成功", f"PDF确认单已生成！\n保存位置: {filename}")
        except Exception as e:
            messagebox.showerror("错误", f"生成PDF失败: {str(e)}")
    
    def create_pdf(self, filename):
        """创建PDF文档"""
        c = canvas.Canvas(filename, pagesize=A4)
        width, height = A4
        
        # 设置字体
        if self.font_registered:
            c.setFont("Chinese", 18)
        else:
            c.setFont("Helvetica-Bold", 18)
        
        # 标题（中文）
        title = "软件开发模块功能自查确认单"
        c.drawCentredString(width/2, height - 2*cm, title)
        
        if self.font_registered:
            c.setFont("Chinese", 13)
        else:
            c.setFont("Helvetica", 13)
        
        # 基本信息（中文）
        y = height - 3.5*cm
        c.drawString(2*cm, y, f"模块名: {self.module_name.get()}")
        y -= 0.7*cm
        c.drawString(2*cm, y, f"开发人: {self.developer.get()}")
        y -= 0.7*cm
        c.drawString(2*cm, y, f"开始时间: {self.start_date.get_date().strftime('%Y-%m-%d')}")
        y -= 0.7*cm
        c.drawString(2*cm, y, f"完成时间: {self.end_date.get_date().strftime('%Y-%m-%d')}")
        y -= 1*cm
        
        # 绘制分隔线
        c.line(2*cm, y, width - 2*cm, y)
        y -= 0.8*cm
        
        if self.font_registered:
            c.setFont("Chinese", 12)
        else:
            c.setFont("Helvetica", 11)
        
        # 自查项目
        for category, subcategories in self.checklist_items.items():
            # 检查是否需要新页面
            if y < 3*cm:
                c.showPage()
                if self.font_registered:
                    c.setFont("Chinese", 12)
                else:
                    c.setFont("Helvetica", 11)
                y = height - 2*cm
            
            # 大类标题
            if self.font_registered:
                c.setFont("Chinese", 13)
                c.drawString(2*cm, y, category)
                c.setFont("Chinese", 11)
            else:
                c.setFont("Helvetica-Bold", 12)
                c.drawString(2*cm, y, category)
                c.setFont("Helvetica", 10)
            y -= 0.7*cm
            
            for subcat, items in subcategories.items():
                if y < 3*cm:
                    c.showPage()
                    if self.font_registered:
                        c.setFont("Chinese", 11)
                    else:
                        c.setFont("Helvetica", 10)
                    y = height - 2*cm
                
                # 子类标题
                c.drawString(2.5*cm, y, subcat)
                y -= 0.6*cm
                
                for item in items:
                    if y < 3*cm:
                        c.showPage()
                        if self.font_registered:
                            c.setFont("Chinese", 11)
                        else:
                            c.setFont("Helvetica", 10)
                        y = height - 2*cm
                    
                    # 复选框
                    checked = self.checkbox_vars[item].get()
                    checkbox = "[√]" if checked else "[ ]"
                    
                    # 处理长文本换行
                    text = f"{checkbox} {item}"
                    max_width = width - 5*cm
                    
                    if self.font_registered:
                        text_width = c.stringWidth(text, "Chinese", 11)
                    else:
                        text_width = c.stringWidth(text, "Helvetica", 10)
                    
                    if text_width > max_width:
                        # 简单换行处理
                        words = text.split()
                        line = ""
                        for word in words:
                            test_line = f"{line} {word}".strip()
                            if self.font_registered:
                                test_width = c.stringWidth(test_line, "Chinese", 11)
                            else:
                                test_width = c.stringWidth(test_line, "Helvetica", 10)
                            
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
        
        # 确认信息（中文）
        if y < 5*cm:
            c.showPage()
            y = height - 2*cm
        
        y -= 1*cm
        c.line(2*cm, y, width - 2*cm, y)
        y -= 1*cm
        
        if self.font_registered:
            c.setFont("Chinese", 13)
        else:
            c.setFont("Helvetica-Bold", 13)
        
        c.drawString(2*cm, y, "三、开发人确认")
        y -= 0.8*cm
        
        if self.font_registered:
            c.setFont("Chinese", 12)
        else:
            c.setFont("Helvetica", 12)
        
        c.drawString(2*cm, y, "我确认上述功能自查都已完成、实现。")
        y -= 1*cm
        
        c.drawString(2*cm, y, f"确认人: {self.developer.get()}")
        y -= 0.7*cm
        c.drawString(2*cm, y, f"确认日期: {datetime.now().strftime('%Y-%m-%d')}")
        
        # 统计信息
        total_items = len(self.checkbox_vars)
        checked_items = sum(1 for var in self.checkbox_vars.values() if var.get())
        y -= 1*cm
        c.drawString(2*cm, y, f"自查完成率: {checked_items}/{total_items} 项 ({checked_items*100//total_items}%)")
        
        c.save()

def main():
    root = tk.Tk()
    app = ModuleChecklistApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
