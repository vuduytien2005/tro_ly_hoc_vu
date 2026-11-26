# Đưa hệ thống về trạng thái SẠCH để demo lại từ đầu (chạy giữa các lần demo).
#   .\scripts\reset_demo.ps1            # đầy đủ
#   .\scripts\reset_demo.ps1 -ChiQlsv   # chỉ dữ liệu QLSV (đăng ký, đơn từ...)
#
# Đầy đủ gồm:
#   1. tlhv_qlsv      : chạy lại database/01_qlsv_schema.sql + 03_qlsv_seed.sql + 11_bo_sung_du_lieu_demo.sql
#                       + 12_du_lieu_mo_phong_hunre.sql.
#   2. tlhv_assistant : database/90_reset_demo_assistant.sql — xóa hội thoại, nhật ký, thẻ xác nhận,
#                       đánh giá; bật lại MCP server + công cụ theo seed (sau demo 7). GIỮ văn bản đã
#                       lập chỉ mục và tài khoản.
#   3. seed_users.py --reset-password: tài khoản demo về mật khẩu công khai trong README.
# KHÔNG đụng CSDL QLSV cũ của máy. Các service có thể đang chạy (không cần tắt); trên web bấm
# tải lại trang (F5) sau khi reset.
# Cấu hình máy chủ lấy từ .env (DB_SERVER, DB_USER, DB_PASSWORD); DB_USER trống = Windows Authentication.
param(
    [switch]$ChiQlsv,
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"
$Backend = Split-Path -Parent $PSScriptRoot
$Root = Split-Path -Parent $Backend
$EnvFile = Join-Path $Root ".env"
$Python = Join-Path $Backend ".venv\Scripts\python.exe"

$cfg = @{
    DB_SERVER = "localhost\SQLEXPRESS01"; DB_USER = ""; DB_PASSWORD = ""
    DB_QLSV = "tlhv_qlsv"; DB_ASSISTANT = "tlhv_assistant"
}
if (Test-Path $EnvFile) {
    foreach ($line in Get-Content $EnvFile -Encoding UTF8) {
        if ($line -match '^\s*(DB_SERVER|DB_USER|DB_PASSWORD|DB_QLSV|DB_ASSISTANT)\s*=\s*(.*?)\s*$') {
            $cfg[$Matches[1]] = $Matches[2].Trim('"').Trim("'")
        }
    }
}
# Các file SQL ghi cứng tên CSDL -> chỉ chạy khi .env dùng đúng tên này (tránh xóa nhầm CSDL khác)
if ($cfg.DB_QLSV -ne "tlhv_qlsv" -or $cfg.DB_ASSISTANT -ne "tlhv_assistant") {
    Write-Error "Script chỉ reset tlhv_qlsv / tlhv_assistant (.env đang đặt '$($cfg.DB_QLSV)' / '$($cfg.DB_ASSISTANT)')."
}

$sqlcmd = (Get-Command sqlcmd -ErrorAction SilentlyContinue).Source
if (-not $sqlcmd) {
    $sqlcmd = Get-ChildItem "C:\Program Files\Microsoft SQL Server\Client SDK\ODBC\*\Tools\Binn\sqlcmd.exe" -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $sqlcmd) { Write-Error "Không tìm thấy sqlcmd. Cài 'sqlcmd' hoặc chạy các file SQL bằng SSMS." }

# Bọc @(...): "if" trả MỘT phần tử thì PowerShell mở mảng thành chuỗi, splat chuỗi sẽ sai tham số
$auth = @(if ($cfg.DB_USER) { "-U", $cfg.DB_USER, "-P", $cfg.DB_PASSWORD } else { "-E" })

function Invoke-SqlFile([string]$Name) {
    $file = Join-Path $Root "database\$Name"
    # -b: dừng khi lỗi; -C: tin chứng chỉ tự ký; -f 65001: đọc file UTF-8 (giữ dấu tiếng Việt)
    $out = & $sqlcmd -S $cfg.DB_SERVER @auth -C -b -f 65001 -i $file 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Output $out
        Write-Error "Lỗi khi chạy $Name."
    }
    return $out
}

function Write-Step([string]$Text) {
    if (-not $Quiet) { Write-Host $Text -ForegroundColor Cyan }
}

Write-Step "1/3 Dữ liệu QLSV (tlhv_qlsv)..."
Invoke-SqlFile "01_qlsv_schema.sql" | Out-Null
Invoke-SqlFile "03_qlsv_seed.sql" | Out-Null
Invoke-SqlFile "11_bo_sung_du_lieu_demo.sql" | Out-Null
Invoke-SqlFile "12_du_lieu_mo_phong_hunre.sql" | Out-Null

if (-not $ChiQlsv) {
    Write-Step "2/3 Hội thoại, nhật ký, cấu hình công cụ (tlhv_assistant)..."
    $summary = Invoke-SqlFile "90_reset_demo_assistant.sql"
    if (-not $Quiet) { $summary | Where-Object { $_ -match '\d' } | Select-Object -Last 1 | ForEach-Object { Write-Host "    van_ban_da_lap_chi_muc / cong_cu_dang_bat: $($_.Trim())" } }

    Write-Step "3/3 Tài khoản demo..."
    if (-not (Test-Path $Python)) { Write-Error "Chưa có venv: $Python (xem README)." }
    Push-Location $Backend
    try {
        $out = & $Python scripts\seed_users.py --reset-password 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Output $out
            Write-Error "seed_users.py lỗi."
        }
    } finally {
        Pop-Location
    }
}

if (-not $Quiet) {
    $what = if ($ChiQlsv) { "dữ liệu QLSV" } else { "toàn bộ dữ liệu demo" }
    Write-Host "Đã reset $what về trạng thái ban đầu." -ForegroundColor Green
}
