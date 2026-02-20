// W_FinaleScreen.cpp
// Implementation of finale screen widget with cognitive profile display
// Programmatic UI - no Blueprint required

#include "W_FinaleScreen.h"
#include "UEBridgeRuntime.h"
#include "Components/TextBlock.h"
#include "Components/Border.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Components/ScrollBox.h"
#include "Components/ScrollBoxSlot.h"
#include "Components/HorizontalBox.h"
#include "Components/HorizontalBoxSlot.h"
#include "Components/Spacer.h"
#include "Blueprint/WidgetTree.h"
#include "UEBridgeStyle.h"


UW_FinaleScreen::UW_FinaleScreen(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
{
    BackgroundColor = FUEBridgeStyle::GetColor("Color.Background");
    TitleColor = FUEBridgeStyle::GetColor("Color.Cyan");
    SubtitleColor = FUEBridgeStyle::GetColor("Color.TextSecondary");
    TraitLabelColor = FUEBridgeStyle::GetColor("Color.CyanFaint");
    TraitValueColor = FUEBridgeStyle::GetColor("Color.TextPrimary");
    InsightColor = FUEBridgeStyle::GetColor("Color.Insight");
    DimColor = FUEBridgeStyle::GetColor("Color.TextMuted");
}


TSharedRef<SWidget> UW_FinaleScreen::RebuildWidget()
{
    if (!TitleText)
    {
        BuildWidgetTree();
    }
    return Super::RebuildWidget();
}


void UW_FinaleScreen::NativeConstruct()
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
    if (PathText)
    {
        PathText->SetColorAndOpacity(FSlateColor(DimColor));
    }
    if (ChecksumText)
    {
        ChecksumText->SetColorAndOpacity(FSlateColor(DimColor));
    }

    UE_LOG(LogUEBridge, Log, TEXT("[W_FinaleScreen] Constructed (Programmatic UI with Profile Display)"));
}


void UW_FinaleScreen::SetCompletionMessage(const FString& Message)
{
    if (SubtitleText)
    {
        SubtitleText->SetText(FText::FromString(Message));
    }
}


void UW_FinaleScreen::SetUsdPath(const FString& Path)
{
    if (PathText)
    {
        FString DisplayPath = FString::Printf(TEXT("Exported to %s"), *Path);
        PathText->SetText(FText::FromString(DisplayPath));
        PathText->SetVisibility(ESlateVisibility::Visible);
    }
}


void UW_FinaleScreen::DisplayProfile(const FUEBridgeProfile& Profile)
{
    if (!Profile.IsValid())
    {
        UE_LOG(LogUEBridge, Warning, TEXT("[W_FinaleScreen] Empty profile - nothing to display"));
        return;
    }

    // Populate traits
    if (TraitsContainer)
    {
        TraitsContainer->ClearChildren();

        for (const FTranslatorsTrait& Trait : Profile.Traits)
        {
            // Create a horizontal row: dimension | label | score bar | behavior
            UHorizontalBox* Row = WidgetTree->ConstructWidget<UHorizontalBox>(UHorizontalBox::StaticClass());

            // Dimension name (dim color, left-aligned)
            UTextBlock* DimText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
            FString CleanDim = Trait.Dimension.Replace(TEXT("_"), TEXT(" "));
            DimText->SetText(FText::FromString(CleanDim));
            DimText->SetColorAndOpacity(FSlateColor(DimColor));
            DimText->SetFont(FUEBridgeStyle::GetFont("Font.Caption"));

            UHorizontalBoxSlot* DimSlot = Row->AddChildToHorizontalBox(DimText);
            if (DimSlot)
            {
                DimSlot->SetPadding(FMargin(0.0f, 0.0f, 16.0f, 0.0f));
                DimSlot->SetSize(FSlateChildSize(ESlateSizeRule::Fill));
            }

            // Label (cyan, bold-ish)
            UTextBlock* LabelText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
            LabelText->SetText(FText::FromString(Trait.Label));
            LabelText->SetColorAndOpacity(FSlateColor(TraitLabelColor));
            LabelText->SetFont(FUEBridgeStyle::GetFont("Font.Progress"));

            UHorizontalBoxSlot* LabelSlot = Row->AddChildToHorizontalBox(LabelText);
            if (LabelSlot)
            {
                LabelSlot->SetPadding(FMargin(0.0f, 0.0f, 16.0f, 0.0f));
                LabelSlot->SetSize(FSlateChildSize(ESlateSizeRule::Automatic));
            }

            // Score (numeric)
            UTextBlock* ScoreText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
            FString ScoreStr = FString::Printf(TEXT("%.0f%%"), Trait.Score * 100.0f);
            ScoreText->SetText(FText::FromString(ScoreStr));
            ScoreText->SetColorAndOpacity(FSlateColor(TraitValueColor));
            ScoreText->SetFont(FUEBridgeStyle::GetFont("Font.Caption"));

            UHorizontalBoxSlot* ScoreSlot = Row->AddChildToHorizontalBox(ScoreText);
            if (ScoreSlot)
            {
                ScoreSlot->SetSize(FSlateChildSize(ESlateSizeRule::Automatic));
            }

            UVerticalBoxSlot* RowSlot = TraitsContainer->AddChildToVerticalBox(Row);
            if (RowSlot)
            {
                RowSlot->SetPadding(FMargin(0.0f, 4.0f, 0.0f, 4.0f));
            }

            // Behavior description (below the row, if present)
            if (!Trait.Behavior.IsEmpty())
            {
                UTextBlock* BehaviorText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
                BehaviorText->SetText(FText::FromString(Trait.Behavior));
                BehaviorText->SetColorAndOpacity(FSlateColor(SubtitleColor));
                BehaviorText->SetAutoWrapText(true);
                BehaviorText->SetFont(FUEBridgeStyle::GetFont("Font.Small"));

                UVerticalBoxSlot* BehaviorSlot = TraitsContainer->AddChildToVerticalBox(BehaviorText);
                if (BehaviorSlot)
                {
                    BehaviorSlot->SetPadding(FMargin(20.0f, 0.0f, 0.0f, 8.0f));
                }
            }
        }
    }

    // Populate insights
    if (InsightsContainer)
    {
        InsightsContainer->ClearChildren();

        for (const FString& Insight : Profile.Insights)
        {
            UTextBlock* InsightText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass());
            FString BulletInsight = FString::Printf(TEXT("  %s"), *Insight);
            InsightText->SetText(FText::FromString(BulletInsight));
            InsightText->SetColorAndOpacity(FSlateColor(InsightColor));
            InsightText->SetAutoWrapText(true);
            InsightText->SetFont(FUEBridgeStyle::GetFont("Font.Insight"));

            UVerticalBoxSlot* InsightSlot = InsightsContainer->AddChildToVerticalBox(InsightText);
            if (InsightSlot)
            {
                InsightSlot->SetPadding(FMargin(0.0f, 3.0f, 0.0f, 3.0f));
            }
        }
    }

    // Checksum/anchor
    if (ChecksumText)
    {
        FString ChecksumDisplay;
        if (!Profile.Anchor.IsEmpty())
        {
            ChecksumDisplay = Profile.Anchor;
        }
        else if (!Profile.Checksum.IsEmpty())
        {
            ChecksumDisplay = FString::Printf(TEXT("[TRANSLATORS:%s]"), *Profile.Checksum);
        }

        if (!ChecksumDisplay.IsEmpty())
        {
            ChecksumText->SetText(FText::FromString(ChecksumDisplay));
            ChecksumText->SetVisibility(ESlateVisibility::Visible);
        }
    }

    UE_LOG(LogUEBridge, Log, TEXT("[W_FinaleScreen] Displayed profile: %d traits, %d insights"),
        Profile.Traits.Num(), Profile.Insights.Num());
}


void UW_FinaleScreen::BuildWidgetTree()
{
    // Create full-screen canvas
    UCanvasPanel* RootCanvas = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("RootCanvas"));
    WidgetTree->RootWidget = RootCanvas;

    // Full-screen background
    BackgroundBorder = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("BackgroundBorder"));
    BackgroundBorder->SetBrushColor(BackgroundColor);

    UCanvasPanelSlot* BorderSlot = RootCanvas->AddChildToCanvas(BackgroundBorder);
    if (BorderSlot)
    {
        BorderSlot->SetAnchors(FAnchors(0.0f, 0.0f, 1.0f, 1.0f));
        BorderSlot->SetOffsets(FMargin(0.0f));
    }

    // Scrollable content area (centered, constrained width)
    UScrollBox* ScrollArea = WidgetTree->ConstructWidget<UScrollBox>(UScrollBox::StaticClass(), TEXT("ScrollArea"));

    UCanvasPanelSlot* ScrollSlot = RootCanvas->AddChildToCanvas(ScrollArea);
    if (ScrollSlot)
    {
        // Center with padding
        ScrollSlot->SetAnchors(FAnchors(0.15f, 0.05f, 0.85f, 0.95f));
        ScrollSlot->SetOffsets(FMargin(0.0f));
    }

    // Main content vertical box
    UVerticalBox* ContentBox = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("ContentBox"));
    ScrollArea->AddChild(ContentBox);

    // === Title: "Your Cognitive Profile" ===
    TitleText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("TitleText"));
    TitleText->SetText(NSLOCTEXT("UEBridge", "FinaleScreen.Title", "Your Cognitive Profile"));
    TitleText->SetColorAndOpacity(FSlateColor(TitleColor));
    TitleText->SetJustification(ETextJustify::Center);

    TitleText->SetFont(FUEBridgeStyle::GetFont("Font.Heading"));

    UVerticalBoxSlot* TitleSlot = ContentBox->AddChildToVerticalBox(TitleText);
    if (TitleSlot)
    {
        TitleSlot->SetPadding(FMargin(0.0f, 20.0f, 0.0f, 8.0f));
        TitleSlot->SetHorizontalAlignment(HAlign_Center);
    }

    // === Subtitle ===
    SubtitleText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("SubtitleText"));
    SubtitleText->SetText(NSLOCTEXT("UEBridge", "FinaleScreen.Subtitle", "Your cognitive profile has been generated."));
    SubtitleText->SetColorAndOpacity(FSlateColor(SubtitleColor));
    SubtitleText->SetJustification(ETextJustify::Center);

    SubtitleText->SetFont(FUEBridgeStyle::GetFont("Font.Body"));

    UVerticalBoxSlot* SubtitleSlot = ContentBox->AddChildToVerticalBox(SubtitleText);
    if (SubtitleSlot)
    {
        SubtitleSlot->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 30.0f));
        SubtitleSlot->SetHorizontalAlignment(HAlign_Center);
    }

    // === Traits section header ===
    UTextBlock* TraitsHeader = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("TraitsHeader"));
    TraitsHeader->SetText(NSLOCTEXT("UEBridge", "FinaleScreen.DimensionsHeader", "DIMENSIONS"));
    TraitsHeader->SetColorAndOpacity(FSlateColor(DimColor));

    TraitsHeader->SetFont(FUEBridgeStyle::GetFont("Font.Caption"));

    UVerticalBoxSlot* TraitsHeaderSlot = ContentBox->AddChildToVerticalBox(TraitsHeader);
    if (TraitsHeaderSlot)
    {
        TraitsHeaderSlot->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 10.0f));
    }

    // === Traits container (populated dynamically) ===
    TraitsContainer = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("TraitsContainer"));

    UVerticalBoxSlot* TraitsSlot = ContentBox->AddChildToVerticalBox(TraitsContainer);
    if (TraitsSlot)
    {
        TraitsSlot->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 30.0f));
    }

    // === Insights section header ===
    UTextBlock* InsightsHeader = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("InsightsHeader"));
    InsightsHeader->SetText(NSLOCTEXT("UEBridge", "FinaleScreen.InsightsHeader", "INSIGHTS"));
    InsightsHeader->SetColorAndOpacity(FSlateColor(DimColor));

    InsightsHeader->SetFont(FUEBridgeStyle::GetFont("Font.Caption"));

    UVerticalBoxSlot* InsightsHeaderSlot = ContentBox->AddChildToVerticalBox(InsightsHeader);
    if (InsightsHeaderSlot)
    {
        InsightsHeaderSlot->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 10.0f));
    }

    // === Insights container (populated dynamically) ===
    InsightsContainer = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("InsightsContainer"));

    UVerticalBoxSlot* InsightsSlot = ContentBox->AddChildToVerticalBox(InsightsContainer);
    if (InsightsSlot)
    {
        InsightsSlot->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 30.0f));
    }

    // === Checksum/anchor (hidden until profile loaded) ===
    ChecksumText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("ChecksumText"));
    ChecksumText->SetText(FText::FromString(TEXT("")));
    ChecksumText->SetColorAndOpacity(FSlateColor(DimColor));
    ChecksumText->SetJustification(ETextJustify::Center);
    ChecksumText->SetVisibility(ESlateVisibility::Collapsed);

    ChecksumText->SetFont(FUEBridgeStyle::GetFont("Font.Small"));

    UVerticalBoxSlot* ChecksumSlot = ContentBox->AddChildToVerticalBox(ChecksumText);
    if (ChecksumSlot)
    {
        ChecksumSlot->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 16.0f));
        ChecksumSlot->SetHorizontalAlignment(HAlign_Center);
    }

    // === Export path (hidden until set) ===
    PathText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("PathText"));
    PathText->SetText(FText::FromString(TEXT("")));
    PathText->SetColorAndOpacity(FSlateColor(DimColor));
    PathText->SetJustification(ETextJustify::Center);
    PathText->SetVisibility(ESlateVisibility::Collapsed);

    PathText->SetFont(FUEBridgeStyle::GetFont("Font.Small"));

    UVerticalBoxSlot* PathSlot = ContentBox->AddChildToVerticalBox(PathText);
    if (PathSlot)
    {
        PathSlot->SetHorizontalAlignment(HAlign_Center);
    }

    UE_LOG(LogUEBridge, Log, TEXT("[W_FinaleScreen] Built programmatic widget tree with profile display"));
}
