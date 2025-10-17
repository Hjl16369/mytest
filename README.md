# 📊 OCR表格识别转Excel工具

自动识别图片中的表格数据，一键导出为Excel文件。

## 🚀 功能特性

- ✅ 支持 JPG、PNG、PDF 格式
- ✅ 中英文混合识别
- ✅ 智能表格解析
- ✅ 导出 Excel/CSV 格式
- ✅ 完全免费，云端运行

## 📖 使用方法

1. 上传图片文件
2. 点击"开始识别"
3. 查看识别结果
4. 下载生成的Excel文件

## 🔧 本地运行
```bash
# 安装依赖
pip install -r requirements.txt

# Linux 系统还需要
sudo apt-get install tesseract-ocr tesseract-ocr-chi-sim poppler-utils

# 运行应用
streamlit run app.py
```

## 📝 技术栈

- Streamlit - Web框架
- Tesseract OCR - 文字识别引擎
- OpenCV - 图像处理
- Pandas - 数据处理
- Openpyxl - Excel生成

## 📄 License

MIT License