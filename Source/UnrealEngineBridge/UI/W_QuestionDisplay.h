// W_QuestionDisplay.h
// Main widget displaying question text and answer options
// Part of The UnrealEngine Bridge - Claude Code → UE5.7 Bridge

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Components/VerticalBox.h"
#include "Components/TextBlock.h"
#include "Components/Border.h"
#include "BridgeTypes.h"
#include "W_QuestionDisplay.generated.h"

// Forward declaration
class UW_OptionButton;

// Delegate for option selection (bubbles up from buttons)
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnAnswerSelected, int32, OptionIndex);

/**
 * W_QuestionDisplay - Main question display widget
 *
 * Shows:
 * - Question text (multi-line)
 * - Progress indicator (1/8)
 * - Option buttons (dynamically created)
 *
 * Deterministic: fixed widget structure, same input produces same visual output.
 */
UCLASS(Blueprintable, BlueprintType)
class TRANSLATORSCARD_API UW_QuestionDisplay : public UUserWidget
{
    GENERATED_BODY()

public:
    UW_QuestionDisplay(const FObjectInitializer& ObjectInitializer);

    // === DELEGATES ===

    /** Fired when user selects an answer */
    UPROPERTY(BlueprintAssignable, Category = "UEBridge|Events")
    FOnAnswerSelected OnAnswerSelected;

    // === PROPERTIES ===

    /** Class to use for option buttons (set in Blueprint) */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Config")
    TSubclassOf<UW_OptionButton> OptionButtonClass;

    /** Current question data */
    UPROPERTY(BlueprintReadOnly, Category = "UEBridge|State")
    FUEBridgeQuestion CurrentQuestion;

    // === STYLE ===

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor BackgroundColor = FLinearColor(0.05f, 0.05f, 0.08f, 0.95f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor QuestionTextColor = FLinearColor(1.0f, 1.0f, 1.0f, 1.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor ProgressTextColor = FLinearColor(0.5f, 0.5f, 0.5f, 1.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor DepthLabelColor = FLinearColor(0.5f, 0.8f, 0.5f, 1.0f);  // Default sage green

    // === FUNCTIONS ===

    /** Display a new question */
    UFUNCTION(BlueprintCallable, Category = "UEBridge|Display")
    void ShowQuestion(const FUEBridgeQuestion& Question);

    /** Update progress text */
    UFUNCTION(BlueprintCallable, Category = "UEBridge|Display")
    void UpdateProgress(int32 Current, int32 Total);

    /** Clear all options and reset */
    UFUNCTION(BlueprintCallable, Category = "UEBridge|Display")
    void ClearOptions();

    /** Show/hide the entire widget with animation */
    UFUNCTION(BlueprintCallable, Category = "UEBridge|Display")
    void SetDisplayVisible(bool bVisible);

    /** Get the currently selected option index (-1 if none) */
    UFUNCTION(BlueprintCallable, Category = "UEBridge|State")
    int32 GetSelectedOptionIndex() const { return SelectedOptionIndex; }

    virtual TSharedRef<SWidget> RebuildWidget() override;

protected:
    virtual void NativeConstruct() override;

    // Widget components (bind in Blueprint)
    UPROPERTY(BlueprintReadOnly, meta = (BindWidget, OptionalWidget = true))
    UTextBlock* QuestionText;

    UPROPERTY(BlueprintReadOnly, meta = (BindWidget, OptionalWidget = true))
    UTextBlock* ProgressText;

    UPROPERTY(BlueprintReadOnly, meta = (BindWidget, OptionalWidget = true))
    UTextBlock* DepthText;

    UPROPERTY(BlueprintReadOnly, meta = (BindWidget, OptionalWidget = true))
    UVerticalBox* OptionsContainer;

    UPROPERTY(BlueprintReadOnly, meta = (BindWidget, OptionalWidget = true))
    UBorder* BackgroundBorder;

private:
    /** Handle option button click */
    UFUNCTION()
    void HandleOptionClicked(int32 OptionIndex);

    /** Create option buttons for current question */
    void CreateOptionButtons();

    /** Build widget tree programmatically (no Blueprint required) */
    void BuildWidgetTree();

    /** Currently selected option (-1 = none) */
    int32 SelectedOptionIndex = -1;

    /** Created option button widgets */
    UPROPERTY()
    TArray<UW_OptionButton*> OptionButtons;
};
