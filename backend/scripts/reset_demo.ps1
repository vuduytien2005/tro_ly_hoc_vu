# Đưa CSDL tlhv_qlsv về dữ liệu mẫu ban đầu (chạy lại database/01_qlsv_schema.sql + 03_qlsv_seed.sql).
# Dùng trước mỗi lượt thực nghiệm TN3/TN4 vì kịch bản ghi (đăng ký, nộp đơn) làm thay đổi dữ liệu.
# CHỈ đụng tlhv_qlsv — không đụng tlhv_assistant, không đụng CSDL QLSV cũ.
#   .\scripts\reset_demo.ps1
# Cấu hình máy chủ lấy từ .env (DB_SERVER, DB_USER, DB_PASSWORD); DB_USER trống = Windows Authentication.
param(
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$EnvFile = Join-Path $Root ".env"

$cfg = @{ DB_SERVER = "localhost\SQLEXPRESS01"; DB_USER = ""; DB_PASSWORD = ""; DB_QLSV = "tlhv_qlsv" }
if (Test-Path $EnvFile) {
    foreach ($line in Get-Content $EnvFile -Encoding UTF8) {
        if ($line -match '^\s*(DB_SERVER|DB_USER|DB_PASSWORD|DB_QLSV)\s*=\s*(.*?)\s*$') {
            $cfg[$Matches[1]] = $Matches[2].Trim('"').Trim("'")
        }
    }
}
if ($cfg.DB_QLSV -ne "tlhv_qlsv") {
    Write-Error "DB_QLSV = '$($cfg.DB_QLSV)': script chỉ reset tlhv_qlsv, dừng để tránh xóa nhầm CSDL."
}

$sqlcmd = (Get-Command sqlcmd -ErrorAction SilentlyContinue).Source
if (-not $sqlcmd) {
    $sqlcmd = Get-ChildItem "C:\Program Files\Microsoft SQL Server\Client SDK\ODBC\*\Tools\Binn\sqlcmd.exe" -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $sqlcmd) { Write-Error "Không tìm thấy sqlcmd. Cài 'sqlcmd' hoặc chạy 2 file SQL bằng SSMS." }

# Bọc @(...): "if" trả MỘT phần tử thì PowerShell mở mảng thành chuỗi, splat chuỗi sẽ sai tham số
$auth = @(if ($cfg.DB_USER) { "-U", $cfg.DB_USER, "-P", $cfg.DB_PASSWORD } else { "-E" })
$files = @("01_qlsv_schema.sql", "03_qlsv_seed.sql") | ForEach-Object { Join-Path $Root "database\$_" }

foreach ($file in $files) {
    # -b: dừng khi lỗi; -C: tin chứng chỉ tự ký; -f 65001: đọc file UTF-8 (giữ dấu tiếng Việt)
    $out = & $sqlcmd -S $cfg.DB_SERVER @auth -C -b -f 65001 -i $file 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Output $out
        Write-Error "Lỗi khi chạy $(Split-Path -Leaf $file)."
    }
}
if (-not $Quiet) { Write-Host "Đã reset tlhv_qlsv về dữ liệu mẫu." -ForegroundColor Green }
