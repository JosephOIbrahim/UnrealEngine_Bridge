// W_ProgressIndicator.cpp
// Implementation of progress indicator widget
// Programmatic UI - no Blueprint required

#include "W_ProgressIndicator.h"
#include "UEBridgeRuntime.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/Image.h"
#include "Components/TextBlock.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Blueprint/WidgetTree.h"
#include "UEBridgeStyle.h"


UW_ProgressIndicator::UW_ProgressIndicator(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
{
    TotalQuestions = 8;
    CurrentQuestion = 0;

    // 8-bit color scheme
    CompletedColor = FUEBridgeStyle::GetColor("Color.Cyan");
    IncompleteColor = FUEBridgeStyle::GetColor("Color.IncompleteGray");
    CurrentColor = FUEBridgeStyle::GetColor("Color.Gold");
}


void UW_ProgressIndicator::NativeConstruct()
{
    Super::NativeConstruct();

    // Build widget tree programmatically if not bound from Blueprint
    if (!IndicatorContainer)
    {
        BuildWidgetTree();
    }

    // Create indicator images if we have a container
    if (IndicatorContainer)
    {
        IndicatorContainer->ClearChildren();
        IndicatorImages.Empty();

        for (int32 i = 0; i < TotalQuestions; i++)
        {
            UImage* Indicator = WidgetTree->ConstructWidget<UImage>(UImage::StaticClass());
            if (Indicator)
            {
                // Set size (small square)
                Indicator->SetDesiredSizeOverride(FVector2D(12.0f, 12.0f));

                // Add to container
                UHorizontalBoxSlot* IndicatorSlot = IndicatorContainer->AddChildToHorizontalBox(Indicator);
                if (IndicatorSlot)
                {
                    IndicatorSlot->SetPadding(FMargin(4.0f, 0.0f, 4.0f, 0.0f));
                    IndicatorSlot->SetVerticalAlignment(VAlign_Center);
                }

                IndicatorImages.Add(Indicator);
            }
        }
    }

    // Initial state
    RefreshIndicators();

    UE_LOG(LogUEBridge, Log, TEXT("[W_ProgressIndicator] Constructed with %d slots"), TotalQuestions);
}


void UW_ProgressIndicator::UpdateProgress(int32 QuestionsCompleted)
{
    CurrentQuestion = FMath::Clamp(QuestionsCompleted, 0, TotalQuestions);
    RefreshIndicators();

    UE_LOG(LogUEBridge, Log, TEXT("[W_ProgressIndicator] Progress: %d/%d (%.0f%%)"),
        CurrentQuestion, TotalQuestions, GetCompletionPercent() * 100.0f);
}


void UW_ProgressIndicator::SetTotalQuestions(int32 Total)
{
    TotalQuestions = FMath::Max(1, Total);

    // Rebuild indicators if needed
    if (IndicatorImages.Num() != TotalQuestions && IndicatorContainer)
    {
        // Clear and rebuild
        IndicatorContainer->ClearChildren();
        IndicatorImages.Empty();

        for (int32 i = 0; i < TotalQuestions; i++)
        {
            UImage* Indicator = WidgetTree->ConstructWidget<UImage>(UImage::StaticClass());
            if (Indicator)
            {
                Indicator->SetDesiredSizeOverride(FVector2D(12.0f, 12.0f));
                UHorizontalBoxSlot* IndicatorSlot = IndicatorContainer->AddChildToHorizontalBox(Indicator);
                if (IndicatorSlot)
                {
                    IndicatorSlot->SetPadding(FMargin(4.0f, 0.0f, 4.0f, 0.0f));
                }
                IndicatorImages.Add(Indicator);
            }
        }
    }

    RefreshIndicators();
}


float UW_ProgressIndicator::GetCompletionPercent() const
{
    if (TotalQuestions <= 0)
    {
        return 0.0f;
    }
    return static_cast<float>(CurrentQuestion) / static_cast<float>(TotalQuestions);
}


void UW_ProgressIndicator::RefreshIndicators()
{
    // Update indicator colors
    for (int32 i = 0; i < IndicatorImages.Num(); i++)
    {
        UImage* Indicator = IndicatorImages[i];
        if (!Indicator) continue;

        FLinearColor Color;
        if (i < CurrentQuestion)
        {
            // Completed
            Color = CompletedColor;
        }
        else if (i == CurrentQuestion)
        {
            // Current (in progress)
            Color = CurrentColor;
        }
        else
        {
            // Not yet reached
            Color = IncompleteColor;
        }

        Indicator->SetColorAndOpacity(Color);
    }

    // Update text label
    if (ProgressLabel)
    {
        FString LabelText = FString::Printf(TEXT("%d / %d"), CurrentQuestion, TotalQuestions);
        ProgressLabel->SetText(FText::FromString(LabelText));
    }
}


void UW_ProgressIndicator::BuildWidgetTree()
{
    // Create root canvas
    UCanvasPanel* RootCanvas = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("RootCanvas"));
    WidgetTree->RootWidget = RootCanvas;

    // Create horizontal container for indicators
    IndicatorContainer = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass(), TEXT("IndicatorContainer"));

    UCanvasPanelSlot* ContainerSlot = RootCanvas->AddChildToCanvas(IndicatorContainer);
    if (ContainerSlot)
    {
        ContainerSlot->SetAnchors(FAnchors(0.5f, 0.5f, 0.5f, 0.5f));
        ContainerSlot->SetAlignment(FVector2D(0.5f, 0.5f));
        ContainerSlot->SetAutoSize(true);
    }

    UE_LOG(LogUEBridge, Log, TEXT("[W_ProgressIndicator] Built programmatic widget tree"));
}
