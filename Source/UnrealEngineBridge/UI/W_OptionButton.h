// W_OptionButton.h
// Clickable button widget for answer options
// Part of The UnrealEngine Bridge - Claude Code → UE5.7 Bridge

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "Components/Button.h"
#include "Components/TextBlock.h"
#include "Components/Border.h"
#include "W_OptionButton.generated.h"

// Delegate fired when option is selected
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnOptionClicked, int32, OptionIndex);

/**
 * W_OptionButton - Individual answer option button
 *
 * Features:
 * - 8-bit styled button with hover effects
 * - Keyboard focusable (accessibility)
 * - Fires delegate with option index when clicked
 *
 * Deterministic: fixed visual states and click-to-delegate flow.
 */
UCLASS(Blueprintable, BlueprintType)
class TRANSLATORSCARD_API UW_OptionButton : public UUserWidget
{
    GENERATED_BODY()

public:
    UW_OptionButton(const FObjectInitializer& ObjectInitializer);

    // === DELEGATES ===

    /** Fired when this option is clicked */
    UPROPERTY(BlueprintAssignable, Category = "UEBridge|Events")
    FOnOptionClicked OnOptionClicked;

    // === PROPERTIES ===

    /** Index of this option (0, 1, or 2) */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Option")
    int32 OptionIndex = 0;

    /** Display text for this option */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Option", meta = (MultiLine = true))
    FText LabelText;

    /** Direction associated with this option (for visual cues) */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Option")
    FString Direction;

    // === COLORS (8-bit aesthetic) ===

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor NormalColor = FLinearColor(0.1f, 0.1f, 0.15f, 1.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor HoveredColor = FLinearColor(0.2f, 0.4f, 0.5f, 1.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor PressedColor = FLinearColor(0.36f, 1.0f, 0.86f, 1.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor TextColor = FLinearColor(0.9f, 0.9f, 0.9f, 1.0f);

    // === FUNCTIONS ===

    /** Set up the button with option data */
    UFUNCTION(BlueprintCallable, Category = "UEBridge|Option")
    void SetupOption(int32 Index, const FText& Label, const FString& Dir);

    /** Update the visual state */
    UFUNCTION(BlueprintCallable, Category = "UEBridge|Option")
    void SetHighlighted(bool bHighlighted);

    /** Simulate a click (for keyboard input) */
    UFUNCTION(BlueprintCallable, Category = "UEBridge|Option")
    void SimulateClick();

    virtual TSharedRef<SWidget> RebuildWidget() override;

protected:
    virtual void NativeConstruct() override;
    virtual void NativeDestruct() override;

    // Widget components (bind in Blueprint or create in C++)
    UPROPERTY(BlueprintReadOnly, meta = (BindWidget, OptionalWidget = true))
    UButton* OptionButton;

    UPROPERTY(BlueprintReadOnly, meta = (BindWidget, OptionalWidget = true))
    UTextBlock* OptionLabel;

    UPROPERTY(BlueprintReadOnly, meta = (BindWidget, OptionalWidget = true))
    UBorder* ButtonBorder;

private:
    UFUNCTION()
    void HandleButtonClicked();

    UFUNCTION()
    void HandleButtonHovered();

    UFUNCTION()
    void HandleButtonUnhovered();

    void UpdateVisualState(const FLinearColor& BackgroundColor);

    /** Build widget tree programmatically (no Blueprint required) */
    void BuildWidgetTree();
};
