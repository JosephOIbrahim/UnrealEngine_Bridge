// UEBridgeHUD.h
// Main HUD class connecting BridgeComponent to UI widgets
// Part of The UnrealEngine Bridge - Claude Code -> UE5.7 Bridge

#pragma once

#include "CoreMinimal.h"
#include "GameFramework/HUD.h"
#include "../BridgeComponent.h"
#include "UEBridgeHUD.generated.h"

// Forward declarations
class UW_QuestionDisplay;
class UW_TitleScreen;
class UW_FinaleScreen;
class UW_ProgressIndicator;
class UUserWidget;

/**
 * AUEBridgeHUD - Main game HUD
 *
 * Manages the full game flow: Title -> Connecting -> Questions -> Finale
 *
 * Responsibilities:
 * 1. Find and connect to BridgeComponent
 * 2. Create and manage UI widgets
 * 3. Handle BridgeComponent events
 * 4. Track response timing
 * 5. Send answers back to bridge
 * 6. Parse and display cognitive profile on finale
 */
UCLASS()
class TRANSLATORSCARD_API AUEBridgeHUD : public AHUD
{
    GENERATED_BODY()

public:
    AUEBridgeHUD();

    // === CONFIGURATION ===

    /** Widget class for question display (set in Blueprint child) */
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "UEBridge|Config")
    TSubclassOf<UW_QuestionDisplay> QuestionDisplayClass;

    /** Widget class for connecting message */
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "UEBridge|Config")
    TSubclassOf<UUserWidget> ConnectingWidgetClass;

    /** Widget class for finale screen */
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "UEBridge|Config")
    TSubclassOf<UUserWidget> FinaleWidgetClass;

    /** Widget class for title screen */
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category = "UEBridge|Config")
    TSubclassOf<UUserWidget> TitleWidgetClass;

    // === STATE ===

    /** Is the bridge connected? */
    UPROPERTY(BlueprintReadOnly, Category = "UEBridge|State")
    bool bIsBridgeConnected = false;

    /** Is the questionnaire complete? */
    UPROPERTY(BlueprintReadOnly, Category = "UEBridge|State")
    bool bIsComplete = false;

    // === FUNCTIONS ===

    /** Manually trigger acknowledgment (call from Blueprint if needed) */
    UFUNCTION(BlueprintCallable, Category = "UEBridge|Bridge")
    void SendAcknowledgment();

    virtual void Tick(float DeltaSeconds) override;
    virtual void DrawHUD() override;

protected:
    virtual void BeginPlay() override;
    virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;

    // === EVENT HANDLERS ===

    /** Called when bridge is ready */
    UFUNCTION()
    void OnBridgeReady(int32 TotalQuestions);

    /** Called when a question is received */
    UFUNCTION()
    void OnQuestionReceived(const FString& QuestionJson);

    /** Called when transition is received */
    UFUNCTION()
    void OnTransitionReceived(const FString& Direction, const FString& NextScene);

    /** Called when finale is received */
    UFUNCTION()
    void OnFinaleReceived(const FString& UsdPath);

    /** Called when user selects an answer */
    UFUNCTION()
    void OnAnswerSelected(int32 OptionIndex);

    /** Called when user presses Enter on title screen */
    UFUNCTION()
    void OnTitleStartRequested();

    // === WIDGETS ===

    UPROPERTY()
    UW_QuestionDisplay* QuestionWidget;

    UPROPERTY()
    UUserWidget* ConnectingWidget;

    UPROPERTY()
    UUserWidget* FinaleWidget;

    UPROPERTY()
    UW_TitleScreen* TitleWidget;

private:
    /** High-level game screen states */
    enum class EHUDState : uint8
    {
        Title,       // Title screen - waiting for Enter
        Connecting,  // Waiting for bridge connection
        Questions,   // Answering questions
        Finale       // Profile results
    };

    /** Find BridgeComponent in the world */
    UBridgeComponent* FindBridgeComponent();

    /** Create UI widgets */
    void CreateWidgets();

    /** Transition to a new HUD state */
    void SetHUDState(EHUDState NewState);

    /** Show title screen */
    void ShowTitleScreen();

    /** Show connecting message */
    void ShowConnectingScreen();

    /** Hide connecting, show question */
    void ShowQuestionScreen();

    /** Show finale screen */
    void ShowFinaleScreen(const FString& Message);

    /** Update transition animation in Tick */
    void UpdateTransition(float DeltaSeconds);

    /** Reference to bridge component */
    UPROPERTY()
    UBridgeComponent* BridgeComponent;

    /** Handle keyboard input for option selection */
    void HandleKeyInput();

    /** Current HUD state */
    EHUDState CurrentHUDState = EHUDState::Title;

    /** Time when current question was shown */
    float QuestionStartTime = 0.0f;

    /** Current question data */
    FUEBridgeQuestion CurrentQuestion;

    /** Total questions for progress tracking */
    int32 TotalQuestions = 8;

    // === TRANSITION STATE ===

    enum class EHUDTransition : uint8
    {
        None,           // Idle - accepting input
        AnswerHold,     // Brief hold showing selected answer (0.7s)
        FadeOut,        // Fading out question widget (0.3s)
        WaitForNext,    // Waiting for next question from bridge
        FadeIn          // Fading in new question (0.3s)
    };

    EHUDTransition TransitionState = EHUDTransition::None;
    float TransitionTimer = 0.0f;
    int32 PendingAnswerIndex = -1;

    static constexpr float ANSWER_HOLD_TIME = 0.7f;
    static constexpr float FADE_DURATION = 0.3f;
};
