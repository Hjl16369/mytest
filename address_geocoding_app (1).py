import streamlit as st
import pandas as pd
import requests
import time
from io import BytesIO
import folium
from streamlit_folium import st_folium

# 页面配置
st.set_page_config(
    page_title="正掌讯客户地址-经纬度转换系统V2.0",
    page_icon="🗺️",
    layout="wide"
)

# 初始化 session_state
if 'result_df' not in st.session_state:
    st.session_state.result_df = None
if 'conversion_done' not in st.session_state:
    st.session_state.conversion_done = False

st.title("🗺️ 客户地址经纬度转换工具")
st.markdown("---")

# 侧边栏 - API配置
st.sidebar.header("⚙️ API配置")
map_service = st.sidebar.selectbox(
    "选择地图服务",
    ["高德地图", "百度地图"]
)

api_key = st.sidebar.text_input(
    "请输入API Key",
    type="password",
    help="请在对应地图开放平台申请API密钥"
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 📋 使用说明")
st.sidebar.info(
    """
    1. 选择地图服务（高德或百度）
    2. 输入对应的API Key
    3. 上传包含客户信息的Excel文件
    4. 点击"开始转换"按钮
    5. 下载转换后的结果文件
    
    **Excel文件必须包含以下列：**
    - 客户名称
    - 省份
    - 城市
    - 客户地址
    """
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔗 API申请链接")
st.sidebar.markdown("[高德地图开放平台](https://lbs.amap.com/)")
st.sidebar.markdown("[百度地图开放平台](https://lbsyun.baidu.com/)")

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ 百度地图API配置提示")
st.sidebar.warning("""
**重要：** 百度地图API需要正确配置：

1. 确保创建的是**服务端应用（非浏览器端）**
2. 开启**地理编码服务**
3. 配置**IP白名单**或关闭白名单验证
4. 确认配额充足

如遇到错误102（白名单），请在百度开放平台关闭IP白名单或添加当前IP。
""")


def geocode_amap(address, api_key):
    """使用高德地图API进行地理编码"""
    url = "https://restapi.amap.com/v3/geocode/geo"
    params = {
        "address": address,
        "key": api_key,
        "output": "json"
    }
    
    # 高德地图API错误码说明
    error_messages = {
        "INVALID_USER_KEY": "API Key不正确或过期",
        "INVALID_USER_IP": "IP地址不在白名单中",
        "INVALID_USER_DOMAIN": "域名不在白名单中",
        "INVALID_USER_SIGNATURE": "签名错误",
        "INVALID_USER_SCODE": "安全码错误",
        "USERKEY_PLAT_NOMATCH": "Key与绑定平台不符",
        "IP_QUERY_OVER_LIMIT": "IP访问超限",
        "NOT_SUPPORT_HTTPS": "服务不支持HTTPS",
        "INSUFFICIENT_PRIVILEGES": "权限不足",
        "USER_KEY_RECYCLED": "Key已被删除",
        "QPS_OVER_LIMIT": "访问已超出QPS配额",
        "GATEWAY_TIMEOUT": "服务响应超时",
        "INVALID_PARAMS": "请求参数非法",
        "MISSING_REQUIRED_PARAMS": "缺少必填参数",
        "ILLEGAL_REQUEST": "非法请求",
        "UNKNOWN_ERROR": "未知错误"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        result = response.json()
        
        status = result.get("status")
        info_code = result.get("infocode")
        
        if status == "1" and result.get("geocodes"):
            location = result["geocodes"][0]["location"]
            lng, lat = location.split(",")
            return float(lng), float(lat), "成功"
        else:
            info = result.get('info', '未知错误')
            error_detail = error_messages.get(info, info)
            return None, None, f"高德API错误[{info_code}]: {error_detail}"
    except requests.exceptions.Timeout:
        return None, None, "请求超时，请检查网络连接"
    except requests.exceptions.ConnectionError:
        return None, None, "网络连接失败，无法访问高德地图API"
    except Exception as e:
        return None, None, f"请求异常: {str(e)}"


def geocode_baidu(address, api_key):
    """使用百度地图API进行地理编码"""
    url = "https://api.map.baidu.com/geocoding/v3/"
    params = {
        "address": address,
        "output": "json",
        "ak": api_key
    }
    
    # 百度地图API错误码说明
    error_messages = {
        1: "服务器内部错误",
        2: "请求参数非法",
        3: "权限校验失败",
        4: "配额校验失败",
        5: "ak不存在或者非法",
        101: "服务禁用",
        102: "不通过白名单或者安全码不对",
        200: "无权限",
        211: "当前IP无访问权限",
        240: "百度地图API服务被开发者删除",
        250: "用户不存在",
        251: "用户Key不存在",
        260: "服务不存在",
        261: "服务被删除",
        301: "永久配额超限，限制访问",
        302: "天配额超限，限制访问"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        result = response.json()
        
        status = result.get("status")
        
        if status == 0:
            location = result["result"]["location"]
            return location["lng"], location["lat"], "成功"
        else:
            error_msg = error_messages.get(status, f"未知错误(状态码:{status})")
            detail = result.get('message', '')
            return None, None, f"百度API错误[{status}]: {error_msg} {detail}"
    except requests.exceptions.Timeout:
        return None, None, "请求超时，请检查网络连接"
    except requests.exceptions.ConnectionError:
        return None, None, "网络连接失败，无法访问百度地图API"
    except Exception as e:
        return None, None, f"请求异常: {str(e)}"


def process_addresses(df, api_key, map_service):
    """批量处理地址转换"""
    results = []
    total = len(df)
    
    # 创建进度条
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, row in df.iterrows():
        # 构建完整地址
        full_address = f"{row['省份']}{row['城市']}{row['客户地址']}"
        
        # 根据选择的地图服务调用相应API
        if map_service == "高德地图":
            lng, lat, status = geocode_amap(full_address, api_key)
        else:
            lng, lat, status = geocode_baidu(full_address, api_key)
        
        # 保存结果
        results.append({
            "客户名称": row["客户名称"],
            "省份": row["省份"],
            "城市": row["城市"],
            "详细地址": row["客户地址"],
            "经度": lng if lng else "",
            "纬度": lat if lat else "",
            "转换状态": status
        })
        
        # 更新进度
        progress = (idx + 1) / total
        progress_bar.progress(progress)
        status_text.text(f"正在处理: {idx + 1}/{total} - {row['客户名称']}")
        
        # 避免API请求过快，添加延迟
        time.sleep(0.2)
    
    progress_bar.empty()
    status_text.empty()
    
    return pd.DataFrame(results)


# 主界面
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📤 上传客户清单")
    uploaded_file = st.file_uploader(
        "选择Excel文件 (.xlsx 或 .xls)",
        type=["xlsx", "xls"],
        help="文件必须包含：客户名称、省份、城市、客户地址"
    )

with col2:
 #   st.subheader("📊 文件预览")

# 重置按钮
if st.session_state.conversion_done:
    if st.button("🔄 重新开始转换", type="secondary"):
        st.session_state.result_df = None
        st.session_state.conversion_done = False
        st.rerun()

# 文件上传后的处理
if uploaded_file is not None and not st.session_state.conversion_done:
    try:
        # 读取Excel文件
        df = pd.read_excel(uploaded_file)
        
        # 验证必需的列
        required_columns = ["客户名称", "省份", "城市", "客户地址"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            st.error(f"❌ 文件缺少必需的列: {', '.join(missing_columns)}")
        else:
            # 显示数据预览
            st.success(f"✅ 文件读取成功！共 {len(df)} 条客户记录")
            st.dataframe(df.head(10), use_container_width=True)
            
            st.markdown("---")
            
            # 转换按钮
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if not api_key:
                    st.warning("⚠️ 请在左侧侧边栏输入API Key")
                    start_convert = st.button("开始转换", disabled=True, use_container_width=True)
                else:
                    start_convert = st.button("🚀 开始转换", type="primary", use_container_width=True)
            
            # 执行转换
            if start_convert and api_key:
                st.markdown("---")
                st.subheader("🔄 转换进行中...")
                
                with st.spinner("正在批量转换地址..."):
                    result_df = process_addresses(df, api_key, map_service)
                    st.session_state.result_df = result_df
                    st.session_state.conversion_done = True
                
                st.rerun()
                
    except Exception as e:
        st.error(f"❌ 文件读取错误: {str(e)}")
        st.info("请确保上传的是有效的Excel文件，并包含所有必需的列。")

elif st.session_state.conversion_done and st.session_state.result_df is not None:
    # 显示转换结果
    result_df = st.session_state.result_df
    
    # 统计转换结果
    success_count = len(result_df[result_df["转换状态"] == "成功"])
    fail_count = len(result_df) - success_count
    
    # 显示统计信息
    st.subheader("📊 转换统计")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("总记录数", len(result_df))
    with col2:
        st.metric("转换成功", success_count, delta=f"{success_count/len(result_df)*100:.1f}%")
    with col3:
        st.metric("转换失败", fail_count, delta=f"-{fail_count/len(result_df)*100:.1f}%" if fail_count > 0 else "0%")
    
    st.markdown("---")
    
    # 显示转换结果
    st.subheader("📋 转换结果")
    st.dataframe(result_df, use_container_width=True)
    
    # 地图可视化 - 显示转换成功的前10个客户
    success_df = result_df[result_df["转换状态"] == "成功"].copy()
    
    if len(success_df) > 0:
        st.markdown("---")
        st.subheader("🗺️ 客户位置地图展示（前10个成功转换的客户）")
        
        # 获取前10个成功的客户，并确保经纬度不为空
        map_df = success_df.head(10).copy()
        
        # 过滤掉经纬度为空的记录
        map_df = map_df[map_df["经度"].notna() & map_df["纬度"].notna()]
        map_df = map_df[map_df["经度"] != ""]
        
        if len(map_df) > 0:
            try:
                # 确保经纬度是数字类型
                map_df["经度"] = pd.to_numeric(map_df["经度"], errors='coerce')
                map_df["纬度"] = pd.to_numeric(map_df["纬度"], errors='coerce')
                
                # 再次过滤NaN值
                map_df = map_df[map_df["经度"].notna() & map_df["纬度"].notna()]
                
                if len(map_df) == 0:
                    st.error("❌ 没有有效的经纬度数据可以显示在地图上")
                else:
                    # 计算地图中心点（所有客户的平均位置）
                    center_lat = float(map_df["纬度"].mean())
                    center_lng = float(map_df["经度"].mean())
                    
                    # 创建地图
                    m = folium.Map(
                        location=[center_lat, center_lng],
                        zoom_start=11,
                        tiles='OpenStreetMap'
                    )
                    
                    # 为每个客户添加标记
                    marker_count = 0
                    for idx, row in map_df.iterrows():
                        try:
                            lat = float(row["纬度"])
                            lng = float(row["经度"])
                            
                            # 创建弹出窗口内容
                            popup_html = f"""
                            <div style="font-family: Arial; min-width: 200px;">
                                <h4 style="color: #1f77b4; margin-bottom: 10px;">📍 {row['客户名称']}</h4>
                                <hr style="margin: 5px 0;">
                                <p><b>省份：</b>{row['省份']}</p>
                                <p><b>城市：</b>{row['城市']}</p>
                                <p><b>地址：</b>{row['详细地址']}</p>
                                <hr style="margin: 5px 0;">
                                <p><b>经度：</b>{lng:.6f}</p>
                                <p><b>纬度：</b>{lat:.6f}</p>
                            </div>
                            """
                            
                            # 添加标记点
                            folium.Marker(
                                location=[lat, lng],
                                popup=folium.Popup(popup_html, max_width=300),
                                tooltip=row["客户名称"],
                                icon=folium.Icon(color='red', icon='info-sign')
                            ).add_to(m)
                            
                            # 添加圆形区域标记
                            folium.Circle(
                                location=[lat, lng],
                                radius=500,  # 500米半径
                                color='blue',
                                fill=True,
                                fillColor='blue',
                                fillOpacity=0.1,
                                opacity=0.3
                            ).add_to(m)
                            
                            marker_count += 1
                        except Exception as e:
                            st.warning(f"⚠️ 无法为 {row['客户名称']} 添加标记：{str(e)}")
                    
                    st.success(f"✅ 成功在地图上显示 {marker_count} 个客户位置")
                    
                    # 显示地图 - 使用 key 参数防止重复渲染
                    st_folium(m, width=1200, height=600, key="customer_map")
                    
                    # 显示地图上的客户列表
                    st.markdown("---")
                    st.write("**地图上展示的客户列表：**")
                    display_cols = ["客户名称", "省份", "城市", "详细地址", "经度", "纬度"]
                    st.dataframe(
                        map_df[display_cols].reset_index(drop=True),
                        use_container_width=True
                    )
                    
                    if len(success_df) > 10:
                        st.info(f"ℹ️ 共有 {len(success_df)} 个客户转换成功，地图仅展示前10个客户位置")
            
            except Exception as e:
                st.error(f"❌ 创建地图时出错：{str(e)}")
                st.write("**错误详情：**")
                st.exception(e)
        else:
            st.warning("⚠️ 过滤后没有有效的坐标数据")
    else:
        st.warning("⚠️ 没有成功转换的客户记录，无法显示地图")
    
    st.markdown("---")
    
    # 显示失败记录详情
    if fail_count > 0:
        st.subheader("⚠️ 失败记录详情")
        failed_df = result_df[result_df["转换状态"] != "成功"]
        
        # 统计错误类型
        error_types = failed_df["转换状态"].value_counts()
        
        st.warning(f"共有 {fail_count} 条记录转换失败，请查看详细错误信息：")
        
        # 显示错误统计
        st.write("**错误类型统计：**")
        for error, count in error_types.items():
            st.write(f"- {error}: {count} 条")
        
        st.markdown("---")
        st.write("**失败记录明细：**")
        st.dataframe(
            failed_df[["客户名称", "省份", "城市", "客户地址", "转换状态"]], 
            use_container_width=True
        )
        
        # 常见错误解决方案
        st.markdown("---")
        st.info("""
        **💡 常见错误解决方案：**
        
        **百度地图API常见错误：**
        - `错误码5`: API Key不存在或非法 → 请检查API Key是否正确
        - `错误码102`: 白名单校验失败 → 需在百度地图开放平台配置IP白名单或关闭IP白名单
        - `错误码240`: 服务被删除 → 请在百度地图开放平台检查服务是否正常
        - `错误码302`: 天配额超限 → 当天配额已用完，请明天再试或升级配额
        
        **高德地图API常见错误：**
        - `INVALID_USER_KEY`: Key无效 → 请检查API Key是否正确
        - `INVALID_USER_IP`: IP不在白名单 → 需在高德开放平台配置IP白名单
        - `QPS_OVER_LIMIT`: 访问频率超限 → 请降低请求频率或升级配额
        
        **地址格式问题：**
        - 地址过于模糊或不完整
        - 地址中包含特殊字符
        - 省份、城市信息不准确
        """)
    
    # 准备下载文件
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        result_df.to_excel(writer, index=False, sheet_name='客户坐标')
    output.seek(0)
    
    # 下载按钮
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.download_button(
            label="📥 下载转换结果",
            data=output,
            file_name=f"客户坐标_{time.strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True
        )
    
    if fail_count == 0:
        st.success("✅ 全部转换成功！请点击上方按钮下载结果文件。")
    else:
        st.warning(f"⚠️ 转换完成，但有 {fail_count} 条记录失败。请查看上方失败详情并下载结果文件。")

else:
    st.info("👆 请上传包含客户信息的Excel文件开始转换")
    
    # 显示示例数据格式
    st.markdown("---")
    st.subheader("📄 Excel文件格式示例")
    sample_df = pd.DataFrame({
        "客户名称": ["示例公司A", "示例公司B", "示例公司C"],
        "省份": ["北京市", "广东省", "上海市"],
        "城市": ["北京市", "深圳市", "上海市"],
        "详细地址": ["朝阳区建国路1号", "南山区科技园", "浦东新区陆家嘴"]
    })
    st.dataframe(sample_df, use_container_width=True)

# 页脚
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666; padding: 20px;'>
        <p>💡 提示：转换过程中请保持网络连接稳定 | 建议分批处理大量数据</p>
    </div>
    """,
    unsafe_allow_html=True
)