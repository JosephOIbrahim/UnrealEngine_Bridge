// UEBridgeEditor.h
// Editor module for the UE Bridge plugin.
// Registers the "UE Bridge" toolbar button, Tools-menu entry, and dockable
// control panel — the recognizable in-editor home for the plugin. Also owns the
// BridgeEditorSubsystem (DirectoryWatcher + Python bridge process lifecycle).

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

class SDockTab;
class FSpawnTabArgs;

class FUEBridgeEditorModule : public IModuleInterface
{
public:
    virtual void StartupModule() override;
    virtual void ShutdownModule() override;

private:
    /** Extend the level-editor toolbar + Tools menu (called once ToolMenus is ready). */
    void RegisterMenus();

    /** Bring the UE Bridge panel tab to the foreground. */
    void OpenBridgeTab();

    /** Build the dockable UE Bridge control panel. */
    TSharedRef<SDockTab> OnSpawnBridgeTab(const FSpawnTabArgs& Args);

    /** Tab identifier for the dockable panel. */
    static const FName BridgeTabName;
};
