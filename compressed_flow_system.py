import streamlit as st
import pandas as pd
import zipfile
import tempfile
import os
import shutil
from datetime import datetime
from io import BytesIO
import warnings

warnings.filterwarnings("ignore", message="missing ScriptRunContext")
warnings.filterwarnings("ignore", message="ScriptRunContext")
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

st.set_page_config(
    page_title="正掌讯商业流向数据AI处理系统",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 客户名称对应关系字典
customer_alias_mapping = {
    '四川医药总部': '国药控股四川医药股份有限公司',
    '国控攀枝花总部': '国药控股四川攀枝花医药有限公司',
    '国控甘孜总部': '国药控股甘孜州医药有限公司',
    '国控广安总部': '国药控股广安有限公司',
    '国控达州总部': '国药控股达州有限公司',
    '国控乐山总部': '国药控股(乐山)巴蜀药医药有限公司',
    '国控凉山总部': '国药控股凉山医药有限公司',
    '国控眉山总部': '国药控股眉山医药有限公司'
}

# 产品映射字典
product_mapping = {
    '奥卡西平片(30S)': {
        '商品名称': ['奥卡西平片', '奥卡西平片(30S)'],
        '规格': ['0.3g*30片', '0.3g/片*10片/板*3板/盒*200盒'],
        '单位换算系数': {
            '0.3g*30片': 1,
            '0.3g/片*10片/板*3板/盒*200盒': 1,
            'default': 1
        }
    },
    '布洛芬（100ml）': {
        '商品名称': ['布洛芬混悬液(迪尔诺)'],
        '规格': ['2%*100ml：2.0g/瓶/盒'],
        '单位换算系数': {
            '2%*100ml：2.0g/瓶/盒': 1,
            'default': 1
        }
    },
    '尿激酶（10万单位）': {
        '商品名称': ['注射用尿激酶'],
        '规格': ['10万iu×5瓶/盒'],
        '单位换算系数': {
            '10万iu×5瓶/盒': 5,
            'default': 5
        }
    }
}

def get_conversion_factor(product_name, spec):
    try:
        if product_name in product_mapping:
            conversion_factors = product_mapping[product_name]['单位换算系数']
            if spec and spec in conversion_factors:
                return conversion_factors[spec]
            return conversion_factors.get('default', 1)
        return 1
    except Exception as e:
        print(f"获取换算系数时出错: {e}")
        return 1

def create_reverse_mappings():
    reverse_customer_mapping = {v: k for k, v in customer_alias_mapping.items()}
    reverse_product_mapping = {}
    for out_product_name, product_info in product_mapping.items():
        for sales_product_name in product_info['商品名称']:
            reverse_product_mapping[sales_product_name] = out_product_name
            for spec in product_info['规格']:
                combined_key = f"{sales_product_name}|{spec}"
                reverse_product_mapping[combined_key] = out_product_name
    return reverse_customer_mapping, reverse_product_mapping

def create_record_key(record):
    try:
        date_str = pd.to_datetime(record['出库日期']).strftime('%Y-%m-%d') if pd.notna(record['出库日期']) else ''
        key = (
            date_str,
            str(record['商业公司']).strip(),
            str(record['产品名称']).strip(), 
            str(record['批号']).strip(),
            float(record['数量']) if pd.notna(record['数量']) else 0.0
        )
        return key
    except Exception as e:
        print(f"创建记录键失败: {e}")
        return None

def is_duplicate_record(new_record, existing_records_df):
    if existing_records_df.empty:
        return False
    new_key = create_record_key(new_record)
    if new_key is None:
        return False
    for _, existing_row in existing_records_df.iterrows():
        existing_key = create_record_key(existing_row)
        if existing_key == new_key:
            return True
    return False

def find_matching_sales_data(row, sales_detail_df, reverse_customer_mapping, reverse_product_mapping):
    try:
        out_company = str(row['商业公司']).strip()
        out_product = str(row['产品名称']).strip()
        out_batch = str(row['批号']).strip()
        
        # 公司名称匹配
        company_matched_rows = []
        for idx, sales_row in sales_detail_df.iterrows():
            sales_company = str(sales_row['公司名称']).strip()
            if sales_company in customer_alias_mapping:
                mapped_company = customer_alias_mapping[sales_company]
                if mapped_company == out_company:
                    company_matched_rows.append(idx)
        
        if not company_matched_rows:
            return pd.DataFrame()
        
        company_matched_df = sales_detail_df.loc[company_matched_rows].copy()
        
        # 产品名称匹配
        product_matched_rows = []
        for idx, sales_row in company_matched_df.iterrows():
            sales_product = str(sales_row['商品名称']).strip()
            sales_spec = str(sales_row['规格']).strip() if '规格' in sales_row and pd.notna(sales_row['规格']) else ''
            
            match_found = False
            if sales_product in reverse_product_mapping:
                if reverse_product_mapping[sales_product] == out_product:
                    match_found = True
            
            if not match_found and sales_spec:
                combined_key = f"{sales_product}|{sales_spec}"
                if combined_key in reverse_product_mapping:
                    if reverse_product_mapping[combined_key] == out_product:
                        match_found = True
            
            if not match_found:
                for map_key, map_info in product_mapping.items():
                    if map_key == out_product:
                        if sales_product in map_info['商品名称']:
                            if not sales_spec or sales_spec in map_info['规格']:
                                match_found = True
                                break
            
            if match_found:
                product_matched_rows.append(idx)
        
        if not product_matched_rows:
            return pd.DataFrame()
        
        product_matched_df = sales_detail_df.loc[product_matched_rows].copy()
        
        # 批号精确匹配
        batch_matched_df = product_matched_df[
            product_matched_df['批号'].astype(str).str.strip() == out_batch
        ].copy()
        
        return batch_matched_df
        
    except Exception as e:
        print(f"匹配过程中出错: {e}")
        return pd.DataFrame()

def calculate_converted_quantity(sales_quantity, out_product, sales_spec):
    try:
        conversion_factor = get_conversion_factor(out_product, sales_spec)
        converted_quantity = sales_quantity * conversion_factor
        return converted_quantity
    except Exception as e:
        print(f"计算转换数量时出错: {e}")
        return sales_quantity

def is_company_like(name):
    if not name or not isinstance(name, str):
        return False
    name = name.strip()
    company_suffixes = [
        '有限公司', '有限责任公司', '股份有限公司', '集团有限公司',
        '医药公司', '药业公司', '药房', '诊所', '医院'
    ]
    return any(name.endswith(suffix) for suffix in company_suffixes)

def find_previous_level_company(product_name, batch_no, previous_level, direct_sale_df):
    try:
        matched_records = direct_sale_df[
            (direct_sale_df['产品名称'].astype(str).str.strip() == str(product_name).strip()) &
            (direct_sale_df['批号'].astype(str).str.strip() == str(batch_no).strip()) &
            (direct_sale_df['级次'] == previous_level)
        ]
        
        if not matched_records.empty:
            previous_company = str(matched_records.iloc[0]['商业公司']).strip()
            return previous_company
        else:
            return ''
    except Exception as e:
        print(f"查找上一级商业公司时出错: {e}")
        return ''

def process_flow_data_with_fixed_matching(direct_sale_df, sales_detail_df):
    reverse_customer_mapping, reverse_product_mapping = create_reverse_mappings()
    
    flow_template_cols = [
        '流向商业公司名', '供货方', '所属月份', '单据日期', '代理商', 
        '一级商业名称', '二级商业名称', '三级商业名称', '四级商业名称', 
        '终端名称', '品规', '批号', '销售数量', '转换后数量', '换算系数', '原始规格', '流向级别'
    ]
    
    flow_template_df = pd.DataFrame(columns=flow_template_cols)
    next_level_data = []
    existing_records_keys = set()
    
    for level in range(1, 5):
        current_level_df = direct_sale_df[direct_sale_df['级次'] == level].copy()
        
        if current_level_df.empty:
            continue
        
        level_processed_count = 0
        
        for _, row in current_level_df.iterrows():
            try:
                matched_sales = find_matching_sales_data(
                    row, sales_detail_df, reverse_customer_mapping, reverse_product_mapping
                )
                
                if matched_sales.empty:
                    continue
                
                for _, sales_row in matched_sales.iterrows():
                    try:
                        out_date = pd.to_datetime(row['出库日期']) if pd.notna(row['出库日期']) else pd.Timestamp.now()
                        sales_quantity = pd.to_numeric(sales_row['销售数量'], errors='coerce')
                        if pd.isna(sales_quantity):
                            sales_quantity = 0
                        
                        sales_spec = str(sales_row['规格']).strip() if '规格' in sales_row and pd.notna(sales_row['规格']) else ''
                        out_product = str(row['产品名称']).strip()
                        
                        converted_quantity = calculate_converted_quantity(sales_quantity, out_product, sales_spec)
                        conversion_factor = get_conversion_factor(out_product, sales_spec)
                        
                        new_row = {
                            '流向商业公司名': str(row['商业公司']).strip(),
                            '供货方': "",
                            '所属月份': out_date.strftime('%Y-%m'),
                            '单据日期': out_date,
                            '代理商': "",
                            '一级商业名称': '',
                            '二级商业名称': '',
                            '三级商业名称': '',
                            '四级商业名称': '',
                            '终端名称': str(sales_row['客户名称']).strip(),
                            '品规': str(row['产品名称']).strip(),
                            '批号': str(row['批号']).strip(),
                            '销售数量': sales_quantity,
                            '转换后数量': converted_quantity,
                            '换算系数': conversion_factor,
                            '原始规格': sales_spec,
                            '流向级别': level
                        }
                        
                        level_key = f'{["", "一", "二", "三", "四"][level]}级商业名称'
                        new_row[level_key] = str(row['商业公司']).strip()
                        
                        if level > 1:
                            previous_level = level - 1
                            previous_company = find_previous_level_company(
                                str(row['产品名称']).strip(),
                                str(row['批号']).strip(), 
                                previous_level,
                                direct_sale_df
                            )
                            
                            if previous_company:
                                previous_level_key = f'{["", "一", "二", "三", "四"][previous_level]}级商业名称'
                                new_row[previous_level_key] = previous_company
                        
                        flow_template_df = pd.concat([flow_template_df, pd.DataFrame([new_row])], ignore_index=True)
                        level_processed_count += 1
                        
                        customer_name = str(sales_row['客户名称']).strip()
                        if level < 4 and is_company_like(customer_name):
                            next_level_row = {
                                '出库日期': row['出库日期'],
                                '商业公司': customer_name,
                                '产品名称': row['产品名称'],
                                '批号': row['批号'],
                                '数量': converted_quantity,
                                '级次': level + 1
                            }
                            
                            new_record_key = create_record_key(next_level_row)
                            
                            if new_record_key is not None:
                                if not is_duplicate_record(next_level_row, direct_sale_df):
                                    if new_record_key not in existing_records_keys:
                                        next_level_data.append(next_level_row)
                                        existing_records_keys.add(new_record_key)
                    
                    except Exception as e:
                        print(f"处理销售行数据时出错: {e}")
                        continue
            
            except Exception as e:
                print(f"处理出库行数据时出错: {e}")
                continue
        
        if next_level_data:
            next_level_df = pd.DataFrame(next_level_data)
            direct_sale_df = pd.concat([direct_sale_df, next_level_df], ignore_index=True)
            
            for record in next_level_data:
                record_key = create_record_key(record)
                if record_key:
                    existing_records_keys.add(record_key)
                    
            next_level_data = []
    
    return flow_template_df

def read_excel_file(file_path):
    try:
        if file_path.endswith('.xlsx'):
            return pd.read_excel(file_path, engine='openpyxl')
        elif file_path.endswith('.xls'):
            try:
                return pd.read_excel(file_path, engine='openpyxl')
            except Exception:
                try:
                    return pd.read_excel(file_path, engine='xlrd')
                except Exception:
                    return pd.read_excel(file_path)
        else:
            return pd.read_excel(file_path)
    except Exception as e:
        st.error(f"读取文件失败 {file_path}: {e}")
        return None

def safe_delete_file(file_path):
    try:
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)
            return True
    except Exception as e:
        print(f"无法删除文件 {file_path}: {e}")
        return False

def safe_delete_directory(dir_path):
    try:
        if dir_path and os.path.exists(dir_path):
            shutil.rmtree(dir_path, ignore_errors=True)
            return True
    except Exception as e:
        print(f"无法删除目录 {dir_path}: {e}")
        return False

def find_column_mapping(df_columns):
    mapping = {}
    column_mappings = {
        'date': ['出库日期', '操作日期', '日期', '单据日期'],
        'company': ['商业公司', '购货单位', '客户', '公司', '公司名称'],
        'product': ['产品名称', '产品', '商品名称', '品名'],
        'batch': ['批号'],
        'quantity': ['数量', '批号出库数量', '出库数量', '销售数量']
    }
    
    df_columns_str = [str(col).strip() for col in df_columns]
    
    for col_str in df_columns_str:
        for key, possible_names in column_mappings.items():
            if col_str in possible_names and key not in mapping:
                mapping[key] = col_str
                break
    
    return mapping

def validate_required_columns(sales_df, required_cols=['公司名称', '商品名称', '批号', '销售数量', '客户名称']):
    missing_cols = []
    for col in required_cols:
        if col not in sales_df.columns:
            missing_cols.append(col)
    return missing_cols

def process_files(zip_file, sales_file):
    temp_files = {}
    
    try:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.text("读取销售明细表...")
        progress_bar.progress(10)
        
        try:
            sales_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
            temp_files['sales_file'] = sales_temp_file.name
            sales_temp_file.write(sales_file.getvalue())
            sales_temp_file.close()
            
            sales_detail_df = read_excel_file(temp_files['sales_file'])
            if sales_detail_df is None:
                st.error("无法读取销售明细表")
                return None, None
                
            sales_detail_df.columns = sales_detail_df.columns.str.strip()
            
            missing_cols = validate_required_columns(sales_detail_df)
            if missing_cols:
                st.error(f"销售明细表缺少必需的列: {missing_cols}")
                return None, None
            
            st.success(f"销售明细表读取成功，共 {len(sales_detail_df)} 行数据")
            
        except Exception as e:
            st.error(f"读取销售明细表失败: {e}")
            return None, None
        
        status_text.text("解压并处理出库明细压缩包...")
        progress_bar.progress(20)
        
        zip_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        temp_files['zip_file'] = zip_temp_file.name
        zip_temp_file.write(zip_file.getvalue())
        zip_temp_file.close()
        
        try:
            extract_dir = tempfile.mkdtemp()
            temp_files['extract_dir'] = extract_dir
            
            with zipfile.ZipFile(temp_files['zip_file'], 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
                
            excel_files = [f for f in os.listdir(extract_dir) if f.endswith(('.xlsx', '.xls'))]
            st.info(f"压缩包中包含 {len(excel_files)} 个Excel文件")
            
            if not excel_files:
                st.warning("压缩包中未找到Excel文件")
                return None, None
            
            direct_sale_cols = ['出库日期', '商业公司', '产品名称', '批号', '数量', '级次']
            direct_sale_df = pd.DataFrame(columns=direct_sale_cols)
            
            total_files = len(excel_files)
            processed_files = 0
            
            for file_name in excel_files:
                file_path = os.path.join(extract_dir, file_name)
                
                try:
                    df = read_excel_file(file_path)
                    if df is None or df.empty:
                        continue
                    
                    column_mapping = find_column_mapping(df.columns)
                    required_cols = ['date', 'company', 'product', 'batch', 'quantity']
                    missing_cols = [col for col in required_cols if col not in column_mapping]
                    
                    if missing_cols:
                        continue
                    
                    selected_df = df[[
                        column_mapping['date'],
                        column_mapping['company'],
                        column_mapping['product'],
                        column_mapping['batch'],
                        column_mapping['quantity']
                    ]].copy()
                    
                    selected_df.columns = ['出库日期', '商业公司', '产品名称', '批号', '数量']
                    selected_df = selected_df.dropna(subset=['商业公司', '产品名称', '批号'])
                    selected_df['数量'] = pd.to_numeric(selected_df['数量'], errors='coerce').fillna(0)
                    selected_df['级次'] = 1
                    
                    direct_sale_df = pd.concat([direct_sale_df, selected_df], ignore_index=True)
                    
                    processed_files += 1
                    progress_bar.progress(20 + int(60 * processed_files / total_files))
                    
                except Exception as e:
                    continue
            
            st.success(f"成功处理 {processed_files}/{total_files} 个文件，获得 {len(direct_sale_df)} 条出库记录")
            
        except Exception as e:
            st.error(f"解压或处理压缩包失败: {e}")
            return None, None
        
        if direct_sale_df.empty:
            st.warning("未获取到任何有效的出库数据")
            return None, None
        
        status_text.text("处理流向数据...")
        progress_bar.progress(80)
        
        try:
            flow_template_df = process_flow_data_with_fixed_matching(direct_sale_df, sales_detail_df)
            
            if flow_template_df.empty:
                st.warning("未生成任何流向数据，请检查数据匹配情况")
                return None, None
            
            result_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
            temp_files['result_file'] = result_temp_file.name
            result_temp_file.close()
            
            flow_template_df.to_excel(temp_files['result_file'], index=False)
            
            progress_bar.progress(100)
            status_text.text("处理完成！")
            
            return temp_files['result_file'], temp_files
            
        except Exception as e:
            st.error(f"处理流向数据失败: {e}")
            return None, None
            
    except Exception as e:
        st.error(f"处理过程中发生错误: {e}")
        return None, None

def cleanup_temp_files(temp_files):
    if not temp_files:
        return
    
    for key, file_path in temp_files.items():
        if key == 'extract_dir':
            safe_delete_directory(file_path)
        elif key != 'result_file':
            safe_delete_file(file_path)

def main():
    st.title("📊 流向数据处理AI系统")
    st.markdown("---")
    
    # 文件上传区域
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📦  厂家出库明细压缩包")
        st.info("上传包含出库明细Excel文件的ZIP压缩包")
        zip_file = st.file_uploader("上传出库明细压缩包 (.zip)", type=['zip'], key='zip_uploader')
    
    with col2:
        st.subheader("📋 商业公司销售明细表")
        st.info("上传商业公司销售明细Excel文件")
        sales_file = st.file_uploader("上传商业公司销售明细表 (.xlsx)", type=['xlsx'], key='sales_uploader')
    
    # 处理按钮
    if st.button("🚀 开始处理", type="primary", use_container_width=True):
        if zip_file is None or sales_file is None:
            st.warning("请先上传所有必需的文件！")
            return
        
        temp_files_to_cleanup = None
        result_file_path = None
        
        try:
            with st.spinner("正在处理数据，请稍候..."):
                result_file_path, temp_files_to_cleanup = process_files(zip_file, sales_file)
                
                if result_file_path:
                    try:
                        result_df = pd.read_excel(result_file_path)
                        
                        st.success("✅ 数据处理完成！")
                        
                        # 显示统计信息
                        col1, col2, col3, col4, col5 = st.columns(5)
                        
                        with col1:
                            st.metric("总记录数", len(result_df))
                        
                        with col2:
                            unique_companies = result_df['流向商业公司名'].nunique()
                            st.metric("涉及商业公司数", unique_companies)
                        
                        with col3:
                            unique_products = result_df['品规'].nunique()
                            st.metric("涉及产品数", unique_products)
                            
                        with col4:
                            total_original_quantity = result_df['销售数量'].sum()
                            st.metric("原始销售数量", f"{total_original_quantity:,.0f}")
                            
                        with col5:
                            total_converted_quantity = result_df['转换后数量'].sum()
                            st.metric("转换后销售数量", f"{total_converted_quantity:,.0f}")
                        
                        # 按流向级别统计
                        st.subheader("📈 流向级别统计")
                        level_stats = result_df.groupby('流向级别').agg({
                            '流向商业公司名': 'count',
                            '销售数量': 'sum',
                            '转换后数量': 'sum'
                        }).rename(columns={
                            '流向商业公司名': '记录数',
                            '销售数量': '原始总数量',
                            '转换后数量': '转换后总数量'
                        })
                        st.dataframe(level_stats)
                        
                        # 显示数据预览
                        st.subheader("📊 处理结果预览")
                        st.dataframe(result_df.head(10))
                        
                        # 提供下载链接
                        st.subheader("📥 下载处理结果")
                        
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            result_df.to_excel(writer, index=False, sheet_name='流向数据')
                            level_stats.to_excel(writer, sheet_name='级别统计')
                        
                        output.seek(0)
                        
                        download_filename = f"流向数据_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                        
                        st.download_button(
                            label="📥 下载清洗完成流向数据Excel文件",
                            data=output.getvalue(),
                            file_name=download_filename,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                        
                        st.success(f"文件已准备好下载：{download_filename}")
                            
                    except Exception as e:
                        st.error(f"读取结果文件失败: {e}")
                else:
                    st.error("❌ 数据处理失败，请检查文件格式和数据内容")
                    
        except Exception as e:
            st.error(f"处理过程中发生未预期的错误: {e}")
            
        finally:
            if temp_files_to_cleanup:
                cleanup_temp_files(temp_files_to_cleanup)
            
            if result_file_path:
                safe_delete_file(result_file_path)

if __name__ == "__main__":
    main()