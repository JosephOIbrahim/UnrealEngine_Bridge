// UEBridgeEditor.h
// Editor module for the UE Bridge plugin.
// Owns DirectoryWatcher, MCP server lifecycle, Python bridge process management,
// and BridgeComponent detail panel customization.

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

class FUEBridgeEditorModule : public IModuleInterface
{
public:
    virtual void StartupModule() override;
    virtual void ShutdownModule() override;
};
