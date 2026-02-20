// W_TitleScreen.cpp
// Implementation of title screen widget
// Programmatic UI - no Blueprint required

#include "W_TitleScreen.h"
#include "UEBridgeRuntime.h"
#include "Components/TextBlock.h"
#include "Components/Border.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Components/Spacer.h"
#include "Blueprint/WidgetTree.h"
#include "Misc/Paths.h"
#include "EnhancedInputComponent.h"
#include "UEBridgeStyle.h"
#include "EnhancedInputSubsystems.h"
#include "InputAction.h"
#include "InputActionValue.h"


UW_TitleScreen::UW_TitleScreen(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
{
    // Dark background matching the game aesthetic
    BackgroundColor = FUEBridgeStyle::GetColor("Color.BackgroundSolid");
    TitleColor = FUEBridgeStyle::GetColor("Color.Cyan");
    SubtitleColor = FUEBridgeStyle::GetColor("Color.TextDim");
    PromptColor = FUEBridgeStyle::GetColor("Color.CyanDim");

    // Widget must be focusable to receive key events
    SetIsFocusable(true);
}


TSharedRef<SWidget> UW_TitleScreen::RebuildWidget()
{
    if (!TitleText)
    {
        BuildWidgetTree();
    }
    return Super::RebuildWidget();
}


void UW_TitleScreen::NativeConstruct()
{
    Super::NativeConstruct();

    // Apply colors
    if (BackgroundBorder)
    {
        BackgroundBorder->SetBrushColor(BackgroundColor);
    }
    if (TitleText)
    {
        TitleText->SetColorAndOpacity(FSlateColor(TitleColor));
    }
    if (SubtitleText)
    {
        SubtitleText->SetColorAndOpacity(FSlateColor(SubtitleColor));
    }
    if (PromptText)
    {
        PromptText->SetColorAndOpacity(FSlateColor(PromptColor));
    }

    // Request keyboard focus so we can receive Enter key
    SetKeyboardFocus();

    // Optionally bind Enhanced Input action (if configured by designer)
    if (StartInputAction)
    {
        if (APlayerController* PC = GetOwningPlayer())
        {
            if (UEnhancedInputComponent* EIC = Cast<UEnhancedInputComponent>(PC->InputComponent))
            {
                EIC->BindAction(StartInputAction, ETriggerEvent::Started, this, &UW_TitleScreen::HandleStartAction);
                UE_LOG(LogUEBridge, Log, TEXT("[W_TitleScreen] Bound StartInputAction via Enhanced Input"));
            }
        }
    }

    UE_LOG(LogUEBridge, Log, TEXT("[W_TitleScreen] Constructed (Programmatic UI)"));
}


void UW_TitleScreen::NativeTick(const FGeometry& MyGeometry, float InDeltaTime)
{
    Super::NativeTick(MyGeometry, InDeltaTime);

    // Pulse the "Press ENTER to begin" text opacity
    PulseTimer += InDeltaTime;
    if (PromptText)
    {
        // Sine wave oscillation between 0.3 and 1.0
        float Alpha = 0.3f + 0.7f * (0.5f + 0.5f * FMath::Sin(PulseTimer * 2.5f));
        PromptText->SetRenderOpacity(Alpha);
    }
}


FReply UW_TitleScreen::NativeOnKeyDown(const FGeometry& InGeometry, const FKeyEvent& InKeyEvent)
{
    if (!bStartRequested)
    {
        FKey Key = InKeyEvent.GetKey();
        if (Key == EKeys::Enter || Key == EKeys::SpaceBar)
        {
            bStartRequested = true;
            UE_LOG(LogUEBridge, Log, TEXT("[W_TitleScreen] Start requested!"));
            OnStartRequested.Broadcast();
            return FReply::Handled();
        }
    }

    return Super::NativeOnKeyDown(InGeometry, InKeyEvent);
}


void UW_TitleScreen::HandleStartAction(const FInputActionValue& Value)
{
    if (!bStartRequested)
    {
        bStartRequested = true;
        UE_LOG(LogUEBridge, Log, TEXT("[W_TitleScreen] Start requested via Enhanced Input!"));
        OnStartRequested.Broadcast();
    }
}


void UW_TitleScreen::BuildWidgetTree()
{
    // Simple structure: Border (root, fills viewport) -> centered VerticalBox -> TextBlocks
    // Avoids CanvasPanel AutoSize issues that can collapse to zero
    BackgroundBorder = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("BackgroundBorder"));
    BackgroundBorder->SetBrushColor(BackgroundColor);
    BackgroundBorder->SetHorizontalAlignment(HAlign_Center);
    BackgroundBorder->SetVerticalAlignment(VAlign_Center);
    BackgroundBorder->SetPadding(FMargin(40.0f));
    WidgetTree->RootWidget = BackgroundBorder;

    // Content box (centered by border alignment)
    UVerticalBox* ContentBox = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("ContentBox"));
    BackgroundBorder->AddChild(ContentBox);

    // === Title: "UE Bridge" ===
    TitleText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("TitleText"));
    TitleText->SetText(NSLOCTEXT("UEBridge", "TitleScreen.Title", "UE Bridge"));
    TitleText->SetColorAndOpacity(FSlateColor(TitleColor));
    TitleText->SetJustification(ETextJustify::Center);
    TitleText->SetFont(FUEBridgeStyle::GetFont("Font.Title"));

    UVerticalBoxSlot* TitleSlot = ContentBox->AddChildToVerticalBox(TitleText);
    if (TitleSlot)
    {
        TitleSlot->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 12.0f));
        TitleSlot->SetHorizontalAlignment(HAlign_Center);
    }

    // === Subtitle: "A cognitive profiling experience" ===
    SubtitleText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("SubtitleText"));
    SubtitleText->SetText(NSLOCTEXT("UEBridge", "TitleScreen.Subtitle", "A cognitive profiling experience"));
    SubtitleText->SetColorAndOpacity(FSlateColor(SubtitleColor));
    SubtitleText->SetJustification(ETextJustify::Center);
    SubtitleText->SetFont(FUEBridgeStyle::GetFont("Font.Subtitle"));

    UVerticalBoxSlot* SubtitleSlot = ContentBox->AddChildToVerticalBox(SubtitleText);
    if (SubtitleSlot)
    {
        SubtitleSlot->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 60.0f));
        SubtitleSlot->SetHorizontalAlignment(HAlign_Center);
    }

    // === Prompt: "Press ENTER to begin" ===
    PromptText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("PromptText"));
    PromptText->SetText(NSLOCTEXT("UEBridge", "TitleScreen.Prompt", "Press ENTER to begin"));
    PromptText->SetColorAndOpacity(FSlateColor(PromptColor));
    PromptText->SetJustification(ETextJustify::Center);
    PromptText->SetFont(FUEBridgeStyle::GetFont("Font.Body"));

    UVerticalBoxSlot* PromptSlot = ContentBox->AddChildToVerticalBox(PromptText);
    if (PromptSlot)
    {
        PromptSlot->SetHorizontalAlignment(HAlign_Center);
    }

    UE_LOG(LogUEBridge, Log, TEXT("[W_TitleScreen] Built programmatic widget tree (Border root)"));
}
