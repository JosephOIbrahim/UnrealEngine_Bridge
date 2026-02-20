// UEBridgeSubsystem.h
// GameInstanceSubsystem that owns the bridge state machine, file I/O,
// USDA/JSON parsing, behavioral signals, and profile generation.
//
// Phase 4: All game flow logic migrated from BridgeComponent.
// BridgeComponent is now a thin actor-component relay for Blueprint binding.

#pragma once

#include "CoreMinimal.h"
#include "Subsystems/GameInstanceSubsystem.h"
#include "Tickable.h"
#include "BridgeTypes.h"
#include "UEBridgeSubsystem.generated.h"

UCLASS()
class TRANSLATORSBRIDGERUNTIME_API UUEBridgeSubsystem
    : public UGameInstanceSubsystem
    , public FTickableGameObject
{
    GENERATED_BODY()

public:
    // === LIFECYCLE ===

    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;

    // FTickableGameObject
    virtual void Tick(float DeltaTime) override;
    virtual TStatId GetStatId() const override;
    virtual bool IsTickable() const override { return bIsActive; }
    virtual bool IsTickableInEditor() const override { return false; }

    // === GAME FLOW ===

    /** Start the bridge: resolve path, create directory, begin polling */
    UFUNCTION(BlueprintCallable, Category = "UE Bridge", meta = (ToolTip = "Start the bridge and begin watching for state files"))
    void StartGame();

    /** Stop the bridge and reset state */
    UFUNCTION(BlueprintCallable, Category = "UE Bridge", meta = (ToolTip = "Stop the bridge and clean up"))
    void StopGame();

    /** Submit a player answer (prefers USD, falls back to JSON) */
    UFUNCTION(BlueprintCallable, Category = "UE Bridge", meta = (ToolTip = "Submit the player's answer for the current question"))
    void SubmitAnswer(const FString& QuestionId, int32 OptionIndex, float ResponseTimeMs);

    /** Send acknowledgment that UE5 is ready (prefers USD, falls back to JSON) */
    UFUNCTION(BlueprintCallable, Category = "UE Bridge", meta = (ToolTip = "Acknowledge readiness to the Python bridge"))
    void SendAcknowledge();

    /** Force reload the USD stage (broadcast for Blueprint handling) */
    UFUNCTION(BlueprintCallable, Category = "UE Bridge", meta = (ToolTip = "Force USD Stage Actor to reload"))
    void ForceReloadUsdStage();

    /** Parse cognitive profile from exported USDA file */
    UFUNCTION(BlueprintCallable, Category = "UE Bridge", meta = (ToolTip = "Parse a cognitive profile from a .usda file"))
    FUEBridgeProfile ParseCognitiveProfile(const FString& UsdPath);

    // === ACCESSORS ===

    /** Get the current bridge state */
    UFUNCTION(BlueprintCallable, BlueprintPure, Category = "UE Bridge", meta = (ToolTip = "Get the current bridge state machine state"))
    EUEBridgeState GetBridgeState() const { return CurrentState; }

    /** Get the currently active question */
    UFUNCTION(BlueprintCallable, BlueprintPure, Category = "UE Bridge", meta = (ToolTip = "Get the currently active question data"))
    FUEBridgeQuestion GetCurrentQuestion() const { return CurrentQuestion; }

    /** Get accumulated behavioral signals */
    UFUNCTION(BlueprintCallable, BlueprintPure, Category = "UE Bridge", meta = (ToolTip = "Get accumulated behavioral signals for MoE routing"))
    FBehavioralSignals GetBehavioralSignals() const { return Signals; }

    /** Check if bridge is connected to the Python side */
    UFUNCTION(BlueprintCallable, BlueprintPure, Category = "UE Bridge", meta = (ToolTip = "True if bridge is connected to the Python backend"))
    bool IsBridgeConnected() const { return CurrentState != EUEBridgeState::Idle && CurrentState != EUEBridgeState::Error; }

    /** Check if using USD mode (v2.0.0) */
    UFUNCTION(BlueprintCallable, BlueprintPure, Category = "UE Bridge", meta = (ToolTip = "True if using USD-native transport mode"))
    bool IsUsingUsdMode() const { return bUsingUsdMode; }

    /** Get the bridge exchange directory path */
    UFUNCTION(BlueprintCallable, BlueprintPure, Category = "UE Bridge", meta = (ToolTip = "Get the bridge exchange directory path"))
    FString GetBridgePath() const { return BridgePath; }

    // === DELEGATES ===

    /** Fired when Python bridge_orchestrator signals ready */
    UPROPERTY(BlueprintAssignable, Category = "UE Bridge|Events")
    FOnBridgeReady OnBridgeReady;

    /** Fired when a new question arrives (fully parsed) */
    UPROPERTY(BlueprintAssignable, Category = "UE Bridge|Events")
    FOnQuestionReady OnQuestionReady;

    /** Fired during scene transitions */
    UPROPERTY(BlueprintAssignable, Category = "UE Bridge|Events")
    FOnTransitionReady OnTransitionReady;

    /** Fired when the cognitive profile is complete */
    UPROPERTY(BlueprintAssignable, Category = "UE Bridge|Events")
    FOnProfileComplete OnProfileComplete;

    /** Fired on any bridge error */
    UPROPERTY(BlueprintAssignable, Category = "UE Bridge|Events")
    FOnBridgeError OnBridgeError;

    /** Fired when a USD profile file changes on disk */
    UPROPERTY(BlueprintAssignable, Category = "UE Bridge|Events")
    FOnUsdProfileUpdated OnUsdProfileUpdated;

    // === CONFIGURATION ===

    /** Debounce time in seconds for file change detection */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UE Bridge|Config", meta = (ClampMin = "0.01", ClampMax = "1.0"))
    float DebounceTime = 0.05f;

    /** Polling interval in seconds */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UE Bridge|Config", meta = (ClampMin = "0.1", ClampMax = "5.0"))
    float PollInterval = 0.5f;

    /** Enable verbose logging */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UE Bridge|Config")
    bool bVerboseLogging = false;

    /** Notify the subsystem that a file in the bridge directory changed.
     *  Called by BridgeEditorSubsystem in editor builds or by external code. */
    void NotifyFileChanged(const FString& Filename, bool bIsUsdProfile);

private:
    // === STATE ===

    void SetState(EUEBridgeState NewState);
    FString ResolveBridgePath() const;
    FString GetBridgeFilePath(const FString& Filename) const;
    void BridgeLog(const FString& Message) const;

    // === FILE I/O ===

    void ProcessStateFile();
    void WriteJsonToFile(const FString& Filename, const TSharedPtr<FJsonObject>& JsonObj);

    // === JSON STATE HANDLERS ===

    void HandleReadyState(const TSharedPtr<FJsonObject>& JsonObj);
    void HandleQuestionState(const TSharedPtr<FJsonObject>& JsonObj);
    void HandleTransitionState(const TSharedPtr<FJsonObject>& JsonObj);
    void HandleFinaleState(const TSharedPtr<FJsonObject>& JsonObj);

    // === USD NATIVE COMMUNICATION (v2.0.0) ===

    bool ProcessBridgeStateUsda();
    FString ParseUsdaVariant(const FString& Content, const FString& VariantSetName);
    FString ParseUsdaAttribute(const FString& Content, const FString& PrimPath, const FString& AttrName);
    void HandleUsdaReadyState(const FString& Content);
    void HandleUsdaQuestionState(const FString& Content);
    void HandleUsdaTransitionState(const FString& Content);
    void HandleUsdaFinaleState(const FString& Content);
    FString BuildQuestionJson();
    FString UpdateUsdaVariant(const FString& Content, const FString& VariantSetName, const FString& NewValue);
    FString UpdateUsdaAttribute(const FString& Content, const FString& PrimName, const FString& AttrName, const FString& NewValue, bool bIsString);

    // === BEHAVIORAL SIGNALS ===

    void UpdateBehavioralSignals(FString& Content, float ResponseTimeMs);

    // === DEPTH LABELS ===

    static FString GetDepthLabelForIndex(int32 Index);

    // === INTERNAL STATE ===

    EUEBridgeState CurrentState = EUEBridgeState::Idle;
    FUEBridgeQuestion CurrentQuestion;
    FBehavioralSignals Signals;
    FString BridgePath;
    FString CurrentStateJson;
    bool bIsActive = false;
    bool bUsingUsdMode = false;

    // Response time history for behavioral signal computation
    TArray<float> ResponseTimes;

    // Debouncing
    float TimeSinceLastStateChange = 0.0f;
    bool bStateChangePending = false;
    float TimeSinceLastUsdChange = 0.0f;
    bool bUsdChangePending = false;

    // Polling
    float PollTimer = 0.0f;
    FDateTime LastStateFileTime;
    FDateTime LastUsdFileTime;
};
