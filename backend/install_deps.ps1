# 分批安装 Python 依赖，避免网络超时
# 使用方法：在 backend 目录下运行 .\install_deps.ps1

Write-Host "开始安装 Python 依赖..." -ForegroundColor Green

# 激活虚拟环境
.\.venv\Scripts\Activate.ps1

# 升级 pip
Write-Host "`n[1/5] 升级 pip..." -ForegroundColor Cyan
python -m pip install --upgrade pip

# 第一批：核心 Web 框架
Write-Host "`n[2/5] 安装 Web 框架..." -ForegroundColor Cyan
pip install --default-timeout=100 fastapi==0.121.0 uvicorn[standard]==0.38.0 python-multipart==0.0.20

# 第二批：数据库相关
Write-Host "`n[3/5] 安装数据库驱动..." -ForegroundColor Cyan
pip install --default-timeout=100 sqlalchemy==2.0.25 asyncpg==0.29.0 psycopg2-binary==2.9.9

# 第三批：数据验证和 AI 服务
Write-Host "`n[4/5] 安装 AI 服务..." -ForegroundColor Cyan
pip install --default-timeout=100 pydantic==2.12.4 pydantic-settings==2.11.0 openai==2.7.0 anthropic==0.72.0

# 第四批：工具库
Write-Host "`n[5/5] 安装工具库..." -ForegroundColor Cyan
pip install --default-timeout=100 httpx==0.28.1 python-dotenv==1.0.0 mcp==1.21.0

# 第五批：Embedding 相关（最大的包，单独安装）
Write-Host "`n[6/7] 安装 NumPy..." -ForegroundColor Cyan
pip install --default-timeout=100 numpy==1.26.4

Write-Host "`n[7/7] 安装 ChromaDB（较大，请耐心等待）..." -ForegroundColor Cyan
pip install --default-timeout=200 chromadb==1.3.2

Write-Host "`n[8/8] 安装 Transformers..." -ForegroundColor Cyan
pip install --default-timeout=200 transformers==4.57.1 sentence-transformers==5.1.2

Write-Host "`n✅ 所有依赖安装完成！" -ForegroundColor Green
Write-Host "现在可以运行：python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload" -ForegroundColor Yellow

