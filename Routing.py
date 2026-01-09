import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import math
import streamlit as st

st.title("店铺配送路线优化系统")
st.write("上传包含店铺地址信息的CSV文件，系统将自动优化配送路线")

# File uploader
uploaded_file = st.file_uploader("选择CSV文件", type=['csv'])

if uploaded_file is not None:
    # Load the dataset
    data = pd.read_csv(uploaded_file)
    
    st.write("### 数据预览")
    st.write(data.head())
    
    # Extract relevant columns: Name, Longitude, Latitude
    # Assuming columns at indices 1, 9, 10
    try:
        df = data.iloc[:, [1, 9, 10]].copy()
        df.columns = ['Name', 'Longitude', 'Latitude']
        
        # Drop any rows with missing coordinates
        df = df.dropna()
        
        st.write(f"### 成功加载 {len(df)} 家店铺")
        
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
        
        # Scenario A: Original Order (The "Before")
        dist_before = 0
        path_before_indices = list(range(len(df)))
        path_before_indices.append(0) # Return to start
        
        for i in range(len(path_before_indices) - 1):
            idx1 = path_before_indices[i]
            idx2 = path_before_indices[i+1]
            dist_before += haversine_distance(
                df.iloc[idx1]['Latitude'], df.iloc[idx1]['Longitude'],
                df.iloc[idx2]['Latitude'], df.iloc[idx2]['Longitude']
            )
        
        # Scenario B: Nearest Neighbor Heuristic (The "After")
        current_idx = 0
        unvisited = set(range(1, len(df)))
        path_after_indices = [0]
        dist_after = 0
        
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
                    
            # Move to nearest
            dist_after += min_dist
            path_after_indices.append(nearest_idx)
            unvisited.remove(nearest_idx)
            current_idx = nearest_idx
        
        # Return to start for the loop
        last_idx = path_after_indices[-1]
        start_idx = path_after_indices[0]
        dist_after += haversine_distance(
            df.iloc[last_idx]['Latitude'], df.iloc[last_idx]['Longitude'],
            df.iloc[start_idx]['Latitude'], df.iloc[start_idx]['Longitude']
        )
        path_after_indices.append(start_idx)
        
        # Display results
        st.write("## 优化结果")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("优化前总路程", f"{dist_before:.2f} km")
        
        with col2:
            st.metric("优化后总路程", f"{dist_after:.2f} km")
        
        with col3:
            savings_km = dist_before - dist_after
            savings_percent = (savings_km / dist_before) * 100
            st.metric("节省路程", f"{savings_km:.2f} km", f"{savings_percent:.1f}%")
        
        # Visualization
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        
        # Plot 1: Before
        lons_b = df.iloc[path_before_indices]['Longitude']
        lats_b = df.iloc[path_before_indices]['Latitude']
        ax1.plot(lons_b, lats_b, 'o-', color='gray', alpha=0.7, markersize=5)
        ax1.plot(lons_b.iloc[0], lats_b.iloc[0], 'r*', markersize=15, label='起点')
        for i in range(len(path_before_indices) - 1):
            ax1.annotate(str(i+1), (lons_b.iloc[i], lats_b.iloc[i]), fontsize=8)
        ax1.set_title(f"优化前 (原始顺序)\n总路程: {dist_before:.2f} km")
        ax1.set_xlabel("经度")
        ax1.set_ylabel("纬度")
        ax1.legend()
        ax1.grid(True, linestyle='--', alpha=0.5)
        
        # Plot 2: After
        lons_a = df.iloc[path_after_indices]['Longitude']
        lats_a = df.iloc[path_after_indices]['Latitude']
        ax2.plot(lons_a, lats_a, 'o-', color='blue', alpha=0.7, markersize=5)
        ax2.plot(lons_a.iloc[0], lats_a.iloc[0], 'r*', markersize=15, label='起点')
        
        # Add arrows to show direction
        for i in range(len(path_after_indices) - 1):
            p1 = (lons_a.iloc[i], lats_a.iloc[i])
            p2 = (lons_a.iloc[i+1], lats_a.iloc[i+1])
            ax2.annotate('', xy=p2, xytext=p1, arrowprops=dict(arrowstyle="->", color='blue', lw=1.5))
            ax2.text(p1[0], p1[1], str(i+1), fontsize=9, color='black', weight='bold')
        
        ax2.set_title(f"优化后 (智能路径)\n总路程: {dist_after:.2f} km")
        ax2.set_xlabel("经度")
        ax2.set_ylabel("纬度")
        ax2.legend()
        ax2.grid(True, linestyle='--', alpha=0.5)
        
        plt.tight_layout()
        st.pyplot(fig)
        
        # Show optimized route order
        st.write("## 优化后的配送顺序")
        route_df = pd.DataFrame({
            '顺序': range(1, len(path_after_indices)),
            '店铺名称': [df.iloc[idx]['Name'] for idx in path_after_indices[:-1]],
            '经度': [df.iloc[idx]['Longitude'] for idx in path_after_indices[:-1]],
            '纬度': [df.iloc[idx]['Latitude'] for idx in path_after_indices[:-1]]
        })
        st.dataframe(route_df)
        
    except Exception as e:
        st.error(f"处理数据时出错: {str(e)}")
        st.write("请确保CSV文件格式正确，第2列为店铺名称，第10列为经度，第11列为纬度")
else:
    st.info("👆 请上传CSV文件开始优化路线")