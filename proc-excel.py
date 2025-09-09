import os
import zipfile
import pandas as pd
from typing import List, Dict
import streamlit as st
import tempfile
from io import BytesIO

class SpreadsheetProcessor:
    def __init__(self):
        self.target_columns = ['日期', '客户名称', '产品', '品规', '数量', '批号']
        self.supported_extensions = ['.xlsx', '.xls', '.csv']
    
    def extract_zip(self, uploaded_zip) -> str:
        """解压上传的压缩文件"""
        if uploaded_zip is None:
            raise Exception("未上传文件")
        
        # 创建临时目录
        temp_dir = tempfile.mkdtemp()
        
        # 保存上传的zip文件
        zip_path = os.path.join(temp_dir, "uploaded_files.zip")
        with open(zip_path, "wb") as f:
            f.write(uploaded_zip.getvalue())
        
        # 解压文件
        extract_dir = os.path.join(temp_dir, "extracted_files")
        os.makedirs(extract_dir, exist_ok=True)
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
        except zipfile.BadZipFile:
            raise Exception("上传的文件不是有效的ZIP文件")
        
        return extract_dir
    
    def is_spreadsheet_file(self, filename: str) -> bool:
        """检查文件是否为支持的电子表格格式"""
        return any(filename.lower().endswith(ext) for ext in self.supported_extensions)
    
    def extract_columns_from_file(self, file_path: str) -> pd.DataFrame:
        """从单个文件中提取指定列"""
        try:
            if file_path.endswith('.csv'):
                # 尝试多种编码
                encodings = ['utf-8', 'gbk', 'gb2312', 'latin-1']
                df = None
                for encoding in encodings:
                    try:
                        df = pd.read_csv(file_path, encoding=encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                if df is None:
                    raise Exception("无法用任何编码读取CSV文件")
            else:
                df = pd.read_excel(file_path)
        except Exception as e:
            st.error(f"读取文件 {os.path.basename(file_path)} 时出错: {e}")
            return pd.DataFrame()
        
        # 查找实际存在的列名（处理可能的列名变体）
        available_columns = []
        for target_col in self.target_columns:
            # 尝试匹配列名（包括可能的空格或大小写变化）
            matching_cols = [col for col in df.columns if target_col.strip() in col.strip() or col.strip() in target_col.strip()]
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
        processed_count = 0
        error_files = []
        
        for root, _, files in os.walk(directory):
            for file in files:
                if self.is_spreadsheet_file(file):
                    file_path = os.path.join(root, file)
                    st.write(f"正在处理文件: {file}")
                    
                    file_data = self.extract_columns_from_file(file_path)
                    if not file_data.empty:
                        all_data = pd.concat([all_data, file_data], ignore_index=True)
                        processed_count += 1
                    else:
                        error_files.append(file)
        
        if error_files:
            st.warning(f"以下文件处理失败: {', '.join(error_files)}")
        
        return all_data
    
    def run(self, uploaded_zip):
        """运行整个处理流程"""
        try:
            # 显示进度
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # 1. 解压压缩包
            status_text.text("正在解压文件...")
            extract_dir = self.extract_zip(uploaded_zip)
            progress_bar.progress(25)
            
            # 2. 处理所有文件
            status_text.text("开始处理文件...")
            result_df = self.process_all_files(extract_dir)
            progress_bar.progress(75)
            
            if result_df.empty:
                status_text.text("未找到任何数据")
                progress_bar.progress(100)
                return None
            
            # 3. 准备结果
            status_text.text("准备结果...")
            progress_bar.progress(100)
            status_text.text("处理完成！")
            
            return result_df
            
        except Exception as e:
            st.error(f"处理过程中出错: {e}")
            return None

def main():
    st.set_page_config(
        page_title="Excel文件处理器",
        page_icon="📊",
        layout="wide"
    )
    
    st.title("📊 Excel/CSV文件批量处理器")
    st.markdown("上传包含Excel/CSV文件的ZIP压缩包，系统将自动提取指定列的数据")
    
    # 侧边栏配置
    with st.sidebar:
        st.header("配置选项")
        
        # 自定义列名
        default_columns = ['日期', '客户名称', '产品', '品规', '数量', '批号']
        custom_columns = st.text_area(
            "自定义要提取的列名（每行一个）",
            value="\n".join(default_columns),
            help="每行输入一个列名，系统会尝试匹配文件中的对应列"
        )
    
    # 文件上传
    uploaded_file = st.file_uploader(
        "上传ZIP压缩文件",
        type="zip",
        help="请上传包含Excel(.xlsx/.xls)或CSV文件的ZIP压缩包"
    )
    
    # 初始化处理器
    processor = SpreadsheetProcessor()
    
    # 更新目标列
    if custom_columns.strip():
        processor.target_columns = [col.strip() for col in custom_columns.split('\n') if col.strip()]
    
    if uploaded_file is not None:
        # 显示文件信息
        file_details = {
            "文件名": uploaded_file.name,
            "文件大小": f"{uploaded_file.size / 1024:.1f} KB"
        }
        st.write("文件信息:", file_details)
        
        # 处理按钮
        if st.button("开始处理", type="primary"):
            with st.spinner("处理中，请稍候..."):
                result_df = processor.run(uploaded_file)
                
                if result_df is not None:
                    # 显示处理结果
                    st.success(f"处理完成！共提取 {len(result_df)} 条数据")
                    
                    # 显示数据预览
                    st.subheader("数据预览")
                    st.dataframe(result_df.head(), use_container_width=True)
                    
                    # 显示统计信息
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("总行数", len(result_df))
                    with col2:
                        st.metric("涉及文件数", result_df['源文件'].nunique())
                    with col3:
                        st.metric("列数", len(result_df.columns))
                    
                    # 下载按钮
                    st.subheader("下载结果")
                    
                    # 将DataFrame转换为Excel文件
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        result_df.to_excel(writer, index=False, sheet_name='提取结果')
                    
                    # 提供下载链接
                    st.download_button(
                        label="下载Excel文件",
                        data=output.getvalue(),
                        file_name="提取结果.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                    
                    # 显示列映射信息
                    with st.expander("查看列映射详情"):
                        st.write("目标列配置:", processor.target_columns)
                        st.write("实际处理的数据列:", list(result_df.columns))

if __name__ == "__main__":
    main()