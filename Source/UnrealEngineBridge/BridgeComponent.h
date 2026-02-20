// BridgeComponent.h
// Actor component relay for the UE Bridge.
//
// Phase 4: Game flow logic migrated to UUEBridgeSubsystem.
// This component is now a thin Blueprint-bindable relay that:
// - Gets the subsystem on BeginPlay and calls StartGame()
// - Forwards subsystem delegates to legacy component delegates
// - Provides deprecated wrapper functions for backward compatibility
//
// New Blueprints should bind directly to UUEBridgeSubsystem.

#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "BridgeTypes.h"
#include "BridgeComponent.generated.h"

// Forward declarations
class UUEBridgeSubsystem;

// ============================================================================
// Legacy delegates (v1 Blueprint compatibility)
// New code should use the typed delegates on UUEBridgeSubsystem.
// ============================================================================

DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnQuestionReceived, const FString&, QuestionJson);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnTransitionReceived, const FString&, Direction, const FString&, NextScene);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnFinaleReceived, const FString&, UsdPath);
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnUsdUpdated);
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnLegacyBridgeReady, int32, TotalQuestions);


UCLASS(ClassGroup=(Custom), meta=(BlueprintSpawnableComponent, DisplayName="UE Bridge", ToolTip="Relay component — delegates to UUEBridgeSubsystem for game flow"))
class TRANSLATORSCARD_API UBridgeComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UBridgeComponent();

    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

    // === LEGACY DELEGATES (Bind in Blueprint) ===

    /** Fired when a new question arrives (raw JSON for backward compat) */
    UPROPERTY(BlueprintAssignable, Category = "UE Bridge", meta = (ToolTip = "Fires when a new question arrives (legacy JSON)"))
    FOnQuestionReceived OnQuestionReceived;

    /** Fired when Python sends a transition command */
    UPROPERTY(BlueprintAssignable, Category = "UE Bridge", meta = (ToolTip = "Fires on scene transitions"))
    FOnTransitionReceived OnTransitionReceived;

    /** Fired when questionnaire completes */
    UPROPERTY(BlueprintAssignable, Category = "UE Bridge", meta = (ToolTip = "Fires when profile is complete"))
    FOnFinaleReceived OnFinaleReceived;

    /** Fired when cognitive_substrate.usda updates */
    UPROPERTY(BlueprintAssignable, Category = "UE Bridge", meta = (ToolTip = "Fires when USD profile file changes"))
    FOnUsdUpdated OnUsdUpdated;

    /** Fired when Python bridge is ready */
    UPROPERTY(BlueprintAssignable, Category = "UE Bridge", meta = (ToolTip = "Fires when Python bridge connects"))
    FOnLegacyBridgeReady OnBridgeReady;

    // === BLUEPRINT CALLABLE (forwarded to subsystem) ===

    /** Send acknowledgment (delegates to subsystem) */
    UFUNCTION(BlueprintCallable, Category = "UE Bridge", meta = (ToolTip = "Send acknowledgment to Python bridge", DeprecatedFunction, DeprecationMessage = "Use UUEBridgeSubsystem::SendAcknowledge instead"))
    void SendAcknowledge();

    /** Send answer (delegates to subsystem) */
    UFUNCTION(BlueprintCallable, Category = "UE Bridge", meta = (ToolTip = "Send answer to Python bridge", DeprecatedFunction, DeprecationMessage = "Use UUEBridgeSubsystem::SubmitAnswer instead"))
    void SendAnswer(const FString& QuestionId, int32 OptionIndex, float ResponseTimeMs);

    /** Get the current question from subsystem */
    UFUNCTION(BlueprintCallable, Category = "UE Bridge", meta = (ToolTip = "Get the currently active question"))
    FUEBridgeQuestion GetCurrentQuestion() const;

    /** Parse cognitive profile (delegates to subsystem) */
    UFUNCTION(BlueprintCallable, Category = "UE Bridge", meta = (ToolTip = "Parse a cognitive profile from a .usda file"))
    FUEBridgeProfile ParseCognitiveProfile(const FString& UsdPath);

    /** Check if bridge is connected */
    UFUNCTION(BlueprintCallable, BlueprintPure, Category = "UE Bridge", meta = (ToolTip = "True if Python bridge is connected"))
    bool IsBridgeConnected() const;

    /** Check if using USD mode */
    UFUNCTION(BlueprintCallable, BlueprintPure, Category = "UE Bridge", meta = (ToolTip = "True if using USD-native transport"))
    bool IsUsingUsdMode() const;

    // === CONFIGURATION ===

    /** Bridge directory path override. Leave empty to use default (~/.translators) */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UE Bridge", meta = (ToolTip = "Path to the bridge exchange directory (empty = default)"))
    FString BridgePath;

    /** Enable verbose logging */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UE Bridge", meta = (ToolTip = "Show detailed bridge logs on screen"))
    bool bVerboseLogging = false;

private:
    /** Cached subsystem pointer (valid between BeginPlay and EndPlay) */
    UPROPERTY()
    TObjectPtr<UUEBridgeSubsystem> BridgeSubsystem;

    // Subsystem delegate handlers
    UFUNCTION()
    void OnSubsystemBridgeReady(int32 TotalQuestions);

    UFUNCTION()
    void OnSubsystemQuestionReady(const FUEBridgeQuestion& Question);

    UFUNCTION()
    void OnSubsystemTransitionReady(const FString& Direction, const FString& NextScene, float Progress);

    UFUNCTION()
    void OnSubsystemProfileComplete(const FUEBridgeProfile& Profile, const FString& UsdPath);

    UFUNCTION()
    void OnSubsystemUsdProfileUpdated(const FString& UpdatedFilePath);
};
