import pandas as pd
import streamlit as st
from io import BytesIO

# 设置页面标题
st.set_page_config(page_title="终端客户档案分析", page_icon="📊", layout="wide")
st.title("📊 终端客户档案分析工具")

# 功能介绍
st.markdown("""
欢迎使用终端客户档案分析工具！本工具可以帮助您：
1. 上传终端客户档案电子表格文件
2. 自动统计各省份的终端客户名称数量
3. 下载统计结果
""")

# 文件上传区域
st.header("第一步：上传电子表格文件")
uploaded_file = st.file_uploader(
    "请选择终端客户档案文件（支持Excel和CSV格式）", 
    type=['xlsx', 'xls', 'csv'],
    help="请确保文件中包含省份和终端客户名称信息列"
)

if uploaded_file is not None:
    try:
        # 根据文件类型读取数据
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        st.success("文件上传成功！")
        
        # 显示数据预览
        st.subheader("数据预览")
        st.dataframe(df.head(), use_container_width=True)
        
        # 显示数据基本信息
        st.write(f"数据集形状: {df.shape[0]} 行 × {df.shape[1]} 列")
        
        # 选择省份列和终端客户名称列
        st.subheader("数据列选择")

        col1, col2 = st.columns(2)


        with col1:
            province_col = st.selectbox(
                "请选择省份列",
                options=df.columns.tolist(),
                index=0,
                help="请选择包含省份信息的列"
            )
        
        with col2:
            # 尝试自动识别终端客户名称列
            terminal_candidates = [col for col in df.columns if any(word in col for word in ['客户', '名称', '终端', '企业', '公司'])]
            default_index = 0 if not terminal_candidates else df.columns.get_loc(terminal_candidates[0])
            
            terminal_col = st.selectbox(
                "请选择终端客户名称列",
                options=df.columns.tolist(),
                index=default_index,
                help="请选择包含终端客户名称的列"
            )
        
        # 处理数据
        st.subheader("数据处理")
        if st.checkbox("显示数据处理选项", False):
            col1, col2 = st.columns(2)
            with col1:
                remove_na = st.checkbox("删除空值", True)
            with col2:
                remove_duplicates = st.checkbox("删除重复的终端客户", True)
                
            if remove_na:
                initial_count = df.shape[0]
                df = df.dropna(subset=[province_col, terminal_col])
                after_count = df.shape[0]
                st.write(f"删除空值后: {after_count} 行 (删除了 {initial_count - after_count} 行)")
            
            if remove_duplicates:
                initial_count = df.shape[0]
                df = df.drop_duplicates(subset=[province_col, terminal_col])
                after_count = df.shape[0]
                st.write(f"删除重复终端客户后: {after_count} 行 (删除了 {initial_count - after_count} 行)")
        
        # 统计各省份终端客户数量
        st.subheader("统计各省份终端客户数量")
        
        # 方法选择
        method = st.radio(
            "选择统计方法",
            ["统计每个省份的终端客户数量", "查看每个省份的终端客户列表"],
            horizontal=True
        )
        
        if method == "统计每个省份的终端客户数量":
            # 统计每个省份的终端客户数量
            result = df.groupby(province_col)[terminal_col].nunique().reset_index()
            result.columns = ['省份', '终端客户数量']
            result = result.sort_values('终端客户数量', ascending=False)
            
            # 显示统计结果
            st.dataframe(result, use_container_width=True)
            
            # 可视化展示
            st.subheader("可视化展示")
            chart_type = st.radio("选择图表类型", ["柱状图", "饼图"], horizontal=True)
            
            if chart_type == "柱状图":
                st.bar_chart(result.set_index('省份'))
            else:
                # 饼图只显示前10个省份，其他归为"其他"
                if len(result) > 10:
                    top_10 = result.head(10)
                    other_sum = result['终端客户数量'].iloc[10:].sum()
                    other_row = pd.DataFrame([['其他', other_sum]], columns=['省份', '终端客户数量'])
                    pie_data = pd.concat([top_10, other_row])
                else:
                    pie_data = result
                
                st.plotly_chart(
                    {
                        "data": [{
                            "type": "pie",
                            "labels": pie_data['省份'].tolist(),
                            "values": pie_data['终端客户数量'].tolist(),
                            "hole": 0.4,
                        }],
                        "layout": {"title": "各省份终端客户数量分布"}
                    },
                    use_container_width=True
                )
            
            # 提供下载功能
            st.subheader("下载统计结果")
            
            # 转换为Excel文件供下载
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                result.to_excel(writer, index=False, sheet_name='各省终端客户统计')
                # 添加原始数据 sheet
                df.to_excel(writer, index=False, sheet_name='原始数据')
            
            processed_data = output.getvalue()
            
            st.download_button(
                label="📥 下载统计结果（Excel格式）",
                data=processed_data,
                file_name="各省终端客户数量统计.xlsx",
                mime="application/vnd.ms-excel"
            )
            
            # 也提供CSV格式下载
            csv_data = result.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 下载统计结果（CSV格式）",
                data=csv_data,
                file_name="各省终端客户数量统计.csv",
                mime="text/csv"
            )
        
        else:
            # 显示每个省份的终端客户列表
            st.info("以下显示每个省份的终端客户列表")
            
            # 按省份分组显示终端客户
            provinces = df[province_col].unique()
            for province in sorted(provinces):
                with st.expander(f"{province} (点击展开查看终端客户)"):
                    customers = df[df[province_col] == province][terminal_col].unique()
                    st.write(f"{province}共有 {len(customers)} 个终端客户:")
                    for i, customer in enumerate(customers, 1):
                        st.write(f"{i}. {customer}")
            
            # 提供详细数据下载
            st.subheader("下载详细数据")
            
            # 创建详细统计表
            detailed_result = df.groupby(province_col)[terminal_col].agg(['count', 'nunique', lambda x: list(x)]).reset_index()
            detailed_result.columns = ['省份', '总记录数', '唯一终端客户数', '终端客户列表']
            
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                detailed_result.to_excel(writer, index=False, sheet_name='详细统计')
                df.to_excel(writer, index=False, sheet_name='原始数据')
            
            detailed_data = output.getvalue()
            
            st.download_button(
                label="📥 下载详细统计结果（Excel格式）",
                data=detailed_data,
                file_name="各省终端客户详细统计.xlsx",
                mime="application/vnd.ms-excel"
            )
    
    except Exception as e:
        st.error(f"处理文件时出错: {str(e)}")
        st.info("请确保上传了正确格式的文件，并且文件没有损坏")

else:
    # 没有上传文件时的说明
    st.info("👆 请先上传终端客户档案文件")
    
    # 提供示例文件下载
    st.subheader("示例文件格式")
    sample_data = pd.DataFrame({
        '省份': ['广东', '江苏', '浙江', '广东', '山东', '江苏', '浙江', '广东'],
        '终端客户名称': ['客户A', '客户B', '客户C', '客户D', '客户E', '客户F', '客户G', '客户A'],
        '地址': ['地址1', '地址2', '地址3', '地址4', '地址5', '地址6', '地址7', '地址1']
    })
    
    st.dataframe(sample_data)
    
    # 提供示例文件下载
    sample_output = BytesIO()
    with pd.ExcelWriter(sample_output, engine='xlsxwriter') as writer:
        sample_data.to_excel(writer, index=False, sheet_name='示例数据')
    
    sample_processed = sample_output.getvalue()
    
    st.download_button(
        label="📥 下载示例文件",
        data=sample_processed,
        file_name="终端客户档案示例.xlsx",
        mime="application/vnd.ms-excel"
    )

# 页脚信息
st.markdown("---")
st.markdown("### 使用说明")
st.markdown("""
1. 上传包含省份和终端客户名称信息的电子表格文件（Excel或CSV格式）
2. 选择包含省份信息的列
3. 选择包含终端客户名称的列
4. 选择统计方法：
   - "统计每个省份的终端客户数量"：显示各省份的终端客户数量统计
   - "查看每个省份的终端客户列表"：显示每个省份的具体终端客户名称
5. 查看统计结果和可视化图表
6. 下载统计结果
""")