# Launch-UEBridge.ps1
# Artist-friendly launcher for UE Bridge — the Claude Code <-> Unreal Engine 5.7 agentic bridge.
# One click: open the project so Claude Code can perceive and build in your scene.
#
#   .\Launch-UEBridge.ps1            launch the editor for the agentic bridge (default)
#   .\Launch-UEBridge.ps1 -SkipUE    don't launch the editor (you'll open it yourself)
#   .\Launch-UEBridge.ps1 -Game      run the legacy cognitive-profiling questionnaire instead

param(
    [switch]$SkipUE,
    [switch]$Game
)

# ============================================
#  Configuration
# ============================================

$UEProject = "$PSScriptRoot\UnrealEngine_Bridge.uproject"
$UEEditor  = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe"
$RCPort    = 30010   # UE Remote Control API — the MCP server talks to this

# ============================================
#  Display helpers
# ============================================

function Write-Banner {
    Clear-Host
    $inner = 59
    $pre   = "   "
    $name  = "UE BRIDGE"
    $rest  = "  -  Agentic Unreal Engine for Claude Code"
    $pad   = $inner - $pre.Length - $name.Length - $rest.Length
    Write-Host ""
    Write-Host ("  +" + ("=" * $inner) + "+") -ForegroundColor Cyan
    Write-Host ("  |" + (" " * $inner) + "|") -ForegroundColor Cyan
    Write-Host ("  |" + $pre) -ForegroundColor Cyan -NoNewline
    Write-Host $name -ForegroundColor White -NoNewline
    Write-Host ($rest + (" " * $pad) + "|") -ForegroundColor Cyan
    Write-Host ("  |" + ("   Claude Code  <->  Unreal Engine 5.7").PadRight($inner) + "|") -ForegroundColor Cyan
    Write-Host ("  |" + (" " * $inner) + "|") -ForegroundColor Cyan
    Write-Host ("  +" + ("=" * $inner) + "+") -ForegroundColor Cyan
    Write-Host ""
}

function Write-Info    { param([string]$Text) Write-Host "  -> " -ForegroundColor Cyan  -NoNewline; Write-Host $Text }
function Write-Success  { param([string]$Text) Write-Host "  ok " -ForegroundColor Green -NoNewline; Write-Host $Text }
function Write-Warn     { param([string]$Text) Write-Host "  !  " -ForegroundColor Yellow -NoNewline; Write-Host $Text }

# ============================================
#  Launch
# ============================================

Write-Banner

# Step 1: project file must exist
Write-Info "Checking project file..."
if (Test-Path $UEProject) {
    Write-Success "UnrealEngine_Bridge.uproject found"
} else {
    Write-Host ""
    Write-Host "  ERROR: Project file not found!" -ForegroundColor Red
    Write-Host "  Expected: $UEProject" -ForegroundColor Red
    Write-Host ""
    Read-Host "  Press Enter to exit"
    exit 1
}

# Step 2: launch the editor
if (-not $SkipUE) {
    Write-Info "Launching UE5.7..."
    Write-Host "  (this may take a moment to load)" -ForegroundColor DarkGray
    if (Test-Path $UEEditor) {
        Start-Process $UEEditor -ArgumentList "`"$UEProject`""
    } else {
        Write-Warn "UE5.7 not found at the default path; opening the .uproject via its file association"
        Start-Process $UEProject
    }
    Write-Success "UE5 launching..."
} else {
    Write-Info "Skipping editor launch (-SkipUE). Open UnrealEngine_Bridge.uproject yourself."
}

# ============================================
#  Mode: legacy cognitive-profiling game (opt-in) vs agentic bridge (default)
# ============================================

if ($Game) {
    Write-Host ""
    Write-Info "Starting the legacy cognitive-profiling questionnaire..."
    $orchestrator = "$PSScriptRoot\bridge_orchestrator.py"
    if (Test-Path $orchestrator) {
        $wt = Get-Command "wt" -ErrorAction SilentlyContinue
        if ($wt) {
            Start-Process "wt" -ArgumentList "new-tab --title `"UE Bridge - Questionnaire`" -d `"$PSScriptRoot`" python `"$orchestrator`""
        } else {
            Start-Process "cmd" -ArgumentList "/k cd /d `"$PSScriptRoot`" && python `"$orchestrator`""
        }
        Write-Success "Orchestrator launching..."
    } else {
        Write-Warn "bridge_orchestrator.py not found. Start it manually: python bridge_orchestrator.py"
    }
    Write-Host ""
    Write-Host "  NEXT STEPS (questionnaire):" -ForegroundColor Yellow
    Write-Host "    1. Wait for UE5 to finish loading" -ForegroundColor DarkGray
    Write-Host "    2. Press Play in the viewport" -ForegroundColor DarkGray
    Write-Host "    3. Answer the questions; your profile exports as USD automatically" -ForegroundColor DarkGray
    Write-Host ""
    Start-Sleep -Seconds 3
    return
}

# Default: agentic bridge
Write-Host ""
Write-Host "  NEXT STEPS (agentic bridge):" -ForegroundColor Yellow
Write-Host "    1. Wait for UE5 to finish loading" -ForegroundColor DarkGray
Write-Host "    2. The UE Remote Control server listens on localhost:$RCPort" -ForegroundColor DarkGray
Write-Host "    3. Make sure the 'ue-mcp' server is configured in Claude Code (see README)" -ForegroundColor DarkGray
Write-Host "    4. In Claude Code, the ue_* tools are now live — ask Claude to" -ForegroundColor DarkGray
Write-Host "       perceive and build in your scene" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Claude Code now drives Unreal Engine through the bridge." -ForegroundColor Green
Write-Host "  (Want the legacy questionnaire instead? Re-run with -Game.)" -ForegroundColor DarkGray
Write-Host ""
Start-Sleep -Seconds 3
