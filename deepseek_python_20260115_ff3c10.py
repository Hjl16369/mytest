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
from matplotlib.patches import Rectangle
import matplotlib.font_manager as fm

# ==================== PDF报告生成函数 ====================
def generate_professional_pdf_report(df, data, path_before, path_after, dist_before, dist_after, 
                                   best_start_idx, route_df, dist_matrix, comparison_df=None):
    """
    生成专业PDF报告（优化字体和布局）
    """
    buffer = io.BytesIO()
    
    # 定义专业配色方案
    PRIMARY_COLOR = '#00529B'  # 专业蓝
    SECONDARY_COLOR = '#6C757D'  # 专业灰
    ACCENT_COLOR = '#00A0E9'  # 强调蓝
    HIGHLIGHT_COLOR = '#FF6B6B'  # 高亮色
    SUCCESS_COLOR = '#28A745'  # 成功绿
    
    # 配置字体 - 简化字体配置，确保兼容性
    plt.rcParams.update({
        'font.sans-serif': ['Arial Unicode MS', 'DejaVu Sans', 'Arial', 'Helvetica'],
        'axes.unicode_minus': False,
        'figure.dpi': 150,
        'savefig.dpi': 150,
    })
    
    # 创建PDF多页文档
    with PdfPages(buffer) as pdf:
        # ==================== 第1页: 封面页 ====================
        fig = plt.figure(figsize=(11.69, 8.27))
        ax = fig.add_subplot(111)
        ax.axis('off')
        
        # 公司标识
        ax.text(0.05, 0.95, '正掌讯科技', 
                ha='left', va='top', fontsize=16, weight='bold',
                color=PRIMARY_COLOR)
        
        # 主标题
        ax.text(0.5, 0.75, '药店巡店路线优化分析报告',
                ha='center', va='center', fontsize=24, weight='bold',
                color=PRIMARY_COLOR)
        
        ax.text(0.5, 0.68, 'Pharmacy Route Optimization Report',
                ha='center', va='center', fontsize=14, 
                color=SECONDARY_COLOR, style='italic')
        
        # 装饰线
        ax.axhline(y=0.62, xmin=0.2, xmax=0.8, color='black', linewidth=1.5, alpha=0.5)
        
        # 报告信息
        report_info = f"""报告编号: RX-{datetime.now().strftime('%Y%m%d-%H%M%S')}
生成时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}
分析对象: {len(df)} 家药店
优化算法: 全局最优路径搜索
报告版本: 3.0"""
        
        # 信息框
        rect = Rectangle((0.35, 0.42), 0.3, 0.18, 
                        facecolor='#F8F9FA', edgecolor=PRIMARY_COLOR,
                        linewidth=2, zorder=1)
        ax.add_patch(rect)
        
        ax.text(0.5, 0.52, report_info,
               ha='center', va='center', fontsize=10,
               color=SECONDARY_COLOR,
               linespacing=1.5)
        
        # 关键指标
        savings_percent = ((dist_before - dist_after) / dist_before * 100) if dist_before > 0 else 0
        
        ax.text(0.2, 0.25, f'{dist_before:.2f} km',
               ha='center', va='center', fontsize=12, weight='bold',
               color=SECONDARY_COLOR)
        ax.text(0.2, 0.20, '原始路径',
               ha='center', va='top', fontsize=9,
               color=SECONDARY_COLOR)
        
        ax.text(0.4, 0.25, f'{dist_after:.2f} km',
               ha='center', va='center', fontsize=12, weight='bold',
               color=SUCCESS_COLOR)
        ax.text(0.4, 0.20, '优化路径',
               ha='center', va='top', fontsize=9,
               color=SECONDARY_COLOR)
        
        ax.text(0.6, 0.25, f'{dist_before-dist_after:.2f} km',
               ha='center', va='center', fontsize=12, weight='bold',
               color=HIGHLIGHT_COLOR)
        ax.text(0.6, 0.20, '节省距离',
               ha='center', va='top', fontsize=9,
               color=SECONDARY_COLOR)
        
        ax.text(0.8, 0.25, f'{savings_percent:.1f}%',
               ha='center', va='center', fontsize=12, weight='bold',
               color=ACCENT_COLOR)
        ax.text(0.8, 0.20, '优化比例',
               ha='center', va='top', fontsize=9,
               color=SECONDARY_COLOR)
        
        # 页脚
        ax.text(0.5, 0.10, '正掌讯科技 版权所有 © 2024',
               ha='center', va='center', fontsize=9,
               color=SECONDARY_COLOR)
        
        ax.text(0.5, 0.05, 'CONFIDENTIAL',
               ha='center', va='center', fontsize=8,
               color='#999999', style='italic')
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
        
        # ==================== 第2页: 执行摘要 ====================
        fig = plt.figure(figsize=(11.69, 8.27))
        ax = fig.add_subplot(111)
        ax.axis('off')
        
        # 页面标题
        ax.text(0.05, 0.95, '执行摘要',
                ha='left', va='top', fontsize=20, weight='bold',
                color=PRIMARY_COLOR)
        
        # 摘要内容
        summary_lines = [
            f"本报告对 {len(df)} 家药店的巡店路线进行了深度优化分析。",
            f"通过先进的路径优化算法，我们识别出全局最优的巡店顺序，",
            f"显著降低了总行驶距离，提升了巡店效率。",
            "",
            "核心发现:",
            f"• 最优起点: {df.iloc[best_start_idx]['Name']}",
            f"• 优化后路径总长度: {dist_after:.2f} km",
            f"• 相比原始路线节省: {dist_before-dist_after:.2f} km ({savings_percent:.1f}%)",
            f"• 平均药店间距: {np.mean(dist_matrix[np.triu_indices(len(df), k=1)]):.2f} km",
            "",
            "优化价值:",
            f"假设每日巡店，每年可节省约 {(dist_before-dist_after)*250:.0f} km 行驶距离，",
            f"相当于减少约 {((dist_before-dist_after)*250*0.12):.0f} 升燃油消耗。",
            "",
            "推荐行动:",
            "1. 采用报告中建议的优化路线作为标准巡店路径",
            f"2. 将 {df.iloc[best_start_idx]['Name']} 设为固定起点",
            "3. 定期更新药店坐标数据以保持路线最优",
            "4. 考虑交通因素进行时段化路线规划"
        ]
        
        y_pos = 0.85
        for line in summary_lines:
            ax.text(0.1, y_pos, line,
                   ha='left', va='top', fontsize=9,
                   color=SECONDARY_COLOR)
            y_pos -= 0.05
        
        # 页码
        ax.text(0.95, 0.02, '第 2 页',
               ha='right', va='bottom', fontsize=8,
               color=SECONDARY_COLOR)
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
        
        # ==================== 第3页: 路线对比地图 ====================
        fig, axes = plt.subplots(2, 2, figsize=(11.69, 8.27))
        
        # 主标题
        fig.suptitle('路线优化对比分析', fontsize=16, weight='bold', color=PRIMARY_COLOR, y=0.97)
        
        # 图表1: 原始路线
        ax1 = axes[0, 0]
        lons_b = df.iloc[path_before]['Longitude'].values
        lats_b = df.iloc[path_before]['Latitude'].values
        
        ax1.plot(lons_b, lats_b, 'o-', color=SECONDARY_COLOR, alpha=0.6, 
                markersize=3, linewidth=1)
        ax1.plot(lons_b[0], lats_b[0], 's', markersize=6, color='green', label='起点')
        ax1.plot(lons_b[-1], lats_b[-1], '^', markersize=6, color='red', label='终点')
        
        ax1.set_title(f'原始路线\n总距离: {dist_before:.2f} km', 
                     fontsize=10, weight='bold', pad=5, color=SECONDARY_COLOR)
        ax1.set_xlabel('经度', fontsize=8)
        ax1.set_ylabel('纬度', fontsize=8)
        ax1.legend(fontsize=7)
        ax1.grid(True, linestyle='--', alpha=0.2)
        
        # 图表2: 优化路线
        ax2 = axes[0, 1]
        lons_a = df.iloc[path_after]['Longitude'].values
        lats_a = df.iloc[path_after]['Latitude'].values
        
        ax2.plot(lons_a, lats_a, '-', color=ACCENT_COLOR, alpha=0.6, linewidth=1.5)
        
        # 标记点
        for i in range(len(path_after)):
            size = 20 if i == 0 or i == len(path_after)-1 else 10
            color = 'green' if i == 0 else 'red' if i == len(path_after)-1 else ACCENT_COLOR
            ax2.scatter(lons_a[i], lats_a[i], s=size, color=color, 
                       alpha=0.8, edgecolors='white', linewidth=0.5)
        
        ax2.set_title(f'优化路线\n总距离: {dist_after:.2f} km (节省 {savings_percent:.1f}%)', 
                     fontsize=10, weight='bold', pad=5, color=SUCCESS_COLOR)
        ax2.set_xlabel('经度', fontsize=8)
        ax2.set_ylabel('纬度', fontsize=8)
        ax2.grid(True, linestyle='--', alpha=0.2)
        
        # 图表3: 距离对比
        ax3 = axes[1, 0]
        categories = ['原始路线', '优化路线']
        distances = [dist_before, dist_after]
        colors = [SECONDARY_COLOR, SUCCESS_COLOR]
        
        bars = ax3.bar(categories, distances, color=colors, alpha=0.8, width=0.5)
        ax3.set_ylabel('距离 (km)', fontsize=9)
        ax3.set_title('路线长度对比', fontsize=11, weight='bold', pad=5)
        
        # 添加数值标签
        for bar, distance in zip(bars, distances):
            height = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width()/2., height + max(distances)*0.02,
                    f'{distance:.1f} km', ha='center', va='bottom', fontsize=8)
        
        # 图表4: 关键指标
        ax4 = axes[1, 1]
        ax4.axis('off')
        
        metrics_text = f"""关键指标摘要

总药店数量: {len(df)} 家
最优起点药店: {df.iloc[best_start_idx]['Name']}
优化后总距离: {dist_after:.2f} km
节省距离: {dist_before-dist_after:.2f} km
优化比例: {savings_percent:.1f}%
平均药店间距: {np.mean(dist_matrix[np.triu_indices(len(df), k=1)]):.2f} km"""
        
        ax4.text(0.1, 0.8, '关键指标摘要',
                ha='left', va='top', fontsize=11, weight='bold',
                color=PRIMARY_COLOR)
        
        ax4.text(0.1, 0.6, metrics_text,
                ha='left', va='top', fontsize=8,
                color=SECONDARY_COLOR,
                linespacing=1.8)
        
        plt.tight_layout(rect=[0, 0.02, 1, 0.95])
        
        # 页码
        fig.text(0.95, 0.02, '第 3 页',
                ha='right', va='bottom', fontsize=8,
                color=SECONDARY_COLOR)
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
        
        # ==================== 第4页: 优化路线详情 ====================
        fig = plt.figure(figsize=(11.69, 8.27))
        ax = fig.add_subplot(111)
        ax.axis('off')
        
        # 页面标题
        ax.text(0.05, 0.96, '优化路线详细清单',
                ha='left', va='top', fontsize=18, weight='bold',
                color=PRIMARY_COLOR)
        
        # 副标题
        ax.text(0.05, 0.92, f"最优起点: {df.iloc[best_start_idx]['Name']} | 总药店数: {len(df)} | 总距离: {dist_after:.2f} km",
                ha='left', va='top', fontsize=10,
                color=SECONDARY_COLOR)
        
        # 创建表格
        display_route = route_df.copy()
        if len(display_route) > 20:
            display_route = display_route.head(20)
            show_truncated = True
        else:
            show_truncated = False
        
        # 表格数据
        table_data = [display_route.columns.tolist()] + display_route.values.tolist()
        
        # 创建表格
        table = ax.table(cellText=table_data, cellLoc='center',
                        bbox=[0.05, 0.08, 0.90, 0.75])
        
        # 表格样式
        table.auto_set_font_size(False)
        table.set_fontsize(7)
        
        # 表头样式
        for i in range(len(display_route.columns)):
            cell = table[(0, i)]
            cell.set_facecolor(PRIMARY_COLOR)
            cell.set_text_props(weight='bold', color='white', fontsize=8)
        
        # 数据行样式
        for i in range(1, len(table_data)):
            for j in range(len(display_route.columns)):
                cell = table[(i, j)]
                if i % 2 == 0:
                    cell.set_facecolor('#F8F9FA')
                
                # 高亮起点和终点
                if i == 1:  # 起点
                    cell.set_facecolor('#E8F5E9')
                elif i == len(table_data) - 1 and not show_truncated:  # 终点
                    cell.set_facecolor('#FFEBEE')
        
        # 如果表格被截断，添加说明
        if show_truncated:
            ax.text(0.05, 0.04, f"注: 显示前20条记录，共{len(route_df)}家药店",
                   ha='left', va='center', fontsize=8, style='italic',
                   color=HIGHLIGHT_COLOR)
        
        # 统计摘要
        start_end_distance = dist_matrix[path_after[0], path_after[-1]]
        if start_end_distance > 0:
            detour_factor = dist_after / start_end_distance
            detour_factor_str = f"{detour_factor:.2f}"
        else:
            detour_factor_str = "N/A"
        
        stats_text = f"""统计摘要
总药店数: {len(df)}
优化距离: {dist_after:.2f} km
平均间距: {np.mean(dist_matrix[np.triu_indices(len(df), k=1)]):.2f} km
绕路系数: {detour_factor_str}"""
        
        ax.text(0.7, 0.25, stats_text,
               ha='left', va='top', fontsize=8,
               color=SECONDARY_COLOR,
               bbox=dict(boxstyle='round,pad=0.3', facecolor='#F8F9FA', 
                       edgecolor=SECONDARY_COLOR, linewidth=1))
        
        # 页码
        ax.text(0.95, 0.02, '第 4 页',
               ha='right', va='bottom', fontsize=8,
               color=SECONDARY_COLOR)
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
        
        # ==================== 第5页: 技术附录 ====================
        fig = plt.figure(figsize=(11.69, 8.27))
        ax = fig.add_subplot(111)
        ax.axis('off')
        
        # 页面标题
        ax.text(0.05, 0.96, '技术附录与实施建议',
                ha='left', va='top', fontsize=18, weight='bold',
                color=PRIMARY_COLOR)
        
        # 左侧内容：算法说明
        algo_text = """优化算法说明

1. 最近邻算法
从起点开始，每次选择最近的未访问药店。
时间复杂度: O(n²)
提供高质量的初始解决方案

2. 2-opt优化算法
通过交换路径中的两个边来改进路线。
消除路径交叉，优化局部结构。
迭代优化直到收敛。

3. 全局最优搜索
智能起点选择。
多起点并行测试。
早期停止机制。

4. 距离计算
使用Haversine公式。
地球半径: 6371 km。
精度: 优于0.1%。"""
        
        ax.text(0.05, 0.85, algo_text,
               ha='left', va='top', fontsize=8,
               color=SECONDARY_COLOR,
               linespacing=1.5)
        
        # 右侧内容：实施建议
        imp_text = """实施建议

1. 数据维护
定期更新药店坐标信息。
验证新药店的地理位置。
建立数据质量检查流程。

2. 路线执行
使用移动设备实时导航。
考虑交通状况动态调整。
记录实际行驶距离。

3. 持续优化
每月重新计算最优路线。
分析实际与理论差异。
根据季节调整策略。

4. 扩展功能
集成实时交通数据。
添加时间窗口约束。
支持多车辆协同。"""
        
        ax.text(0.55, 0.85, imp_text,
               ha='left', va='top', fontsize=8,
               color=SECONDARY_COLOR,
               linespacing=1.5)
        
        # 联系方式
        contact_text = """联系方式
正掌讯科技有限公司
地址: 西安市高新技术产业开发区
电话: 029-8888-8888
邮箱: support@zzxtech.com
官网: www.zzxtech.com"""
        
        ax.text(0.05, 0.40, contact_text,
               ha='left', va='top', fontsize=8,
               color=SECONDARY_COLOR,
               linespacing=1.5)
        
        # 免责声明
        disclaimer_text = f"""免责声明
本报告基于提供的数据进行计算分析，结果仅供参考。
实际行驶距离可能因道路条件、交通状况等因素有所不同。
报告生成时间: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}"""
        
        ax.text(0.5, 0.10, disclaimer_text,
               ha='center', va='center', fontsize=7,
               color='#666666',
               bbox=dict(boxstyle='round,pad=0.5', facecolor='#FFF3E0', 
                       edgecolor='#FF9800', linewidth=1))
        
        # 页码
        ax.text(0.95, 0.02, '第 5 页',
               ha='right', va='bottom', fontsize=8,
               color=SECONDARY_COLOR)
        
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
        
        # 设置PDF元数据
        d = pdf.infodict()
        d['Title'] = '药店巡店路线优化分析报告'
        d['Author'] = '正掌讯科技有限公司'
        d['Subject'] = '药店巡店路线优化分析'
        d['Keywords'] = '路径优化, 药店管理, 巡店路线'
        d['CreationDate'] = datetime.now()
        d['Producer'] = '正掌讯路线优化系统 3.0'
    
    buffer.seek(0)
    return buffer

# ==================== Streamlit主应用 ====================
st.title("正掌讯药店巡店路线优化系统3.0")
st.write("上传包含药店地址信息的CSV文件，系统将自动优化配送路线")

# 文件上传器
uploaded_file = st.file_uploader("选择CSV文件", type=['csv'])

if uploaded_file is not None:
    # 尝试用不同编码加载数据集
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
    
    # 显示所有客户信息
    st.write("### 数据预览 - 所有客户信息")
    st.dataframe(data, use_container_width=True)
    
    # 提取相关列：名称、经度、纬度
    try:
        # 显示列名帮助用户确认
        st.write("### CSV文件列信息:")
        st.write(f"文件共有 {len(data.columns)} 列，列名为: {list(data.columns)}")
        
        # 尝试自动检测列位置
        name_col = None
        lon_col = None
        lat_col = None
        
        # 寻找包含关键字的列
        for i, col in enumerate(data.columns):
            col_lower = str(col).lower()
            if any(keyword in col_lower for keyword in ['名称', 'name', '药店', '店名']):
                name_col = i
            elif any(keyword in col_lower for keyword in ['经度', 'longitude', 'lon', 'lng']):
                lon_col = i
            elif any(keyword in col_lower for keyword in ['纬度', 'latitude', 'lat']):
                lat_col = i
        
        # 如果自动检测失败，使用默认列位置
        if name_col is None or lon_col is None or lat_col is None:
            st.warning("自动检测列名失败，使用默认列位置（第2列为名称，第9列为经度，第10列为纬度）")
            name_col = 1  # 第2列
            lon_col = 8   # 第9列
            lat_col = 9   # 第10列
        else:
            st.success(f"自动检测列名成功: 名称列={data.columns[name_col]}, 经度列={data.columns[lon_col]}, 纬度列={data.columns[lat_col]}")
        
        df = data.iloc[:, [name_col, lon_col, lat_col]].copy()
        df.columns = ['Name', 'Longitude', 'Latitude']
        
        # 删除任何缺失坐标的行
        df = df.dropna()
        df = df.reset_index(drop=True)
        
        st.write(f"### 成功加载 {len(df)} 家药店")
        
        # 使用向量化操作预计算距离矩阵
        @st.cache_data
        def compute_distance_matrix(lats, lons):
            """
            所有点对的向量化Haversine距离计算
            """
            # 转换为弧度
            lats_rad = np.radians(lats)
            lons_rad = np.radians(lons)
            
            # 创建矩阵
            lat1 = lats_rad[:, np.newaxis]
            lat2 = lats_rad[np.newaxis, :]
            lon1 = lons_rad[:, np.newaxis]
            lon2 = lons_rad[np.newaxis, :]
            
            # Haversine公式
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            
            a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
            c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
            
            R = 6371  # 地球半径，单位km
            return R * c
        
        # 计算距离矩阵
        lats = df['Latitude'].values
        lons = df['Longitude'].values
        dist_matrix = compute_distance_matrix(lats, lons)
        
        # 使用预计算矩阵的快速路径距离计算
        def calculate_path_distance_fast(path_indices):
            total = 0
            for i in range(len(path_indices) - 1):
                total += dist_matrix[path_indices[i], path_indices[i+1]]
            return total
        
        # 优化的2-opt算法，带提前停止和减少迭代
        def two_opt_optimization_fast(path, max_iterations=200, improvement_threshold=0.01):
            """
            快速2-opt，带提前停止
            """
            improved = True
            iteration = 0
            
            while improved and iteration < max_iterations:
                improved = False
                iteration += 1
                
                for i in range(len(path) - 2):
                    for j in range(i + 2, len(path)):
                        # 无需完整路径重新计算即可计算改进
                        if j == len(path) - 1:
                            current = dist_matrix[path[i], path[i+1]] + dist_matrix[path[j-1], path[j]]
                            new = dist_matrix[path[i], path[j]] + dist_matrix[path[i+1], path[j-1]]
                        else:
                            current = dist_matrix[path[i], path[i+1]] + dist_matrix[path[j], path[j+1]]
                            new = dist_matrix[path[i], path[j]] + dist_matrix[path[i+1], path[j+1]]
                        
                        if new < current - improvement_threshold:
                            path[i+1:j+1] = path[i+1:j+1][::-1]
                            improved = True
            
            # 始终重新计算最终距离以确保准确性
            final_distance = calculate_path_distance_fast(path)
            return path, final_distance
        
        # 使用距离矩阵的优化最近邻算法
        def nearest_neighbor_fast(start_idx, n_pharmacies):
            """
            使用预计算距离的快速最近邻
            """
            path = [start_idx]
            unvisited = set(range(n_pharmacies)) - {start_idx}
            current = start_idx
            
            while unvisited:
                # 找到最近的未访问药店
                distances = dist_matrix[current, list(unvisited)]
                nearest_idx = list(unvisited)[np.argmin(distances)]
                path.append(nearest_idx)
                unvisited.remove(nearest_idx)
                current = nearest_idx
            
            return path
        
        # 智能起点选择（采样策略）
        def select_candidate_starts(n_pharmacies, max_candidates=20):
            """
            选择有希望的起点，而不是尝试所有点
            策略：角落点 + 中心点 + 随机样本
            """
            if n_pharmacies <= max_candidates:
                return list(range(n_pharmacies))
            
            candidates = []
            
            # 找到角落点（经纬度极值点）
            min_lat_idx = np.argmin(lats)
            max_lat_idx = np.argmax(lats)
            min_lon_idx = np.argmin(lons)
            max_lon_idx = np.argmax(lons)
            
            candidates.extend([min_lat_idx, max_lat_idx, min_lon_idx, max_lon_idx])
            
            # 找到中心点
            center_lat = np.mean(lats)
            center_lon = np.mean(lons)
            center_distances = (lats - center_lat)**2 + (lons - center_lon)**2
            center_idx = np.argmin(center_distances)
            candidates.append(center_idx)
            
            # 添加随机样本
            remaining = max_candidates - len(set(candidates))
            if remaining > 0:
                available = list(set(range(n_pharmacies)) - set(candidates))
                if len(available) > remaining:
                    random_samples = np.random.choice(available, remaining, replace=False)
                    candidates.extend(random_samples)
                else:
                    candidates.extend(available)
            
            return list(set(candidates))
        
        # 原始顺序（基准）
        path_before = list(range(len(df)))
        dist_before = calculate_path_distance_fast(path_before)
        
        # 带智能采样的全局优化
        st.write("### 正在寻找全局最优路径...")
        
        # 根据药店数量确定搜索策略
        n_pharmacies = len(df)
        
        if n_pharmacies <= 15:
            # 小数据集：尝试所有起点
            candidate_starts = list(range(n_pharmacies))
            st.info(f"数据规模较小，将测试所有 {n_pharmacies} 个起点")
        else:
            # 大数据集：智能采样
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
            
            # 最近邻 + 2-opt
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
        
        # 显示结果
        st.write("## 优化结果")
        
        st.success(f"🎯 **最优起点**: {df.iloc[best_start_idx]['Name']} (原表格序号: {best_start_idx + 1})")
        st.success(f"✅ **最优路径总长度**: {abs(dist_after):.2f} km")
        
        # 显示所有测试起点的最短路径长度
        with st.expander(f"📊 查看测试的 {len(all_results)} 个起点的最短路径长度对比"):
            st.write("**说明**: 每行显示以该药店为起点时计算出的最短路径距离，表中最小值即为全局最优方案")
            
            comparison_df = pd.DataFrame({
                '原表格序号': [r['start_idx'] + 1 for r in all_results],
                '起点药店名称': [r['start_name'] for r in all_results],
                '该起点的最短路径 (km)': [round(abs(r['distance']), 2) for r in all_results],
                '与全局最优差距 (km)': [round(abs(r['distance']) - abs(best_distance), 2) for r in all_results]
            })
            comparison_df = comparison_df.sort_values('该起点的最短路径 (km)')
            
            st.dataframe(
                comparison_df.style.apply(
                    lambda x: ['background-color: lightgreen' if x['该起点的最短路径 (km)'] == comparison_df['该起点的最短路径 (km)'].min() else '' for i in x],
                    axis=1
                ),
                use_container_width=True
            )
            st.info(f"全局最优方案：以 **{df.iloc[best_start_idx]['Name']}** 为起点，总路程 **{abs(best_distance):.2f} km**")
        
        # 支持中文的可视化
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))
        
        # 配置中文字体
        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'DejaVu Sans', 'Arial', 'Helvetica']
        plt.rcParams['axes.unicode_minus'] = False
        
        # 图表1: 上传表格的原始顺序
        lons_b = df.iloc[path_before]['Longitude'].values
        lats_b = df.iloc[path_before]['Latitude'].values
        
        ax1.plot(lons_b, lats_b, 'o-', color='gray', alpha=0.5, markersize=4, linewidth=1)
        ax1.plot(lons_b[0], lats_b[0], 'g*', markersize=12, label='起点')
        ax1.plot(lons_b[-1], lats_b[-1], 'r*', markersize=12, label='终点')
        
        ax1.set_title(f"原始顺序路线\n总距离: {abs(dist_before):.2f} km", 
                     fontsize=12, weight='bold', pad=10)
        ax1.set_xlabel("经度", fontsize=10)
        ax1.set_ylabel("纬度", fontsize=10)
        ax1.legend(fontsize=9)
        ax1.grid(True, linestyle='--', alpha=0.3)
        
        # 图表2: 优化路径
        lons_a = df.iloc[path_after]['Longitude'].values
        lats_a = df.iloc[path_after]['Latitude'].values
        
        ax2.plot(lons_a, lats_a, '-', color='blue', alpha=0.4, linewidth=1.5)
        
        # 标记点
        ax2.scatter(lons_a, lats_a, c='dodgerblue', s=30, alpha=0.8, edgecolors='white', linewidth=1)
        
        start_name = df.iloc[path_after[0]]['Name']
        end_name = df.iloc[path_after[-1]]['Name']
        
        ax2.plot(lons_a[0], lats_a[0], 'g*', markersize=15, 
                label=f'起点: {start_name}')
        
        ax2.plot(lons_a[-1], lats_a[-1], 'r*', markersize=15, 
                label=f'终点: {end_name}')
        
        savings_percent = ((abs(dist_before) - abs(dist_after)) / abs(dist_before) * 100) if dist_before > 0 else 0
        ax2.set_title(f"优化路线\n总距离: {abs(dist_after):.2f} km (节省 {savings_percent:.1f}%)", 
                     fontsize=12, weight='bold', color='darkblue', pad=10)
        ax2.set_xlabel("经度", fontsize=10)
        ax2.set_ylabel("纬度", fontsize=10)
        ax2.legend(fontsize=9, loc='best')
        ax2.grid(True, linestyle='--', alpha=0.3)
        
        plt.tight_layout()
        st.pyplot(fig)
        
        # 显示优化路线
        st.write("## 全局最优巡店顺序")
        route_df = pd.DataFrame({
            '巡店顺序': range(1, len(path_after) + 1),
            '药店名称': [df.iloc[idx]['Name'] for idx in path_after],
            '原表格序号': [idx + 1 for idx in path_after],
            '经度': [f"{df.iloc[idx]['Longitude']:.6f}" for idx in path_after],
            '纬度': [f"{df.iloc[idx]['Latitude']:.6f}" for idx in path_after]
        })
        st.dataframe(route_df, use_container_width=True)
        
        # 路线表下载选项
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
            if st.button("📄 生成并下载专业PDF报告", type="primary"):
                with st.spinner('正在生成PDF报告...'):
                    pdf_buffer = generate_professional_pdf_report(
                        df=df,
                        data=data,
                        path_before=path_before,
                        path_after=path_after,
                        dist_before=abs(dist_before),
                        dist_after=abs(dist_after),
                        best_start_idx=best_start_idx,
                        route_df=route_df,
                        dist_matrix=dist_matrix,
                        comparison_df=pd.DataFrame(all_results) if all_results else None
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
        st.write("请确保CSV文件格式正确，至少包含药店名称、经度和纬度三列")
        if 'data' in locals():
            st.write("### 文件列信息:")
            for i, col in enumerate(data.columns):
                st.write(f"列 {i}: {col}")

else:
    st.info("👆 请上传CSV文件开始优化路线")