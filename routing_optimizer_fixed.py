import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import math
import streamlit as st

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
            uploaded_file.seek(0)  # Reset file pointer
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
        df = df.reset_index(drop=True)  # Reset index for consistency
        
        st.write(f"### 成功加载 {len(df)} 家药店")
        
        # Haversine Formula to calculate distance between two points on Earth
        def haversine_distance(lat1, lon1, lat2, lon2):
            R = 6371  # Earth radius in km
            phi1, phi2 = math.radians(lat1), math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlambda = math.radians(lon2 - lon1)
            
            a = math.sin(dphi / 2)**2 + \
                math.cos(phi1) * math.cos(phi2) * \
                math.sin(dlambda / 2)**2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            
            return R * c
        
        # Calculate total distance for a given path
        def calculate_path_distance(path_indices, df):
            total_dist = 0
            for i in range(len(path_indices) - 1):
                idx1 = path_indices[i]
                idx2 = path_indices[i+1]
                total_dist += haversine_distance(
                    df.iloc[idx1]['Latitude'], df.iloc[idx1]['Longitude'],
                    df.iloc[idx2]['Latitude'], df.iloc[idx2]['Longitude']
                )
            return total_dist
        
        # 2-opt optimization algorithm for open path
        def two_opt_optimization(path_indices, df, max_iterations=1000):
            """
            2-opt algorithm optimized for open paths (start to end, no loop back)
            """
            path = list(path_indices)
            improved = True
            iteration = 0
            
            while improved and iteration < max_iterations:
                improved = False
                iteration += 1
                
                for i in range(len(path) - 2):
                    for j in range(i + 2, len(path)):
                        # For open path, we check if reversing path[i+1:j+1] improves distance
                        if j == len(path) - 1:
                            # Special case: reversing to the end
                            current_dist = (
                                haversine_distance(
                                    df.iloc[path[i]]['Latitude'], df.iloc[path[i]]['Longitude'],
                                    df.iloc[path[i+1]]['Latitude'], df.iloc[path[i+1]]['Longitude']
                                ) +
                                haversine_distance(
                                    df.iloc[path[j-1]]['Latitude'], df.iloc[path[j-1]]['Longitude'],
                                    df.iloc[path[j]]['Latitude'], df.iloc[path[j]]['Longitude']
                                )
                            )
                            
                            new_dist = (
                                haversine_distance(
                                    df.iloc[path[i]]['Latitude'], df.iloc[path[i]]['Longitude'],
                                    df.iloc[path[j]]['Latitude'], df.iloc[path[j]]['Longitude']
                                ) +
                                haversine_distance(
                                    df.iloc[path[i+1]]['Latitude'], df.iloc[path[i+1]]['Longitude'],
                                    df.iloc[path[j-1]]['Latitude'], df.iloc[path[j-1]]['Longitude']
                                )
                            )
                        else:
                            # Normal case: reversing middle segment
                            current_dist = (
                                haversine_distance(
                                    df.iloc[path[i]]['Latitude'], df.iloc[path[i]]['Longitude'],
                                    df.iloc[path[i+1]]['Latitude'], df.iloc[path[i+1]]['Longitude']
                                ) +
                                haversine_distance(
                                    df.iloc[path[j]]['Latitude'], df.iloc[path[j]]['Longitude'],
                                    df.iloc[path[j+1]]['Latitude'], df.iloc[path[j+1]]['Longitude']
                                )
                            )
                            
                            new_dist = (
                                haversine_distance(
                                    df.iloc[path[i]]['Latitude'], df.iloc[path[i]]['Longitude'],
                                    df.iloc[path[j]]['Latitude'], df.iloc[path[j]]['Longitude']
                                ) +
                                haversine_distance(
                                    df.iloc[path[i+1]]['Latitude'], df.iloc[path[i+1]]['Longitude'],
                                    df.iloc[path[j+1]]['Latitude'], df.iloc[path[j+1]]['Longitude']
                                )
                            )
                        
                        # If improvement found, reverse the segment
                        if new_dist < current_dist:
                            path[i+1:j+1] = reversed(path[i+1:j+1])
                            improved = True
            
            return path
        
        # Function to find optimal path from a given starting point
        def find_optimal_path_from_start(start_idx, df):
            """
            Find the optimal path starting from a specific pharmacy
            """
            # Step 1: Nearest Neighbor Heuristic
            current_idx = start_idx
            unvisited = set(range(len(df))) - {start_idx}
            path = [start_idx]
            
            while unvisited:
                nearest_idx = -1
                min_dist = float('inf')
                
                curr_lat = df.iloc[current_idx]['Latitude']
                curr_lon = df.iloc[current_idx]['Longitude']
                
                for candidate_idx in unvisited:
                    cand_lat = df.iloc[candidate_idx]['Latitude']
                    cand_lon = df.iloc[candidate_idx]['Longitude']
                    d = haversine_distance(curr_lat, curr_lon, cand_lat, cand_lon)
                    
                    if d < min_dist:
                        min_dist = d
                        nearest_idx = candidate_idx
                        
                path.append(nearest_idx)
                unvisited.remove(nearest_idx)
                current_idx = nearest_idx
            
            # Step 2: Apply 2-opt optimization
            path = two_opt_optimization(path, df)
            
            # Calculate distance
            distance = calculate_path_distance(path, df)
            
            return path, distance
        
        # Scenario A: Original Order (The "Before")
        path_before_indices = list(range(len(df)))
        dist_before = calculate_path_distance(path_before_indices, df)
        
        # Scenario B: Global Optimal Route
        # Try every pharmacy as a potential starting point
        st.write("### 正在寻找全局最优路径...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        best_path = None
        best_distance = float('inf')
        best_start_idx = 0
        
        all_results = []  # Store all results for analysis
        
        for start_idx in range(len(df)):
            status_text.text(f"正在测试以第 {start_idx + 1} 家药店为起点... ({start_idx + 1}/{len(df)})")
            progress_bar.progress((start_idx + 1) / len(df))
            
            path, distance = find_optimal_path_from_start(start_idx, df)
            
            all_results.append({
                'start_idx': start_idx,
                'start_name': df.iloc[start_idx]['Name'],
                'path': path,
                'distance': distance
            })
            
            if distance < best_distance:
                best_distance = distance
                best_path = path
                best_start_idx = start_idx
        
        status_text.text(f"✅ 优化完成！找到全局最优路径")
        progress_bar.empty()
        
        path_after_indices = best_path
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
        
        # Show top 5 best starting points
        with st.expander("📊 查看各起点的路径长度对比"):
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
        lons_b = df.iloc[path_before_indices]['Longitude'].tolist()
        lats_b = df.iloc[path_before_indices]['Latitude'].tolist()
        
        ax1.plot(lons_b, lats_b, 'o-', color='gray', alpha=0.5, markersize=6, linewidth=1.5)
        ax1.plot(lons_b[0], lats_b[0], 'g*', markersize=18, label='起点', zorder=10)
        ax1.plot(lons_b[-1], lats_b[-1], 'r*', markersize=18, label='终点', zorder=10)
        
        for i in range(len(path_before_indices)):
            ax1.annotate(str(i+1), (lons_b[i], lats_b[i]), 
                        fontsize=7, ha='center', va='center',
                        bbox=dict(boxstyle='circle,pad=0.3', facecolor='white', edgecolor='gray', alpha=0.7))
        
        ax1.set_title(f"优化前 (原始顺序)\n单程路程: {dist_before:.2f} km", fontsize=12, fontweight='bold')
        ax1.set_xlabel("经度", fontsize=10)
        ax1.set_ylabel("纬度", fontsize=10)
        ax1.legend(fontsize=10)
        ax1.grid(True, linestyle='--', alpha=0.3)
        
        # Plot 2: After (Global Optimal)
        lons_a = df.iloc[path_after_indices]['Longitude'].tolist()
        lats_a = df.iloc[path_after_indices]['Latitude'].tolist()
        
        # Draw path
        ax2.plot(lons_a, lats_a, '-', color='blue', alpha=0.4, linewidth=2)
        
        # Add arrows to show direction
        for i in range(len(path_after_indices) - 1):
            p1 = (lons_a[i], lats_a[i])
            p2 = (lons_a[i+1], lats_a[i+1])
            ax2.annotate('', xy=p2, xytext=p1, 
                        arrowprops=dict(arrowstyle='->', 
                                      color='blue', lw=1.5, alpha=0.6))
        
        # Mark all intermediate points
        if len(path_after_indices) > 2:
            ax2.scatter(lons_a[1:-1], lats_a[1:-1], 
                       c='dodgerblue', s=80, alpha=0.8, edgecolors='white', linewidth=1.5, zorder=5)
        
        # Mark first store (green)
        ax2.plot(lons_a[0], lats_a[0], 'g*', markersize=22, 
                label=f'起点: {df.iloc[path_after_indices[0]]["Name"]}', zorder=10, 
                markeredgecolor='darkgreen', markeredgewidth=1.5)
        
        # Mark last store (red)
        ax2.plot(lons_a[-1], lats_a[-1], 'r*', markersize=22, 
                label=f'终点: {df.iloc[path_after_indices[-1]]["Name"]}', zorder=10, 
                markeredgecolor='darkred', markeredgewidth=1.5)
        
        # Add sequence numbers
        for i in range(len(path_after_indices)):
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
        
        # Show optimized route order
        st.write("## 全局最优巡店顺序")
        route_df = pd.DataFrame({
            '顺序': range(1, len(path_after_indices) + 1),
            '药店名称': [df.iloc[idx]['Name'] for idx in path_after_indices],
            '原序号': [idx + 1 for idx in path_after_indices],
            '经度': [f"{df.iloc[idx]['Longitude']:.6f}" for idx in path_after_indices],
            '纬度': [f"{df.iloc[idx]['Latitude']:.6f}" for idx in path_after_indices]
        })
        st.dataframe(route_df, use_container_width=True)
        
        # Download option
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