// UEBridgeRuntime.cpp
// Runtime module implementation.

#include "UEBridgeRuntime.h"
#include "UEBridgeStyle.h"
#include "Modules/ModuleManager.h"

DEFINE_LOG_CATEGORY(LogUEBridge);

void FUEBridgeRuntimeModule::StartupModule()
{
    FUEBridgeStyle::Initialize();
    UE_LOG(LogUEBridge, Log, TEXT("UEBridge Runtime module loaded (v%s)"), BRIDGE_VERSION);
}

void FUEBridgeRuntimeModule::ShutdownModule()
{
    FUEBridgeStyle::Shutdown();
    UE_LOG(LogUEBridge, Log, TEXT("UEBridge Runtime module unloaded"));
}

IMPLEMENT_MODULE(FUEBridgeRuntimeModule, UEBridgeRuntime)
