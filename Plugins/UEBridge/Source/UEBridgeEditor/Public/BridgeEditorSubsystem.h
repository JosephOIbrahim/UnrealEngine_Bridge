// BridgeEditorSubsystem.h
// Editor subsystem that owns:
// - IDirectoryWatcher for ~/.translators/ file change detection
// - Python bridge_orchestrator.py process lifecycle
// - MCP server startup/shutdown
//
// Phase 3: DirectoryWatcher migrated from BridgeComponent.
// The subsystem watches the bridge directory and notifies any active
// BridgeComponents via their NotifyFileChanged() method.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/EditorSubsystem.h"
#include "BridgeEditorSubsystem.generated.h"

struct FFileChangeData;
class UBridgeComponent;

/** Delegate broadcast when the bridge directory changes */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnBridgeFileChanged, const FString&, Filename, bool, bIsUsdProfile);

UCLASS()
class TRANSLATORSBRIDGEEDITOR_API UBridgeEditorSubsystem : public UEditorSubsystem
{
    GENERATED_BODY()

public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

    // === FILE WATCHING ===

    /** Start watching a bridge directory for file changes */
    UFUNCTION(BlueprintCallable, Category = "UE Bridge|Editor", meta = (ToolTip = "Start watching the bridge directory"))
    void StartWatching(const FString& BridgePath);

    /** Stop watching the bridge directory */
    UFUNCTION(BlueprintCallable, Category = "UE Bridge|Editor", meta = (ToolTip = "Stop watching the bridge directory"))
    void StopWatching();

    /** Fired when a file changes in the watched bridge directory */
    UPROPERTY(BlueprintAssignable, Category = "UE Bridge|Editor", meta = (ToolTip = "Fires when a file changes in the bridge directory"))
    FOnBridgeFileChanged OnBridgeFileChanged;

    // === PYTHON PROCESS ===

    /** Launch the Python bridge_orchestrator process */
    UFUNCTION(BlueprintCallable, Category = "UE Bridge|Editor", meta = (ToolTip = "Launch bridge_orchestrator.py"))
    void StartBridgeProcess();

    /** Terminate the Python bridge_orchestrator process */
    UFUNCTION(BlueprintCallable, Category = "UE Bridge|Editor", meta = (ToolTip = "Stop bridge_orchestrator.py"))
    void StopBridgeProcess();

    /** Check if the Python bridge process is running */
    UFUNCTION(BlueprintCallable, BlueprintPure, Category = "UE Bridge|Editor", meta = (ToolTip = "True if bridge_orchestrator.py is running"))
    bool IsBridgeProcessRunning() const;

private:
    void OnDirectoryChanged(const TArray<FFileChangeData>& Changes);

    // Directory watcher state
    FDelegateHandle WatchHandle;
    FString WatchedPath;
    bool bIsWatching = false;

    // Python process handle
    FProcHandle BridgeProcessHandle;
    uint32 BridgeProcId = 0;
    bool bBridgeProcessRunning = false;
};
