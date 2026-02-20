// BridgeComponent.cpp
// Phase 4: Thin relay — all game flow logic lives in UUEBridgeSubsystem.
// This component binds subsystem delegates to legacy component delegates
// so existing Blueprints continue to work without modification.

#include "BridgeComponent.h"
#include "UEBridgeRuntime.h"
#include "UEBridgeSubsystem.h"
#include "BridgeTypes.h"
#include "Engine/GameInstance.h"


UBridgeComponent::UBridgeComponent()
{
    PrimaryComponentTick.bCanEverTick = false; // No longer needs tick — subsystem handles polling
}


void UBridgeComponent::BeginPlay()
{
    Super::BeginPlay();

    // Get the subsystem
    UGameInstance* GI = GetWorld() ? GetWorld()->GetGameInstance() : nullptr;
    if (GI)
    {
        BridgeSubsystem = GI->GetSubsystem<UUEBridgeSubsystem>();
    }

    if (!BridgeSubsystem)
    {
        UE_LOG(LogUEBridge, Error, TEXT("[BridgeComponent] Could not find UUEBridgeSubsystem — is the UEBridge plugin enabled?"));
        return;
    }

    // Forward config overrides to subsystem
    BridgeSubsystem->bVerboseLogging = bVerboseLogging;

    // Bind subsystem delegates to our legacy delegates
    BridgeSubsystem->OnBridgeReady.AddDynamic(this, &UBridgeComponent::OnSubsystemBridgeReady);
    BridgeSubsystem->OnQuestionReady.AddDynamic(this, &UBridgeComponent::OnSubsystemQuestionReady);
    BridgeSubsystem->OnTransitionReady.AddDynamic(this, &UBridgeComponent::OnSubsystemTransitionReady);
    BridgeSubsystem->OnProfileComplete.AddDynamic(this, &UBridgeComponent::OnSubsystemProfileComplete);
    BridgeSubsystem->OnUsdProfileUpdated.AddDynamic(this, &UBridgeComponent::OnSubsystemUsdProfileUpdated);

    // Start the bridge
    BridgeSubsystem->StartGame();
}


void UBridgeComponent::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    if (BridgeSubsystem)
    {
        // Unbind our delegates
        BridgeSubsystem->OnBridgeReady.RemoveDynamic(this, &UBridgeComponent::OnSubsystemBridgeReady);
        BridgeSubsystem->OnQuestionReady.RemoveDynamic(this, &UBridgeComponent::OnSubsystemQuestionReady);
        BridgeSubsystem->OnTransitionReady.RemoveDynamic(this, &UBridgeComponent::OnSubsystemTransitionReady);
        BridgeSubsystem->OnProfileComplete.RemoveDynamic(this, &UBridgeComponent::OnSubsystemProfileComplete);
        BridgeSubsystem->OnUsdProfileUpdated.RemoveDynamic(this, &UBridgeComponent::OnSubsystemUsdProfileUpdated);

        BridgeSubsystem->StopGame();
        BridgeSubsystem = nullptr;
    }

    Super::EndPlay(EndPlayReason);
}


// === BLUEPRINT CALLABLE (forwarded to subsystem) ===

void UBridgeComponent::SendAcknowledge()
{
    if (BridgeSubsystem)
    {
        BridgeSubsystem->SendAcknowledge();
    }
}


void UBridgeComponent::SendAnswer(const FString& QuestionId, int32 OptionIndex, float ResponseTimeMs)
{
    if (BridgeSubsystem)
    {
        BridgeSubsystem->SubmitAnswer(QuestionId, OptionIndex, ResponseTimeMs);
    }
}


FUEBridgeQuestion UBridgeComponent::GetCurrentQuestion() const
{
    return BridgeSubsystem ? BridgeSubsystem->GetCurrentQuestion() : FUEBridgeQuestion();
}


FUEBridgeProfile UBridgeComponent::ParseCognitiveProfile(const FString& UsdPath)
{
    return BridgeSubsystem ? BridgeSubsystem->ParseCognitiveProfile(UsdPath) : FUEBridgeProfile();
}


bool UBridgeComponent::IsBridgeConnected() const
{
    return BridgeSubsystem ? BridgeSubsystem->IsBridgeConnected() : false;
}


bool UBridgeComponent::IsUsingUsdMode() const
{
    return BridgeSubsystem ? BridgeSubsystem->IsUsingUsdMode() : false;
}


// === SUBSYSTEM DELEGATE HANDLERS ===

void UBridgeComponent::OnSubsystemBridgeReady(int32 TotalQuestions)
{
    OnBridgeReady.Broadcast(TotalQuestions);
}


void UBridgeComponent::OnSubsystemQuestionReady(const FUEBridgeQuestion& Question)
{
    // Build legacy JSON string for backward-compatible delegate
    FString QuestionJson = FString::Printf(
        TEXT("{\"type\":\"question\",\"index\":%d,\"total\":%d,\"id\":\"%s\",\"text\":\"%s\",\"scene\":\"%s\"}"),
        Question.Index, Question.Total, *Question.QuestionId, *Question.Text, *Question.Scene);

    OnQuestionReceived.Broadcast(QuestionJson);
}


void UBridgeComponent::OnSubsystemTransitionReady(const FString& Direction, const FString& NextScene, float Progress)
{
    OnTransitionReceived.Broadcast(Direction, NextScene);
}


void UBridgeComponent::OnSubsystemProfileComplete(const FUEBridgeProfile& Profile, const FString& UsdPath)
{
    OnFinaleReceived.Broadcast(UsdPath);
}


void UBridgeComponent::OnSubsystemUsdProfileUpdated(const FString& UpdatedFilePath)
{
    OnUsdUpdated.Broadcast();
}
