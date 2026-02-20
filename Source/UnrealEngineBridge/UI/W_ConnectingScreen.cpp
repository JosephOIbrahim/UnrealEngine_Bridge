// W_ConnectingScreen.cpp
// Implementation of connecting screen widget
// Programmatic UI - no Blueprint required

#include "W_ConnectingScreen.h"
#include "UEBridgeRuntime.h"
#include "Components/TextBlock.h"
#include "Components/Border.h"
#include "Blueprint/WidgetTree.h"
#include "UEBridgeStyle.h"


UW_ConnectingScreen::UW_ConnectingScreen(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
{
    // 8-bit color scheme
    BackgroundColor = FUEBridgeStyle::GetColor("Color.Background");
    TextColor = FUEBridgeStyle::GetColor("Color.TextDim");
}


TSharedRef<SWidget> UW_ConnectingScreen::RebuildWidget()
{
    if (!StatusText)
    {
        BuildWidgetTree();
    }
    return Super::RebuildWidget();
}


void UW_ConnectingScreen::NativeConstruct()
{
    Super::NativeConstruct();

    // Apply colors
    if (BackgroundBorder)
    {
        BackgroundBorder->SetBrushColor(BackgroundColor);
    }
    if (StatusText)
    {
        StatusText->SetColorAndOpacity(FSlateColor(TextColor));
    }

    UE_LOG(LogUEBridge, Log, TEXT("[W_ConnectingScreen] Constructed (Programmatic UI)"));
}


void UW_ConnectingScreen::SetStatusText(const FString& Status)
{
    if (StatusText)
    {
        StatusText->SetText(FText::FromString(Status));
    }
}


void UW_ConnectingScreen::BuildWidgetTree()
{
    // Border root (fills viewport, centers content)
    BackgroundBorder = WidgetTree->ConstructWidget<UBorder>(UBorder::StaticClass(), TEXT("BackgroundBorder"));
    BackgroundBorder->SetBrushColor(BackgroundColor);
    BackgroundBorder->SetHorizontalAlignment(HAlign_Center);
    BackgroundBorder->SetVerticalAlignment(VAlign_Center);
    WidgetTree->RootWidget = BackgroundBorder;

    // Centered text
    StatusText = WidgetTree->ConstructWidget<UTextBlock>(UTextBlock::StaticClass(), TEXT("StatusText"));
    StatusText->SetText(NSLOCTEXT("UEBridge", "ConnectingScreen.Status", "Connecting to Claude Code..."));
    StatusText->SetColorAndOpacity(FSlateColor(TextColor));
    StatusText->SetJustification(ETextJustify::Center);
    StatusText->SetFont(FUEBridgeStyle::GetFont("Font.Question"));
    BackgroundBorder->AddChild(StatusText);

    UE_LOG(LogUEBridge, Log, TEXT("[W_ConnectingScreen] Built programmatic widget tree (Border root)"));
}
