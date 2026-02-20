// W_QuestionDisplay.cpp
// Implementation of main question display widget
// Programmatic UI - no Blueprint required

#include "W_QuestionDisplay.h"
#include "W_OptionButton.h"
#include "UEBridgeRuntime.h"
#include "Components/CanvasPanel.h"
#include "Components/CanvasPanelSlot.h"
#include "Components/VerticalBox.h"
#include "Components/VerticalBoxSlot.h"
#include "Components/TextBlock.h"
#include "Components/Border.h"
#include "Components/SizeBox.h"
#include "Blueprint/WidgetTree.h"
#include "UEBridgeStyle.h"


UW_QuestionDisplay::UW_QuestionDisplay(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
{
    // 8-bit color scheme
    BackgroundColor = FUEBridgeStyle::GetColor("Color.Background");
    QuestionTextColor = FUEBridgeStyle::GetColor("Color.Cyan");
    ProgressTextColor = FUEBridgeStyle::GetColor("Color.TextDim");
}


TSharedRef<SWidget> UW_QuestionDisplay::RebuildWidget()
{
    if (!QuestionText || !OptionsContainer)
    {
        BuildWidgetTree();
    }
    return Super::RebuildWidget();
}


void UW_QuestionDisplay::NativeConstruct()
{
    Super::NativeConstruct();

    // Apply colors
    if (BackgroundBorder)
    {
        BackgroundBorder->SetBrushColor(BackgroundColor);
    }
    if (QuestionText)
    {
        QuestionText->SetColorAndOpacity(FSlateColor(QuestionTextColor));
    }
    if (ProgressText)
    {
        ProgressText->SetColorAndOpacity(FSlateColor(ProgressTextColor));
    }

    UE_LOG(LogUEBridge, Log, TEXT("[W_QuestionDisplay] Constructed (Programmatic UI)"));
}


void UW_QuestionDisplay::BuildWidgetTree()
{
    // Create root canvas
    UCanvasPanel* RootCanvas = WidgetTree->ConstructWidget<UCanvasPanel>(UCanvasPanel::StaticClass(), TEXT("RootCanvas"));
    WidgetTree->RootWidget = RootCanvas;

    // Create background border - centered panel
    BackgroundBorder = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("BackgroundBorder"));
    BackgroundBorder->SetBrushColor(BackgroundColor);
    BackgroundBorder->SetPadding(FMargin(40.0f, 30.0f));

    UCanvasPanelSlot* BorderSlot = RootCanvas->AddChildToCanvas(BackgroundBorder);
    if (BorderSlot)
    {
        // Center the panel
        BorderSlot->SetAnchors(FAnchors(0.5f, 0.5f, 0.5f, 0.5f));
        BorderSlot->SetAlignment(FVector2D(0.5f, 0.5f));
        BorderSlot->SetAutoSize(true);
    }

    // Create main vertical layout
    UVerticalBox* MainLayout = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("MainLayout"));
    BackgroundBorder->AddChild(MainLayout);

    // Create size box to constrain width
    USizeBox* ContentSizeBox = WidgetTree->ConstructWidget<USizeBox>(USizeBox::StaticClass(), TEXT("ContentSizeBox"));
    ContentSizeBox->SetWidthOverride(600.0f);
    UVerticalBoxSlot* SizeBoxSlot = MainLayout->AddChildToVerticalBox(ContentSizeBox);
    if (SizeBoxSlot)
    {
        SizeBoxSlot->SetHorizontalAlignment(HAlign_Center);
    }

    // Inner vertical box for content
    UVerticalBox* ContentBox = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("ContentBox"));
    ContentSizeBox->AddChild(ContentBox);

    // Depth label (top - e.g. "SURFACE", "PATTERNS", etc.)
    DepthText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("DepthText"));
    DepthText->SetText(NSLOCTEXT("UEBridge", "QuestionDisplay.DefaultDepth", "SURFACE"));
    DepthText->SetColorAndOpacity(FSlateColor(DepthLabelColor));
    DepthText->SetJustification(ETextJustify::Center);

    DepthText->SetFont(FUEBridgeStyle::GetFont("Font.Caption"));

    UVerticalBoxSlot* DepthSlot = ContentBox->AddChildToVerticalBox(DepthText);
    if (DepthSlot)
    {
        DepthSlot->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 8.0f));
        DepthSlot->SetHorizontalAlignment(HAlign_Center);
    }

    // Progress text
    ProgressText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("ProgressText"));
    ProgressText->SetText(NSLOCTEXT("UEBridge", "QuestionDisplay.DefaultProgress", "1 / 8"));
    ProgressText->SetColorAndOpacity(FSlateColor(ProgressTextColor));
    ProgressText->SetJustification(ETextJustify::Center);

    ProgressText->SetFont(FUEBridgeStyle::GetFont("Font.Progress"));

    UVerticalBoxSlot* ProgressSlot = ContentBox->AddChildToVerticalBox(ProgressText);
    if (ProgressSlot)
    {
        ProgressSlot->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 20.0f));
        ProgressSlot->SetHorizontalAlignment(HAlign_Center);
    }

    // Question text (center)
    QuestionText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("QuestionText"));
    QuestionText->SetText(NSLOCTEXT("UEBridge", "QuestionDisplay.Loading", "Loading question..."));
    QuestionText->SetColorAndOpacity(FSlateColor(QuestionTextColor));
    QuestionText->SetJustification(ETextJustify::Center);
    QuestionText->SetAutoWrapText(true);

    QuestionText->SetFont(FUEBridgeStyle::GetFont("Font.Question"));

    UVerticalBoxSlot* QuestionSlot = ContentBox->AddChildToVerticalBox(QuestionText);
    if (QuestionSlot)
    {
        QuestionSlot->SetPadding(FMargin(0.0f, 0.0f, 0.0f, 30.0f));
        QuestionSlot->SetHorizontalAlignment(HAlign_Fill);
    }

    // Options container
    OptionsContainer = WidgetTree->ConstructWidget<UVerticalBox>(UVerticalBox::StaticClass(), TEXT("OptionsContainer"));
    UVerticalBoxSlot* OptionsSlot = ContentBox->AddChildToVerticalBox(OptionsContainer);
    if (OptionsSlot)
    {
        OptionsSlot->SetHorizontalAlignment(HAlign_Fill);
    }

    UE_LOG(LogUEBridge, Log, TEXT("[W_QuestionDisplay] Built programmatic widget tree"));
}


void UW_QuestionDisplay::ShowQuestion(const FUEBridgeQuestion& Question)
{
    CurrentQuestion = Question;
    SelectedOptionIndex = -1;

    // Update depth label with tier-specific color
    if (DepthText)
    {
        DepthText->SetText(FText::FromString(Question.DepthLabel));

        // Color by tier
        FLinearColor TierColor;
        if (Question.DepthLabel == TEXT("SURFACE"))
        {
            TierColor = FUEBridgeStyle::GetColor("Color.DepthSurface");
        }
        else if (Question.DepthLabel == TEXT("PATTERNS"))
        {
            TierColor = FUEBridgeStyle::GetColor("Color.DepthPatterns");
        }
        else if (Question.DepthLabel == TEXT("FEELINGS"))
        {
            TierColor = FUEBridgeStyle::GetColor("Color.DepthFeelings");
        }
        else // CORE
        {
            TierColor = FUEBridgeStyle::GetColor("Color.DepthCore");
        }
        DepthText->SetColorAndOpacity(FSlateColor(TierColor));
    }

    // Update question text
    if (QuestionText)
    {
        FString FormattedText = Question.Text.Replace(TEXT("\\n"), TEXT("\n"));
        QuestionText->SetText(FText::FromString(FormattedText));
    }

    // Update progress
    UpdateProgress(Question.Index + 1, Question.Total);

    // Create option buttons
    CreateOptionButtons();

    UE_LOG(LogUEBridge, Log, TEXT("[W_QuestionDisplay] Showing question %d/%d: %s"),
        Question.Index + 1, Question.Total, *Question.QuestionId);
}


void UW_QuestionDisplay::UpdateProgress(int32 Current, int32 Total)
{
    if (ProgressText)
    {
        FString ProgressString = FString::Printf(TEXT("%d / %d"), Current, Total);
        ProgressText->SetText(FText::FromString(ProgressString));
    }
}


void UW_QuestionDisplay::ClearOptions()
{
    for (UW_OptionButton* Button : OptionButtons)
    {
        if (Button)
        {
            Button->OnOptionClicked.RemoveAll(this);
            Button->RemoveFromParent();
        }
    }
    OptionButtons.Empty();
    SelectedOptionIndex = -1;
}


void UW_QuestionDisplay::SetDisplayVisible(bool bVisible)
{
    SetVisibility(bVisible ? ESlateVisibility::Visible : ESlateVisibility::Hidden);
}


void UW_QuestionDisplay::CreateOptionButtons()
{
    ClearOptions();

    if (!OptionsContainer)
    {
        UE_LOG(LogUEBridge, Warning, TEXT("[W_QuestionDisplay] No OptionsContainer"));
        return;
    }

    TSubclassOf<UW_OptionButton> ButtonClass = OptionButtonClass;
    if (!ButtonClass)
    {
        ButtonClass = UW_OptionButton::StaticClass();
    }

    const int32 NumOptions = CurrentQuestion.OptionLabels.Num();
    for (int32 i = 0; i < NumOptions; i++)
    {
        UW_OptionButton* NewButton = CreateWidget<UW_OptionButton>(this, ButtonClass);
        if (NewButton)
        {
            FText Label = FText::FromString(CurrentQuestion.OptionLabels[i]);
            FString Dir = CurrentQuestion.OptionDirections.IsValidIndex(i)
                ? CurrentQuestion.OptionDirections[i]
                : TEXT("forward");

            NewButton->SetupOption(i, Label, Dir);
            NewButton->OnOptionClicked.AddDynamic(this, &UW_QuestionDisplay::HandleOptionClicked);

            UVerticalBoxSlot* ButtonSlot = OptionsContainer->AddChildToVerticalBox(NewButton);
            if (ButtonSlot)
            {
                ButtonSlot->SetPadding(FMargin(0.0f, 8.0f, 0.0f, 8.0f));
                ButtonSlot->SetHorizontalAlignment(HAlign_Fill);
            }

            OptionButtons.Add(NewButton);
        }
    }
}


void UW_QuestionDisplay::HandleOptionClicked(int32 OptionIndex)
{
    if (SelectedOptionIndex != -1)
    {
        return;
    }

    SelectedOptionIndex = OptionIndex;

    for (int32 i = 0; i < OptionButtons.Num(); i++)
    {
        if (OptionButtons[i])
        {
            OptionButtons[i]->SetHighlighted(i == OptionIndex);
        }
    }

    UE_LOG(LogUEBridge, Log, TEXT("[W_QuestionDisplay] Answer: option %d"), OptionIndex);
    OnAnswerSelected.Broadcast(OptionIndex);
}
