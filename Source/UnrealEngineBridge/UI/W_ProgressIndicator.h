// W_ProgressIndicator.h
// Progress indicator showing questionnaire completion
// Part of The UnrealEngine Bridge - Claude Code → UE5.7 Bridge

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Components/HorizontalBox.h"
#include "Components/Image.h"
#include "Components/TextBlock.h"
#include "W_ProgressIndicator.generated.h"

/**
 * W_ProgressIndicator - Visual progress through 8 questions
 *
 * Shows:
 * - 8 dots/boxes (filled for completed, empty for remaining)
 * - Text like "3/8 COMPLETE"
 *
 * Deterministic: fixed 8 indicator slots, predictable visual state.
 */
UCLASS(Blueprintable, BlueprintType)
class TRANSLATORSCARD_API UW_ProgressIndicator : public UUserWidget
{
    GENERATED_BODY()

public:
    UW_ProgressIndicator(const FObjectInitializer& ObjectInitializer);

    // === PROPERTIES ===

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Progress")
    int32 TotalQuestions = 8;

    UPROPERTY(BlueprintReadOnly, Category = "UEBridge|Progress")
    int32 CurrentQuestion = 0;

    // === STYLE ===

    /** Color for completed question indicators */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor CompletedColor = FLinearColor(0.36f, 1.0f, 0.86f, 1.0f);  // Cyan

    /** Color for incomplete question indicators */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor IncompleteColor = FLinearColor(0.3f, 0.3f, 0.3f, 0.5f);  // Gray

    /** Color for current question indicator */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor CurrentColor = FLinearColor(1.0f, 0.8f, 0.2f, 1.0f);  // Gold

    // === FUNCTIONS ===

    /** Update progress to show N questions completed */
    UFUNCTION(BlueprintCallable, Category = "UEBridge|Progress")
    void UpdateProgress(int32 QuestionsCompleted);

    /** Set total number of questions */
    UFUNCTION(BlueprintCallable, Category = "UEBridge|Progress")
    void SetTotalQuestions(int32 Total);

    /** Get completion percentage (0.0 - 1.0) */
    UFUNCTION(BlueprintCallable, BlueprintPure, Category = "UEBridge|Progress")
    float GetCompletionPercent() const;

protected:
    virtual void NativeConstruct() override;

    // Widget components (bind in Blueprint)
    UPROPERTY(BlueprintReadOnly, meta = (BindWidget, OptionalWidget = true))
    UHorizontalBox* IndicatorContainer;

    UPROPERTY(BlueprintReadOnly, meta = (BindWidget, OptionalWidget = true))
    UTextBlock* ProgressLabel;

private:
    /** Update all indicator visuals */
    void RefreshIndicators();

    /** Build widget tree programmatically (no Blueprint required) */
    void BuildWidgetTree();

    /** Created indicator images */
    UPROPERTY()
    TArray<UImage*> IndicatorImages;
};
