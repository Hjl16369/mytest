import streamlit as st
import pandas as pd
import os
import zipfile
from io import BytesIO
import shutil

st.set_page_config(page_title="工作日报统计工具", layout="centered")
st.title("📊 工作日报周统计工具")

st.markdown("""
该工具用于统计**开发与测试人员**一周的工作量。  
请上传一个包含多个人员日报的 **ZIP 压缩包**（每个日报为 `.xlsx` 文件）。  
""")

# === Step 1: 上传压缩包 ===
uploaded_file = st.file_uploader("📂 上传工作日报压缩包（ZIP 格式）", type=["zip"])

if uploaded_file is not None:
    # 临时解压目录
    temp_dir = "temp_daily_reports"
    
    # 清理旧的临时目录
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir, exist_ok=True)

    # 解压文件
    try:
        with zipfile.ZipFile(uploaded_file, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        st.success("✅ 压缩包已上传并解压成功！")
    except Exception as e:
        st.error(f"❌ 解压失败：{e}")
        st.stop()

    # === Step 2: 点击开始处理 ===
    if st.button("🚀 开始处理日报"):
        all_records = []
        debug_info = []

        def read_daily_report(file_path: str):
            """读取单个日报文件（xlsx），返回 DataFrame"""
            file_name = os.path.basename(file_path)
            
            # 跳过临时文件和隐藏文件
            if file_name.startswith('~$') or file_name.startswith('.'):
                return pd.DataFrame()
            
            try:
                excel_file = pd.ExcelFile(file_path)
                file_records = []
                
                for sheet in excel_file.sheet_names:
                    try:
                        # 读取整个工作表，不指定header
                        df_full = pd.read_excel(file_path, sheet_name=sheet, header=None)
                        
                        # 跳过空表
                        if df_full.empty or len(df_full) < 5:
                            st.warning(f"⚠️ {file_name} 的 sheet《{sheet}》数据不足，已跳过。")
                            continue
                        
                        # 读取人员信息（B2单元格，索引为[1,1]）
                        try:
                            person_name = str(df_full.iloc[1, 1]).strip()
                            if pd.isna(df_full.iloc[1, 1]) or person_name == '' or person_name == 'nan':
                                person_name = file_name.replace(".xlsx", "").replace(".xls", "")
                                st.info(f"ℹ️ {file_name} 的 sheet《{sheet}》B2单元格为空，使用文件名作为人员名")
                        except:
                            person_name = file_name.replace(".xlsx", "").replace(".xls", "")
                            st.warning(f"⚠️ {file_name} 的 sheet《{sheet}》无法读取B2单元格，使用文件名作为人员名")
                        
                        # 读取日期信息（B3单元格，索引为[2,1]）
                        try:
                            date_value = df_full.iloc[2, 1]
                            if pd.isna(date_value) or str(date_value).strip() == '':
                                date_str = sheet  # 使用sheet名称作为日期
                                st.info(f"ℹ️ {file_name} 的 sheet《{sheet}》B3单元格为空，使用sheet名称作为日期")
                            else:
                                # 如果是日期类型，转换为字符串
                                if isinstance(date_value, pd.Timestamp):
                                    date_str = date_value.strftime('%Y-%m-%d')
                                else:
                                    date_str = str(date_value).strip()
                        except:
                            date_str = sheet
                            st.warning(f"⚠️ {file_name} 的 sheet《{sheet}》无法读取B3单元格，使用sheet名称作为日期")
                        
                        # 从第5行开始读取工作内容（索引为4开始，即第5行）
                        # 列为A、B、C、D（索引0、1、2、3）
                        df_work = pd.read_excel(file_path, sheet_name=sheet, header=4, usecols=[0, 1, 2, 3])
                        
                        # 设置列名
                        df_work.columns = ["项目名称", "模块名称", "工作内容", "完成状态"]
                        
                        # 删除所有列都为空的行
                        df_work = df_work.dropna(how='all')
                        
                        # 删除项目名称和模块名称都为空的行
                        df_work = df_work[~(df_work["项目名称"].isna() & df_work["模块名称"].isna())]
                        
                        if df_work.empty:
                            st.warning(f"⚠️ {file_name} 的 sheet《{sheet}》没有有效的工作记录，已跳过。")
                            continue
                        
                        # 添加人员和日期信息
                        df_work["人员"] = person_name
                        df_work["日期"] = date_str
                        
                        file_records.append(df_work)
                        
                        # 调试信息
                        debug_info.append({
                            "文件": file_name,
                            "Sheet": sheet,
                            "人员": person_name,
                            "日期": date_str,
                            "记录数": len(df_work),
                            "状态": "✅ 成功"
                        })
                        
                    except Exception as e:
                        debug_info.append({
                            "文件": file_name,
                            "Sheet": sheet,
                            "人员": "-",
                            "日期": "-",
                            "记录数": 0,
                            "状态": f"❌ 失败: {str(e)}"
                        })
                        st.warning(f"⚠️ 读取 {file_name} 的 sheet《{sheet}》时出错：{e}")
                
                if file_records:
                    return pd.concat(file_records, ignore_index=True)
                    
            except Exception as e:
                st.error(f"❌ 无法读取文件 {file_name}：{e}")
                debug_info.append({
                    "文件": file_name,
                    "Sheet": "-",
                    "人员": "-",
                    "日期": "-",
                    "记录数": 0,
                    "状态": f"❌ 文件错误: {str(e)}"
                })
                
            return pd.DataFrame()

        # === Step 3: 扫描所有 .xlsx 文件 ===
        st.info("📂 正在读取日报文件，请稍候...")
        
        xlsx_files = []
        for root, _, files in os.walk(temp_dir):
            for f in files:
                if f.lower().endswith((".xlsx", ".xls")) and not f.startswith('~$') and not f.startswith('.'):
                    xlsx_files.append(os.path.join(root, f))
        
        if not xlsx_files:
            st.error("❌ 压缩包中没有找到 Excel 文件（.xlsx 或 .xls）")
            st.stop()
        
        st.info(f"找到 {len(xlsx_files)} 个 Excel 文件")
        
        # 读取所有文件
        progress_bar = st.progress(0)
        for idx, fpath in enumerate(xlsx_files):
            df = read_daily_report(fpath)
            if not df.empty:
                all_records.append(df)
            progress_bar.progress((idx + 1) / len(xlsx_files))

        # 显示调试信息
        if debug_info:
            with st.expander("🔍 查看文件读取详情（调试信息）", expanded=True):
                debug_df = pd.DataFrame(debug_info)
                st.dataframe(debug_df, use_container_width=True)

        if not all_records:
            st.error("❌ 未读取到任何有效日报，请检查表格格式。")
            st.error("💡 请确保：")
            st.error("   - B2单元格：人员姓名")
            st.error("   - B3单元格：日期")
            st.error("   - 第5行开始：A列=项目名称、B列=模块名称、C列=工作内容、D列=完成状态")
            st.stop()

        all_data = pd.concat(all_records, ignore_index=True)
        st.success(f"✅ 成功读取 {len(all_data)} 条工作记录，涉及 {all_data['人员'].nunique()} 名人员")

        # 显示原始数据预览
        with st.expander("📋 查看原始数据", expanded=False):
            st.dataframe(all_data, use_container_width=True)

        # === Step 4: 区分开发 / 测试人员 ===
        tester_names = ["杨妮", "测试"]  # 可在此添加测试人员名单
        all_data["人员类型"] = all_data["人员"].apply(
            lambda x: "测试" if any(t in str(x) for t in tester_names) else "开发"
        )

        # === Step 5: 开发统计 ===
        dev_data = all_data[all_data["人员类型"] == "开发"]
        
        if not dev_data.empty:
            dev_summary = (
                dev_data.groupby(["人员", "模块名称"])
                .size()
                .reset_index(name="开发次数")
            )
            dev_module_count = (
                dev_summary.groupby("人员")["模块名称"].nunique().reset_index(name="模块数量")
            )
            dev_output = pd.merge(dev_module_count, dev_summary, on="人员", how="left")
            
            # 按人员和开发次数排序
            dev_output = dev_output.sort_values(by=["人员", "开发次数"], ascending=[True, False])
        else:
            dev_output = pd.DataFrame(columns=["人员", "模块数量", "模块名称", "开发次数"])
            st.info("ℹ️ 未找到开发人员数据")

        # === Step 6: 测试统计 ===
        test_data = all_data[all_data["人员类型"] == "测试"]
        
        if not test_data.empty:
            test_summary = (
                test_data.groupby(["人员", "模块名称"])
                .size()
                .reset_index(name="测试次数")
            )
            test_module_count = (
                test_summary.groupby("人员")["模块名称"].nunique().reset_index(name="模块数量")
            )
            test_output = pd.merge(test_module_count, test_summary, on="人员", how="left")
            
            # 按人员和测试次数排序
            test_output = test_output.sort_values(by=["人员", "测试次数"], ascending=[True, False])
        else:
            test_output = pd.DataFrame(columns=["人员", "模块数量", "模块名称", "测试次数"])
            st.info("ℹ️ 未找到测试人员数据")

        # 显示预览
        st.subheader("📊 统计结果预览")
        
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**开发人员统计** ({len(dev_output)} 条记录)")
            if not dev_output.empty:
                st.dataframe(dev_output, use_container_width=True)
            else:
                st.info("无数据")
        with col2:
            st.write(f"**测试人员统计** ({len(test_output)} 条记录)")
            if not test_output.empty:
                st.dataframe(test_output, use_container_width=True)
            else:
                st.info("无数据")

        # === Step 7: 输出文件 ===
        dev_buffer = BytesIO()
        test_buffer = BytesIO()
        
        with pd.ExcelWriter(dev_buffer, engine='openpyxl') as writer:
            dev_output.to_excel(writer, index=False, sheet_name='开发统计')
        
        with pd.ExcelWriter(test_buffer, engine='openpyxl') as writer:
            test_output.to_excel(writer, index=False, sheet_name='测试统计')
        
        dev_buffer.seek(0)
        test_buffer.seek(0)

        st.success("🎉 日报处理完成！请下载统计结果👇")

        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="⬇️ 下载开发人员统计",
                data=dev_buffer,
                file_name="开发人员工作量统计.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        with col2:
            st.download_button(
                label="⬇️ 下载测试人员统计",
                data=test_buffer,
                file_name="测试人员工作量统计.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        # 清理临时文件
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
