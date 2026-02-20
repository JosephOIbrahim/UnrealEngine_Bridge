// UnrealEngineBridge.cpp
// Module implementation for the UnrealEngine Bridge game

#include "UnrealEngineBridge.h"
#include "UEBridgeRuntime.h"
#include "Modules/ModuleManager.h"

#define LOCTEXT_NAMESPACE "FUnrealEngineBridgeModule"

void FUnrealEngineBridgeModule::StartupModule()
{
    UE_LOG(LogUEBridge, Log, TEXT("[UnrealEngineBridge] Module started"));
    UE_LOG(LogUEBridge, Log, TEXT("[UnrealEngineBridge] Bridge component available for use"));
}

void FUnrealEngineBridgeModule::ShutdownModule()
{
    UE_LOG(LogUEBridge, Log, TEXT("[UnrealEngineBridge] Module shutdown"));
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FUnrealEngineBridgeModule, UnrealEngineBridge)
