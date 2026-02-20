// UEBridgeRuntime.h
// Runtime module for the UE Bridge plugin.

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

DECLARE_LOG_CATEGORY_EXTERN(LogUEBridge, Log, All);

class FUEBridgeRuntimeModule : public IModuleInterface
{
public:
    virtual void StartupModule() override;
    virtual void ShutdownModule() override;
};
