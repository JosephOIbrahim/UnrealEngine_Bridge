// W_ConnectingScreen.h
// Simple "Connecting..." screen widget
// Part of The UnrealEngine Bridge - Claude Code -> UE5.7 Bridge

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "W_ConnectingScreen.generated.h"

class UTextBlock;
class UBorder;

/**
 * W_ConnectingScreen - Displayed while waiting for bridge connection
 *
 * Shows a simple "Connecting to Claude Code..." message
 * Programmatic UI - no Blueprint required
 */
UCLASS(Blueprintable, BlueprintType)
class TRANSLATORSCARD_API UW_ConnectingScreen : public UUserWidget
{
    GENERATED_BODY()

public:
    UW_ConnectingScreen(const FObjectInitializer& ObjectInitializer);

    // === STYLE ===

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor BackgroundColor = FLinearColor(0.02f, 0.02f, 0.05f, 0.98f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor TextColor = FLinearColor(0.5f, 0.5f, 0.6f, 1.0f);

    // === FUNCTIONS ===

    /** Update the status message */
    UFUNCTION(BlueprintCallable, Category = "UEBridge|Display")
    void SetStatusText(const FString& Status);

    virtual TSharedRef<SWidget> RebuildWidget() override;

protected:
    virtual void NativeConstruct() override;

    UPROPERTY(BlueprintReadOnly, meta = (BindWidget, OptionalWidget = true))
    UTextBlock* StatusText;

    UPROPERTY(BlueprintReadOnly, meta = (BindWidget, OptionalWidget = true))
    UBorder* BackgroundBorder;

private:
    void BuildWidgetTree();
};
