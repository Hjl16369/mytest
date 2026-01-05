import streamlit as st
import pandas as pd
import numpy as np
from scipy.spatial.distance import cdist
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans
import warnings
from datetime import datetime
import io
import zipfile

warnings.filterwarnings('ignore')

# 设置页面配置
st.set_page_config(
    page_title="基于GIS的正掌讯智能客户分配系统V2.0",
    page_icon="🎯",
    layout="wide"
)

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

st.title("🎯 基于GIS的正掌讯智能客户分配系统V2.0")
st.markdown("---")

# 侧边栏说明
with st.sidebar:
    st.header("📖 使用说明")
    st.markdown("""
    ### 操作步骤：
    1. 上传**客户名单Excel**（包含客户名称、经纬度）
    2. 上传**代表名单Excel**（包含代表姓名）
    3. 点击"开始分配"按钮
    4. 查看分配结果和可视化图表
    5. 下载各代表的客户清单
    
    ### 文件要求：
    - 客户文件需包含：客户名称、纬度、经度
    - 代表文件需包含：代表姓名
    - 文件格式：.xlsx 或 .xls
    """)

# 文件上传区域
col1, col2 = st.columns(2)

with col1:
    st.subheader("📁 上传客户名单")
    customer_file = st.file_uploader(
        "选择客户Excel文件",
        type=['xlsx', 'xls'],
        key='customer'
    )
    
with col2:
    st.subheader("📁 上传代表名单")
    rep_file = st.file_uploader(
        "选择代表Excel文件",
        type=['xlsx', 'xls'],
        key='rep'
    )

# 主要处理逻辑
if customer_file and rep_file:
    
    try:
        # 读取文件
        df_customers = pd.read_excel(customer_file)
        df_reps = pd.read_excel(rep_file)
        
        st.success(f"✓ 文件读取成功！客户: {len(df_customers)} 条，代表: {len(df_reps)} 位")
        
        # 显示原始数据预览
        with st.expander("📊 查看原始数据"):
            col1, col2 = st.columns(2)
            with col1:
                st.write("**客户数据预览**")
                st.dataframe(df_customers.head(), use_container_width=True)
            with col2:
                st.write("**代表数据预览**")
                st.dataframe(df_reps.head(), use_container_width=True)
        
        # 智能列名识别
        def identify_columns(df_customers, df_reps):
            # 识别客户名称列
            name_candidates = ['客户名称', '终端名称', '名称', '店名', '药店名称', '终端']
            customer_name_col = None
            for col in df_customers.columns:
                col_lower = col.lower()
                for candidate in name_candidates:
                    if candidate in col or col in candidate or candidate in col_lower:
                        customer_name_col = col
                        break
                if customer_name_col:
                    break
            
            # 识别经纬度列（注意：兼容"维度"这个错别字）
            lat_col = lon_col = None
            for col in df_customers.columns:
                col_lower = col.lower()
                # 纬度：支持"纬度"、"维度"（错别字）、"lat"、"latitude"
                if '纬度' in col or '维度' in col or 'lat' in col_lower or 'latitude' in col_lower:
                    lat_col = col
                # 经度：支持"经度"、"lon"、"lng"、"longitude"
                if '经度' in col or 'lon' in col_lower or 'lng' in col_lower or 'longitude' in col_lower:
                    lon_col = col
            
            # 识别代表姓名列
            rep_name_candidates = ['代表姓名', '代表名称', '姓名', '名称']
            rep_name_col = None
            for col in df_reps.columns:
                col_lower = col.lower()
                for candidate in rep_name_candidates:
                    if candidate in col or col in candidate or candidate in col_lower:
                        rep_name_col = col
                        break
                if rep_name_col:
                    break
            
            return customer_name_col, lat_col, lon_col, rep_name_col
        
        customer_name_col, lat_col, lon_col, rep_name_col = identify_columns(df_customers, df_reps)
        
        # 验证列是否找到
        if not all([customer_name_col, lat_col, lon_col, rep_name_col]):
            st.error("❌ 无法识别必要的列，请检查文件格式")
            st.write("客户文件列名:", list(df_customers.columns))
            st.write("代表文件列名:", list(df_reps.columns))
            st.stop()
        
        st.info(f"✓ 列识别成功 - 客户名称: {customer_name_col}, 纬度: {lat_col}, 经度: {lon_col}, 代表姓名: {rep_name_col}")
        
        # 统一列名
        df_customers = df_customers.rename(columns={
            customer_name_col: '客户名称',
            lat_col: '纬度',
            lon_col: '经度'
        })
        df_reps = df_reps.rename(columns={rep_name_col: '代表姓名'})
        
        # 数据清洗
        original_count = len(df_customers)
        df_customers = df_customers.dropna(subset=['纬度', '经度', '客户名称'])
        df_customers = df_customers[
            (df_customers['纬度'].apply(lambda x: isinstance(x, (int, float)))) &
            (df_customers['经度'].apply(lambda x: isinstance(x, (int, float))))
        ]
        cleaned_count = len(df_customers)
        
        if original_count > cleaned_count:
            st.warning(f"⚠️ 已移除 {original_count - cleaned_count} 条无效数据")
        
        # 开始分配按钮
        if st.button("🚀 开始智能分配", type="primary", use_container_width=True):
            
            with st.spinner("正在执行智能分配算法..."):
                
                n_customers = len(df_customers)
                n_reps = len(df_reps)
                avg_capacity = n_customers / n_reps
                
                MIN_CAPACITY = int(avg_capacity * 0.85)
                MAX_CAPACITY = int(avg_capacity * 1.15)
                
                # 提取坐标
                customers_coords = df_customers[['纬度', '经度']].values
                
                # K-Means聚类
                kmeans = KMeans(n_clusters=n_reps, random_state=42, n_init=10, max_iter=300)
                initial_labels = kmeans.fit_predict(customers_coords)
                cluster_centers = kmeans.cluster_centers_
                
                # 计算距离矩阵
                dist_matrix = cdist(customers_coords, cluster_centers, metric='euclidean')
                
                # 容量平衡优化
                assignments = initial_labels.copy()
                
                progress_bar = st.progress(0)
                for iteration in range(100):
                    progress_bar.progress((iteration + 1) / 100)
                    
                    counts = np.bincount(assignments, minlength=n_reps)
                    overloaded = np.where(counts > MAX_CAPACITY)[0]
                    underloaded = np.where(counts < MIN_CAPACITY)[0]
                    
                    if len(overloaded) == 0 and len(underloaded) == 0:
                        break
                    
                    changes = 0
                    
                    for over_cluster in overloaded:
                        over_customers = np.where(assignments == over_cluster)[0]
                        distances = dist_matrix[over_customers, over_cluster]
                        sorted_indices = over_customers[np.argsort(-distances)]
                        
                        for customer_idx in sorted_indices:
                            if counts[over_cluster] <= MAX_CAPACITY:
                                break
                            
                            customer_distances = dist_matrix[customer_idx, :]
                            sorted_clusters = np.argsort(customer_distances)
                            
                            for candidate_cluster in sorted_clusters:
                                if candidate_cluster != over_cluster and counts[candidate_cluster] < MAX_CAPACITY:
                                    assignments[customer_idx] = candidate_cluster
                                    counts[over_cluster] -= 1
                                    counts[candidate_cluster] += 1
                                    changes += 1
                                    break
                    
                    if changes == 0:
                        break
                
                progress_bar.empty()
                
                # 统计结果
                final_counts = np.bincount(assignments, minlength=n_reps)
                
                df_customers['rep_index'] = assignments
                
                # 生成代表中心信息
                rep_info = []
                for i in range(n_reps):
                    rep_name = df_reps.iloc[i]['代表姓名']
                    center_lat = cluster_centers[i][0]
                    center_lon = cluster_centers[i][1]
                    customer_count = np.sum(assignments == i)
                    
                    rep_info.append({
                        '代表姓名': rep_name,
                        '代表索引': i,
                        '区域中心纬度': round(center_lat, 6),
                        '区域中心经度': round(center_lon, 6),
                        '负责客户数': customer_count
                    })
                
                df_rep_centers = pd.DataFrame(rep_info)
                
                # 映射代表信息
                def get_rep_info(rep_idx):
                    rep = df_rep_centers[df_rep_centers['代表索引'] == rep_idx].iloc[0]
                    return rep['代表姓名'], rep['区域中心纬度'], rep['区域中心经度']
                
                rep_data = df_customers['rep_index'].apply(lambda idx: pd.Series(get_rep_info(idx)))
                df_customers[['建议负责代表', '代表中心纬度', '代表中心经度']] = rep_data
                
                # 计算距离
                def calculate_distance(row):
                    lat_diff = row['纬度'] - row['代表中心纬度']
                    lon_diff = row['经度'] - row['代表中心经度']
                    distance = np.sqrt(lat_diff**2 + lon_diff**2) * 111
                    return round(distance, 2)
                
                df_customers['距离代表中心距离(km)'] = df_customers.apply(calculate_distance, axis=1)
                
                st.success("✅ 分配完成！")
                
                # 显示统计信息
                st.subheader("📊 分配统计")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("总客户数", f"{n_customers} 个")
                with col2:
                    st.metric("代表人数", f"{n_reps} 人")
                with col3:
                    st.metric("平均每人", f"{avg_capacity:.1f} 个")
                with col4:
                    st.metric("平均距离", f"{df_customers['距离代表中心距离(km)'].mean():.2f} km")
                
                # 显示详细统计表
                st.subheader("📈 各代表分配详情")
                
                stats_df = df_customers.groupby('建议负责代表').agg({
                    '客户名称': 'count',
                    '距离代表中心距离(km)': ['mean', 'median', 'max', 'min']
                }).round(2)
                
                stats_df.columns = ['客户数量', '平均距离(km)', '中位距离(km)', '最远距离(km)', '最近距离(km)']
                
                st.dataframe(stats_df, use_container_width=True)
                
                # 生成可视化图表
                st.subheader("🎨 分配效果图")
                
                fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
                
                colors = plt.cm.Set3(np.linspace(0, 1, n_reps))
                
                # 图1: 地理分布图
                for i in range(n_reps):
                    mask = df_customers['rep_index'] == i
                    customer_subset = df_customers[mask]
                    rep_name = df_rep_centers.iloc[i]['代表姓名']
                    
                    ax1.scatter(customer_subset['经度'], customer_subset['纬度'],
                               c=[colors[i]], s=50, alpha=0.6, label=rep_name,
                               edgecolors='white', linewidth=0.5)
                
                ax1.scatter(df_rep_centers['区域中心经度'], df_rep_centers['区域中心纬度'],
                           c='red', marker='*', s=800, edgecolors='black', linewidth=2,
                           label='代表中心', zorder=10)
                
                for idx, row in df_rep_centers.iterrows():
                    ax1.annotate(row['代表姓名'],
                                xy=(row['区域中心经度'], row['区域中心纬度']),
                                xytext=(10, 10), textcoords='offset points',
                                fontsize=9, fontweight='bold',
                                bbox=dict(boxstyle='round,pad=0.5', facecolor='yellow', alpha=0.7))
                
                ax1.set_title(f'客户地理分布图\n{n_customers} 个客户 → {n_reps} 位代表',
                             fontsize=12, fontweight='bold')
                ax1.set_xlabel('经度', fontsize=10)
                ax1.set_ylabel('纬度', fontsize=10)
                ax1.legend(loc='best', fontsize=8)
                ax1.grid(True, alpha=0.3, linestyle='--')
                
                # 图2: 分配数量柱状图
                rep_names = df_rep_centers['代表姓名'].values
                counts = df_rep_centers['负责客户数'].values
                
                bars = ax2.bar(range(len(rep_names)), counts, color=colors, edgecolor='black', linewidth=1.5)
                ax2.axhline(counts.mean(), color='red', linestyle='--', linewidth=2,
                           label=f'平均值: {counts.mean():.1f}')
                
                ax2.set_xticks(range(len(rep_names)))
                ax2.set_xticklabels(rep_names, rotation=0, ha='center')
                ax2.set_title('各代表负责客户数量', fontsize=12, fontweight='bold')
                ax2.set_ylabel('客户数量', fontsize=10)
                ax2.legend(fontsize=9)
                ax2.grid(True, alpha=0.3, axis='y', linestyle='--')
                
                for bar in bars:
                    height = bar.get_height()
                    ax2.text(bar.get_x() + bar.get_width()/2., height,
                            f'{int(height)}',
                            ha='center', va='bottom', fontsize=10, fontweight='bold')
                
                plt.tight_layout()
                st.pyplot(fig)
                
                # 下载区域
                st.subheader("📥 下载分配结果")
                
                # 创建ZIP文件
                zip_buffer = io.BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    
                    # 为每个代表生成独立文件
                    for idx, rep_row in df_rep_centers.iterrows():
                        rep_name = rep_row['代表姓名']
                        rep_idx = rep_row['代表索引']
                        
                        rep_customers = df_customers[df_customers['rep_index'] == rep_idx].copy()
                        rep_customers_clean = rep_customers.drop(columns=['rep_index', '代表中心纬度', '代表中心经度'])
                        
                        excel_buffer = io.BytesIO()
                        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                            rep_customers_clean.to_excel(writer, sheet_name='客户明细', index=False)
                            
                            stats = pd.DataFrame({
                                '统计项': ['客户总数', '平均距离', '最远距离', '最近距离'],
                                '数值': [
                                    f"{len(rep_customers)} 个",
                                    f"{rep_customers['距离代表中心距离(km)'].mean():.2f} km",
                                    f"{rep_customers['距离代表中心距离(km)'].max():.2f} km",
                                    f"{rep_customers['距离代表中心距离(km)'].min():.2f} km"
                                ]
                            })
                            stats.to_excel(writer, sheet_name='统计信息', index=False)
                        
                        zip_file.writestr(f"{rep_name}_客户名单({len(rep_customers)}个).xlsx", excel_buffer.getvalue())
                    
                    # 添加汇总统计
                    summary_row = pd.DataFrame({
                        '客户数量': [stats_df['客户数量'].sum()],
                        '平均距离(km)': [stats_df['平均距离(km)'].mean()],
                        '中位距离(km)': [stats_df['中位距离(km)'].median()],
                        '最远距离(km)': [stats_df['最远距离(km)'].max()],
                        '最近距离(km)': [stats_df['最近距离(km)'].min()]
                    }, index=['【总计】'])
                    
                    stats_df_full = pd.concat([stats_df, summary_row])
                    
                    summary_buffer = io.BytesIO()
                    stats_df_full.to_excel(summary_buffer)
                    zip_file.writestr("【汇总】分配统计报告.xlsx", summary_buffer.getvalue())
                    
                    # 添加完整明细
                    output_df = df_customers.drop(columns=['rep_index', '代表中心纬度', '代表中心经度'])
                    full_buffer = io.BytesIO()
                    output_df.to_excel(full_buffer, index=False)
                    zip_file.writestr("完整分配明细.xlsx", full_buffer.getvalue())
                
                zip_buffer.seek(0)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    label="📦 下载所有文件（ZIP压缩包）",
                    data=zip_buffer,
                    file_name=f"分配结果_{timestamp}.zip",
                    mime="application/zip",
                    use_container_width=True
                )
                
                st.info("💡 提示：ZIP包含各代表的客户清单、汇总统计报告和完整明细")
    
    except Exception as e:
        st.error(f"❌ 处理出错: {str(e)}")
        st.exception(e)

else:
    st.info("👆 请先上传客户名单和代表名单Excel文件")
    
    # 显示示例数据格式
    with st.expander("📝 查看文件格式示例"):
        st.write("**客户名单示例：**")
        st.dataframe(pd.DataFrame({
            '客户名称': ['药店A', '药店B', '药店C'],
            '纬度': [39.9042, 39.9100, 39.8950],
            '经度': [116.4074, 116.4200, 116.3900]
        }))
        
        st.write("**代表名单示例：**")
        st.dataframe(pd.DataFrame({
            '代表姓名': ['张三', '李四', '王五']
        }))

st.markdown("---")
st.markdown("**智能客户分配系统** | 基于聚类算法 | Powered by 正讯软件")