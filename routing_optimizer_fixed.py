import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st
from scipy.spatial.distance import cdist
import matplotlib
matplotlib.use('Agg')
from matplotlib.backends.backend_pdf import PdfPages
from datetime import datetime
import io

st.title("正掌讯药店巡店路线优化系统3.0")
st.write("上传包含药店地址信息的CSV文件，系统将自动优化配送路线")

# File uploader
uploaded_file = st.file_uploader("选择CSV文件", type=['csv'])

if uploaded_file is not None:
    # Try to load the dataset with different encodings
    encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin1']
    data = None
    
    for encoding in encodings:
        try:
            uploaded_file.seek(0)
            data = pd.read_csv(uploaded_file, encoding=encoding)
            st.success(f"成功使用 {encoding} 编码读取文件")
            break
        except UnicodeDecodeError:
            continue
        except Exception as e:
            continue
    
    if data is None:
        st.error("无法读取文件，请检查文件编码格式")
        st.stop()
    
    # Display all customer information
    st.write("### 数据预览 - 所有客户信息")
    st.dataframe(data, use_container_width=True)
    
    # Extract relevant columns: Name, Longitude, Latitude
    try:
        df = data.iloc[:, [1, 8, 9]].copy()
        df.columns = ['Name', 'Longitude', 'Latitude']
        
        # Drop any rows with missing coordinates
        df = df.dropna()
        df = df.reset_index(drop=True)
        
        st.write(f"### 成功加载 {len(df)} 家药店")
        
        # Pre-compute distance matrix using vectorized operations
        @st.cache_data
        def compute_distance_matrix(lats, lons):
            """
            Vectorized haversine distance calculation for all pairs
            """
            # Convert to radians
            lats_rad = np.radians(lats)
            lons_rad = np.radians(lons)
            
            # Create matrices
            lat1 = lats_rad[:, np.newaxis]
            lat2 = lats_rad[np.newaxis, :]
            lon1 = lons_rad[:, np.newaxis]
            lon2 = lons_rad[np.newaxis, :]
            
            # Haversine formula
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
            c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
            
            R = 6371  # Earth radius in km
            return R * c
        
        # Compute distance matrix once
        lats = df['Latitude'].values
        lons = df['Longitude'].values
        dist_matrix = compute_distance_matrix(lats, lons)
        
        # Fast path distance calculation using pre-computed matrix
        def calculate_path_distance_fast(path_indices):
            total = 0
            for i in range(len(path_indices) - 1):
                total += dist_matrix[path_indices[i], path_indices[i+1]]
            return total
        
        # Optimized 2-opt with early stopping and reduced iterations
        def two_opt_optimization_fast(path, max_iterations=200, improvement_threshold=0.01):
            """
            Fast 2-opt with early stopping
            """
            improved = True
            iteration = 0
            
            while improved and iteration < max_iterations:
                improved = False
                iteration += 1
                
                for i in range(len(path) - 2):
                    for j in range(i + 2, len(path)):
                        # Calculate improvement without full path recalculation
                        if j == len(path) - 1:
                            current = dist_matrix[path[i], path[i+1]] + dist_matrix[path[j-1], path[j]]
                            new = dist_matrix[path[i], path[j]] + dist_matrix[path[i+1], path[j-1]]
                        else:
                            current = dist_matrix[path[i], path[i+1]] + dist_matrix[path[j], path[j+1]]
                            new = dist_matrix[path[i], path[j]] + dist_matrix[path[i+1], path[j+1]]
                        
                        if new < current - improvement_threshold:
                            path[i+1:j+1] = path[i+1:j+1][::-1]
                            improved = True
            
            # Always recalculate final distance to ensure accuracy
            final_distance = calculate_path_distance_fast(path)
            return path, final_distance
        
        # Optimized nearest neighbor using distance matrix
        def nearest_neighbor_fast(start_idx, n_pharmacies):
            """
            Fast nearest neighbor using pre-computed distances
            """
            path = [start_idx]
            unvisited = set(range(n_pharmacies)) - {start_idx}
            current = start_idx
            
            while unvisited:
                # Find nearest unvisited pharmacy
                distances = dist_matrix[current, list(unvisited)]
                nearest_idx = list(unvisited)[np.argmin(distances)]
                path.append(nearest_idx)
                unvisited.remove(nearest_idx)
                current = nearest_idx
            
            return path
        
        # Smart starting point selection (sample strategy)
        def select_candidate_starts(n_pharmacies, max_candidates=20):
            """
            Select promising starting points instead of trying all
            Strategy: corners + center + random samples
            """
            if n_pharmacies <= max_candidates:
                return list(range(n_pharmacies))
            
            candidates = []
            
            # Find corner points (extremes in lat/lon)
            min_lat_idx = np.argmin(lats)
            max_lat_idx = np.argmax(lats)
            min_lon_idx = np.argmin(lons)
            max_lon_idx = np.argmax(lons)
            
            candidates.extend([min_lat_idx, max_lat_idx, min_lon_idx, max_lon_idx])
            
            # Find center point
            center_lat = np.mean(lats)
            center_lon = np.mean(lons)
            center_distances = (lats - center_lat)**2 + (lons - center_lon)**2
            center_idx = np.argmin(center_distances)
            candidates.append(center_idx)
            
            # Add random samples
            remaining = max_candidates - len(set(candidates))
            if remaining > 0:
                available = list(set(range(n_pharmacies)) - set(candidates))
                if len(available) > remaining:
                    random_samples = np.random.choice(available, remaining, replace=False)
                    candidates.extend(random_samples)
                else:
                    candidates.extend(available)
            
            return list(set(candidates))
        
        # Original order (baseline)
        path_before = list(range(len(df)))
        dist_before = calculate_path_distance_fast(path_before)
        
        # Global optimization with smart sampling
        st.write("### 正在寻找全局最优路径...")
        
        # Determine search strategy based on pharmacy count
        n_pharmacies = len(df)
        
        if n_pharmacies <= 15:
            # Small dataset: try all starting points
            candidate_starts = list(range(n_pharmacies))
            st.info(f"数据规模较小，将测试所有 {n_pharmacies} 个起点")
        else:
            # Large dataset: smart sampling
            max_candidates = min(20, n_pharmacies)
            candidate_starts = select_candidate_starts(n_pharmacies, max_candidates)
            st.info(f"数据规模较大，采用智能采样策略，测试 {len(candidate_starts)} 个候选起点")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        best_path = None
        best_distance = float('inf')
        best_start_idx = 0
        
        all_results = []
        
        for idx, start_idx in enumerate(candidate_starts):
            status_text.text(f"正在测试起点 {idx + 1}/{len(candidate_starts)}: {df.iloc[start_idx]['Name']}")
            progress_bar.progress((idx + 1) / len(candidate_starts))
            
            # Nearest neighbor + 2-opt
            path = nearest_neighbor_fast(start_idx, n_pharmacies)
            path, distance = two_opt_optimization_fast(path)
            
            all_results.append({
                'start_idx': start_idx,
                'start_name': df.iloc[start_idx]['Name'],
                'distance': distance,
                'path': path
            })
            
            if distance < best_distance:
                best_distance = distance
                best_path = path
                best_start_idx = start_idx
        
        status_text.text(f"✅ 优化完成！找到全局最优路径")
        progress_bar.empty()
        
        path_after = best_path
        dist_after = best_distance
        
        # Display results
        st.write("## 优化结果")
        
        st.success(f"🎯 **最优起点**: {df.iloc[best_start_idx]['Name']} (原表格序号: {best_start_idx + 1})")
        st.success(f"✅ **最优路径总长度**: {abs(dist_after):.2f} km")
        
        # Show all tested starting points with their optimal distances
        with st.expander(f"📊 查看测试的 {len(all_results)} 个起点的最短路径长度对比"):
            st.write("**说明**: 每行显示以该药店为起点时计算出的最短路径距离，表中最小值即为全局最优方案")
            
            # Ensure all distances are positive
            comparison_df = pd.DataFrame({
                '原表格序号': [r['start_idx'] + 1 for r in all_results],
                '起点药店名称': [r['start_name'] for r in all_results],
                '该起点的最短路径 (km)': [round(abs(r['distance']), 2) for r in all_results],
                '与全局最优差距 (km)': [round(abs(r['distance']) - abs(best_distance), 2) for r in all_results]
            })
            # Sort by distance
            comparison_df = comparison_df.sort_values('该起点的最短路径 (km)')
            # Highlight the best one
            st.dataframe(
                comparison_df.style.apply(
                    lambda x: ['background-color: lightgreen' if x['该起点的最短路径 (km)'] == comparison_df['该起点的最短路径 (km)'].min() else '' for i in x],
                    axis=1
                ),
                use_container_width=True
            )
            st.info(f"全局最优方案：以 **{df.iloc[best_start_idx]['Name']}** 为起点，总路程 **{abs(best_distance):.2f} km**")
        
        # Visualization with Chinese font support
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))
        
        # Configure Chinese font - try multiple methods for better compatibility
        try:
            # Method 1: Try system fonts
            from matplotlib import font_manager
            
            # List of Chinese fonts to try
            chinese_fonts = ['SimHei', 'Microsoft YaHei', 'STHeiti', 'Arial Unicode MS', 
                           'WenQuanYi Micro Hei', 'Noto Sans CJK SC', 'Source Han Sans CN']
            
            available_fonts = [f.name for f in font_manager.fontManager.ttflist]
            
            font_found = False
            for font_name in chinese_fonts:
                if font_name in available_fonts:
                    plt.rcParams['font.sans-serif'] = [font_name]
                    font_found = True
                    break
            
            if not font_found:
                # Method 2: Use DejaVu Sans and warn user
                plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
                st.warning("未检测到中文字体，图表中的中文可能显示为方框。这不影响数据的正确性。")
        except:
            plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
        
        plt.rcParams['axes.unicode_minus'] = False
        
        # Plot 1: Original order from uploaded table
        lons_b = df.iloc[path_before]['Longitude'].values
        lats_b = df.iloc[path_before]['Latitude'].values
        
        ax1.plot(lons_b, lats_b, 'o-', color='gray', alpha=0.5, markersize=6, linewidth=1.5)
        ax1.plot(lons_b[0], lats_b[0], 'g*', markersize=18, label='Start Point', zorder=10)
        ax1.plot(lons_b[-1], lats_b[-1], 'r*', markersize=18, label='End Point', zorder=10)
        
        # Only show numbers if not too many pharmacies
        if len(df) <= 30:
            for i in range(len(path_before)):
                ax1.annotate(str(i+1), (lons_b[i], lats_b[i]), 
                            fontsize=7, ha='center', va='center',
                            bbox=dict(boxstyle='circle,pad=0.3', facecolor='white', edgecolor='gray', alpha=0.7))
        
        ax1.set_title(f"Original Order Route\n(Table Upload Sequence)\nTotal Distance: {abs(dist_before):.2f} km", 
                     fontsize=13, fontweight='bold', pad=15)
        ax1.set_xlabel("Longitude", fontsize=11)
        ax1.set_ylabel("Latitude", fontsize=11)
        ax1.legend(fontsize=10, loc='best')
        ax1.grid(True, linestyle='--', alpha=0.3)
        
        # Plot 2: Optimized path
        lons_a = df.iloc[path_after]['Longitude'].values
        lats_a = df.iloc[path_after]['Latitude'].values
        
        ax2.plot(lons_a, lats_a, '-', color='blue', alpha=0.4, linewidth=2)
        
        # Add arrows (sample for large datasets)
        arrow_step = max(1, len(path_after) // 20)
        for i in range(0, len(path_after) - 1, arrow_step):
            p1 = (lons_a[i], lats_a[i])
            p2 = (lons_a[i+1], lats_a[i+1])
            ax2.annotate('', xy=p2, xytext=p1, 
                        arrowprops=dict(arrowstyle='->', color='blue', lw=1.5, alpha=0.6))
        
        # Mark points
        if len(path_after) > 2:
            ax2.scatter(lons_a[1:-1], lats_a[1:-1], 
                       c='dodgerblue', s=80, alpha=0.8, edgecolors='white', linewidth=1.5, zorder=5)
        
        # Get start and end pharmacy names
        start_name = df.iloc[path_after[0]]['Name']
        end_name = df.iloc[path_after[-1]]['Name']
        
        ax2.plot(lons_a[0], lats_a[0], 'g*', markersize=22, 
                label=f'Start: {start_name}', zorder=10, 
                markeredgecolor='darkgreen', markeredgewidth=1.5)
        
        ax2.plot(lons_a[-1], lats_a[-1], 'r*', markersize=22, 
                label=f'End: {end_name}', zorder=10, 
                markeredgecolor='darkred', markeredgewidth=1.5)
        
        # Only show numbers if not too many pharmacies
        if len(df) <= 30:
            for i in range(len(path_after)):
                ax2.text(lons_a[i], lats_a[i], str(i+1), 
                        fontsize=8, color='white', weight='bold', ha='center', va='center',
                        bbox=dict(boxstyle='circle,pad=0.25', facecolor='navy', alpha=0.7), zorder=6)
        
        savings_percent = ((abs(dist_before) - abs(dist_after)) / abs(dist_before) * 100) if dist_before > 0 else 0
        ax2.set_title(f"Optimized Route\n(Global Best Solution)\nTotal Distance: {abs(dist_after):.2f} km (Save {savings_percent:.1f}%)", 
                     fontsize=13, fontweight='bold', color='darkblue', pad=15)
        ax2.set_xlabel("Longitude", fontsize=11)
        ax2.set_ylabel("Latitude", fontsize=11)
        ax2.legend(fontsize=9, loc='best', framealpha=0.9)
        ax2.grid(True, linestyle='--', alpha=0.3)
        
        plt.tight_layout()
        st.pyplot(fig)
        
        # Show optimized route
        st.write("## 全局最优巡店顺序")
        route_df = pd.DataFrame({
            '巡店顺序': range(1, len(path_after) + 1),
            '药店名称': [df.iloc[idx]['Name'] for idx in path_after],
            '原表格序号': [idx + 1 for idx in path_after],
            '经度': [f"{df.iloc[idx]['Longitude']:.6f}" for idx in path_after],
            '纬度': [f"{df.iloc[idx]['Latitude']:.6f}" for idx in path_after]
        })
        st.dataframe(route_df, use_container_width=True)
        
        # Download option for route table
        csv = route_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.download_button(
                label="📥 下载全局最优路线表 (CSV)",
                data=csv,
                file_name="全局最优路线.csv",
                mime="text/csv",
            )
        
        with col2:
            # Generate PDF Report
            if st.button("📄 生成并下载专业PDF报告", type="primary"):
                with st.spinner('正在生成PDF报告...'):
                    pdf_buffer = generate_pdf_report(
                        df=df,
                        data=data,
                        path_before=path_before,
                        path_after=path_after,
                        dist_before=abs(dist_before),
                        dist_after=abs(dist_after),
                        best_start_idx=best_start_idx,
                        route_df=route_df,
                        dist_matrix=dist_matrix
                    )
                    
                    st.download_button(
                        label="⬇️ 下载PDF报告",
                        data=pdf_buffer,
                        file_name=f"正掌讯药店巡店路线优化报告_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                        mime="application/pdf",
                    )
                    st.success("✅ PDF报告生成成功！")
        
    except Exception as e:
        st.error(f"处理数据时出错: {str(e)}")
        st.write("请确保CSV文件格式正确，第2列为药店名称，第9列为经度，第10列为纬度")
        st.write("### 文件列信息:")
        if 'data' in locals():
            st.write(f"文件共有 {len(data.columns)} 列")
            st.write(data.columns.tolist())

else:
    st.info("👆 请上传CSV文件开始优化路线")


# PDF Report Generation Function
def generate_pdf_report(df, data, path_before, path_after, dist_before, dist_after, 
                       best_start_idx, route_df, dist_matrix):
    """
    Generate a professional PDF report for route optimization
    """
    buffer = io.BytesIO()
    
    # Create PDF with multiple pages
    with PdfPages(buffer) as pdf:
        # Configure font for the entire PDF
        plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        
        # PAGE 1: Title Page
        fig = plt.figure(figsize=(11, 8.5))
        fig.patch.set_facecolor('white')
        ax = fig.add_subplot(111)
        ax.axis('off')
        
        # Add decorative border
        from matplotlib.patches import Rectangle
        border = Rectangle((0.05, 0.05), 0.9, 0.9, fill=False, 
                          edgecolor='#2C5F8D', linewidth=3, transform=fig.transFigure)
        fig.patches.append(border)
        
        # Title
        ax.text(0.5, 0.75, 'Pharmacy Route Optimization Report', 
               ha='center', va='center', fontsize=28, fontweight='bold', 
               color='#2C5F8D', transform=fig.transFigure)
        
        ax.text(0.5, 0.68, 'Zhengzhangxun Pharmacy Inspection Route Analysis',
               ha='center', va='center', fontsize=16, color='#555555',
               transform=fig.transFigure)
        
        # Add a decorative line
        ax.plot([0.2, 0.8], [0.63, 0.63], 'k-', lw=2, transform=fig.transFigure)
        
        # Report details
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        ax.text(0.5, 0.50, f'Report Generation Time: {current_time}',
               ha='center', va='center', fontsize=12, color='#333333',
               transform=fig.transFigure)
        
        ax.text(0.5, 0.45, f'Total Pharmacies: {len(df)}',
               ha='center', va='center', fontsize=12, color='#333333',
               transform=fig.transFigure)
        
        ax.text(0.5, 0.40, f'Optimal Starting Point: {df.iloc[best_start_idx]["Name"]}',
               ha='center', va='center', fontsize=12, color='#333333',
               transform=fig.transFigure)
        
        # Optimization results box
        results_text = f"""
        Optimization Results
        
        Original Route Distance: {dist_before:.2f} km
        Optimized Route Distance: {dist_after:.2f} km
        Distance Saved: {dist_before - dist_after:.2f} km
        Improvement: {((dist_before - dist_after) / dist_before * 100):.1f}%
        """
        
        ax.text(0.5, 0.25, results_text,
               ha='center', va='center', fontsize=11, color='#1a5490',
               bbox=dict(boxstyle='round,pad=1', facecolor='#E8F4F8', 
                        edgecolor='#2C5F8D', linewidth=2),
               transform=fig.transFigure, family='monospace')
        
        # Footer
        ax.text(0.5, 0.08, 'Issued by:',
               ha='center', va='center', fontsize=10, color='#666666',
               transform=fig.transFigure)
        
        ax.text(0.5, 0.04, "Xi'an Zhengxun Software Co., Ltd.",
               ha='center', va='center', fontsize=14, fontweight='bold',
               color='#2C5F8D', transform=fig.transFigure)
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
        
        # PAGE 2: Pharmacy List Table
        fig = plt.figure(figsize=(11, 8.5))
        fig.patch.set_facecolor('white')
        ax = fig.add_subplot(111)
        ax.axis('off')
        
        # Page title
        ax.text(0.5, 0.95, 'Pharmacy List to be Optimized',
               ha='center', va='top', fontsize=18, fontweight='bold',
               color='#2C5F8D', transform=fig.transFigure)
        
        # Create table data - show first 30 pharmacies to fit on one page
        display_df = df.head(30).copy()
        display_df.insert(0, 'No.', range(1, len(display_df) + 1))
        
        table_data = [display_df.columns.tolist()] + display_df.values.tolist()
        
        # Create table
        table = ax.table(cellText=table_data, cellLoc='left',
                        bbox=[0.1, 0.1, 0.8, 0.80],
                        colWidths=[0.1, 0.5, 0.2, 0.2])
        
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        
        # Style header row
        for i in range(len(display_df.columns)):
            cell = table[(0, i)]
            cell.set_facecolor('#2C5F8D')
            cell.set_text_props(weight='bold', color='white')
            cell.set_height(0.03)
        
        # Style data rows with alternating colors
        for i in range(1, len(table_data)):
            for j in range(len(display_df.columns)):
                cell = table[(i, j)]
                if i % 2 == 0:
                    cell.set_facecolor('#F0F0F0')
                cell.set_height(0.025)
        
        # Add note if there are more pharmacies
        if len(df) > 30:
            ax.text(0.5, 0.05, f'Note: Showing first 30 of {len(df)} pharmacies',
                   ha='center', va='center', fontsize=10, style='italic',
                   color='#666666', transform=fig.transFigure)
        
        # Footer
        ax.text(0.95, 0.02, "Xi'an Zhengxun Software Co., Ltd.",
               ha='right', va='bottom', fontsize=8, color='#999999',
               transform=fig.transFigure)
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
        
        # PAGE 3: Route Comparison Maps
        fig = plt.figure(figsize=(11, 8.5))
        fig.patch.set_facecolor('white')
        
        # Main title
        fig.text(0.5, 0.96, 'Route Optimization Comparison',
                ha='center', va='top', fontsize=18, fontweight='bold', color='#2C5F8D')
        
        # Create two subplots
        ax1 = plt.subplot(1, 2, 1)
        ax2 = plt.subplot(1, 2, 2)
        
        # Plot 1: Original Route
        lons_b = df.iloc[path_before]['Longitude'].values
        lats_b = df.iloc[path_before]['Latitude'].values
        
        ax1.plot(lons_b, lats_b, 'o-', color='gray', alpha=0.5, markersize=5, linewidth=1.5)
        ax1.plot(lons_b[0], lats_b[0], 'g*', markersize=15, label='Start', zorder=10)
        ax1.plot(lons_b[-1], lats_b[-1], 'r*', markersize=15, label='End', zorder=10)
        
        if len(df) <= 25:
            for i in range(len(path_before)):
                ax1.annotate(str(i+1), (lons_b[i], lats_b[i]), 
                           fontsize=6, ha='center', va='center',
                           bbox=dict(boxstyle='circle,pad=0.2', facecolor='white', 
                                   edgecolor='gray', alpha=0.7))
        
        ax1.set_title(f'Original Route\nDistance: {dist_before:.2f} km', 
                     fontsize=11, fontweight='bold', pad=10)
        ax1.set_xlabel('Longitude', fontsize=9)
        ax1.set_ylabel('Latitude', fontsize=9)
        ax1.legend(fontsize=8, loc='best')
        ax1.grid(True, linestyle='--', alpha=0.3)
        
        # Plot 2: Optimized Route
        lons_a = df.iloc[path_after]['Longitude'].values
        lats_a = df.iloc[path_after]['Latitude'].values
        
        ax2.plot(lons_a, lats_a, '-', color='blue', alpha=0.4, linewidth=2)
        
        arrow_step = max(1, len(path_after) // 15)
        for i in range(0, len(path_after) - 1, arrow_step):
            ax2.annotate('', xy=(lons_a[i+1], lats_a[i+1]), 
                        xytext=(lons_a[i], lats_a[i]),
                        arrowprops=dict(arrowstyle='->', color='blue', lw=1.2, alpha=0.6))
        
        if len(path_after) > 2:
            ax2.scatter(lons_a[1:-1], lats_a[1:-1], 
                       c='dodgerblue', s=60, alpha=0.8, edgecolors='white', 
                       linewidth=1.2, zorder=5)
        
        ax2.plot(lons_a[0], lats_a[0], 'g*', markersize=18, 
                label=f'Start: {df.iloc[path_after[0]]["Name"][:10]}...', 
                zorder=10, markeredgecolor='darkgreen', markeredgewidth=1.2)
        
        ax2.plot(lons_a[-1], lats_a[-1], 'r*', markersize=18, 
                label=f'End: {df.iloc[path_after[-1]]["Name"][:10]}...', 
                zorder=10, markeredgecolor='darkred', markeredgewidth=1.2)
        
        if len(df) <= 25:
            for i in range(len(path_after)):
                ax2.text(lons_a[i], lats_a[i], str(i+1), 
                        fontsize=6, color='white', weight='bold', 
                        ha='center', va='center',
                        bbox=dict(boxstyle='circle,pad=0.2', facecolor='navy', alpha=0.7), 
                        zorder=6)
        
        savings_percent = ((dist_before - dist_after) / dist_before * 100) if dist_before > 0 else 0
        ax2.set_title(f'Optimized Route\nDistance: {dist_after:.2f} km (Save {savings_percent:.1f}%)', 
                     fontsize=11, fontweight='bold', color='darkblue', pad=10)
        ax2.set_xlabel('Longitude', fontsize=9)
        ax2.set_ylabel('Latitude', fontsize=9)
        ax2.legend(fontsize=7, loc='best', framealpha=0.9)
        ax2.grid(True, linestyle='--', alpha=0.3)
        
        plt.tight_layout(rect=[0, 0.02, 1, 0.94])
        
        # Footer
        fig.text(0.95, 0.01, "Xi'an Zhengxun Software Co., Ltd.",
                ha='right', va='bottom', fontsize=8, color='#999999')
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
        
        # PAGE 4: Optimized Route Table
        fig = plt.figure(figsize=(11, 8.5))
        fig.patch.set_facecolor('white')
        ax = fig.add_subplot(111)
        ax.axis('off')
        
        # Page title
        ax.text(0.5, 0.95, 'Optimized Pharmacy Visit Sequence',
               ha='center', va='top', fontsize=18, fontweight='bold',
               color='#2C5F8D', transform=fig.transFigure)
        
        # Subtitle with key info
        ax.text(0.5, 0.90, f'Starting Point: {df.iloc[best_start_idx]["Name"]} | Total Distance: {dist_after:.2f} km',
               ha='center', va='top', fontsize=12, color='#555555',
               transform=fig.transFigure)
        
        # Create table - show first 30 entries
        display_route = route_df.head(30).copy()
        table_data = [display_route.columns.tolist()] + display_route.values.tolist()
        
        # Create table
        table = ax.table(cellText=table_data, cellLoc='left',
                        bbox=[0.08, 0.08, 0.84, 0.78])
        
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        
        # Style header
        for i in range(len(display_route.columns)):
            cell = table[(0, i)]
            cell.set_facecolor('#2C5F8D')
            cell.set_text_props(weight='bold', color='white')
            cell.set_height(0.03)
        
        # Style rows
        for i in range(1, len(table_data)):
            for j in range(len(display_route.columns)):
                cell = table[(i, j)]
                if i == 1:  # Highlight first pharmacy
                    cell.set_facecolor('#C6E5C6')
                elif i == len(table_data) - 1 and len(display_route) == len(route_df):  # Last
                    cell.set_facecolor('#F5C6C6')
                elif i % 2 == 0:
                    cell.set_facecolor('#F0F0F0')
                cell.set_height(0.025)
        
        # Add note if truncated
        if len(route_df) > 30:
            ax.text(0.5, 0.04, f'Note: Showing first 30 of {len(route_df)} pharmacies in sequence',
                   ha='center', va='center', fontsize=10, style='italic',
                   color='#666666', transform=fig.transFigure)
        
        # Footer
        ax.text(0.95, 0.01, "Xi'an Zhengxun Software Co., Ltd.",
               ha='right', va='bottom', fontsize=8, color='#999999',
               transform=fig.transFigure)
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
        
        # Set PDF metadata
        d = pdf.infodict()
        d['Title'] = 'Pharmacy Route Optimization Report'
        d['Author'] = "Xi'an Zhengxun Software Co., Ltd."
        d['Subject'] = 'Route Optimization Analysis'
        d['Keywords'] = 'Pharmacy, Route Optimization, Zhengzhangxun'
        d['CreationDate'] = datetime.now()
    
    buffer.seek(0)
    return buffer