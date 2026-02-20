// UEBridgeGameMode.cpp
// Implementation of game mode

#include "UEBridgeGameMode.h"
#include "UEBridgeRuntime.h"
#include "UEBridgeHUD.h"
#include "../BridgeComponent.h"
#include "GameFramework/PlayerController.h"
#include "Engine/World.h"


AUEBridgeGameMode::AUEBridgeGameMode()
{
    // Set default HUD class
    HUDClass = AUEBridgeHUD::StaticClass();

    // No pawn needed for questionnaire game
    DefaultPawnClass = nullptr;

    // Use default player controller
    PlayerControllerClass = APlayerController::StaticClass();

    BridgeActor = nullptr;

    UE_LOG(LogUEBridge, Log, TEXT("[UEBridgeGameMode] Constructed with UEBridgeHUD"));
}


void AUEBridgeGameMode::InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage)
{
    Super::InitGame(MapName, Options, ErrorMessage);

    // Auto-spawn BridgeActor so HUD can find BridgeComponent without manual placement
    UWorld* World = GetWorld();
    if (World)
    {
        FActorSpawnParameters SpawnParams;
        SpawnParams.Name = FName(TEXT("UEBridgeActor"));
        SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;

        BridgeActor = World->SpawnActor<AActor>(AActor::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator, SpawnParams);
        if (BridgeActor)
        {
            UBridgeComponent* Bridge = NewObject<UBridgeComponent>(BridgeActor, TEXT("BridgeComponent"));
            Bridge->bVerboseLogging = true;
            Bridge->RegisterComponent();
            BridgeActor->AddInstanceComponent(Bridge);

            UE_LOG(LogUEBridge, Log, TEXT("[UEBridgeGameMode] Auto-spawned BridgeActor with BridgeComponent"));
        }
    }
}
