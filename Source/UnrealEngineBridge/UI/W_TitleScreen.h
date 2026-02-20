// W_TitleScreen.h
// Title screen for The Translators cognitive profiling game
// Part of The UnrealEngine Bridge - Claude Code -> UE5.7 Bridge

#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "W_TitleScreen.generated.h"

class UTextBlock;
class UBorder;
class UVerticalBox;
class UInputAction;
struct FInputActionValue;

// Delegate fired when user presses Enter to start
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnStartRequested);

/**
 * W_TitleScreen - Opening title screen
 *
 * Displays:
 * - "UE Bridge" (large, cyan)
 * - "A cognitive profiling experience" (dim subtitle)
 * - "Press ENTER to begin" (pulsing opacity)
 *
 * Programmatic UI - no Blueprint required
 */
UCLASS(Blueprintable, BlueprintType)
class TRANSLATORSCARD_API UW_TitleScreen : public UUserWidget
{
    GENERATED_BODY()

public:
    UW_TitleScreen(const FObjectInitializer& ObjectInitializer);

    // === DELEGATES ===

    /** Fired when user presses Enter to start the game */
    UPROPERTY(BlueprintAssignable, Category = "UEBridge|Events")
    FOnStartRequested OnStartRequested;

    // === STYLE ===

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor BackgroundColor = FLinearColor(0.02f, 0.02f, 0.05f, 1.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor TitleColor = FLinearColor(0.36f, 1.0f, 0.86f, 1.0f);  // Cyan #5cffdb

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor SubtitleColor = FLinearColor(0.5f, 0.5f, 0.6f, 1.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Style")
    FLinearColor PromptColor = FLinearColor(0.36f, 1.0f, 0.86f, 0.8f);

    // === INPUT ===

    /** Optional Enhanced Input action for starting the game. If set, binds to Enhanced Input system. */
    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "UEBridge|Input")
    TObjectPtr<UInputAction> StartInputAction;

    // Build widget tree BEFORE Slate hierarchy is constructed
    virtual TSharedRef<SWidget> RebuildWidget() override;

protected:
    virtual void NativeConstruct() override;
    virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;
    virtual FReply NativeOnKeyDown(const FGeometry& InGeometry, const FKeyEvent& InKeyEvent) override;

    UPROPERTY(BlueprintReadOnly, meta = (BindWidget, OptionalWidget = true))
    UTextBlock* TitleText;

    UPROPERTY(BlueprintReadOnly, meta = (BindWidget, OptionalWidget = true))
    UTextBlock* SubtitleText;

    UPROPERTY(BlueprintReadOnly, meta = (BindWidget, OptionalWidget = true))
    UTextBlock* PromptText;

    UPROPERTY(BlueprintReadOnly, meta = (BindWidget, OptionalWidget = true))
    UBorder* BackgroundBorder;

private:
    void BuildWidgetTree();

    /** Handle Enhanced Input start action */
    void HandleStartAction(const FInputActionValue& Value);

    /** Elapsed time for pulsing animation */
    float PulseTimer = 0.0f;

    /** Whether start has already been requested (prevent double-fire) */
    bool bStartRequested = false;
};
