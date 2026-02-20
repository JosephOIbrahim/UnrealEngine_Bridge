// BridgeTypes.h
// Shared data types and delegates for the UE Bridge plugin.
// Included by both Runtime and Editor modules.

#pragma once

#include "CoreMinimal.h"
#include "BridgeTypes.generated.h"

// ============================================================================
// Enums
// ============================================================================

/** Bridge state machine states */
UENUM(BlueprintType, meta = (ToolTip = "Bridge state machine states"))
enum class EUEBridgeState : uint8
{
    /** No file watcher running. StartGame() not called yet. */
    Idle            UMETA(DisplayName = "Idle"),

    /** File watcher running, waiting for Python bridge_orchestrator "ready" message. */
    WaitingForBridge UMETA(DisplayName = "Waiting For Bridge"),

    /** Python sent "ready". UE5 sent acknowledgment. Waiting for first question. */
    Connected       UMETA(DisplayName = "Connected"),

    /** A question is active and awaiting player input. */
    QuestionActive  UMETA(DisplayName = "Question Active"),

    /** Answer submitted. Waiting for next question from Python side. */
    AnswerPending   UMETA(DisplayName = "Answer Pending"),

    /** Scene transition in progress between questions. */
    Transitioning   UMETA(DisplayName = "Transitioning"),

    /** Profile complete and exported to disk. */
    Complete        UMETA(DisplayName = "Complete"),

    /** File I/O error, parse failure, or timeout. */
    Error           UMETA(DisplayName = "Error")
};

/** Error codes for bridge failures */
UENUM(BlueprintType, meta = (ToolTip = "Error codes for bridge failures"))
enum class EBridgeErrorCode : uint8
{
    None                    UMETA(DisplayName = "None"),
    BridgeDirectoryMissing  UMETA(DisplayName = "Bridge Directory Missing"),
    FileReadFailure         UMETA(DisplayName = "File Read Failure"),
    FileWriteFailure        UMETA(DisplayName = "File Write Failure"),
    JsonParseFailure        UMETA(DisplayName = "JSON Parse Failure"),
    UsdParseFailure         UMETA(DisplayName = "USD Parse Failure"),
    AnswerTimeout           UMETA(DisplayName = "Answer Timeout"),
    ProfileParseFailure     UMETA(DisplayName = "Profile Parse Failure"),
    QuestionIdMismatch      UMETA(DisplayName = "Question ID Mismatch")
};

/** Depth tier for question progression */
UENUM(BlueprintType, meta = (ToolTip = "Depth tier for question progression"))
enum class EDepthTier : uint8
{
    Surface     UMETA(DisplayName = "SURFACE"),     // Q1-Q2
    Patterns    UMETA(DisplayName = "PATTERNS"),     // Q3-Q4
    Feelings    UMETA(DisplayName = "FEELINGS"),     // Q5-Q6
    Core        UMETA(DisplayName = "CORE")          // Q7-Q8
};

// ============================================================================
// Structs
// ============================================================================

/** Structured question data from the Python orchestrator */
USTRUCT(BlueprintType, meta = (ToolTip = "Structured question data from the Python orchestrator"))
struct TRANSLATORSBRIDGERUNTIME_API FUEBridgeQuestion
{
    GENERATED_BODY()

    /** 0-based question index */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "0-based question index"))
    int32 Index = 0;

    /** Total number of questions (always 8 in current set) */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Total questions in the set"))
    int32 Total = 0;

    /** Unique question identifier (e.g. "load", "pace", "uncertainty") */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Unique question ID"))
    FString QuestionId;

    /** Display text for the question */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Question display text"))
    FString Text;

    /** Scene identifier (e.g. "forest_edge", "mirror_pool") */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Scene identifier for visual context"))
    FString Scene;

    /** Display labels for each option (length always 3) */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Answer option display labels"))
    TArray<FString> OptionLabels;

    /** Direction values for each option ("low", "mid", "high") */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Option direction values"))
    TArray<FString> OptionDirections;

    /** Human-readable depth label: "SURFACE", "PATTERNS", "FEELINGS", "CORE" */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Depth tier label"))
    FString DepthLabel;

    /** Typed depth tier for Blueprint switch nodes */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Depth tier enum"))
    EDepthTier DepthTier = EDepthTier::Surface;

    /** Cognitive dimension this question maps to */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Cognitive dimension ID"))
    FString DimensionId;

    /** Returns true if this question has been populated */
    bool IsValid() const { return Total > 0 && !QuestionId.IsEmpty(); }
};


/** A submitted player answer */
USTRUCT(BlueprintType, meta = (ToolTip = "A submitted player answer"))
struct TRANSLATORSBRIDGERUNTIME_API FTranslatorsAnswer
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Unique question identifier"))
    FString QuestionId;

    /** 0-based option index. -1 means skipped. */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Selected option index (0-based, -1 if skipped)"))
    int32 OptionIndex = -1;

    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Display label of the selected option"))
    FString SelectedLabel;

    /** "low", "mid", or "high" */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Direction value of the selected option"))
    FString SelectedDirection;

    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Player response time in milliseconds"))
    float ResponseTimeMs = 0.0f;

    /** ISO 8601 timestamp */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "ISO 8601 timestamp of the answer"))
    FString Timestamp;

    bool IsValid() const { return OptionIndex >= 0 && !QuestionId.IsEmpty(); }
};


/** A single cognitive profile trait */
USTRUCT(BlueprintType, meta = (ToolTip = "A single cognitive profile trait"))
struct TRANSLATORSBRIDGERUNTIME_API FTranslatorsTrait
{
    GENERATED_BODY()

    /** Dimension identifier (e.g. "cognitive_density") */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Cognitive dimension identifier"))
    FString Dimension;

    /** Human-readable label (e.g. "Balanced") */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Human-readable trait label"))
    FString Label;

    /** Normalized score 0.0 - 1.0 */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Normalized trait score from 0 to 1"))
    float Score = 0.0f;

    /** Behavioral description (e.g. "You can hold moderate complexity") */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Behavioral description of the trait"))
    FString Behavior;
};


/** Complete cognitive profile result */
USTRUCT(BlueprintType, meta = (ToolTip = "Complete cognitive profile result"))
struct TRANSLATORSBRIDGERUNTIME_API FUEBridgeProfile
{
    GENERATED_BODY()

    /** One trait per question/dimension */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "One trait per cognitive dimension"))
    TArray<FTranslatorsTrait> Traits;

    /** Generated insights from the profile */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Generated insights from the profile"))
    TArray<FString> Insights;

    /** 8-char hex DJB2 checksum (e.g. "101bfab5") */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "8-char hex DJB2 deterministic checksum"))
    FString Checksum;

    /** Anchor string: "[TRANSLATORS:checksum]" */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Anchor string for AI recognition"))
    FString Anchor;

    /** Raw dimension scores keyed by dimension ID */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Raw dimension scores keyed by dimension ID"))
    TMap<FString, float> Dimensions;

    /** Ordered answer history */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Ordered history of player answers"))
    TArray<FTranslatorsAnswer> Answers;

    /** Disk path to exported cognitive_profile.usda */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Disk path to exported cognitive_profile.usda"))
    FString UsdExportPath;

    /** Bridge version that generated this profile */
    UPROPERTY(BlueprintReadOnly, Category = "Translators", meta = (ToolTip = "Bridge version that generated this profile"))
    FString GeneratorVersion;

    /** Returns true if profile has been populated */
    UFUNCTION(BlueprintCallable, BlueprintPure, Category = "Translators", meta = (ToolTip = "True if profile has valid trait data"))
    bool IsValid() const { return Traits.Num() > 0 && !Checksum.IsEmpty(); }
};


/** Accumulated behavioral signals for ADHD_MoE expert routing */
USTRUCT(BlueprintType, meta = (ToolTip = "Accumulated behavioral signals for MoE expert routing"))
struct TRANSLATORSBRIDGERUNTIME_API FBehavioralSignals
{
    GENERATED_BODY()

    /** Responses longer than 10 seconds */
    UPROPERTY(BlueprintReadOnly, Category = "UEBridge|Behavioral", meta = (ToolTip = "Count of responses longer than 10 seconds"))
    int32 HesitationCount = 0;

    /** Responses shorter than 500ms */
    UPROPERTY(BlueprintReadOnly, Category = "UEBridge|Behavioral", meta = (ToolTip = "Count of responses shorter than 500ms"))
    int32 RapidClickCount = 0;

    /** Skipped questions (reserved) */
    UPROPERTY(BlueprintReadOnly, Category = "UEBridge|Behavioral", meta = (ToolTip = "Number of skipped questions"))
    int32 SkipCount = 0;

    /** Back navigation count (reserved) */
    UPROPERTY(BlueprintReadOnly, Category = "UEBridge|Behavioral", meta = (ToolTip = "Number of back navigations"))
    int32 BackNavigationCount = 0;

    /** Most recent response time in ms */
    UPROPERTY(BlueprintReadOnly, Category = "UEBridge|Behavioral", meta = (ToolTip = "Most recent response time in milliseconds"))
    float LastResponseTimeMs = 0.0f;

    /** Running average response time in ms */
    UPROPERTY(BlueprintReadOnly, Category = "UEBridge|Behavioral", meta = (ToolTip = "Running average response time in milliseconds"))
    float AverageResponseTimeMs = 0.0f;

    /** MoE detected cognitive state (e.g. "focused", "stuck", "frustrated") */
    UPROPERTY(BlueprintReadOnly, Category = "UEBridge|Behavioral", meta = (ToolTip = "MoE-detected cognitive state"))
    FString DetectedState;

    /** MoE recommended expert (e.g. "Direct", "Scaffolder", "Validator") */
    UPROPERTY(BlueprintReadOnly, Category = "UEBridge|Behavioral", meta = (ToolTip = "MoE-recommended expert for this state"))
    FString RecommendedExpert;

    /** Burnout level: "GREEN", "YELLOW", "ORANGE", "RED" */
    UPROPERTY(BlueprintReadOnly, Category = "UEBridge|Behavioral", meta = (ToolTip = "Burnout level: GREEN, YELLOW, ORANGE, or RED"))
    FString BurnoutLevel;

    /** Momentum phase: "building", "rolling", "peak", "declining", "crashed" */
    UPROPERTY(BlueprintReadOnly, Category = "UEBridge|Behavioral", meta = (ToolTip = "Current momentum phase"))
    FString MomentumPhase;

    /** Total answers recorded */
    UPROPERTY(BlueprintReadOnly, Category = "UEBridge|Behavioral", meta = (ToolTip = "Total number of answers recorded"))
    int32 TotalResponsesRecorded = 0;
};


// ============================================================================
// Delegates
// ============================================================================

/** Fired when Python bridge_orchestrator signals ready */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnBridgeReady, int32, TotalQuestions);

/** Fired when a new question arrives (fully parsed) */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnQuestionReady, const FUEBridgeQuestion&, Question);

/** Fired during scene transitions between questions */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_ThreeParams(FOnTransitionReady, const FString&, Direction, const FString&, NextScene, float, Progress);

/** Fired when the cognitive profile is complete and exported */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnProfileComplete, const FUEBridgeProfile&, Profile, const FString&, UsdPath);

/** Fired on any bridge error */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_TwoParams(FOnBridgeError, EBridgeErrorCode, ErrorCode, const FString&, Message);

/** Fired when a USD profile file changes on disk */
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnUsdProfileUpdated, const FString&, UpdatedFilePath);
