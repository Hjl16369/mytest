import streamlit as st
import pandas as pd
import zipfile
import tempfile
import os
import shutil
from datetime import datetime
from io import BytesIO
import warnings

# 明确的警告过滤设置
warnings.filterwarnings("ignore", message="missing ScriptRunContext")
warnings.filterwarnings("ignore", message="ScriptRunContext")
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# 设置页面配置
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
    '国控乐山总部': '国药控股(乐山)川药医药有限公司',
    '国控凉山总部': '国药控股凉山医药有限公司',
    '国控眉山总部': '国药控股眉山医药有限公司'
}

# 产品映射字典 - 新增单位换算系数
product_mapping = {
    '奥卡西平片(30S)': {
        '商品名称': ['奥卡西平片', '奥卡西平片(30S)'],
        '规格': ['0.3g*30片', '0.3g/片*10片/板*3板/盒*200盒'],
        '单位换算系数': {
            # 基准单位：片，出库明细通常以盒为单位，销售明细以片为单位
            '0.3g*30片': 1,  # 1盒 = 30片
            '0.3g/片*10片/板*3板/盒*200盒': 1,  # 1箱(200盒) = 6000片
            'default': 1  # 默认换算系数
        }
    },
    '布洛芬（100ml）': {
        '商品名称': ['布洛芬混悬液(迪儿诺)'],
        '规格': ['2%*100ml：2.0g/瓶/盒'],
        '单位换算系数': {
            # 基准单位：瓶
            '2%*100ml：2.0g/瓶/盒': 1,  # 1盒 = 1瓶
            'default': 1  # 默认换算系数
        }
    },
    '尿激酶（10万单位）': {
        '商品名称': ['注射用尿激酶'],
        '规格': ['10万iu×5瓶/盒'],
        '单位换算系数': {
            # 基准单位：瓶
            '10万iu×5瓶/盒': 5,  # 1盒 = 5瓶
            'default': 5  # 默认换算系数
        }
    }
}

def get_conversion_factor(product_name, spec):
    """
    获取产品的单位换算系数
    
    参数:
    - product_name: 出库明细中的产品名称
    - spec: 销售明细中的规格
    
    返回:
    - 换算系数 (float)
    """
    try:
        if product_name in product_mapping:
            conversion_factors = product_mapping[product_name]['单位换算系数']
            
            # 首先尝试精确匹配规格
            if spec and spec in conversion_factors:
                return conversion_factors[spec]
            
            # 如果没有找到精确匹配，使用默认系数
            return conversion_factors.get('default', 1)
        
        # 如果产品不在映射中，返回默认系数1
        return 1
        
    except Exception as e:
        print(f"获取换算系数时出错: {e}")
        return 1

def create_reverse_mappings():
    """创建反向映射字典，用于从销售明细匹配到出库明细"""
    
    # 创建客户名称反向映射 (全称 -> 简称)
    reverse_customer_mapping = {v: k for k, v in customer_alias_mapping.items()}
    
    # 创建产品名称反向映射 - 修正逻辑
    reverse_product_mapping = {}
    for out_product_name, product_info in product_mapping.items():
        # 处理商品名称列表
        for sales_product_name in product_info['商品名称']:
            reverse_product_mapping[sales_product_name] = out_product_name
            
            # 同时支持商品名称+规格的组合匹配
            for spec in product_info['规格']:
                combined_key = f"{sales_product_name}|{spec}"
                reverse_product_mapping[combined_key] = out_product_name
    
    return reverse_customer_mapping, reverse_product_mapping

def create_record_key(record):
    """创建记录的唯一标识键，用于去重检查"""
    try:
        # 统一日期格式
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
    """检查新记录是否与现有记录重复"""
    if existing_records_df.empty:
        return False
    
    new_key = create_record_key(new_record)
    if new_key is None:
        return False
    
    # 检查现有记录中是否有相同的键
    for _, existing_row in existing_records_df.iterrows():
        existing_key = create_record_key(existing_row)
        if existing_key == new_key:
            return True
    
    return False

def find_matching_sales_data(row, sales_detail_df, reverse_customer_mapping, reverse_product_mapping):
    """
    为出库明细的一行数据找到匹配的销售明细数据
    
    参数:
    - row: 出库明细的一行数据
    - sales_detail_df: 销售明细DataFrame
    - reverse_customer_mapping: 客户名称反向映射
    - reverse_product_mapping: 产品名称反向映射
    
    返回:
    - 匹配的销售明细DataFrame
    """
    try:
        # 1. 从出库明细获取要匹配的信息
        out_company = str(row['商业公司']).strip()
        out_product = str(row['产品名称']).strip()
        out_batch = str(row['批号']).strip()
        
        print(f"匹配目标 - 公司: {out_company}, 产品: {out_product}, 批号: {out_batch}")
        
        # 2. 公司名称匹配 - 修正逻辑
        # 在销售明细中找到能映射到出库公司的记录
        company_matched_rows = []
        for idx, sales_row in sales_detail_df.iterrows():
            sales_company = str(sales_row['公司名称']).strip()
            # 检查销售公司是否能映射到出库公司
            if sales_company in customer_alias_mapping:
                mapped_company = customer_alias_mapping[sales_company]
                if mapped_company == out_company:
                    company_matched_rows.append(idx)
        
        if not company_matched_rows:
            print(f"未找到匹配的公司: {out_company}")
            return pd.DataFrame()
        
        # 获取公司匹配的数据
        company_matched_df = sales_detail_df.loc[company_matched_rows].copy()
        
        # 3. 产品名称匹配 - 修正逻辑
        product_matched_rows = []
        for idx, sales_row in company_matched_df.iterrows():
            sales_product = str(sales_row['商品名称']).strip()
            sales_spec = str(sales_row['规格']).strip() if '规格' in sales_row and pd.notna(sales_row['规格']) else ''
            
            # 尝试多种匹配方式
            match_found = False
            
            # 方式1: 直接通过商品名称匹配
            if sales_product in reverse_product_mapping:
                if reverse_product_mapping[sales_product] == out_product:
                    match_found = True
            
            # 方式2: 通过商品名称+规格组合匹配
            if not match_found and sales_spec:
                combined_key = f"{sales_product}|{sales_spec}"
                if combined_key in reverse_product_mapping:
                    if reverse_product_mapping[combined_key] == out_product:
                        match_found = True
            
            # 方式3: 在产品映射字典中直接查找
            if not match_found:
                for map_key, map_info in product_mapping.items():
                    if map_key == out_product:
                        # 检查商品名称是否匹配
                        if sales_product in map_info['商品名称']:
                            # 如果没有规格信息，或规格匹配
                            if not sales_spec or sales_spec in map_info['规格']:
                                match_found = True
                                break
            
            if match_found:
                product_matched_rows.append(idx)
        
        if not product_matched_rows:
            print(f"未找到匹配的产品: {out_product}")
            return pd.DataFrame()
        
        # 获取产品匹配的数据
        product_matched_df = sales_detail_df.loc[product_matched_rows].copy()
        
        # 4. 批号精确匹配
        batch_matched_df = product_matched_df[
            product_matched_df['批号'].astype(str).str.strip() == out_batch
        ].copy()
        
        if batch_matched_df.empty:
            print(f"未找到匹配的批号: {out_batch}")
        else:
            print(f"找到 {len(batch_matched_df)} 条匹配记录")
        
        return batch_matched_df
        
    except Exception as e:
        print(f"匹配过程中出错: {e}")
        return pd.DataFrame()

def calculate_converted_quantity(sales_quantity, out_product, sales_spec):
    """
    根据单位换算系数计算转换后的数量
    
    参数:
    - sales_quantity: 原始销售数量
    - out_product: 出库产品名称
    - sales_spec: 销售明细中的规格
    
    返回:
    - 转换后的数量
    """
    try:
        # 获取换算系数
        conversion_factor = get_conversion_factor(out_product, sales_spec)
        
        # 计算转换后的数量
        converted_quantity = sales_quantity * conversion_factor
        
        print(f"数量转换: 原始数量={sales_quantity}, 换算系数={conversion_factor}, 转换后数量={converted_quantity}")
        
        return converted_quantity
        
    except Exception as e:
        print(f"计算转换数量时出错: {e}")
        return sales_quantity  # 出错时返回原数量

def is_company_like(name):
    """判断是否为公司名称"""
    if not name or not isinstance(name, str):
        return False
    
    name = name.strip()
    company_suffixes = [
        '有限公司', '有限责任公司', '股份有限公司', '集团有限公司',
        '医药公司', '药业公司', '药房', '诊所', '医院'
    ]
    
    return any(name.endswith(suffix) for suffix in company_suffixes)

def find_previous_level_company(product_name, batch_no, previous_level, direct_sale_df):
    """
    根据产品名称、批号和级次找到上一级的商业公司名称
    
    参数:
    - product_name: 产品名称
    - batch_no: 批号
    - previous_level: 上一级别（当前级别-1）
    - direct_sale_df: 出库明细DataFrame
    
    返回:
    - 上一级商业公司名称，如果未找到返回空字符串
    """
    try:
        # 在direct_sale_df中查找匹配的记录
        matched_records = direct_sale_df[
            (direct_sale_df['产品名称'].astype(str).str.strip() == str(product_name).strip()) &
            (direct_sale_df['批号'].astype(str).str.strip() == str(batch_no).strip()) &
            (direct_sale_df['级次'] == previous_level)
        ]
        
        if not matched_records.empty:
            # 如果找到多条记录，取第一条的商业公司名称
            previous_company = str(matched_records.iloc[0]['商业公司']).strip()
            print(f"找到上一级商业公司: 产品={product_name}, 批号={batch_no}, 级次={previous_level}, 公司={previous_company}")
            return previous_company
        else:
            print(f"未找到上一级商业公司: 产品={product_name}, 批号={batch_no}, 级次={previous_level}")
            return ''
            
    except Exception as e:
        print(f"查找上一级商业公司时出错: {e}")
        return ''

def process_flow_data_with_fixed_matching(direct_sale_df, sales_detail_df):
    """
    使用修正后的匹配逻辑处理流向数据，并添加去重检查和单位换算
    """
    # 创建反向映射
    reverse_customer_mapping, reverse_product_mapping = create_reverse_mappings()
    
    # 流向模板列
    flow_template_cols = [
        '流向商业公司名', '供货方', '所属月份', '单据日期', '代理商', 
        '一级商业名称', '二级商业名称', '三级商业名称', '四级商业名称', 
        '终端名称', '品规', '批号', '销售数量', '转换后数量', '换算系数', '原始规格', '流向级别'
    ]
    
    flow_template_df = pd.DataFrame(columns=flow_template_cols)
    
    # 用于存储需要处理的下一级数据
    next_level_data = []
    
    # 创建已存在记录的集合，用于去重检查
    existing_records_keys = set()
    
    # 处理4个级别的数据
    for level in range(1, 5):
        current_level_df = direct_sale_df[direct_sale_df['级次'] == level].copy()
        
        if current_level_df.empty:
            print(f"第 {level} 级数据为空")
            continue
            
        print(f"处理第 {level} 级数据，共 {len(current_level_df)} 行")
        
        level_processed_count = 0
        
        for _, row in current_level_df.iterrows():
            try:
                # 使用新的匹配逻辑找到匹配的销售数据
                matched_sales = find_matching_sales_data(
                    row, sales_detail_df, reverse_customer_mapping, reverse_product_mapping
                )
                
                if matched_sales.empty:
                    continue
                
                # 处理每个匹配的销售记录
                for _, sales_row in matched_sales.iterrows():
                    try:
                        # 安全转换日期
                        out_date = pd.to_datetime(row['出库日期']) if pd.notna(row['出库日期']) else pd.Timestamp.now()
                        
                        # 安全获取销售数量
                        sales_quantity = pd.to_numeric(sales_row['销售数量'], errors='coerce')
                        if pd.isna(sales_quantity):
                            sales_quantity = 0
                        
                        # 获取规格信息
                        sales_spec = str(sales_row['规格']).strip() if '规格' in sales_row and pd.notna(sales_row['规格']) else ''
                        out_product = str(row['产品名称']).strip()
                        
                        # 计算转换后的数量
                        converted_quantity = calculate_converted_quantity(sales_quantity, out_product, sales_spec)
                        
                        # 获取换算系数（用于记录）
                        conversion_factor = get_conversion_factor(out_product, sales_spec)
                        
                        # 创建流向记录
                        new_row = {
                            '流向商业公司名': str(row['商业公司']).strip(),
                            '供货方': "",# str(row['商业公司']).strip(),
                            '所属月份': out_date.strftime('%Y-%m'),
                            '单据日期': out_date,
                            '代理商': "",# str(row['商业公司']).strip(),
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
                        
                        # 设置对应级别的商业名称
                        level_key = f'{["", "一", "二", "三", "四"][level]}级商业名称'
                        new_row[level_key] = str(row['商业公司']).strip()
                        
                        # 若当前 level > 1，则需补齐上一级商业公司名称
                        if level > 1:
                            previous_level = level - 1
                            previous_company = find_previous_level_company(
                                str(row['产品名称']).strip(),
                                str(row['批号']).strip(), 
                                previous_level,
                                direct_sale_df
                            )
                            
                            # 设置上一级商业公司名称
                            if previous_company:
                                previous_level_key = f'{["", "一", "二", "三", "四"][previous_level]}级商业名称'
                                new_row[previous_level_key] = previous_company
                                print(f"补齐上一级商业公司名称: {previous_level_key} = {previous_company}")
                        
                        # 添加到结果DataFrame
                        flow_template_df = pd.concat([flow_template_df, pd.DataFrame([new_row])], ignore_index=True)
                        level_processed_count += 1
                        
                        # 检查是否需要创建下一级数据 - 使用转换后的数量
                        customer_name = str(sales_row['客户名称']).strip()
                        if level < 4 and is_company_like(customer_name):
                            # 创建下一级出库记录
                            next_level_row = {
                                '出库日期': row['出库日期'],
                                '商业公司': customer_name,
                                '产品名称': row['产品名称'],
                                '批号': row['批号'],
                                '数量': converted_quantity,  # 使用转换后的数量
                                '级次': level + 1
                            }
                            
                            # 检查是否重复
                            new_record_key = create_record_key(next_level_row)
                            
                            if new_record_key is not None:
                                # 检查在现有direct_sale_df中是否已存在
                                if not is_duplicate_record(next_level_row, direct_sale_df):
                                    # 检查在待添加的next_level_data中是否已存在
                                    if new_record_key not in existing_records_keys:
                                        next_level_data.append(next_level_row)
                                        existing_records_keys.add(new_record_key)
                                        print(f"添加下一级记录: 级次{level + 1}, 公司:{customer_name}, 产品:{row['产品名称']}, 批号:{row['批号']}, 数量:{converted_quantity}")
                                    else:
                                        print(f"跳过重复记录(待添加队列): 级次{level + 1}, 公司:{customer_name}, 产品:{row['产品名称']}, 批号:{row['批号']}")
                                else:
                                    print(f"跳过重复记录(已存在): 级次{level + 1}, 公司:{customer_name}, 产品:{row['产品名称']}, 批号:{row['批号']}")
                    
                    except Exception as e:
                        print(f"处理销售行数据时出错: {e}")
                        continue
            
            except Exception as e:
                print(f"处理出库行数据时出错: {e}")
                continue
        
        print(f"第 {level} 级处理完成，生成 {level_processed_count} 条流向记录")
        
        # 将下一级数据添加到direct_sale_df中
        if next_level_data:
            next_level_df = pd.DataFrame(next_level_data)
            direct_sale_df = pd.concat([direct_sale_df, next_level_df], ignore_index=True)
            
            # 更新已存在记录的键集合
            for record in next_level_data:
                record_key = create_record_key(record)
                if record_key:
                    existing_records_keys.add(record_key)
                    
            print(f"添加了 {len(next_level_data)} 条下一级记录到处理队列")
            next_level_data = []  # 清空列表
    
    print(f"流向数据处理完成，共生成 {len(flow_template_df)} 条记录")
    return flow_template_df

def read_excel_file(file_path):
    """读取Excel文件，支持.xlsx和.xls格式"""
    try:
        if file_path.endswith('.xlsx'):
            return pd.read_excel(file_path, engine='openpyxl')
        elif file_path.endswith('.xls'):
            # 尝试使用openpyxl，如果不支持则使用xlrd
            try:
                return pd.read_excel(file_path, engine='openpyxl')
            except Exception:
                try:
                    return pd.read_excel(file_path, engine='xlrd')
                except Exception:
                    # 如果xlrd也不可用，尝试默认引擎
                    return pd.read_excel(file_path)
        else:
            return pd.read_excel(file_path)
    except Exception as e:
        st.error(f"读取文件失败 {file_path}: {e}")
        return None

def safe_delete_file(file_path):
    """安全删除文件，处理文件占用问题"""
    try:
        if file_path and os.path.exists(file_path):
            os.unlink(file_path)
            return True
    except Exception as e:
        print(f"无法删除文件 {file_path}: {e}")
        return False

def safe_delete_directory(dir_path):
    """安全删除目录"""
    try:
        if dir_path and os.path.exists(dir_path):
            shutil.rmtree(dir_path, ignore_errors=True)
            return True
    except Exception as e:
        print(f"无法删除目录 {dir_path}: {e}")
        return False

def safe_convert_date(date_value):
    """安全转换日期"""
    try:
        if pd.isna(date_value):
            return None
        if isinstance(date_value, str):
            return pd.to_datetime(date_value)
        elif isinstance(date_value, datetime):
            return date_value
        else:
            return pd.to_datetime(date_value)
    except Exception:
        return None

def find_column_mapping(df_columns):
    """智能匹配列名"""
    mapping = {}
    
    # 定义可能的列名映射
    column_mappings = {
        'date': ['出库日期', '操作日期', '日期', '单据日期'],
        'company': ['商业公司', '购货单位', '客户', '公司', '公司名称'],
        'product': ['产品名称', '产品', '商品名称', '品名'],
        'batch': ['批号'],
        'quantity': ['数量', '批号出库数量', '出库数量', '销售数量']
    }
    
    # 转换列名为字符串，便于比较
    df_columns_str = [str(col).strip() for col in df_columns]
    
    for col_str in df_columns_str:
        for key, possible_names in column_mappings.items():
            if col_str in possible_names and key not in mapping:
                mapping[key] = col_str
                break
    
    return mapping

def validate_required_columns(sales_df, required_cols=['公司名称', '商品名称', '批号', '销售数量', '客户名称']):
    """验证销售明细表是否包含必需的列"""
    missing_cols = []
    for col in required_cols:
        if col not in sales_df.columns:
            missing_cols.append(col)
    
    return missing_cols

def process_files(zip_file, sales_file):
    """处理文件的主要逻辑"""
    # 初始化临时文件路径
    temp_files = {}
    
    try:
        # 创建进度条
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.text("读取销售明细表...")
        progress_bar.progress(10)
        
        # 读取销售明细表
        try:
            # 保存销售文件到临时文件
            sales_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
            temp_files['sales_file'] = sales_temp_file.name
            sales_temp_file.write(sales_file.getvalue())
            sales_temp_file.close()
            
            sales_detail_df = read_excel_file(temp_files['sales_file'])
            if sales_detail_df is None:
                st.error("无法读取销售明细表")
                return None, None
                
            # 清理列名
            sales_detail_df.columns = sales_detail_df.columns.str.strip()
            
            # 验证必需列
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
        
        # 保存上传的压缩包到临时文件
        zip_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        temp_files['zip_file'] = zip_temp_file.name
        zip_temp_file.write(zip_file.getvalue())
        zip_temp_file.close()
        
        # 解压并处理出库明细压缩包
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
            
            # 初始化直销商业数据
            direct_sale_cols = ['出库日期', '商业公司', '产品名称', '批号', '数量', '级次']
            direct_sale_df = pd.DataFrame(columns=direct_sale_cols)
            
            total_files = len(excel_files)
            processed_files = 0
            
            # 遍历压缩包中的所有文件
            for file_name in excel_files:
                file_path = os.path.join(extract_dir, file_name)
                st.info(f"处理文件: {file_name}")
                
                try:
                    # 读取Excel文件
                    df = read_excel_file(file_path)
                    if df is None or df.empty:
                        st.warning(f"文件 {file_name} 为空或无法读取")
                        continue
                    
                    # 智能匹配列名
                    column_mapping = find_column_mapping(df.columns)
                    
                    # 检查必要的列是否存在
                    required_cols = ['date', 'company', 'product', 'batch', 'quantity']
                    missing_cols = [col for col in required_cols if col not in column_mapping]
                    
                    if missing_cols:
                        st.warning(f"文件 {file_name} 缺少必要的列映射: {missing_cols}")
                        continue
                    
                    # 提取需要的列
                    selected_df = df[[
                        column_mapping['date'],
                        column_mapping['company'],
                        column_mapping['product'],
                        column_mapping['batch'],
                        column_mapping['quantity']
                    ]].copy()
                    
                    # 重命名列
                    selected_df.columns = ['出库日期', '商业公司', '产品名称', '批号', '数量']
                    
                    # 数据清洗
                    selected_df = selected_df.dropna(subset=['商业公司', '产品名称', '批号'])
                    selected_df['数量'] = pd.to_numeric(selected_df['数量'], errors='coerce').fillna(0)
                    
                    # 添加级次列
                    selected_df['级次'] = 1
                    
                    # 合并到直销商业表
                    direct_sale_df = pd.concat([direct_sale_df, selected_df], ignore_index=True)
                    
                    processed_files += 1
                    progress_bar.progress(20 + int(60 * processed_files / total_files))
                    
                except Exception as e:
                    st.warning(f"处理文件 {file_name} 时出错: {e}")
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
        
        # 处理流向数据
        try:
            # 使用修正后的匹配逻辑和单位换算
            flow_template_df = process_flow_data_with_fixed_matching(direct_sale_df, sales_detail_df)
            
            if flow_template_df.empty:
                st.warning("未生成任何流向数据，请检查数据匹配情况")
                st.info("可能的原因：")
                st.info("1. 出库明细和销售明细中的公司名称不匹配")
                st.info("2. 产品名称映射配置不正确")  
                st.info("3. 批号不匹配")
                return None, None
            
            # 保存结果到临时文件
            result_temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx')
            temp_files['result_file'] = result_temp_file.name
            result_temp_file.close()
            
            flow_template_df.to_excel(temp_files['result_file'], index=False)
            
            progress_bar.progress(100)
            status_text.text("处理完成！")
            
            # 返回结果文件路径和临时文件字典
            return temp_files['result_file'], temp_files
            
        except Exception as e:
            st.error(f"处理流向数据失败: {e}")
            return None, None
            
    except Exception as e:
        st.error(f"处理过程中发生错误: {e}")
        return None, None

def cleanup_temp_files(temp_files):
    """清理临时文件"""
    if not temp_files:
        return
    
    # 清理临时文件
    for key, file_path in temp_files.items():
        if key == 'extract_dir':
            safe_delete_directory(file_path)
        elif key != 'result_file':  # result_file 由调用者处理
            safe_delete_file(file_path)

def main():
    """主函数"""
    st.title("📊 流向数据处理AI系统")
    st.markdown("---")
    
    # 显示产品映射信息
    with st.expander("📋 查看产品映射配置"):
        st.write("当前支持的产品映射：")
        for out_name, mapping in product_mapping.items():
            st.write(f"**{out_name}**")
            st.write(f"- 商品名称: {', '.join(mapping['商品名称'])}")
            st.write(f"- 规格: {', '.join(mapping['规格'])}")
            st.write("- 单位换算系数:")
            for spec, factor in mapping['单位换算系数'].items():
                st.write(f"  - {spec}: {factor}")
            st.write("")
    
    # 显示客户映射信息
    with st.expander("🏢 查看客户映射配置"):
        st.write("当前支持的客户映射：")
        for short_name, full_name in customer_alias_mapping.items():
            st.write(f"**{short_name}** → {full_name}")
    
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
        
        # 初始化临时文件列表
        temp_files_to_cleanup = None
        result_file_path = None
        
        try:
            with st.spinner("正在处理数据，请稍候..."):
                result_file_path, temp_files_to_cleanup = process_files(zip_file, sales_file)
                
                if result_file_path:
                    # 读取结果文件
                    try:
                        result_df = pd.read_excel(result_file_path)
                        
                        # 显示处理结果
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
                        
                        # 按产品统计换算系数使用情况
                        st.subheader("📄 单位换算统计")
                        conversion_stats = result_df.groupby(['品规', '换算系数', '原始规格']).agg({
                            '销售数量': ['count', 'sum'],
                            '转换后数量': 'sum'
                        }).round(2)
                        conversion_stats.columns = ['记录数', '原始数量合计', '转换后数量合计']
                        st.dataframe(conversion_stats)
                        
                        # 显示上级商业公司补齐情况统计
                        st.subheader("📊 上级商业公司补齐统计")
                        level_fill_stats = {}
                        for level in range(2, 5):  # 只统计2-4级，因为1级没有上级
                            level_data = result_df[result_df['流向级别'] == level]
                            if not level_data.empty:
                                previous_level_col = f'{["", "一", "二", "三", "四"][level-1]}级商业名称'
                                filled_count = level_data[previous_level_col].notna().sum()
                                total_count = len(level_data)
                                level_fill_stats[f'第{level}级'] = {
                                    '总记录数': total_count,
                                    '已补齐上级公司数': filled_count,
                                    '补齐率': f"{(filled_count/total_count*100):.1f}%" if total_count > 0 else "0%"
                                }
                        
                        if level_fill_stats:
                            fill_stats_df = pd.DataFrame(level_fill_stats).T
                            st.dataframe(fill_stats_df)
                        
                        # 显示数据预览
                        st.subheader("📊 处理结果预览")
                        st.dataframe(result_df.head(10))
                        
                        # 提供下载链接
                        st.subheader("📥 下载处理结果")
                        
                        # 创建下载按钮
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            result_df.to_excel(writer, index=False, sheet_name='流向数据')
                            
                            # 添加统计信息工作表
                            level_stats.to_excel(writer, sheet_name='级别统计')
                            conversion_stats.to_excel(writer, sheet_name='换算统计')
                            
                            # 添加上级公司补齐统计
                            if level_fill_stats:
                                fill_stats_df.to_excel(writer, sheet_name='上级公司补齐统计')
                            
                            # 添加配置信息工作表
                            config_data = []
                            config_data.append(['类型', '简称/商品名', '全称/规格', '换算系数'])
                            config_data.append(['', '', '', ''])
                            config_data.append(['客户映射', '', '', ''])
                            for short, full in customer_alias_mapping.items():
                                config_data.append(['客户', short, full, ''])
                            
                            config_data.append(['', '', '', ''])
                            config_data.append(['产品映射', '', '', ''])
                            for out_name, mapping in product_mapping.items():
                                config_data.append(['产品', out_name, '', ''])
                                for sales_name in mapping['商品名称']:
                                    config_data.append(['', f'  商品名: {sales_name}', '', ''])
                                for spec in mapping['规格']:
                                    factor = mapping['单位换算系数'].get(spec, mapping['单位换算系数']['default'])
                                    config_data.append(['', f'  规格: {spec}', '', str(factor)])
                            
                            config_df = pd.DataFrame(config_data[1:], columns=config_data[0])
                            config_df.to_excel(writer, index=False, sheet_name='配置信息')
                        
                        output.seek(0)
                        
                        # 下载按钮
                        download_filename = f"流向数据_带单位换算_补齐上级公司_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                        
                        st.download_button(
                            label="📥 下载清洗完成流向数据Excel文件",
                            data=output.getvalue(),
                            file_name=download_filename,
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                        
                        # 成功提示
                        st.success(f"文件已准备好下载：{download_filename}")
                        
                        # 数据质量检查
                        st.subheader("🔍 数据质量检查")
                        
                        # 检查是否有空值
                        null_counts = result_df.isnull().sum()
                        if null_counts.sum() > 0:
                            st.warning("发现空值数据：")
                            for col, count in null_counts[null_counts > 0].items():
                                st.write(f"- {col}: {count} 个空值")
                        else:
                            st.success("✅ 数据完整，无空值")
                        
                        # 检查数量异常
                        zero_quantity = len(result_df[result_df['销售数量'] <= 0])
                        if zero_quantity > 0:
                            st.warning(f"发现 {zero_quantity} 条销售数量为0或负数的记录")
                        else:
                            st.success("✅ 销售数量数据正常")
                        
                        # 检查换算系数异常
                        abnormal_factors = result_df[result_df['换算系数'] <= 0]
                        if not abnormal_factors.empty:
                            st.warning(f"发现 {len(abnormal_factors)} 条换算系数异常的记录")
                        else:
                            st.success("✅ 换算系数数据正常")
                        
                        # 显示去重统计信息
                        st.subheader("📄 去重统计信息")
                        st.info("系统已自动检查并避免了重复的出库记录生成")
                        st.write("去重检查条件：出库日期、商业公司、产品名称、批号、数量完全相同的记录")
                        
                        # 显示单位换算说明
                        st.subheader("📄 单位换算说明")
                        st.info("系统根据产品规格自动进行了单位换算，确保数据的一致性")
                        st.write("换算逻辑：")
                        st.write("- 销售数量：销售明细中的原始数量")
                        st.write("- 换算系数：根据产品规格确定的转换倍数")
                        st.write("- 转换后数量：销售数量 × 换算系数")
                        st.write("- 转换后的数量用于生成下一级流向数据")
                        
                        # 显示上级公司补齐说明
                        st.subheader("📄 上级商业公司补齐说明") 
                        st.info("系统已自动补齐了各级流向数据中的上级商业公司名称")
                        st.write("补齐逻辑：")
                        st.write("- 对于第2级及以上的流向记录，系统会查找对应的上一级商业公司")
                        st.write("- 查找条件：相同的产品名称、批号，且级次为当前级次-1")
                        st.write("- 找到后会将上一级商业公司名称填入对应的列中")
                        st.write("- 这样可以完整展现产品的流向链条关系")
                            
                    except Exception as e:
                        st.error(f"读取结果文件失败: {e}")
                else:
                    st.error("❌ 数据处理失败，请检查文件格式和数据内容")
                    
        except Exception as e:
            st.error(f"处理过程中发生未预期的错误: {e}")
            
        finally:
            # 清理临时文件（除了结果文件）
            if temp_files_to_cleanup:
                cleanup_temp_files(temp_files_to_cleanup)
            
            # 清理结果文件
            if result_file_path:
                safe_delete_file(result_file_path)

    # 使用说明
    st.markdown("---")
    st.subheader("📖 使用说明")
    
    with st.expander("点击查看详细说明"):
        st.markdown("""
        ### 文件要求
        
        **出库明细压缩包：**
        - 格式：ZIP压缩包
        - 内容：包含一个或多个Excel文件（.xlsx 或 .xls）
        - 必需列：出库日期、商业公司、产品名称、批号、数量（列名可以有变化，系统会自动识别）
        
        **销售明细表：**
        - 格式：Excel文件（.xlsx）
        - 必需列：公司名称、商品名称、批号、销售数量、客户名称、规格（可选）
        
        ### 数据处理逻辑
        
        1. **公司名称匹配**：根据配置的映射关系，将销售明细中的公司简称匹配到出库明细中的全称
        2. **产品名称匹配**：根据配置的产品映射，匹配不同表中的产品名称和规格
        3. **批号精确匹配**：确保流向数据的准确性
        4. **单位换算处理**：根据产品规格自动进行单位换算，确保数据一致性
        5. **多级流向生成**：自动识别下游公司，生成多级流向关系
        6. **去重检查**：避免生成重复的出库记录，检查条件包括出库日期、商业公司、产品名称、批号、数量
        7. **上级公司补齐**：自动补齐各级流向数据中的上级商业公司名称，完整展现流向链条
        
        ### 单位换算功能
        
        **新增功能说明：**
        - **换算系数配置**：每个产品可配置不同规格的换算系数
        - **自动单位换算**：系统自动根据规格进行数量转换
        - **数据一致性**：确保上下游流向数据的单位统一
        - **换算记录追溯**：保留原始数量、换算系数和转换后数量，便于审计
        
        **换算逻辑：**
        - 原始销售数量来自销售明细
        - 根据产品和规格查找对应的换算系数
        - 转换后数量 = 原始销售数量 × 换算系数
        - 转换后的数量用于生成下一级流向数据
        
        ### 上级公司补齐功能
        
        **新增功能说明：**
        - **自动查找上级**：系统会为2级及以上的流向记录自动查找上一级商业公司
        - **完整链条展示**：补齐后可以清晰看到完整的流向链条关系
        - **查找逻辑**：根据产品名称、批号和级次精确匹配
        - **数据完整性**：确保流向数据的完整性和可追溯性
        
        **补齐逻辑：**
        - 对于级次>1的流向记录，查找级次为当前级次-1的记录
        - 匹配条件：相同的产品名称和批号
        - 找到匹配记录后，将其商业公司名称填入对应的上级列中
        
        ### 输出结果
        
        - **流向数据**：包含完整的流向信息，支持最多4级流向，包含单位换算信息和上级公司补齐
        - **级别统计**：各级别的记录数和销售数量统计（原始和转换后）
        - **换算统计**：各产品的换算系数使用情况统计
        - **上级公司补齐统计**：显示各级别上级公司名称的补齐情况
        - **配置信息**：当前使用的映射配置，便于检查和调试
        
        ### 注意事项
        
        - 确保数据中的公司名称和产品名称在映射配置中有对应关系
        - 批号必须完全一致才能匹配成功
        - 系统会自动过滤无效数据，如空值和异常数量
        - 处理大量数据时请耐心等待，系统会显示处理进度
        - **重要**：系统已加入去重机制，避免同一出库记录被重复处理
        - **新增**：单位换算功能确保了数据的一致性和可追溯性
        - **新增**：上级公司补齐功能提供了完整的流向链条视图
        
        ### 去重机制说明
        
        系统会检查以下字段的组合来判断记录是否重复：
        - 出库日期
        - 商业公司
        - 产品名称  
        - 批号
        - 数量
        
        当这5个字段完全相同时，系统会跳过该记录的添加，避免数据重复。
        
        ### 单位换算系数配置说明
        
        每个产品可以配置多个规格对应的换算系数：
        - **精确匹配**：优先使用与销售明细规格完全匹配的换算系数
        - **默认系数**：如果没有找到精确匹配，使用默认换算系数
        - **系数为1**：如果产品不在配置中，默认使用换算系数1（不进行换算）
        - **数据追溯**：输出结果中包含原始数量、换算系数和转换后数量，便于数据审计
        
        ### 上级公司补齐机制说明
        
        补齐逻辑详细说明：
        - **触发条件**：当流向记录的级别>1时，自动触发上级公司查找
        - **查找范围**：在direct_sale_df中查找级次为当前级次-1的记录
        - **匹配条件**：产品名称和批号必须完全匹配
        - **填充位置**：将找到的上一级商业公司名称填入对应的上级列中
        - **统计展示**：在输出结果中提供补齐率统计，方便数据质量评估
        """)

if __name__ == "__main__":
    main()