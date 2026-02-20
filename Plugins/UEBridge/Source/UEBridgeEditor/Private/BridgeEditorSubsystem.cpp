// BridgeEditorSubsystem.cpp
// Editor subsystem implementation.
// Phase 3: DirectoryWatcher logic migrated from BridgeComponent.

#include "BridgeEditorSubsystem.h"
#include "UEBridgeRuntime.h"
#include "DirectoryWatcherModule.h"
#include "IDirectoryWatcher.h"
#include "HAL/PlatformProcess.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"

void UBridgeEditorSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    UE_LOG(LogUEBridge, Log, TEXT("BridgeEditorSubsystem initialized"));
}

void UBridgeEditorSubsystem::Deinitialize()
{
    StopWatching();
    StopBridgeProcess();

    UE_LOG(LogUEBridge, Log, TEXT("BridgeEditorSubsystem deinitialized"));
    Super::Deinitialize();
}


// === FILE WATCHING ===

void UBridgeEditorSubsystem::StartWatching(const FString& BridgePath)
{
    if (bIsWatching)
    {
        if (WatchedPath == BridgePath)
        {
            return; // Already watching this path
        }
        StopWatching(); // Switch to new path
    }

    FDirectoryWatcherModule& DirWatcherModule =
        FModuleManager::LoadModuleChecked<FDirectoryWatcherModule>(TEXT("DirectoryWatcher"));
    IDirectoryWatcher* DirWatcher = DirWatcherModule.Get();

    if (!DirWatcher)
    {
        UE_LOG(LogUEBridge, Error, TEXT("Could not get DirectoryWatcher module"));
        return;
    }

    IDirectoryWatcher::FDirectoryChanged Callback =
        IDirectoryWatcher::FDirectoryChanged::CreateUObject(
            this, &UBridgeEditorSubsystem::OnDirectoryChanged);

    bool bSuccess = DirWatcher->RegisterDirectoryChangedCallback_Handle(
        BridgePath, Callback, WatchHandle, 0);

    if (bSuccess)
    {
        WatchedPath = BridgePath;
        bIsWatching = true;
        UE_LOG(LogUEBridge, Log, TEXT("Editor file watcher registered for: %s"), *BridgePath);
    }
    else
    {
        UE_LOG(LogUEBridge, Error, TEXT("Failed to register editor file watcher for: %s"), *BridgePath);
    }
}


void UBridgeEditorSubsystem::StopWatching()
{
    if (!bIsWatching || !WatchHandle.IsValid())
    {
        return;
    }

    FDirectoryWatcherModule& DirWatcherModule =
        FModuleManager::LoadModuleChecked<FDirectoryWatcherModule>(TEXT("DirectoryWatcher"));
    IDirectoryWatcher* DirWatcher = DirWatcherModule.Get();

    if (DirWatcher)
    {
        DirWatcher->UnregisterDirectoryChangedCallback_Handle(WatchedPath, WatchHandle);
        UE_LOG(LogUEBridge, Log, TEXT("Editor file watcher unregistered"));
    }

    bIsWatching = false;
    WatchedPath.Empty();
}


void UBridgeEditorSubsystem::OnDirectoryChanged(const TArray<FFileChangeData>& Changes)
{
    for (const FFileChangeData& Change : Changes)
    {
        bool bIsUsdProfile = Change.Filename.EndsWith(TEXT("cognitive_profile.usda")) ||
                             Change.Filename.EndsWith(TEXT("cognitive_substrate.usda"));

        bool bIsBridgeState = Change.Filename.EndsWith(TEXT("state.json")) ||
                              Change.Filename.EndsWith(TEXT("bridge_state.usda"));

        if (bIsBridgeState || bIsUsdProfile)
        {
            // Broadcast to any listeners (BridgeComponents, editor tools, etc.)
            OnBridgeFileChanged.Broadcast(Change.Filename, bIsUsdProfile);
        }
    }
}


// === PYTHON PROCESS ===

void UBridgeEditorSubsystem::StartBridgeProcess()
{
    if (bBridgeProcessRunning)
    {
        UE_LOG(LogUEBridge, Warning, TEXT("Bridge process already running"));
        return;
    }

    // Locate bridge_orchestrator.py — project Scripts/ dir first, then user home fallback
    FString ScriptPath = FPaths::Combine(FPaths::ProjectDir(), TEXT("Scripts"), TEXT("bridge_orchestrator.py"));
    if (!IFileManager::Get().FileExists(*ScriptPath))
    {
        FString UserHome = FPlatformMisc::GetEnvironmentVariable(TEXT("USERPROFILE"));
        ScriptPath = FPaths::Combine(UserHome, TEXT(".translators"), TEXT("bridge_orchestrator.py"));
    }

    if (!IFileManager::Get().FileExists(*ScriptPath))
    {
        UE_LOG(LogUEBridge, Warning,
            TEXT("Bridge script not found. Looked in ProjectDir/Scripts/ and %%USERPROFILE%%/.translators/. "
                 "Use Launch-UEBridge.ps1 for manual launch."));
        return;
    }

    // Resolve Python executable
    const TCHAR* PythonExe = TEXT("python");

    // Build command-line arguments (just the script path)
    FString Args = FString::Printf(TEXT("\"%s\""), *ScriptPath);

    // Launch the process
    const bool bLaunchDetached = true;
    const bool bLaunchHidden = true;
    const bool bLaunchReallyHidden = false;
    constexpr int32 PriorityModifier = 0;
    const TCHAR* WorkingDir = nullptr;

    BridgeProcessHandle = FPlatformProcess::CreateProc(
        PythonExe,
        *Args,
        bLaunchDetached,
        bLaunchHidden,
        bLaunchReallyHidden,
        &BridgeProcId,
        PriorityModifier,
        WorkingDir,
        nullptr  // PipeWriteChild
    );

    if (BridgeProcessHandle.IsValid())
    {
        bBridgeProcessRunning = true;
        UE_LOG(LogUEBridge, Log,
            TEXT("Bridge process launched (PID %u): %s"), BridgeProcId, *ScriptPath);
    }
    else
    {
        UE_LOG(LogUEBridge, Error,
            TEXT("Failed to launch bridge process. Ensure 'python' is on PATH. Script: %s"), *ScriptPath);
    }
}

void UBridgeEditorSubsystem::StopBridgeProcess()
{
    if (!bBridgeProcessRunning)
    {
        return;
    }

    if (BridgeProcessHandle.IsValid() && FPlatformProcess::IsProcRunning(BridgeProcessHandle))
    {
        // Terminate with kill-tree enabled so child processes also stop
        FPlatformProcess::TerminateProc(BridgeProcessHandle, /* bKillTree */ true);
        UE_LOG(LogUEBridge, Log, TEXT("Bridge process terminated (PID %u)"), BridgeProcId);
    }

    FPlatformProcess::CloseProc(BridgeProcessHandle);
    BridgeProcId = 0;
    bBridgeProcessRunning = false;
}

bool UBridgeEditorSubsystem::IsBridgeProcessRunning() const
{
    if (!bBridgeProcessRunning)
    {
        return false;
    }

    // Live check — if the process exited on its own, update our flag
    if (BridgeProcessHandle.IsValid() && !FPlatformProcess::IsProcRunning(BridgeProcessHandle))
    {
        // Process died externally; clean up state (mutable cast for bookkeeping)
        UBridgeEditorSubsystem* MutableThis = const_cast<UBridgeEditorSubsystem*>(this);
        FPlatformProcess::CloseProc(MutableThis->BridgeProcessHandle);
        MutableThis->BridgeProcId = 0;
        MutableThis->bBridgeProcessRunning = false;
        UE_LOG(LogUEBridge, Warning, TEXT("Bridge process (PID %u) exited unexpectedly"), BridgeProcId);
        return false;
    }

    return true;
}
