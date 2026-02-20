// ViewportPerceptionModule.cpp

#include "ViewportPerceptionModule.h"

DEFINE_LOG_CATEGORY(LogViewportPerception);

#define LOCTEXT_NAMESPACE "FViewportPerceptionModule"

void FViewportPerceptionModule::StartupModule()
{
	UE_LOG(LogViewportPerception, Log, TEXT("Module loaded"));
}

void FViewportPerceptionModule::ShutdownModule()
{
	UE_LOG(LogViewportPerception, Log, TEXT("Module unloaded"));
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FViewportPerceptionModule, ViewportPerception)
