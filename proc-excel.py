import os
import zipfile
import pandas as pd
from typing import List, Dict
import tkinter as tk
from tkinter import filedialog, messagebox

class SpreadsheetProcessor:
    def __init__(self):
        self.target_columns = ['日期', '客户名称', '产品', '品规', '数量', '批号']
        self.supported_extensions = ['.xlsx', '.xls', '.csv']
    
    def upload_and_extract_zip(self) -> str:
        """上传压缩文件并解压"""
        root = tk.Tk()
        root.withdraw()
        
        zip_path = filedialog.askopenfilename(
            title="选择压缩文件",
            filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")]
        )
        
        if not zip_path:
            raise Exception("未选择文件")
        
        extract_dir = os.path.join(os.path.dirname(zip_path), "extracted_files")
        os.makedirs(extract_dir, exist_ok=True)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        return extract_dir
    
    def is_spreadsheet_file(self, filename: str) -> bool:
        """检查文件是否为支持的电子表格格式"""
        return any(filename.lower().endswith(ext) for ext in self.supported_extensions)
    
    def extract_columns_from_file(self, file_path: str) -> pd.DataFrame:
        """从单个文件中提取指定列"""
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path, encoding='utf-8')
            else:
                df = pd.read_excel(file_path)
        except Exception as e:
            print(f"读取文件 {file_path} 时出错: {e}")
            return pd.DataFrame()
        
        # 查找实际存在的列名（处理可能的列名变体）
        available_columns = []
        for target_col in self.target_columns:
            # 尝试匹配列名（包括可能的空格或大小写变化）
            matching_cols = [col for col in df.columns if target_col in col or col in target_col]
            if matching_cols:
                available_columns.append(matching_cols[0])
            else:
                available_columns.append(None)
        
        # 提取存在的列
        extracted_data = pd.DataFrame()
        for i, target_col in enumerate(self.target_columns):
            actual_col = available_columns[i]
            if actual_col and actual_col in df.columns:
                extracted_data[target_col] = df[actual_col]
            else:
                extracted_data[target_col] = None  # 列不存在时填充None
        
        extracted_data['源文件'] = os.path.basename(file_path)
        return extracted_data
    
    def process_all_files(self, directory: str) -> pd.DataFrame:
        """处理目录中的所有电子表格文件"""
        all_data = pd.DataFrame()
        
        for root, _, files in os.walk(directory):
            for file in files:
                if self.is_spreadsheet_file(file):
                    file_path = os.path.join(root, file)
                    print(f"正在处理文件: {file_path}")
                    
                    file_data = self.extract_columns_from_file(file_path)
                    if not file_data.empty:
                        all_data = pd.concat([all_data, file_data], ignore_index=True)
        
        return all_data
    
    def save_results(self, df: pd.DataFrame, output_path: str = None):
        """保存处理结果"""
        if output_path is None:
            output_path = os.path.join(os.getcwd(), "提取结果.xlsx")
        
        df.to_excel(output_path, index=False)
        print(f"结果已保存到: {output_path}")
    
    def run(self):
        """运行整个处理流程"""
        try:
            # 1. 上传并解压压缩包
            print("请选择压缩文件...")
            extract_dir = self.upload_and_extract_zip()
            
            # 2. 处理所有文件
            print("开始处理文件...")
            result_df = self.process_all_files(extract_dir)
            
            if result_df.empty:
                print("未找到任何数据")
                return
            
            # 3. 保存结果
            print("保存处理结果...")
            self.save_results(result_df)
            
            print("处理完成！")
            messagebox.showinfo("完成", "文件处理完成！")
            
        except Exception as e:
            print(f"处理过程中出错: {e}")
            messagebox.showerror("错误", f"处理失败: {e}")

# 使用示例
if __name__ == "__main__":
    processor = SpreadsheetProcessor()
    
    # 可以自定义要提取的列
    # processor.target_columns = ['日期', '客户名称', '产品', '规格', '数量', '批号']
    
    processor.run()