# Launch-UEBridge.ps1
# Artist-friendly launcher for Claude Code <-> UE5.7 Bridge
# One-click to start the cognitive profiling experience

param(
    [switch]$SkipUE,
    [switch]$SkipClaude
)

# ============================================
#  Configuration
# ============================================

$UEProject = "$PSScriptRoot\UnrealEngineBridge.uproject"
$BridgeDir = "$env:USERPROFILE\.translators"
$UEEditor = "C:\Program Files\Epic Games\UE_5.7\Engine\Binaries\Win64\UnrealEditor.exe"

# ============================================
#  Colors & Display
# ============================================

function Write-Banner {
    Clear-Host
    Write-Host ""
    Write-Host "  ╔═══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "  ║                                                           ║" -ForegroundColor Cyan
    Write-Host "  ║   " -ForegroundColor Cyan -NoNewline
    Write-Host "THE TRANSLATORS" -ForegroundColor White -NoNewline
    Write-Host " — Cognitive Profiling Bridge        ║" -ForegroundColor Cyan
    Write-Host "  ║                                                           ║" -ForegroundColor Cyan
    Write-Host "  ║   Claude Code  ←→  UE5.7                                  ║" -ForegroundColor Cyan
    Write-Host "  ║                                                           ║" -ForegroundColor Cyan
    Write-Host "  ╚═══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step {
    param([string]$Icon, [string]$Text, [string]$Color = "White")
    Write-Host "  $Icon " -ForegroundColor $Color -NoNewline
    Write-Host $Text
}

function Write-Success {
    param([string]$Text)
    Write-Step "✓" $Text "Green"
}

function Write-Info {
    param([string]$Text)
    Write-Step "→" $Text "Cyan"
}

function Write-Warning {
    param([string]$Text)
    Write-Step "!" $Text "Yellow"
}

# ============================================
#  Main Launch Sequence
# ============================================

Write-Banner

# Step 1: Ensure bridge directory exists
Write-Info "Checking bridge directory..."
if (-not (Test-Path $BridgeDir)) {
    New-Item -ItemType Directory -Path $BridgeDir -Force | Out-Null
    Write-Success "Created $BridgeDir"
} else {
    Write-Success "Bridge directory exists"
}

# Clean stale state files for fresh session
$staleFiles = @("$BridgeDir\state.json", "$BridgeDir\answer.json", "$BridgeDir\ack.json")
foreach ($file in $staleFiles) {
    if (Test-Path $file) {
        Remove-Item $file -Force
    }
}
Write-Success "Cleared stale session files"

# Step 2: Check UE5 installation
Write-Info "Checking UE5.7 installation..."
if (Test-Path $UEEditor) {
    Write-Success "UE5.7 found"
} else {
    Write-Warning "UE5.7 not found at expected location"
    Write-Warning "You may need to open the project manually"
}

# Step 3: Check project file
Write-Info "Checking project file..."
if (Test-Path $UEProject) {
    Write-Success "UnrealEngineBridge.uproject found"
} else {
    Write-Host ""
    Write-Host "  ERROR: Project file not found!" -ForegroundColor Red
    Write-Host "  Expected: $UEProject" -ForegroundColor Red
    Write-Host ""
    Read-Host "  Press Enter to exit"
    exit 1
}

# Step 4: Launch UE5
if (-not $SkipUE) {
    Write-Host ""
    Write-Info "Launching UE5.7..."
    Write-Host "  (This may take a moment to load)" -ForegroundColor DarkGray

    if (Test-Path $UEEditor) {
        Start-Process $UEEditor -ArgumentList "`"$UEProject`""
    } else {
        # Fallback: open .uproject directly (Windows will use associated app)
        Start-Process $UEProject
    }
    Write-Success "UE5 launching..."
}

# Step 5: Launch Bridge Orchestrator (Python)
if (-not $SkipClaude) {
    Write-Host ""
    Write-Info "Launching Bridge Orchestrator..."

    $orchestrator = "$PSScriptRoot\bridge_orchestrator.py"
    $workDir = $PSScriptRoot

    if (Test-Path $orchestrator) {
        # Try to launch in Windows Terminal if available
        $wtExists = Get-Command "wt" -ErrorAction SilentlyContinue
        if ($wtExists) {
            Start-Process "wt" -ArgumentList "new-tab --title `"Translators Orchestrator`" -d `"$workDir`" python `"$orchestrator`""
        } else {
            # Fallback to regular cmd
            Start-Process "cmd" -ArgumentList "/k cd /d `"$workDir`" && python `"$orchestrator`""
        }
        Write-Success "Orchestrator launching..."
    } else {
        Write-Warning "Orchestrator not found. Start manually:"
        Write-Host "    python bridge_orchestrator.py" -ForegroundColor Yellow
    }
}

# ============================================
#  Instructions
# ============================================

Write-Host ""
Write-Host "  ┌─────────────────────────────────────────────────────────────┐" -ForegroundColor DarkGray
Write-Host "  │  " -ForegroundColor DarkGray -NoNewline
Write-Host "NEXT STEPS:" -ForegroundColor Yellow -NoNewline
Write-Host "                                              │" -ForegroundColor DarkGray
Write-Host "  │                                                             │" -ForegroundColor DarkGray
Write-Host "  │  1. Wait for UE5 to finish loading                          │" -ForegroundColor DarkGray
Write-Host "  │  2. Press " -ForegroundColor DarkGray -NoNewline
Write-Host "Play" -ForegroundColor Cyan -NoNewline
Write-Host " in UE5 viewport                              │" -ForegroundColor DarkGray
Write-Host "  │  3. Questions will appear - click your answers              │" -ForegroundColor DarkGray
Write-Host "  │  4. Complete all 8 questions                                │" -ForegroundColor DarkGray
Write-Host "  │                                                             │" -ForegroundColor DarkGray
Write-Host "  │  " -ForegroundColor DarkGray -NoNewline
Write-Host "Your cognitive profile exports as USD automatically" -ForegroundColor Green -NoNewline
Write-Host "         │" -ForegroundColor DarkGray
Write-Host "  └─────────────────────────────────────────────────────────────┘" -ForegroundColor DarkGray
Write-Host ""

# Keep window open briefly so user can read
Start-Sleep -Seconds 3
