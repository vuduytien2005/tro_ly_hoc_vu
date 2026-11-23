# Chạy tất cả service backend, mỗi service một cửa sổ PowerShell riêng.
#   .\scripts\run_all.ps1          # khởi động
#   .\scripts\run_all.ps1 -Stop    # tắt tất cả service do script này mở
# Service chưa có file (vd quy_che, assistant_api ở giai đoạn sau) sẽ được bỏ qua.
param(
    [switch]$Stop
)

$ErrorActionPreference = "Stop"
$Backend = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Backend ".venv\Scripts\python.exe"

# Thứ tự: qlsv_api trước (MCP server gọi vào nó), assistant_api sau cùng.
$Services = @(
    @{ Name = "qlsv_api";      Module = "src.qlsv_api.main";        File = "src\qlsv_api\main.py";        Port = 8001 },
    @{ Name = "mcp dao_tao";   Module = "src.mcp_servers.dao_tao";   File = "src\mcp_servers\dao_tao.py";   Port = 9101 },
    @{ Name = "mcp ctsv";      Module = "src.mcp_servers.ctsv";      File = "src\mcp_servers\ctsv.py";      Port = 9102 },
    @{ Name = "mcp tai_chinh"; Module = "src.mcp_servers.tai_chinh"; File = "src\mcp_servers\tai_chinh.py"; Port = 9103 },
    @{ Name = "mcp quy_che";   Module = "src.mcp_servers.quy_che";   File = "src\mcp_servers\quy_che.py";   Port = 9104 },
    @{ Name = "mcp thu_vien";  Module = "src.mcp_servers.thu_vien";  File = "src\mcp_servers\thu_vien.py";  Port = 9105 },
    @{ Name = "assistant_api"; Module = "src.assistant_api.main";    File = "src\assistant_api\main.py";    Port = 8000 }
)

if ($Stop) {
    $pattern = ($Services | ForEach-Object { [regex]::Escape($_.Module) }) -join "|"
    $procs = Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
        Where-Object { $_.CommandLine -match "-m ($pattern)(\s|$)" }
    foreach ($p in $procs) {
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Write-Host "Đã tắt $(@($procs).Count) tiến trình service." -ForegroundColor Yellow
    return
}

if (-not (Test-Path $Python)) {
    Write-Error "Chưa có môi trường ảo: $Python. Chạy: python -m venv .venv; pip install -e "".[dev]"""
}
if (-not (Test-Path (Join-Path (Split-Path -Parent $Backend) ".env"))) {
    Write-Warning "Chưa có file .env ở thư mục gốc dự án (sao chép từ .env.example)."
}

# Dùng PowerShell 7 nếu có, không thì Windows PowerShell 5.1.
$Shell = if (Get-Command pwsh -ErrorAction SilentlyContinue) { "pwsh" } else { "powershell" }

foreach ($s in $Services) {
    if (-not (Test-Path (Join-Path $Backend $s.File))) {
        Write-Host ("  - {0,-14} bỏ qua (chưa có {1})" -f $s.Name, $s.File) -ForegroundColor DarkGray
        continue
    }
    $title = "$($s.Name) :$($s.Port)"
    $command = "`$Host.UI.RawUI.WindowTitle = '$title'; Set-Location '$Backend'; & '$Python' -m $($s.Module)"
    Start-Process $Shell -ArgumentList "-NoExit", "-NoProfile", "-Command", $command | Out-Null
    Write-Host ("  + {0,-14} http://127.0.0.1:{1}" -f $s.Name, $s.Port) -ForegroundColor Green
    if ($s.Name -eq "qlsv_api") { Start-Sleep -Seconds 2 }
}

Write-Host ""
Write-Host "MCP endpoint: http://127.0.0.1:<cổng>/mcp (OAuth: token JWT do assistant_api cấp; MCP_AUTH_MODE=token -> Bearer <INTERNAL_API_TOKEN>)"
Write-Host "Tắt tất cả: .\scripts\run_all.ps1 -Stop"
