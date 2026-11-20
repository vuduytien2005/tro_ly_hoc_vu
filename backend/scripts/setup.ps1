# Cài đặt từ đầu trên máy mới (Windows). Chạy từ thư mục backend/:
#   .\scripts\setup.ps1                     # hỏi có nạp bộ quy chế giả lập không
#   .\scripts\setup.ps1 -VanBanMau          # nạp luôn bộ quy chế giả lập (evaluation/corpus_demo)
#   .\scripts\setup.ps1 -KhongNapVanBan     # không nạp văn bản (tự nạp PDF thật ở trang Tài liệu)
#   .\scripts\setup.ps1 -TaoLaiCsdl         # XÓA và tạo lại 2 CSDL tlhv_qlsv, tlhv_assistant
#   .\scripts\setup.ps1 -DbServer "localhost\SQLEXPRESS"   # ghi DB_SERVER vào .env
#   .\scripts\setup.ps1 -CaiLaiWeb         # cài lại thư viện web dù đã có node_modules
# Chạy lại an toàn: bước nào đã xong thì bỏ qua (CSDL đã có dữ liệu thì KHÔNG tạo lại nếu không
# có -TaoLaiCsdl). Script KHÔNG đụng khóa API: tự điền ANTHROPIC_API_KEY trong .env.
param(
    [string]$DbServer,
    [switch]$TaoLaiCsdl,
    [switch]$VanBanMau,
    [switch]$KhongNapVanBan,
    [switch]$CaiLaiWeb,
    [switch]$Eval
)

$ErrorActionPreference = "Stop"
$Backend = Split-Path -Parent $PSScriptRoot
$Root = Split-Path -Parent $Backend
$EnvFile = Join-Path $Root ".env"
$Venv = Join-Path $Backend ".venv"
$Python = Join-Path $Venv "Scripts\python.exe"

function Write-Step([string]$Text) { Write-Host "`n== $Text" -ForegroundColor Cyan }
function Write-Ok([string]$Text) { Write-Host "   $Text" -ForegroundColor Green }
function Write-Note([string]$Text) { Write-Host "   $Text" -ForegroundColor Yellow }
function Stop-Setup([string]$Text) { Write-Host "   $Text" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------------------
Write-Step "1/7 Kiểm tra phần mềm cần có"
$sysPython = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $sysPython) { Stop-Setup "Chưa có Python 3.11+ (https://www.python.org/downloads/, tích 'Add python.exe to PATH')." }
$pyVersion = & $sysPython -c "import sys; print('%d.%d' % sys.version_info[:2])"
if ([version]$pyVersion -lt [version]"3.11") { Stop-Setup "Cần Python 3.11+, máy đang có $pyVersion." }
Write-Ok "Python $pyVersion"

$node = (Get-Command node -ErrorAction SilentlyContinue).Source
if (-not $node) { Stop-Setup "Chưa có Node.js 20+ (https://nodejs.org)." }
$nodeMajor = [int]((& node --version).TrimStart("v").Split(".")[0])
if ($nodeMajor -lt 20) { Stop-Setup "Cần Node.js 20+, máy đang có $(& node --version)." }
Write-Ok "Node.js $(& node --version)"

$sqlcmd = (Get-Command sqlcmd -ErrorAction SilentlyContinue).Source
if (-not $sqlcmd) {
    $sqlcmd = Get-ChildItem "C:\Program Files\Microsoft SQL Server\Client SDK\ODBC\*\Tools\Binn\sqlcmd.exe" -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $sqlcmd) { Stop-Setup "Chưa có sqlcmd (cài cùng SQL Server / SSMS, hoặc 'winget install sqlcmd')." }
Write-Ok "sqlcmd: $sqlcmd"

$odbc = Get-OdbcDriver -Name "ODBC Driver 18 for SQL Server" -ErrorAction SilentlyContinue
if (-not $odbc) { Stop-Setup "Chưa có 'ODBC Driver 18 for SQL Server' (tải từ trang Microsoft)." }
Write-Ok "ODBC Driver 18 for SQL Server"

# ---------------------------------------------------------------------------
Write-Step "2/7 Tệp cấu hình .env"
function New-Secret {
    $bytes = New-Object byte[] 48
    # Create().GetBytes chạy được cả Windows PowerShell 5.1 (.NET Framework không có ::Fill)
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}
if (-not (Test-Path $EnvFile)) {
    Copy-Item (Join-Path $Root ".env.example") $EnvFile
    Write-Ok "Đã tạo .env từ .env.example"
}
$lines = Get-Content $EnvFile -Encoding UTF8
$changed = $false
for ($i = 0; $i -lt $lines.Count; $i++) {
    if ($lines[$i] -match '^\s*(JWT_SECRET|INTERNAL_API_TOKEN)\s*=\s*(.*)$') {
        $value = $Matches[2].Trim()
        if ($value.Length -lt 32 -or $value.ToLower().StartsWith("thay_bang")) {
            $lines[$i] = "$($Matches[1])=$(New-Secret)"
            $changed = $true
            Write-Ok "Đã sinh $($Matches[1]) ngẫu nhiên"
        }
    }
    if ($DbServer -and $lines[$i] -match '^\s*DB_SERVER\s*=') {
        $lines[$i] = "DB_SERVER=$DbServer"
        $changed = $true
    }
}
if ($changed) { [System.IO.File]::WriteAllLines($EnvFile, $lines, (New-Object System.Text.UTF8Encoding $false)) }

$cfg = @{ DB_SERVER = ""; DB_USER = ""; DB_PASSWORD = ""; LLM_MODEL = ""; ANTHROPIC_API_KEY = "" }
foreach ($line in $lines) {
    if ($line -match '^\s*(DB_SERVER|DB_USER|DB_PASSWORD|LLM_MODEL|ANTHROPIC_API_KEY)\s*=\s*(.*?)\s*$') {
        $cfg[$Matches[1]] = $Matches[2].Trim('"').Trim("'")
    }
}
Write-Ok "DB_SERVER = $($cfg.DB_SERVER)"
if ($cfg.LLM_MODEL -like "anthropic/*" -and -not $cfg.ANTHROPIC_API_KEY) {
    Write-Note "ANTHROPIC_API_KEY trong .env đang trống: hệ thống chạy được nhưng trợ lý chưa trả lời được."
}

# ---------------------------------------------------------------------------
Write-Step "3/7 Cơ sở dữ liệu SQL Server"
$auth = @(if ($cfg.DB_USER) { "-U", $cfg.DB_USER, "-P", $cfg.DB_PASSWORD } else { "-E" })
function Invoke-Sql([string[]]$SqlArgs) {
    $out = & $sqlcmd -S $cfg.DB_SERVER @auth -C -b -f 65001 @SqlArgs 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Output $out
        Stop-Setup "Lỗi SQL Server. Kiểm tra DB_SERVER trong .env đúng như ô 'Server name' của SSMS."
    }
    return $out
}
$probe = Invoke-Sql @("-h", "-1", "-W", "-Q",
    "SET NOCOUNT ON; SELECT CASE WHEN DB_ID(N'tlhv_assistant') IS NOT NULL AND OBJECT_ID(N'tlhv_assistant.dbo.nguoi_dung') IS NOT NULL THEN 1 ELSE 0 END")
$exists = ($probe | Select-Object -Last 1).ToString().Trim() -eq "1"
if ($exists -and -not $TaoLaiCsdl) {
    Write-Ok "CSDL đã có -> bỏ qua (thêm -TaoLaiCsdl để xóa và tạo lại)."
    # Nâng cấp CSDL cũ (chạy lại an toàn): tool_call_id NVARCHAR(MAX) cho Gemini
    foreach ($name in "05_nang_cap_tool_call_id.sql", "06_nang_cap_ban_duyet.sql", "07_nang_cap_ke_hoach_hoc_ky.sql") {
        Invoke-Sql @("-i", (Join-Path $Root "database\$name")) | Out-Null
        Write-Ok $name
    }
} else {
    foreach ($name in "01_qlsv_schema.sql", "02_assistant_schema.sql", "03_qlsv_seed.sql", "04_assistant_seed.sql") {
        Invoke-Sql @("-i", (Join-Path $Root "database\$name")) | Out-Null
        Write-Ok $name
    }
}

# ---------------------------------------------------------------------------
Write-Step "4/7 Môi trường Python (backend\.venv)"
if (-not (Test-Path $Python)) {
    & $sysPython -m venv $Venv
    Write-Ok "Đã tạo venv"
}
$extras = if ($Eval) { "[dev,eval]" } else { "[dev]" }
Push-Location $Backend
try {
    & $Python -m pip install --disable-pip-version-check -q -e ".$extras"
    if ($LASTEXITCODE -ne 0) { Stop-Setup "pip install lỗi." }
    Write-Ok "Đã cài thư viện backend $extras"

    # -----------------------------------------------------------------------
    Write-Step "5/7 Tài khoản demo"
    & $Python scripts\seed_users.py
    if ($LASTEXITCODE -ne 0) { Stop-Setup "seed_users.py lỗi." }
} finally {
    Pop-Location
}

# ---------------------------------------------------------------------------
Write-Step "6/7 Giao diện web (npm install)"
Push-Location (Join-Path $Root "web")
try {
    if ((Test-Path "node_modules") -and -not $CaiLaiWeb) {
        Write-Ok "Đã có node_modules -> bỏ qua (thêm -CaiLaiWeb để cài lại)."
    } else {
        if (Test-Path "package-lock.json") { & npm ci --no-audit --no-fund } else { & npm install --no-audit --no-fund }
        if ($LASTEXITCODE -ne 0) { Stop-Setup "npm install lỗi." }
        Write-Ok "Đã cài thư viện web"
    }
} finally {
    Pop-Location
}

# ---------------------------------------------------------------------------
Write-Step "7/7 Văn bản quy chế"
$count = Invoke-Sql @("-h", "-1", "-W", "-Q",
    "SET NOCOUNT ON; SELECT COUNT(*) FROM tlhv_assistant.dbo.van_ban WHERE trang_thai = N'da_lap_chi_muc'")
$indexed = [int](($count | Select-Object -Last 1).ToString().Trim())
if ($indexed -gt 0) {
    Write-Ok "Đã có $indexed văn bản được lập chỉ mục."
} elseif ($KhongNapVanBan) {
    Write-Note "Chưa có văn bản: đăng nhập admin -> trang Tài liệu để tải PDF/DOCX quy chế."
} else {
    $load = $VanBanMau
    if (-not $load) {
        $answer = Read-Host "   Chưa có văn bản quy chế. Nạp bộ quy chế GIẢ LẬP (evaluation/corpus_demo) để demo ngay? (c/k)"
        $load = $answer -match '^(c|co|y|yes)$'
    }
    if ($load) {
        $busy = Get-NetTCPConnection -LocalPort 9104 -State Listen -ErrorAction SilentlyContinue
        if ($busy) { Stop-Setup "Server quy_che (cổng 9104) đang chạy: tắt bằng .\scripts\run_all.ps1 -Stop rồi chạy lại." }
        Write-Note "Lần đầu sẽ tải mô hình embedding (~1,1 GB), có thể mất vài phút."
        Push-Location $Backend
        try {
            & $Python scripts\ingest_folder.py --thu-muc (Join-Path $Root "evaluation\corpus_demo")
            if ($LASTEXITCODE -ne 0) { Stop-Setup "Nạp văn bản lỗi." }
        } finally {
            Pop-Location
        }
    } else {
        Write-Note "Bỏ qua: đăng nhập admin -> trang Tài liệu để tải PDF/DOCX quy chế."
    }
}

Write-Host "`nCài đặt xong." -ForegroundColor Green
Write-Host "  Chạy backend : cd backend; .\scripts\run_all.ps1"
Write-Host "  Chạy web     : cd web; npm run dev   -> http://localhost:5173"
Write-Host "  Tài khoản    : sv22001@truong.example / Sv@123456  ·  admin@truong.example / Admin@123456"
