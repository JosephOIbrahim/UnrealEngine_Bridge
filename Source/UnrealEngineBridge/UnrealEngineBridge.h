// UnrealEngineBridge.h
// Module header for the UnrealEngine Bridge game

#pragma once

#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

class FUnrealEngineBridgeModule : public IModuleInterface
{
public:
    /** IModuleInterface implementation */
    virtual void StartupModule() override;
    virtual void ShutdownModule() override;
};
