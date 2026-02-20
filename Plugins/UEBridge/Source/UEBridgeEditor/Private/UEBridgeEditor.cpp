// UEBridgeEditor.cpp
// Editor module implementation.
// Registers BridgeEditorSubsystem and detail panel customizations.

#include "UEBridgeEditor.h"
#include "UEBridgeRuntime.h"
#include "Modules/ModuleManager.h"

void FUEBridgeEditorModule::StartupModule()
{
    UE_LOG(LogUEBridge, Log, TEXT("UEBridge Editor module loaded"));
}

void FUEBridgeEditorModule::ShutdownModule()
{
    UE_LOG(LogUEBridge, Log, TEXT("UEBridge Editor module unloaded"));
}

IMPLEMENT_MODULE(FUEBridgeEditorModule, UEBridgeEditor)
