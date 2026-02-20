// UEBridgeStyle.cpp
// Centralized Slate style set for UE Bridge UI.
// Defines all named color and font tokens consumed by the 6 UI widgets.

#include "UEBridgeStyle.h"
#include "Styling/CoreStyle.h"
#include "Styling/SlateTypes.h"

TSharedPtr<FSlateStyleSet> FUEBridgeStyle::StyleInstance = nullptr;

FName FUEBridgeStyle::GetStyleSetName()
{
	static FName StyleSetName(TEXT("UEBridgeStyle"));
	return StyleSetName;
}

void FUEBridgeStyle::Initialize()
{
	if (!StyleInstance.IsValid())
	{
		StyleInstance = Create();
		FSlateStyleRegistry::RegisterSlateStyle(*StyleInstance);
	}
}

void FUEBridgeStyle::Shutdown()
{
	if (StyleInstance.IsValid())
	{
		FSlateStyleRegistry::UnRegisterSlateStyle(*StyleInstance);
		StyleInstance.Reset();
	}
}

const ISlateStyle& FUEBridgeStyle::Get()
{
	check(StyleInstance.IsValid());
	return *StyleInstance;
}

FLinearColor FUEBridgeStyle::GetColor(const FName& PropertyName)
{
	return Get().GetSlateColor(PropertyName).GetSpecifiedColor();
}

FSlateFontInfo FUEBridgeStyle::GetFont(const FName& PropertyName)
{
	return Get().GetFontStyle(PropertyName);
}

TSharedRef<FSlateStyleSet> FUEBridgeStyle::Create()
{
	TSharedRef<FSlateStyleSet> Style = MakeShareable(new FSlateStyleSet(GetStyleSetName()));

	// -------------------------------------------------------------------------
	// Colors
	// -------------------------------------------------------------------------

	// Backgrounds
	Style->Set("Color.Background",      FSlateColor(FLinearColor(0.02f, 0.02f, 0.05f, 0.98f)));
	Style->Set("Color.BackgroundSolid",  FSlateColor(FLinearColor(0.02f, 0.02f, 0.05f, 1.0f)));

	// Primary accent — cyan family
	Style->Set("Color.Cyan",            FSlateColor(FLinearColor(0.36f, 1.0f, 0.86f, 1.0f)));
	Style->Set("Color.CyanDim",         FSlateColor(FLinearColor(0.36f, 1.0f, 0.86f, 0.8f)));
	Style->Set("Color.CyanFaint",       FSlateColor(FLinearColor(0.36f, 1.0f, 0.86f, 0.9f)));

	// Secondary accent — gold
	Style->Set("Color.Gold",            FSlateColor(FLinearColor(1.0f, 0.8f, 0.2f, 1.0f)));

	// Text hierarchy
	Style->Set("Color.TextPrimary",     FSlateColor(FLinearColor(0.9f, 0.9f, 0.9f, 1.0f)));
	Style->Set("Color.TextSecondary",   FSlateColor(FLinearColor(0.7f, 0.7f, 0.8f, 1.0f)));
	Style->Set("Color.TextDim",         FSlateColor(FLinearColor(0.5f, 0.5f, 0.6f, 1.0f)));
	Style->Set("Color.TextMuted",       FSlateColor(FLinearColor(0.4f, 0.4f, 0.5f, 1.0f)));

	// Semantic colors
	Style->Set("Color.Insight",         FSlateColor(FLinearColor(0.7f, 0.8f, 0.7f, 1.0f)));
	Style->Set("Color.IncompleteGray",  FSlateColor(FLinearColor(0.3f, 0.3f, 0.3f, 0.5f)));

	// Button states
	Style->Set("Color.ButtonNormal",    FSlateColor(FLinearColor(0.1f, 0.1f, 0.15f, 1.0f)));
	Style->Set("Color.ButtonHovered",   FSlateColor(FLinearColor(0.2f, 0.4f, 0.5f, 1.0f)));

	// Question depth tiers
	Style->Set("Color.DepthSurface",    FSlateColor(FLinearColor(0.5f, 0.8f, 0.5f, 1.0f)));
	Style->Set("Color.DepthPatterns",   FSlateColor(FLinearColor(0.3f, 0.8f, 0.8f, 1.0f)));
	Style->Set("Color.DepthFeelings",   FSlateColor(FLinearColor(1.0f, 0.5f, 0.45f, 1.0f)));
	Style->Set("Color.DepthCore",       FSlateColor(FLinearColor(1.0f, 0.85f, 0.3f, 1.0f)));

	// -------------------------------------------------------------------------
	// Fonts (all use FCoreStyle default — DPI-aware, no hardcoded paths)
	// -------------------------------------------------------------------------

	Style->Set("Font.Title",            FCoreStyle::GetDefaultFontStyle("Bold",    56));
	Style->Set("Font.Heading",          FCoreStyle::GetDefaultFontStyle("Bold",    36));
	Style->Set("Font.Subtitle",         FCoreStyle::GetDefaultFontStyle("Regular", 18));
	Style->Set("Font.Body",             FCoreStyle::GetDefaultFontStyle("Regular", 16));
	Style->Set("Font.Question",         FCoreStyle::GetDefaultFontStyle("Regular", 24));
	Style->Set("Font.Option",           FCoreStyle::GetDefaultFontStyle("Regular", 18));
	Style->Set("Font.Progress",         FCoreStyle::GetDefaultFontStyle("Regular", 14));
	Style->Set("Font.Caption",          FCoreStyle::GetDefaultFontStyle("Regular", 12));
	Style->Set("Font.Small",            FCoreStyle::GetDefaultFontStyle("Regular", 11));
	Style->Set("Font.Insight",          FCoreStyle::GetDefaultFontStyle("Regular", 13));

	return Style;
}
