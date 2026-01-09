import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import math

# Load the dataset
file_path = '20家店地址信息.xlsx - Sheet1.csv'
data = pd.read_csv(file_path)

# Extract relevant columns: Name, Longitude, Latitude
# Based on the snippet, Longitude is col 10 (index 9), Latitude is col 11 (index 10)
# But let's use column names if possible or index if not. 
# Looking at snippet: T029000011... 108.9237, 34.1983
# Let's assume the last two columns are Long and Lat as per typical format or parse by value.
# Actually, let's look at the dataframe structure.

# Renaming columns for clarity based on inspection
# The file has no headers in the snippet? Ah, the snippet shows "T029000003..."
# Let's check if the first row is header or data. The snippet implies data starts immediately or after a header.
# Let's standardise using column indices for safety.
# Col 1: Name (index 1), Col 9: Longitude, Col 10: Latitude (0-based index)

df = data.iloc[:, [1, 9, 10]].copy()
df.columns = ['Name', 'Longitude', 'Latitude']

# Drop any rows with missing coordinates
df = df.dropna()

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
# We assume the rep starts at the first shop, visits in list order, and returns to the first shop (loop).
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
# Start at the same first shop
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

# Visualization
plt.figure(figsize=(12, 6))
plt.rcParams['font.sans-serif'] = ['SimHei'] # Use a font that supports Chinese if available, else fallback
plt.rcParams['axes.unicode_minus'] = False

# Plot 1: Before
plt.subplot(1, 2, 1)
lons_b = df.iloc[path_before_indices]['Longitude']
lats_b = df.iloc[path_before_indices]['Latitude']
plt.plot(lons_b, lats_b, 'o-', color='gray', alpha=0.7, markersize=5)
plt.plot(lons_b.iloc[0], lats_b.iloc[0], 'r*', markersize=15, label='起点 (Start)')
for i, txt in enumerate(range(1, len(path_before_indices))):
     plt.annotate(txt, (lons_b.iloc[i], lats_b.iloc[i]), fontsize=8)
plt.title(f"优化前 (原始顺序)\n总路程: {dist_before:.2f} km")
plt.xlabel("经度")
plt.ylabel("纬度")
plt.legend()
plt.grid(True, linestyle='--', alpha=0.5)

# Plot 2: After
plt.subplot(1, 2, 2)
lons_a = df.iloc[path_after_indices]['Longitude']
lats_a = df.iloc[path_after_indices]['Latitude']
plt.plot(lons_a, lats_a, 'o-', color='blue', alpha=0.7, markersize=5)
plt.plot(lons_a.iloc[0], lats_a.iloc[0], 'r*', markersize=15, label='起点 (Start)')

# Add arrows to show direction for optimized route
for i in range(len(path_after_indices) - 1):
    p1 = (lons_a.iloc[i], lats_a.iloc[i])
    p2 = (lons_a.iloc[i+1], lats_a.iloc[i+1])
    plt.annotate('', xy=p2, xytext=p1, arrowprops=dict(arrowstyle="->", color='blue', lw=1.5))
    plt.text(p1[0], p1[1], str(i+1), fontsize=9, color='black', weight='bold')

plt.title(f"优化后 (智能路径)\n总路程: {dist_after:.2f} km")
plt.xlabel("经度")
plt.grid(True, linestyle='--', alpha=0.5)

plt.tight_layout()
plt.savefig('route_optimization_demo.png')

# Summary stats
savings_km = dist_before - dist_after
savings_percent = (savings_km / dist_before) * 100

savings_km, savings_percent, dist_before, dist_after