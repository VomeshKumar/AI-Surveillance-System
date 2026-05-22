param (
    [string]$NodeId = "node_001",
    [string]$GitRepo = "https://github.com/your-org/ai-surveillance-engine.git",
    [string]$TargetDir = "D:\ai-surveillance-engine"
)

Write-Host "Deploying AI Surveillance Node: $NodeId to $TargetDir"

if (Test-Path $TargetDir) {
    Write-Host "Directory exists. Pulling latest..."
    Set-Location $TargetDir
    git pull
} else {
    Write-Host "Cloning repo..."
    git clone $GitRepo $TargetDir
    Set-Location $TargetDir
}

Write-Host "Setting up Python virtual environment..."
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt

Write-Host "Setting up Env..."
Copy-Item .env.example .env -ErrorAction SilentlyContinue
(Get-Content .env) -replace "NODE_ID=.*", "NODE_ID=$NodeId" | Set-Content .env

Write-Host "Registering NSSM services..."
.\.venv\Scripts\python app/services/nssm_service.py ai_detection_worker "$TargetDir\app\workers\detection_worker.py"
.\.venv\Scripts\python app/services/nssm_service.py ai_fastapi "$TargetDir\.venv\Scripts\uvicorn.exe"

Write-Host "Deployment complete."
