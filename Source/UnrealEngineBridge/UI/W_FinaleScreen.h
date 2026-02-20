// W_FinaleScreen.h
// Final completion screen widget with cognitive profile display
// Part of The UnrealEngine Bridge - Claude Code -> UE5.7 Bridge

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "BridgeTypes.h"
#include "W_FinaleScreen.generated.h"

class UTextBlock;
class UBorder;
class UVerticalBox;
class UScrollBox;

/**
 * W_FinaleScreen - Displayed when questionnaire is complete
 *
 * Shows:
 * - "Your Cognitive Profile" title
 * - Trait list with dimension, label, score, behavior
 * - Insights section
 * - Checksum/anchor
 * - Export path
 *
 * Programmatic UI - no Blueprint required
 */
UCLASS(Blueprintable, BlueprintType)
class TRANSLATORSCARD_API UW_FinaleScreen : public UUserWidget
{
    GENERATED_BODY()

public:
    UW_FinaleScreen(const FObjectInitializer& ObjectInitializer);

    // === STYLE ===

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor BackgroundColor = FLinearColor(0.02f, 0.02f, 0.05f, 0.98f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor TitleColor = FLinearColor(0.36f, 1.0f, 0.86f, 1.0f);  // Cyan

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor SubtitleColor = FLinearColor(0.7f, 0.7f, 0.8f, 1.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor TraitLabelColor = FLinearColor(0.36f, 1.0f, 0.86f, 0.9f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor TraitValueColor = FLinearColor(0.9f, 0.9f, 0.9f, 1.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor InsightColor = FLinearColor(0.7f, 0.8f, 0.7f, 1.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor DimColor = FLinearColor(0.4f, 0.4f, 0.5f, 1.0f);

    // === FUNCTIONS ===

    /** Set the completion message */
    UFUNCTION(BlueprintCallable, Category = "UEBridge|Display")
    void SetCompletionMessage(const FString& Message);

    /** Set the USD path display */
    UFUNCTION(BlueprintCallable, Category = "UEBridge|Display")
    void SetUsdPath(const FString& Path);

    /** Display full cognitive profile */
    UFUNCTION(BlueprintCallable, Category = "UEBridge|Display")
    void DisplayProfile(const FUEBridgeProfile& Profile);

    virtual TSharedRef<SWidget> RebuildWidget() override;

protected:
    virtual void NativeConstruct() override;

    UPROPERTY(BlueprintReadOnly, meta = (BindWidget, OptionalWidget = true))
    UTextBlock* TitleText;

    UPROPERTY(BlueprintReadOnly, meta = (BindWidget, OptionalWidget = true))
    UTextBlock* SubtitleText;

    UPROPERTY(BlueprintReadOnly, meta = (BindWidget, OptionalWidget = true))
    UTextBlock* PathText;

    UPROPERTY(BlueprintReadOnly, meta = (BindWidget, OptionalWidget = true))
    UBorder* BackgroundBorder;

    UPROPERTY(BlueprintReadOnly, meta = (BindWidget, OptionalWidget = true))
    UVerticalBox* TraitsContainer;

    UPROPERTY(BlueprintReadOnly, meta = (BindWidget, OptionalWidget = true))
    UVerticalBox* InsightsContainer;

    UPROPERTY(BlueprintReadOnly, meta = (BindWidget, OptionalWidget = true))
    UTextBlock* ChecksumText;

private:
    void BuildWidgetTree();
};
