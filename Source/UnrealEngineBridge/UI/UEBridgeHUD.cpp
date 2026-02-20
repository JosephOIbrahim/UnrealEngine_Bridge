// UEBridgeHUD.cpp
// Implementation of main game HUD with title screen and profile display
// Programmatic UI - no Blueprint required

#include "UEBridgeHUD.h"
#include "UEBridgeRuntime.h"
#include "W_QuestionDisplay.h"
#include "W_ProgressIndicator.h"
#include "W_ConnectingScreen.h"
#include "W_FinaleScreen.h"
#include "W_TitleScreen.h"
#include "../BridgeComponent.h"
#include "Blueprint/UserWidget.h"
#include "Kismet/GameplayStatics.h"
#include "Engine/World.h"
#include "GameFramework/Actor.h"
#include "GameFramework/PlayerController.h"
#include "InputCoreTypes.h"
#include "Engine/Canvas.h"


AUEBridgeHUD::AUEBridgeHUD()
{
    bIsBridgeConnected = false;
    bIsComplete = false;
    TotalQuestions = 8;
    CurrentHUDState = EHUDState::Title;
}


void AUEBridgeHUD::BeginPlay()
{
    Super::BeginPlay();

    UE_LOG(LogUEBridge, Log, TEXT("[UEBridgeHUD] BeginPlay - Initializing..."));

    // Find BridgeComponent
    BridgeComponent = FindBridgeComponent();

    if (BridgeComponent)
    {
        UE_LOG(LogUEBridge, Log, TEXT("[UEBridgeHUD] Found BridgeComponent - binding events"));

        BridgeComponent->OnBridgeReady.AddDynamic(this, &AUEBridgeHUD::OnBridgeReady);
        BridgeComponent->OnQuestionReceived.AddDynamic(this, &AUEBridgeHUD::OnQuestionReceived);
        BridgeComponent->OnTransitionReceived.AddDynamic(this, &AUEBridgeHUD::OnTransitionReceived);
        BridgeComponent->OnFinaleReceived.AddDynamic(this, &AUEBridgeHUD::OnFinaleReceived);
    }
    else
    {
        UE_LOG(LogUEBridge, Warning, TEXT("[UEBridgeHUD] BridgeComponent not found in level!"));
    }

    // Create UI widgets
    CreateWidgets();

    // Start on title screen
    SetHUDState(EHUDState::Title);
}


void AUEBridgeHUD::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (BridgeComponent)
    {
        BridgeComponent->OnBridgeReady.RemoveAll(this);
        BridgeComponent->OnQuestionReceived.RemoveAll(this);
        BridgeComponent->OnTransitionReceived.RemoveAll(this);
        BridgeComponent->OnFinaleReceived.RemoveAll(this);
    }

    if (QuestionWidget)
    {
        QuestionWidget->OnAnswerSelected.RemoveAll(this);
        QuestionWidget->RemoveFromParent();
    }
    if (ConnectingWidget)
    {
        ConnectingWidget->RemoveFromParent();
    }
    if (FinaleWidget)
    {
        FinaleWidget->RemoveFromParent();
    }
    if (TitleWidget)
    {
        TitleWidget->OnStartRequested.RemoveAll(this);
        TitleWidget->RemoveFromParent();
    }

    Super::EndPlay(EndPlayReason);
}


UBridgeComponent* AUEBridgeHUD::FindBridgeComponent()
{
    TArray<AActor*> AllActors;
    UGameplayStatics::GetAllActorsOfClass(GetWorld(), AActor::StaticClass(), AllActors);

    for (AActor* Actor : AllActors)
    {
        UBridgeComponent* Bridge = Actor->FindComponentByClass<UBridgeComponent>();
        if (Bridge)
        {
            return Bridge;
        }
    }

    // Fallback: spawn a dedicated actor with BridgeComponent
    UE_LOG(LogUEBridge, Log, TEXT("[UEBridgeHUD] No BridgeComponent found - spawning BridgeActor"));
    UWorld* World = GetWorld();
    if (World)
    {
        FActorSpawnParameters SpawnParams;
        SpawnParams.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
        AActor* BridgeActor = World->SpawnActor<AActor>(AActor::StaticClass(), FVector::ZeroVector, FRotator::ZeroRotator, SpawnParams);
        if (BridgeActor)
        {
            UBridgeComponent* Bridge = NewObject<UBridgeComponent>(BridgeActor, TEXT("BridgeComponent"));
            Bridge->bVerboseLogging = true;
            BridgeActor->AddInstanceComponent(Bridge);
            Bridge->RegisterComponent();
            return Bridge;
        }
    }

    return nullptr;
}


void AUEBridgeHUD::CreateWidgets()
{
    APlayerController* PC = GetOwningPlayerController();
    if (!PC)
    {
        UE_LOG(LogUEBridge, Warning, TEXT("[UEBridgeHUD] No PlayerController - cannot create widgets"));
        return;
    }

    // Create title screen widget (z-order 40 - on top of everything)
    if (TitleWidgetClass)
    {
        TitleWidget = CreateWidget<UW_TitleScreen>(PC, TitleWidgetClass);
    }
    else
    {
        TitleWidget = CreateWidget<UW_TitleScreen>(PC, UW_TitleScreen::StaticClass());
    }
    if (TitleWidget)
    {
        TitleWidget->AddToViewport(40);
        TitleWidget->OnStartRequested.AddDynamic(this, &AUEBridgeHUD::OnTitleStartRequested);
        UE_LOG(LogUEBridge, Log, TEXT("[UEBridgeHUD] Created TitleWidget"));
    }

    // Create question display widget
    if (QuestionDisplayClass)
    {
        QuestionWidget = CreateWidget<UW_QuestionDisplay>(PC, QuestionDisplayClass);
    }
    else
    {
        QuestionWidget = CreateWidget<UW_QuestionDisplay>(PC, UW_QuestionDisplay::StaticClass());
    }
    if (QuestionWidget)
    {
        QuestionWidget->AddToViewport(10);
        QuestionWidget->SetVisibility(ESlateVisibility::Hidden);
        QuestionWidget->SetRenderOpacity(0.0f);
        QuestionWidget->OnAnswerSelected.AddDynamic(this, &AUEBridgeHUD::OnAnswerSelected);
        UE_LOG(LogUEBridge, Log, TEXT("[UEBridgeHUD] Created QuestionWidget"));
    }

    // Create connecting widget
    if (ConnectingWidgetClass)
    {
        ConnectingWidget = CreateWidget<UUserWidget>(PC, ConnectingWidgetClass);
    }
    else
    {
        ConnectingWidget = CreateWidget<UW_ConnectingScreen>(PC, UW_ConnectingScreen::StaticClass());
    }
    if (ConnectingWidget)
    {
        ConnectingWidget->AddToViewport(20);
        ConnectingWidget->SetVisibility(ESlateVisibility::Hidden);
        UE_LOG(LogUEBridge, Log, TEXT("[UEBridgeHUD] Created ConnectingWidget"));
    }

    // Create finale widget
    if (FinaleWidgetClass)
    {
        FinaleWidget = CreateWidget<UUserWidget>(PC, FinaleWidgetClass);
    }
    else
    {
        FinaleWidget = CreateWidget<UW_FinaleScreen>(PC, UW_FinaleScreen::StaticClass());
    }
    if (FinaleWidget)
    {
        FinaleWidget->AddToViewport(30);
        FinaleWidget->SetVisibility(ESlateVisibility::Hidden);
        FinaleWidget->SetRenderOpacity(0.0f);
        UE_LOG(LogUEBridge, Log, TEXT("[UEBridgeHUD] Created FinaleWidget"));
    }
}


// === STATE MANAGEMENT ===

void AUEBridgeHUD::SetHUDState(EHUDState NewState)
{
    UE_LOG(LogUEBridge, Log, TEXT("[UEBridgeHUD] State transition: %d -> %d"), (uint8)CurrentHUDState, (uint8)NewState);
    CurrentHUDState = NewState;

    switch (NewState)
    {
    case EHUDState::Title:
        ShowTitleScreen();
        break;
    case EHUDState::Connecting:
        ShowConnectingScreen();
        break;
    case EHUDState::Questions:
        ShowQuestionScreen();
        break;
    case EHUDState::Finale:
        // ShowFinaleScreen is called directly with message
        break;
    }
}


void AUEBridgeHUD::ShowTitleScreen()
{
    if (TitleWidget)
    {
        TitleWidget->SetVisibility(ESlateVisibility::Visible);
        TitleWidget->SetRenderOpacity(1.0f);
    }
    if (ConnectingWidget)
    {
        ConnectingWidget->SetVisibility(ESlateVisibility::Hidden);
    }
    if (QuestionWidget)
    {
        QuestionWidget->SetVisibility(ESlateVisibility::Hidden);
    }
    if (FinaleWidget)
    {
        FinaleWidget->SetVisibility(ESlateVisibility::Hidden);
    }

    // Use GameAndUI input mode so PC->WasInputKeyJustPressed works for Enter detection
    APlayerController* PC = GetOwningPlayerController();
    if (PC)
    {
        FInputModeGameAndUI InputMode;
        InputMode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
        PC->SetInputMode(InputMode);
        PC->bShowMouseCursor = false;
    }
}


void AUEBridgeHUD::ShowConnectingScreen()
{
    if (TitleWidget)
    {
        TitleWidget->SetVisibility(ESlateVisibility::Hidden);
    }
    if (ConnectingWidget)
    {
        ConnectingWidget->SetVisibility(ESlateVisibility::Visible);
        ConnectingWidget->SetRenderOpacity(1.0f);
    }
    if (QuestionWidget)
    {
        QuestionWidget->SetVisibility(ESlateVisibility::Hidden);
    }
    if (FinaleWidget)
    {
        FinaleWidget->SetVisibility(ESlateVisibility::Hidden);
    }
}


void AUEBridgeHUD::ShowQuestionScreen()
{
    if (TitleWidget)
    {
        TitleWidget->SetVisibility(ESlateVisibility::Hidden);
    }
    if (ConnectingWidget)
    {
        ConnectingWidget->SetVisibility(ESlateVisibility::Hidden);
    }
    if (QuestionWidget)
    {
        QuestionWidget->SetVisibility(ESlateVisibility::Visible);
    }
    if (FinaleWidget)
    {
        FinaleWidget->SetVisibility(ESlateVisibility::Hidden);
    }

    // Enable mouse cursor for UI interaction
    APlayerController* PC = GetOwningPlayerController();
    if (PC)
    {
        PC->bShowMouseCursor = true;
        FInputModeGameAndUI InputMode;
        InputMode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
        PC->SetInputMode(InputMode);
    }
}


void AUEBridgeHUD::ShowFinaleScreen(const FString& Message)
{
    TransitionState = EHUDTransition::None;
    CurrentHUDState = EHUDState::Finale;

    if (TitleWidget)
    {
        TitleWidget->SetVisibility(ESlateVisibility::Hidden);
    }
    if (ConnectingWidget)
    {
        ConnectingWidget->SetVisibility(ESlateVisibility::Hidden);
    }
    if (QuestionWidget)
    {
        QuestionWidget->SetVisibility(ESlateVisibility::Hidden);
    }
    if (FinaleWidget)
    {
        FinaleWidget->SetVisibility(ESlateVisibility::Visible);
        FinaleWidget->SetRenderOpacity(1.0f);
    }
}


void AUEBridgeHUD::SendAcknowledgment()
{
    if (BridgeComponent)
    {
        BridgeComponent->SendAcknowledge();
        UE_LOG(LogUEBridge, Log, TEXT("[UEBridgeHUD] Sent acknowledgment"));
    }
}


// === EVENT HANDLERS ===

void AUEBridgeHUD::OnTitleStartRequested()
{
    UE_LOG(LogUEBridge, Log, TEXT("[UEBridgeHUD] Title -> Connecting"));
    SetHUDState(EHUDState::Connecting);

    // If bridge is already connected (orchestrator started before Enter was pressed)
    if (BridgeComponent && BridgeComponent->IsBridgeConnected())
    {
        OnBridgeReady(TotalQuestions);
    }
}


void AUEBridgeHUD::OnBridgeReady(int32 InTotalQuestions)
{
    UE_LOG(LogUEBridge, Log, TEXT("[UEBridgeHUD] Bridge ready! Total questions: %d"), InTotalQuestions);

    bIsBridgeConnected = true;
    TotalQuestions = InTotalQuestions;

    SendAcknowledgment();

    // If still on title, don't auto-transition (wait for Enter)
    // If on connecting, check for existing question
    if (CurrentHUDState == EHUDState::Connecting)
    {
        FUEBridgeQuestion Q = BridgeComponent->GetCurrentQuestion();
        if (!Q.QuestionId.IsEmpty())
        {
            UE_LOG(LogUEBridge, Log, TEXT("[UEBridgeHUD] Catching up - bridge already has question: %s"), *Q.QuestionId);
            CurrentQuestion = Q;
            QuestionStartTime = GetWorld()->GetTimeSeconds();
            if (QuestionWidget)
            {
                QuestionWidget->ShowQuestion(CurrentQuestion);
                QuestionWidget->SetRenderOpacity(1.0f);
            }
            SetHUDState(EHUDState::Questions);
        }
    }
}


void AUEBridgeHUD::OnQuestionReceived(const FString& QuestionJson)
{
    UE_LOG(LogUEBridge, Log, TEXT("[UEBridgeHUD] Question received"));

    if (!BridgeComponent)
    {
        return;
    }

    CurrentQuestion = BridgeComponent->GetCurrentQuestion();
    QuestionStartTime = GetWorld()->GetTimeSeconds();

    // Load question content into widget
    if (QuestionWidget)
    {
        QuestionWidget->ShowQuestion(CurrentQuestion);
    }

    // If we're still on connecting/title, transition to questions
    if (CurrentHUDState == EHUDState::Connecting || CurrentHUDState == EHUDState::Title)
    {
        if (QuestionWidget)
        {
            QuestionWidget->SetRenderOpacity(1.0f);
        }
        SetHUDState(EHUDState::Questions);
    }
    // If we're waiting for next question (mid-transition), start fade-in
    else if (TransitionState == EHUDTransition::WaitForNext)
    {
        TransitionState = EHUDTransition::FadeIn;
        TransitionTimer = 0.0f;
        ShowQuestionScreen();
        if (QuestionWidget)
        {
            QuestionWidget->SetRenderOpacity(0.0f);
        }
    }
    else
    {
        // Already in questions state, show immediately
        ShowQuestionScreen();
        if (QuestionWidget)
        {
            QuestionWidget->SetRenderOpacity(1.0f);
        }
    }

    // Debug overlay
    if (GEngine)
    {
        GEngine->AddOnScreenDebugMessage(1, 15.0f, FColor::Green,
            FString::Printf(TEXT("Q%d/%d [%s]: %s"),
                CurrentQuestion.Index + 1, CurrentQuestion.Total,
                *CurrentQuestion.DepthLabel, *CurrentQuestion.QuestionId));
    }

    UE_LOG(LogUEBridge, Log, TEXT("[UEBridgeHUD] Displaying question %d/%d [%s]: %s"),
        CurrentQuestion.Index + 1, CurrentQuestion.Total,
        *CurrentQuestion.DepthLabel, *CurrentQuestion.QuestionId);
}


void AUEBridgeHUD::OnTransitionReceived(const FString& Direction, const FString& NextScene)
{
    UE_LOG(LogUEBridge, Log, TEXT("[UEBridgeHUD] Transition: %s -> %s"), *Direction, *NextScene);

    if (GEngine)
    {
        GEngine->AddOnScreenDebugMessage(2, 3.0f, FColor::Cyan,
            FString::Printf(TEXT("-> %s"), *NextScene));
    }
}


void AUEBridgeHUD::OnFinaleReceived(const FString& UsdPath)
{
    UE_LOG(LogUEBridge, Log, TEXT("[UEBridgeHUD] Finale! USD path: %s"), *UsdPath);

    bIsComplete = true;

    UW_FinaleScreen* FinaleScreen = Cast<UW_FinaleScreen>(FinaleWidget);
    if (FinaleScreen)
    {
        FinaleScreen->SetUsdPath(UsdPath);

        // Parse and display the cognitive profile
        if (BridgeComponent)
        {
            FUEBridgeProfile Profile = BridgeComponent->ParseCognitiveProfile(UsdPath);
            if (Profile.IsValid())
            {
                FinaleScreen->DisplayProfile(Profile);
            }
        }
    }

    ShowFinaleScreen(TEXT("Your cognitive profile is complete."));
}


// === HUD CANVAS DRAWING (bypasses UMG - fallback overlay) ===

void AUEBridgeHUD::DrawHUD()
{
    Super::DrawHUD();

    // The UMG widgets handle the primary UI. This DrawHUD provides
    // a minimal fallback overlay for debugging.

    if (!Canvas)
    {
        return;
    }

    // Only draw debug info if in question state
    if (CurrentHUDState == EHUDState::Questions && !CurrentQuestion.QuestionId.IsEmpty())
    {
        // Small debug text in top-left
        FString DebugStr = FString::Printf(TEXT("Q%d/%d [%s]"),
            CurrentQuestion.Index + 1, CurrentQuestion.Total, *CurrentQuestion.DepthLabel);
        DrawText(DebugStr, FColor(80, 80, 100), 10, 10);
    }
}


// === TICK & TRANSITIONS ===

void AUEBridgeHUD::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    UpdateTransition(DeltaSeconds);
    HandleKeyInput();
}


void AUEBridgeHUD::UpdateTransition(float DeltaSeconds)
{
    if (TransitionState == EHUDTransition::None)
    {
        return;
    }

    TransitionTimer += DeltaSeconds;

    switch (TransitionState)
    {
    case EHUDTransition::AnswerHold:
    {
        if (TransitionTimer >= ANSWER_HOLD_TIME)
        {
            // Now send the answer to bridge
            if (BridgeComponent && PendingAnswerIndex >= 0)
            {
                float ResponseTimeMs = (GetWorld()->GetTimeSeconds() - QuestionStartTime) * 1000.0f;
                BridgeComponent->SendAnswer(CurrentQuestion.QuestionId, PendingAnswerIndex, ResponseTimeMs);
                UE_LOG(LogUEBridge, Log, TEXT("[UEBridgeHUD] Sent deferred answer: option %d (%.0fms)"), PendingAnswerIndex, ResponseTimeMs);
                PendingAnswerIndex = -1;
            }

            TransitionState = EHUDTransition::FadeOut;
            TransitionTimer = 0.0f;
        }
        break;
    }

    case EHUDTransition::FadeOut:
    {
        float Alpha = FMath::Clamp(1.0f - (TransitionTimer / FADE_DURATION), 0.0f, 1.0f);
        if (QuestionWidget)
        {
            QuestionWidget->SetRenderOpacity(Alpha);
        }

        if (TransitionTimer >= FADE_DURATION)
        {
            if (QuestionWidget)
            {
                QuestionWidget->SetRenderOpacity(0.0f);
            }
            TransitionState = EHUDTransition::WaitForNext;
            TransitionTimer = 0.0f;
        }
        break;
    }

    case EHUDTransition::WaitForNext:
    {
        // Safety timeout
        if (TransitionTimer > 10.0f)
        {
            UE_LOG(LogUEBridge, Warning, TEXT("[UEBridgeHUD] Transition timeout - returning to visible"));
            if (QuestionWidget)
            {
                QuestionWidget->SetRenderOpacity(1.0f);
            }
            TransitionState = EHUDTransition::None;
        }
        break;
    }

    case EHUDTransition::FadeIn:
    {
        float Alpha = FMath::Clamp(TransitionTimer / FADE_DURATION, 0.0f, 1.0f);
        if (QuestionWidget)
        {
            QuestionWidget->SetRenderOpacity(Alpha);
        }

        if (TransitionTimer >= FADE_DURATION)
        {
            if (QuestionWidget)
            {
                QuestionWidget->SetRenderOpacity(1.0f);
            }
            TransitionState = EHUDTransition::None;
            QuestionStartTime = GetWorld()->GetTimeSeconds();
        }
        break;
    }

    default:
        break;
    }
}


void AUEBridgeHUD::HandleKeyInput()
{
    APlayerController* PC = GetOwningPlayerController();
    if (!PC)
    {
        return;
    }

    // Title state: Enter or Space to start
    if (CurrentHUDState == EHUDState::Title)
    {
        if (PC->WasInputKeyJustPressed(EKeys::Enter) || PC->WasInputKeyJustPressed(EKeys::SpaceBar))
        {
            OnTitleStartRequested();
        }
        return;
    }

    // Only accept number key input during question state with no transition
    if (CurrentHUDState != EHUDState::Questions)
    {
        return;
    }

    if (TransitionState != EHUDTransition::None)
    {
        return;
    }

    if (!QuestionWidget || QuestionWidget->GetVisibility() != ESlateVisibility::Visible)
    {
        return;
    }
    if (QuestionWidget->GetSelectedOptionIndex() != -1)
    {
        return;
    }

    // Guard: ignore input for 0.5s after question appears
    float TimeSinceQuestion = GetWorld()->GetTimeSeconds() - QuestionStartTime;
    if (TimeSinceQuestion < 0.5f)
    {
        return;
    }

    if (PC->WasInputKeyJustPressed(EKeys::One) || PC->WasInputKeyJustPressed(EKeys::NumPadOne))
    {
        OnAnswerSelected(0);
    }
    else if (PC->WasInputKeyJustPressed(EKeys::Two) || PC->WasInputKeyJustPressed(EKeys::NumPadTwo))
    {
        OnAnswerSelected(1);
    }
    else if (PC->WasInputKeyJustPressed(EKeys::Three) || PC->WasInputKeyJustPressed(EKeys::NumPadThree))
    {
        OnAnswerSelected(2);
    }
}


void AUEBridgeHUD::OnAnswerSelected(int32 OptionIndex)
{
    if (TransitionState != EHUDTransition::None)
    {
        return;
    }

    UE_LOG(LogUEBridge, Log, TEXT("[UEBridgeHUD] Answer selected: option %d"), OptionIndex);

    PendingAnswerIndex = OptionIndex;
    TransitionState = EHUDTransition::AnswerHold;
    TransitionTimer = 0.0f;
}
