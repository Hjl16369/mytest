import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import streamlit as st
from scipy.spatial.distance import cdist

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
    
    st.write("### 数据预览")
    st.write(data.head())
    
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
            best_distance = calculate_path_distance_fast(path)
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
                            best_distance = best_distance - (current - new)
            
            return path, best_distance
        
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
        def select_candidate_starts(n_pharmacies, max_candidates=10):
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
                'distance': distance
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
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("优化前单程路程", f"{dist_before:.2f} km")
        
        with col2:
            st.metric("优化后单程路程", f"{dist_after:.2f} km")
        
        with col3:
            savings_km = dist_before - dist_after
            savings_percent = (savings_km / dist_before) * 100 if dist_before > 0 else 0
            st.metric("节省路程", f"{savings_km:.2f} km", f"{savings_percent:.1f}%")
        
        st.info(f"🎯 **最优起点**: {df.iloc[best_start_idx]['Name']} (原序号: {best_start_idx + 1})")
        
        # Show tested starting points comparison
        with st.expander(f"📊 查看测试的 {len(all_results)} 个起点的路径长度对比"):
            comparison_df = pd.DataFrame({
                '原序号': [r['start_idx'] + 1 for r in all_results],
                '起点药店': [r['start_name'] for r in all_results],
                '路径长度 (km)': [f"{r['distance']:.2f}" for r in all_results],
                '与最优差距 (km)': [f"{r['distance'] - best_distance:.2f}" for r in all_results]
            })
            comparison_df = comparison_df.sort_values('路径长度 (km)')
            st.dataframe(comparison_df, use_container_width=True)
        
        # Visualization
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 7))
        plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        
        # Plot 1: Before
        lons_b = df.iloc[path_before]['Longitude'].values
        lats_b = df.iloc[path_before]['Latitude'].values
        
        ax1.plot(lons_b, lats_b, 'o-', color='gray', alpha=0.5, markersize=6, linewidth=1.5)
        ax1.plot(lons_b[0], lats_b[0], 'g*', markersize=18, label='起点', zorder=10)
        ax1.plot(lons_b[-1], lats_b[-1], 'r*', markersize=18, label='终点', zorder=10)
        
        # Only show numbers if not too many pharmacies
        if len(df) <= 30:
            for i in range(len(path_before)):
                ax1.annotate(str(i+1), (lons_b[i], lats_b[i]), 
                            fontsize=7, ha='center', va='center',
                            bbox=dict(boxstyle='circle,pad=0.3', facecolor='white', edgecolor='gray', alpha=0.7))
        
        ax1.set_title(f"优化前 (原始顺序)\n单程路程: {dist_before:.2f} km", fontsize=12, fontweight='bold')
        ax1.set_xlabel("经度", fontsize=10)
        ax1.set_ylabel("纬度", fontsize=10)
        ax1.legend(fontsize=10)
        ax1.grid(True, linestyle='--', alpha=0.3)
        
        # Plot 2: After
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
        
        ax2.plot(lons_a[0], lats_a[0], 'g*', markersize=22, 
                label=f'起点: {df.iloc[path_after[0]]["Name"]}', zorder=10, 
                markeredgecolor='darkgreen', markeredgewidth=1.5)
        
        ax2.plot(lons_a[-1], lats_a[-1], 'r*', markersize=22, 
                label=f'终点: {df.iloc[path_after[-1]]["Name"]}', zorder=10, 
                markeredgecolor='darkred', markeredgewidth=1.5)
        
        # Only show numbers if not too many pharmacies
        if len(df) <= 30:
            for i in range(len(path_after)):
                ax2.text(lons_a[i], lats_a[i], str(i+1), 
                        fontsize=8, color='white', weight='bold', ha='center', va='center',
                        bbox=dict(boxstyle='circle,pad=0.25', facecolor='navy', alpha=0.7), zorder=6)
        
        ax2.set_title(f"优化后 (全局最优路径)\n单程路程: {dist_after:.2f} km (节省 {savings_percent:.1f}%)", 
                     fontsize=12, fontweight='bold', color='darkblue')
        ax2.set_xlabel("经度", fontsize=10)
        ax2.set_ylabel("纬度", fontsize=10)
        ax2.legend(fontsize=9, loc='best')
        ax2.grid(True, linestyle='--', alpha=0.3)
        
        plt.tight_layout()
        st.pyplot(fig)
        
        # Show optimized route
        st.write("## 全局最优巡店顺序")
        route_df = pd.DataFrame({
            '顺序': range(1, len(path_after) + 1),
            '药店名称': [df.iloc[idx]['Name'] for idx in path_after],
            '原序号': [idx + 1 for idx in path_after],
            '经度': [f"{df.iloc[idx]['Longitude']:.6f}" for idx in path_after],
            '纬度': [f"{df.iloc[idx]['Latitude']:.6f}" for idx in path_after]
        })
        st.dataframe(route_df, use_container_width=True)
        
        # Download
        csv = route_df.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(
            label="📥 下载全局最优路线表",
            data=csv,
            file_name="全局最优路线.csv",
            mime="text/csv",
        )
        
    except Exception as e:
        st.error(f"处理数据时出错: {str(e)}")
        st.write("请确保CSV文件格式正确，第2列为药店名称，第9列为经度，第10列为纬度")
        st.write("### 文件列信息:")
        st.write(f"文件共有 {len(data.columns)} 列")
        st.write(data.columns.tolist())
else:
    st.info("👆 请上传CSV文件开始优化路线")