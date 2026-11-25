# 一键启动三个可运行的参考项目（AI-Search 因 SWC 兼容问题未纳入）
# 用法： .\start_services.ps1           启动并打印地址
#        .\start_services.ps1 -Open     启动后自动打开浏览器
param([switch]$Open)

$root = 'E:\Information Retrieval Technology'
$node = 'E:\node\node.exe'
$py   = 'C:\Users\邢启德\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe'

function Test-Port($port) {
    return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

# 1) ZipNews / World Signal —— 零依赖，Python 标准库
if (-not (Test-Port 8000)) {
    Start-Process -FilePath $py -ArgumentList 'app.py' -WorkingDirectory "$root\ZipNews-main" -WindowStyle Hidden `
        -RedirectStandardOutput "$root\ZipNews-main\server.log" -RedirectStandardError "$root\ZipNews-main\server.err.log"
    Write-Host 'starting ZipNews on 8000 ...'
} else { Write-Host 'ZipNews already on 8000' }

# 2) ai-news-aggregator 前端（Vite）
if (-not (Test-Port 5173)) {
    Start-Process -FilePath $node -ArgumentList 'node_modules\vite\bin\vite.js','--port','5173','--strictPort','--host','127.0.0.1' `
        -WorkingDirectory "$root\ai-news-aggregator-main\web" -WindowStyle Hidden `
        -RedirectStandardOutput "$root\ai-news-aggregator-main\web\dev.log" -RedirectStandardError "$root\ai-news-aggregator-main\web\dev.err.log"
    Write-Host 'starting ai-news on 5173 ...'
} else { Write-Host 'ai-news already on 5173' }

# 3) Insight-News 前端（Vite；无 MongoDB 时列表为空）
if (-not (Test-Port 5174)) {
    Start-Process -FilePath $node -ArgumentList 'node_modules\vite\bin\vite.js','--port','5174','--strictPort','--host','127.0.0.1' `
        -WorkingDirectory "$root\Insight-News-main\frontend" -WindowStyle Hidden `
        -RedirectStandardOutput "$root\Insight-News-main\frontend\dev.log" -RedirectStandardError "$root\Insight-News-main\frontend\dev.err.log"
    Write-Host 'starting Insight-News on 5174 ...'
} else { Write-Host 'Insight-News already on 5174' }

Start-Sleep -Seconds 8

$urls = @(
    @{ Name = 'ZipNews 地图';   Url = 'http://127.0.0.1:8000/' },
    @{ Name = 'ZipNews 市场';   Url = 'http://127.0.0.1:8000/markets' },
    @{ Name = 'ZipNews 信号';   Url = 'http://127.0.0.1:8000/signals' },
    @{ Name = 'ai-news 聚合';   Url = 'http://127.0.0.1:5173/' },
    @{ Name = 'Insight-News';   Url = 'http://127.0.0.1:5174/' },
    @{ Name = 'PIP 日报(自建)'; Url = 'file:///E:/Information%20Retrieval%20Technology/pip_app/web/index.html' }
)

Write-Host ''
foreach ($u in $urls) {
    $ok = if ($u.Url.StartsWith('file:')) { 'ok' } elseif (Test-Port ([uri]$u.Url).Port) { 'ok' } else { 'DOWN' }
    '{0,-16} {1,-6} {2}' -f $u.Name, $ok, $u.Url
}

if ($Open) {
    Start-Process 'http://127.0.0.1:8000/'
    Start-Process 'http://127.0.0.1:5173/'
    Start-Process 'http://127.0.0.1:5174/'
}

Write-Host ''
Write-Host '停止：Get-NetTCPConnection -LocalPort 8000,5173,5174 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }'
