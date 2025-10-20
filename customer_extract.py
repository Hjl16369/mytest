<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>客户名录提取工具</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }

        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            padding: 40px;
            max-width: 600px;
            width: 100%;
        }

        h1 {
            color: #333;
            text-align: center;
            margin-bottom: 10px;
            font-size: 28px;
        }

        .subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }

        .upload-area {
            border: 3px dashed #667eea;
            border-radius: 15px;
            padding: 40px;
            text-align: center;
            cursor: pointer;
            transition: all 0.3s;
            background: #f8f9ff;
        }

        .upload-area:hover {
            border-color: #764ba2;
            background: #f0f2ff;
        }

        .upload-area.dragover {
            border-color: #764ba2;
            background: #e8ebff;
            transform: scale(1.02);
        }

        .upload-icon {
            font-size: 60px;
            margin-bottom: 20px;
        }

        .upload-text {
            color: #667eea;
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 10px;
        }

        .upload-hint {
            color: #999;
            font-size: 14px;
        }

        input[type="file"] {
            display: none;
        }

        .progress-container {
            display: none;
            margin-top: 30px;
        }

        .progress-bar {
            width: 100%;
            height: 30px;
            background: #e0e0e0;
            border-radius: 15px;
            overflow: hidden;
            margin-bottom: 15px;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            width: 0%;
            transition: width 0.3s;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 14px;
        }

        .status {
            text-align: center;
            color: #666;
            font-size: 14px;
            min-height: 20px;
        }

        .results {
            display: none;
            margin-top: 30px;
            padding: 20px;
            background: #f8f9ff;
            border-radius: 10px;
        }

        .results h3 {
            color: #333;
            margin-bottom: 15px;
            font-size: 18px;
        }

        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }

        .stat-item {
            background: white;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
        }

        .stat-label {
            color: #999;
            font-size: 12px;
            margin-bottom: 5px;
        }

        .stat-value {
            color: #667eea;
            font-size: 24px;
            font-weight: bold;
        }

        .download-btn {
            width: 100%;
            padding: 15px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s;
        }

        .download-btn:hover {
            transform: scale(1.05);
        }

        .download-btn:active {
            transform: scale(0.98);
        }

        .reset-btn {
            width: 100%;
            padding: 12px;
            background: white;
            color: #667eea;
            border: 2px solid #667eea;
            border-radius: 10px;
            font-size: 14px;
            font-weight: bold;
            cursor: pointer;
            margin-top: 10px;
            transition: all 0.2s;
        }

        .reset-btn:hover {
            background: #667eea;
            color: white;
        }

        .error {
            color: #e74c3c;
            background: #ffe8e8;
            padding: 15px;
            border-radius: 8px;
            margin-top: 20px;
            text-align: center;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 客户名录提取工具</h1>
        <p class="subtitle">上传包含Excel文件的ZIP压缩包，自动提取并去重客户信息</p>

        <div class="upload-area" id="uploadArea">
            <div class="upload-icon">📦</div>
            <div class="upload-text">点击或拖拽上传ZIP文件</div>
            <div class="upload-hint">支持包含多个.xlsx文件的压缩包</div>
            <input type="file" id="fileInput" accept=".zip" />
        </div>

        <div class="progress-container" id="progressContainer">
            <div class="progress-bar">
                <div class="progress-fill" id="progressFill">0%</div>
            </div>
            <div class="status" id="status"></div>
        </div>

        <div class="results" id="results">
            <h3>✅ 提取完成！</h3>
            <div class="stats">
                <div class="stat-item">
                    <div class="stat-label">客户名称</div>
                    <div class="stat-value" id="customerCount">0</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">售达客户</div>
                    <div class="stat-value" id="soldToCount">0</div>
                </div>
                <div class="stat-item">
                    <div class="stat-label">商业代理</div>
                    <div class="stat-value" id="agentCount">0</div>
                </div>
            </div>
            <button class="download-btn" id="downloadBtn">⬇️ 下载客户名录</button>
            <button class="reset-btn" id="resetBtn">🔄 重新上传</button>
        </div>
    </div>

    <script>
        const uploadArea = document.getElementById('uploadArea');
        const fileInput = document.getElementById('fileInput');
        const progressContainer = document.getElementById('progressContainer');
        const progressFill = document.getElementById('progressFill');
        const status = document.getElementById('status');
        const results = document.getElementById('results');
        const downloadBtn = document.getElementById('downloadBtn');
        const resetBtn = document.getElementById('resetBtn');

        let extractedData = null;

        // 点击上传区域
        uploadArea.addEventListener('click', () => fileInput.click());

        // 拖拽上传
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('dragover');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('dragover');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleFile(files[0]);
            }
        });

        // 文件选择
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleFile(e.target.files[0]);
            }
        });

        // 处理文件
        async function handleFile(file) {
            if (!file.name.endsWith('.zip')) {
                showError('请上传ZIP格式的压缩包文件！');
                return;
            }

            uploadArea.style.display = 'none';
            progressContainer.style.display = 'block';
            results.style.display = 'none';

            try {
                updateProgress(10, '正在读取ZIP文件...');
                
                const zip = await JSZip.loadAsync(file);
                const xlsxFiles = Object.keys(zip.files).filter(name => 
                    name.endsWith('.xlsx') && !name.startsWith('__MACOSX') && !name.includes('~$')
                );

                if (xlsxFiles.length === 0) {
                    throw new Error('ZIP文件中没有找到.xlsx文件！');
                }

                updateProgress(30, `找到 ${xlsxFiles.length} 个Excel文件，正在处理...`);

                const allCustomers = new Set();
                const allSoldTo = new Set();
                const allAgents = new Set();

                for (let i = 0; i < xlsxFiles.length; i++) {
                    const fileName = xlsxFiles[i];
                    updateProgress(30 + (i / xlsxFiles.length) * 50, `处理: ${fileName.split('/').pop()}`);

                    const fileData = await zip.files[fileName].async('arraybuffer');
                    const workbook = XLSX.read(fileData, { type: 'array' });

                    workbook.SheetNames.forEach(sheetName => {
                        const worksheet = workbook.Sheets[sheetName];
                        const jsonData = XLSX.utils.sheet_to_json(worksheet, { defval: '' });

                        jsonData.forEach(row => {
                            const findValue = (possibleKeys) => {
                                for (let key of possibleKeys) {
                                    if (row[key] && String(row[key]).trim()) {
                                        return String(row[key]).trim();
                                    }
                                }
                                return null;
                            };

                            const customer = findValue(['客户名称', '客户', 'Customer Name']);
                            const soldTo = findValue(['售达客户名称', '售达客户', 'Sold-to Customer']);
                            const agent = findValue(['商业代理', '代理', 'Agent', '商业代理商']);

                            if (customer) allCustomers.add(customer);
                            if (soldTo) allSoldTo.add(soldTo);
                            if (agent) allAgents.add(agent);
                        });
                    });
                }

                updateProgress(90, '正在生成客户名录...');

                extractedData = {
                    customers: Array.from(allCustomers).sort(),
                    soldTo: Array.from(allSoldTo).sort(),
                    agents: Array.from(allAgents).sort()
                };

                updateProgress(100, '完成！');
                
                setTimeout(() => {
                    progressContainer.style.display = 'none';
                    showResults();
                }, 500);

            } catch (error) {
                console.error(error);
                showError('处理文件时出错：' + error.message);
            }
        }

        function updateProgress(percent, message) {
            progressFill.style.width = percent + '%';
            progressFill.textContent = Math.round(percent) + '%';
            status.textContent = message;
        }

        function showResults() {
            document.getElementById('customerCount').textContent = extractedData.customers.length;
            document.getElementById('soldToCount').textContent = extractedData.soldTo.length;
            document.getElementById('agentCount').textContent = extractedData.agents.length;
            results.style.display = 'block';
        }

        function showError(message) {
            progressContainer.style.display = 'none';
            uploadArea.style.display = 'block';
            const errorDiv = document.createElement('div');
            errorDiv.className = 'error';
            errorDiv.textContent = message;
            uploadArea.parentElement.appendChild(errorDiv);
            setTimeout(() => errorDiv.remove(), 5000);
        }

        // 下载按钮
        downloadBtn.addEventListener('click', () => {
            const wb = XLSX.utils.book_new();
            
            const maxLen = Math.max(
                extractedData.customers.length,
                extractedData.soldTo.length,
                extractedData.agents.length
            );

            const data = [];
            for (let i = 0; i < maxLen; i++) {
                data.push({
                    '客户名称': extractedData.customers[i] || '',
                    '售达客户名称': extractedData.soldTo[i] || '',
                    '商业代理': extractedData.agents[i] || ''
                });
            }

            const ws = XLSX.utils.json_to_sheet(data);
            
            // 设置列宽
            ws['!cols'] = [
                { wch: 30 },
                { wch: 30 },
                { wch: 30 }
            ];

            XLSX.utils.book_append_sheet(wb, ws, '客户名录');
            
            const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
            XLSX.writeFile(wb, `客户名录_${timestamp}.xlsx`);
        });

        // 重置按钮
        resetBtn.addEventListener('click', () => {
            results.style.display = 'none';
            uploadArea.style.display = 'block';
            fileInput.value = '';
            extractedData = null;
        });
    </script>
</body>
</html>