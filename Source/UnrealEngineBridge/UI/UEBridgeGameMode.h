// UEBridgeGameMode.h
// Game mode for The UnrealEngine Bridge
// Part of The UnrealEngine Bridge - Claude Code → UE5.7 Bridge

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "UEBridgeGameMode.generated.h"

/**
 * AUEBridgeGameMode - Default game mode for UEBridge
 *
 * Sets up:
 * - UEBridgeHUD as default HUD class
 * - Default pawn (none needed for questionnaire)
 * - Auto-spawns BridgeActor with BridgeComponent (no manual placement needed)
 */
UCLASS()
class TRANSLATORSCARD_API AUEBridgeGameMode : public AGameModeBase
{
    GENERATED_BODY()

public:
    AUEBridgeGameMode();

    virtual void InitGame(const FString& MapName, const FString& Options, FString& ErrorMessage) override;

private:
    /** The auto-spawned bridge actor */
    UPROPERTY()
    AActor* BridgeActor;
};
