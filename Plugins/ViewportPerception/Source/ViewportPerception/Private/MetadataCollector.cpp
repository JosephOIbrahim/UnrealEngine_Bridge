// MetadataCollector.cpp

#include "MetadataCollector.h"
#include "ViewportPerceptionModule.h"
#include "Editor.h"
#include "Selection.h"
#include "LevelEditorViewport.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "EditorViewportClient.h"
#include "LevelEditor.h"
#include "SLevelViewport.h"
#include "ILevelEditor.h"

FPerceptionMetadata FMetadataCollector::Collect()
{
	check(IsInGameThread());

	FPerceptionMetadata Meta;

	// Get the active level editor viewport
	if (GEditor)
	{
		// Try to get the active viewport client
		FEditorViewportClient* ViewportClient = nullptr;

		FLevelEditorModule& LevelEditorModule = FModuleManager::GetModuleChecked<FLevelEditorModule>("LevelEditor");
		TSharedPtr<ILevelEditor> LevelEditor = LevelEditorModule.GetFirstLevelEditor();
		if (LevelEditor.IsValid())
		{
			TSharedPtr<SLevelViewport> ActiveViewport = LevelEditor->GetActiveViewportInterface();
			if (ActiveViewport.IsValid())
			{
				ViewportClient = &ActiveViewport->GetLevelViewportClient();
			}
		}

		if (ViewportClient)
		{
			// Camera
			Meta.Camera.Location = ViewportClient->GetViewLocation();
			Meta.Camera.Rotation = ViewportClient->GetViewRotation();
			Meta.Camera.FOV = ViewportClient->ViewFOV;

			// Viewport size
			FIntPoint ViewSize = ViewportClient->Viewport ? ViewportClient->Viewport->GetSizeXY() : FIntPoint::ZeroValue;
			Meta.ViewportSize = ViewSize;

			// Viewport type
			if (ViewportClient->IsSimulateInEditorViewport())
			{
				Meta.ViewportType = TEXT("SIE");
			}
			else if (GEditor->PlayWorld != nullptr)
			{
				Meta.ViewportType = TEXT("PIE");
			}
			else
			{
				Meta.ViewportType = TEXT("LevelEditor");
			}
		}

		// Selected actors
		USelection* Selection = GEditor->GetSelectedActors();
		if (Selection)
		{
			for (int32 i = 0; i < Selection->Num(); ++i)
			{
				AActor* Actor = Cast<AActor>(Selection->GetSelectedObject(i));
				if (Actor)
				{
					Meta.SelectedActors.Add(Actor->GetActorLabel());
				}
			}
		}

		// Map name and actor count
		UWorld* World = GEditor->GetEditorWorldContext().World();
		if (World)
		{
			Meta.MapName = World->GetMapName();

			int32 Count = 0;
			for (TActorIterator<AActor> It(World); It; ++It)
			{
				++Count;
			}
			Meta.ActorCount = Count;
		}

		// Timing
		Meta.DeltaTime = FApp::GetDeltaTime();
		Meta.FPS = (Meta.DeltaTime > 0.0f) ? (1.0f / Meta.DeltaTime) : 0.0f;
	}

	return Meta;
}
