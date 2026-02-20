// UEBridgeSubsystem.cpp
// Phase 4: Game flow logic migrated from BridgeComponent.
// This subsystem is the single source of truth for bridge state.

#include "UEBridgeSubsystem.h"
#include "UEBridgeRuntime.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "HAL/PlatformProcess.h"
#include "HAL/PlatformFileManager.h"
#include "JsonObjectConverter.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonWriter.h"
#include "Serialization/JsonSerializer.h"
#include "Internationalization/Regex.h"
#include "Engine/Engine.h"


// === LIFECYCLE ===

void UUEBridgeSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    BridgePath = ResolveBridgePath();
    UE_LOG(LogUEBridge, Log, TEXT("UEBridgeSubsystem initialized (path: %s)"), *BridgePath);
}

void UUEBridgeSubsystem::Deinitialize()
{
    StopGame();
    UE_LOG(LogUEBridge, Log, TEXT("UEBridgeSubsystem deinitialized"));
    Super::Deinitialize();
}

TStatId UUEBridgeSubsystem::GetStatId() const
{
    RETURN_QUICK_DECLARE_CYCLE_STAT(UUEBridgeSubsystem, STATGROUP_Tickables);
}


// === TICK ===

void UUEBridgeSubsystem::Tick(float DeltaTime)
{
    // Polling for state file changes
    PollTimer += DeltaTime;
    if (PollTimer >= PollInterval)
    {
        PollTimer = 0.0f;

        IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();

        // Check USD state file first
        FString UsdFilePath = GetBridgeFilePath(TEXT("bridge_state.usda"));
        if (PlatformFile.FileExists(*UsdFilePath))
        {
            FDateTime ModTime = PlatformFile.GetTimeStamp(*UsdFilePath);
            if (ModTime > LastStateFileTime)
            {
                LastStateFileTime = ModTime;
                bStateChangePending = true;
                TimeSinceLastStateChange = 0.0f;
            }
        }
        else
        {
            // Fall back to JSON state file
            FString JsonFilePath = GetBridgeFilePath(TEXT("state.json"));
            if (PlatformFile.FileExists(*JsonFilePath))
            {
                FDateTime ModTime = PlatformFile.GetTimeStamp(*JsonFilePath);
                if (ModTime > LastStateFileTime)
                {
                    LastStateFileTime = ModTime;
                    bStateChangePending = true;
                    TimeSinceLastStateChange = 0.0f;
                }
            }
        }

        // Check USD profile files
        FString ProfilePath = GetBridgeFilePath(TEXT("cognitive_profile.usda"));
        FString SubstratePath = GetBridgeFilePath(TEXT("cognitive_substrate.usda"));
        for (const FString& Path : { ProfilePath, SubstratePath })
        {
            if (PlatformFile.FileExists(*Path))
            {
                FDateTime ModTime = PlatformFile.GetTimeStamp(*Path);
                if (ModTime > LastUsdFileTime)
                {
                    LastUsdFileTime = ModTime;
                    bUsdChangePending = true;
                    TimeSinceLastUsdChange = 0.0f;
                }
            }
        }
    }

    // Debounced state file processing
    if (bStateChangePending)
    {
        TimeSinceLastStateChange += DeltaTime;
        if (TimeSinceLastStateChange >= DebounceTime)
        {
            bStateChangePending = false;
            ProcessStateFile();
        }
    }

    // Debounced USD profile processing
    if (bUsdChangePending)
    {
        TimeSinceLastUsdChange += DeltaTime;
        if (TimeSinceLastUsdChange >= DebounceTime)
        {
            bUsdChangePending = false;
            BridgeLog(TEXT("USD profile file changed"));
            // Find which file changed and broadcast
            FString ProfilePath = GetBridgeFilePath(TEXT("cognitive_profile.usda"));
            FString SubstratePath = GetBridgeFilePath(TEXT("cognitive_substrate.usda"));
            IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();
            if (PlatformFile.FileExists(*ProfilePath))
            {
                OnUsdProfileUpdated.Broadcast(ProfilePath);
            }
            else if (PlatformFile.FileExists(*SubstratePath))
            {
                OnUsdProfileUpdated.Broadcast(SubstratePath);
            }
        }
    }
}


// === GAME FLOW ===

void UUEBridgeSubsystem::StartGame()
{
    if (bIsActive)
    {
        BridgeLog(TEXT("Bridge already active"));
        return;
    }

    BridgeLog(TEXT("========================================"));
    BridgeLog(TEXT("TRANSLATORS BRIDGE SUBSYSTEM v2.1.0"));
    BridgeLog(TEXT("USD-native communication with JSON fallback"));
    BridgeLog(FString::Printf(TEXT("Bridge Path: %s"), *BridgePath));
    BridgeLog(TEXT("========================================"));

    // Ensure bridge directory exists
    IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();
    if (!PlatformFile.DirectoryExists(*BridgePath))
    {
        PlatformFile.CreateDirectory(*BridgePath);
        BridgeLog(FString::Printf(TEXT("Created bridge directory: %s"), *BridgePath));
    }

    bIsActive = true;
    SetState(EUEBridgeState::WaitingForBridge);

    // Check for existing state files (Python may have started first)
    FString UsdFilePath = GetBridgeFilePath(TEXT("bridge_state.usda"));
    FString JsonFilePath = GetBridgeFilePath(TEXT("state.json"));

    if (PlatformFile.FileExists(*UsdFilePath))
    {
        BridgeLog(TEXT("Found existing bridge_state.usda - processing..."));
        ProcessStateFile();
    }
    else if (PlatformFile.FileExists(*JsonFilePath))
    {
        BridgeLog(TEXT("Found existing state.json - processing..."));
        ProcessStateFile();
    }
}

void UUEBridgeSubsystem::StopGame()
{
    if (!bIsActive)
    {
        return;
    }

    bIsActive = false;
    bStateChangePending = false;
    bUsdChangePending = false;
    SetState(EUEBridgeState::Idle);

    BridgeLog(TEXT("Bridge stopped"));
}


void UUEBridgeSubsystem::SubmitAnswer(const FString& QuestionId, int32 OptionIndex, float ResponseTimeMs)
{
    // Try USD mode first
    FString FilePath = GetBridgeFilePath(TEXT("bridge_state.usda"));
    FString Content;

    if (bUsingUsdMode && FFileHelper::LoadFileToString(Content, *FilePath))
    {
        FString Timestamp = FDateTime::UtcNow().ToIso8601();
        FString SelectedLabel = (OptionIndex >= 0 && OptionIndex < CurrentQuestion.OptionLabels.Num())
            ? CurrentQuestion.OptionLabels[OptionIndex] : TEXT("");
        FString SelectedDirection = (OptionIndex >= 0 && OptionIndex < CurrentQuestion.OptionDirections.Num())
            ? CurrentQuestion.OptionDirections[OptionIndex] : TEXT("");

        Content = UpdateUsdaVariant(Content, TEXT("sync_status"), TEXT("answer_received"));
        Content = UpdateUsdaVariant(Content, TEXT("message_type"), TEXT("answer"));

        Content = UpdateUsdaAttribute(Content, TEXT("Answer"), TEXT("question_id"), QuestionId, true);
        Content = UpdateUsdaAttribute(Content, TEXT("Answer"), TEXT("option_index"), FString::FromInt(OptionIndex), false);
        Content = UpdateUsdaAttribute(Content, TEXT("Answer"), TEXT("response_time_ms"), FString::SanitizeFloat(ResponseTimeMs), false);
        Content = UpdateUsdaAttribute(Content, TEXT("Answer"), TEXT("selected_label"), SelectedLabel, true);
        Content = UpdateUsdaAttribute(Content, TEXT("Answer"), TEXT("selected_direction"), SelectedDirection, true);
        Content = UpdateUsdaAttribute(Content, TEXT("Answer"), TEXT("timestamp"), Timestamp, true);

        UpdateBehavioralSignals(Content, ResponseTimeMs);

        int32 MaxRetries = 3;
        for (int32 Retry = 0; Retry < MaxRetries; ++Retry)
        {
            if (FFileHelper::SaveStringToFile(Content, *FilePath))
            {
                BridgeLog(FString::Printf(TEXT("USD answer sent: %s = option %d (%.0fms)"),
                    *QuestionId, OptionIndex, ResponseTimeMs));
                SetState(EUEBridgeState::AnswerPending);
                return;
            }
            FPlatformProcess::Sleep(0.1f);
        }

        BridgeLog(TEXT("USD answer write failed, falling back to JSON"));
    }

    // JSON fallback
    TSharedPtr<FJsonObject> JsonObj = MakeShared<FJsonObject>();
    JsonObj->SetStringField(TEXT("$schema"), TEXT("translators-answer-v1"));
    JsonObj->SetStringField(TEXT("type"), TEXT("answer"));
    JsonObj->SetStringField(TEXT("timestamp"), FDateTime::UtcNow().ToIso8601());

    TSharedPtr<FJsonObject> AnswerObj = MakeShared<FJsonObject>();
    AnswerObj->SetStringField(TEXT("question_id"), QuestionId);
    AnswerObj->SetNumberField(TEXT("option_index"), OptionIndex);
    AnswerObj->SetNumberField(TEXT("response_time_ms"), ResponseTimeMs);
    JsonObj->SetObjectField(TEXT("answer"), AnswerObj);

    WriteJsonToFile(TEXT("answer.json"), JsonObj);
    SetState(EUEBridgeState::AnswerPending);

    BridgeLog(FString::Printf(TEXT("JSON answer sent: %s = option %d (%.0fms)"),
        *QuestionId, OptionIndex, ResponseTimeMs));
}


void UUEBridgeSubsystem::SendAcknowledge()
{
    // Try USD mode first
    FString FilePath = GetBridgeFilePath(TEXT("bridge_state.usda"));
    FString Content;

    if (FFileHelper::LoadFileToString(Content, *FilePath))
    {
        FString Timestamp = FDateTime::UtcNow().ToIso8601();

        Content = UpdateUsdaVariant(Content, TEXT("message_type"), TEXT("ack"));
        Content = UpdateUsdaAttribute(Content, TEXT("Ack"), TEXT("ready"), TEXT("true"), false);
        Content = UpdateUsdaAttribute(Content, TEXT("Ack"), TEXT("ue_version"), FString(ENGINE_VERSION_STRING), true);
        Content = UpdateUsdaAttribute(Content, TEXT("Ack"), TEXT("project"), TEXT("UnrealEngineBridge"), true);
        Content = UpdateUsdaAttribute(Content, TEXT("Ack"), TEXT("timestamp"), Timestamp, true);

        if (FFileHelper::SaveStringToFile(Content, *FilePath))
        {
            BridgeLog(TEXT("USD acknowledgment sent"));
            bUsingUsdMode = true;
            return;
        }
    }

    // JSON fallback
    TSharedPtr<FJsonObject> JsonObj = MakeShared<FJsonObject>();
    JsonObj->SetStringField(TEXT("$schema"), TEXT("translators-answer-v1"));
    JsonObj->SetStringField(TEXT("type"), TEXT("ack"));
    JsonObj->SetStringField(TEXT("timestamp"), FDateTime::UtcNow().ToIso8601());

    TSharedPtr<FJsonObject> AckObj = MakeShared<FJsonObject>();
    AckObj->SetBoolField(TEXT("ready"), true);
    AckObj->SetStringField(TEXT("ue_version"), FString(ENGINE_VERSION_STRING));
    AckObj->SetStringField(TEXT("project"), TEXT("UnrealEngineBridge"));
    JsonObj->SetObjectField(TEXT("ack"), AckObj);

    WriteJsonToFile(TEXT("answer.json"), JsonObj);
    BridgeLog(TEXT("JSON acknowledgment sent"));
}


void UUEBridgeSubsystem::ForceReloadUsdStage()
{
    BridgeLog(TEXT("Force USD reload requested — broadcasting OnUsdProfileUpdated"));
    FString ProfilePath = GetBridgeFilePath(TEXT("cognitive_profile.usda"));
    OnUsdProfileUpdated.Broadcast(ProfilePath);
}


void UUEBridgeSubsystem::NotifyFileChanged(const FString& Filename, bool bIsUsdProfile)
{
    if (bIsUsdProfile)
    {
        bUsdChangePending = true;
        TimeSinceLastUsdChange = 0.0f;
    }
    else
    {
        bStateChangePending = true;
        TimeSinceLastStateChange = 0.0f;
    }
}


// === INTERNAL STATE ===

void UUEBridgeSubsystem::SetState(EUEBridgeState NewState)
{
    if (CurrentState != NewState)
    {
        if (bVerboseLogging)
        {
            BridgeLog(FString::Printf(TEXT("State: %d -> %d"), (int32)CurrentState, (int32)NewState));
        }
        CurrentState = NewState;
    }
}


FString UUEBridgeSubsystem::ResolveBridgePath() const
{
    FString HomePath;

#if PLATFORM_WINDOWS
    FString UserProfile = FPlatformMisc::GetEnvironmentVariable(TEXT("USERPROFILE"));
    if (!UserProfile.IsEmpty())
    {
        HomePath = UserProfile;
    }
    else
    {
        HomePath = FPlatformProcess::UserHomeDir();
    }
#else
    HomePath = FPlatformProcess::UserHomeDir();
#endif

    FPaths::NormalizeDirectoryName(HomePath);
    return FPaths::Combine(HomePath, TEXT(".translators"));
}


FString UUEBridgeSubsystem::GetBridgeFilePath(const FString& Filename) const
{
    return FPaths::Combine(BridgePath, Filename);
}


void UUEBridgeSubsystem::BridgeLog(const FString& Message) const
{
    UE_LOG(LogUEBridge, Log, TEXT("[Bridge] %s"), *Message);

#if !UE_BUILD_SHIPPING
    if (bVerboseLogging && GEngine)
    {
        GEngine->AddOnScreenDebugMessage(-1, 5.0f, FColor::Cyan,
            FString::Printf(TEXT("[Bridge] %s"), *Message));
    }
#endif
}


// === FILE I/O ===

void UUEBridgeSubsystem::ProcessStateFile()
{
    // Try USD mode first (v2.0.0)
    FString UsdFilePath = GetBridgeFilePath(TEXT("bridge_state.usda"));
    IPlatformFile& PlatformFile = FPlatformFileManager::Get().GetPlatformFile();

    if (PlatformFile.FileExists(*UsdFilePath))
    {
        if (ProcessBridgeStateUsda())
        {
            return;
        }
    }

    // Fall back to JSON mode (v1.0.0)
    FString FilePath = GetBridgeFilePath(TEXT("state.json"));
    FString Content;

    if (!FFileHelper::LoadFileToString(Content, *FilePath))
    {
        return;
    }

    TSharedPtr<FJsonObject> JsonObj;
    TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Content);

    if (!FJsonSerializer::Deserialize(Reader, JsonObj) || !JsonObj.IsValid())
    {
        OnBridgeError.Broadcast(EBridgeErrorCode::JsonParseFailure, TEXT("Invalid JSON in state.json"));
        return;
    }

    CurrentStateJson = Content;
    bUsingUsdMode = false;

    FString StateType;
    if (JsonObj->TryGetStringField(TEXT("type"), StateType))
    {
        if (StateType == TEXT("ready"))
        {
            HandleReadyState(JsonObj);
        }
        else if (StateType == TEXT("question"))
        {
            HandleQuestionState(JsonObj);
        }
        else if (StateType == TEXT("transition"))
        {
            HandleTransitionState(JsonObj);
        }
        else if (StateType == TEXT("finale"))
        {
            HandleFinaleState(JsonObj);
        }
    }
}


void UUEBridgeSubsystem::WriteJsonToFile(const FString& Filename, const TSharedPtr<FJsonObject>& JsonObj)
{
    FString FilePath = GetBridgeFilePath(Filename);
    FString OutputString;

    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
    FJsonSerializer::Serialize(JsonObj.ToSharedRef(), Writer);

    int32 MaxRetries = 3;
    for (int32 Retry = 0; Retry < MaxRetries; ++Retry)
    {
        if (FFileHelper::SaveStringToFile(OutputString, *FilePath))
        {
            return;
        }

        if (Retry < MaxRetries - 1)
        {
            BridgeLog(FString::Printf(TEXT("Write failed, retry %d/%d..."), Retry + 1, MaxRetries));
            FPlatformProcess::Sleep(0.1f);
        }
    }

    OnBridgeError.Broadcast(EBridgeErrorCode::FileWriteFailure,
        FString::Printf(TEXT("Failed to write %s after %d retries"), *Filename, MaxRetries));
}


// === JSON STATE HANDLERS ===

void UUEBridgeSubsystem::HandleReadyState(const TSharedPtr<FJsonObject>& JsonObj)
{
    const TSharedPtr<FJsonObject>* ReadyObjPtr;
    const TSharedPtr<FJsonObject>& ReadyData =
        JsonObj->TryGetObjectField(TEXT("ready"), ReadyObjPtr) ? *ReadyObjPtr : JsonObj;

    int32 TotalQuestions = ReadyData->GetIntegerField(TEXT("total_questions"));

    BridgeLog(FString::Printf(TEXT("Bridge ready! Total questions: %d"), TotalQuestions));

    SetState(EUEBridgeState::Connected);
    OnBridgeReady.Broadcast(TotalQuestions);
}


void UUEBridgeSubsystem::HandleQuestionState(const TSharedPtr<FJsonObject>& JsonObj)
{
    const TSharedPtr<FJsonObject>* QuestionObjPtr;
    const TSharedPtr<FJsonObject>& QuestionData =
        JsonObj->TryGetObjectField(TEXT("question"), QuestionObjPtr) ? *QuestionObjPtr : JsonObj;

    CurrentQuestion = FUEBridgeQuestion();
    CurrentQuestion.Index = QuestionData->GetIntegerField(TEXT("index"));
    CurrentQuestion.Total = QuestionData->GetIntegerField(TEXT("total"));
    CurrentQuestion.QuestionId = QuestionData->GetStringField(TEXT("id"));
    CurrentQuestion.Text = QuestionData->GetStringField(TEXT("text"));
    CurrentQuestion.Scene = QuestionData->GetStringField(TEXT("scene"));

    const TArray<TSharedPtr<FJsonValue>>* OptionsArray;
    if (QuestionData->TryGetArrayField(TEXT("options"), OptionsArray))
    {
        for (const TSharedPtr<FJsonValue>& OptionVal : *OptionsArray)
        {
            const TSharedPtr<FJsonObject>& OptionObj = OptionVal->AsObject();
            if (OptionObj.IsValid())
            {
                CurrentQuestion.OptionLabels.Add(OptionObj->GetStringField(TEXT("label")));
                CurrentQuestion.OptionDirections.Add(OptionObj->GetStringField(TEXT("direction")));
            }
        }
    }

    CurrentQuestion.DepthLabel = GetDepthLabelForIndex(CurrentQuestion.Index);

    BridgeLog(FString::Printf(TEXT("Question %d/%d [%s]: %s"),
        CurrentQuestion.Index + 1, CurrentQuestion.Total,
        *CurrentQuestion.DepthLabel, *CurrentQuestion.QuestionId));

    SetState(EUEBridgeState::QuestionActive);
    OnQuestionReady.Broadcast(CurrentQuestion);
}


void UUEBridgeSubsystem::HandleTransitionState(const TSharedPtr<FJsonObject>& JsonObj)
{
    const TSharedPtr<FJsonObject>* TransObjPtr;
    const TSharedPtr<FJsonObject>& TransData =
        JsonObj->TryGetObjectField(TEXT("transition"), TransObjPtr) ? *TransObjPtr : JsonObj;

    FString Direction = TransData->GetStringField(TEXT("direction"));
    FString NextScene = TransData->GetStringField(TEXT("next_scene"));
    float Progress = TransData->GetNumberField(TEXT("progress"));

    BridgeLog(FString::Printf(TEXT("Transition: %s -> %s (%.0f%%)"),
        *Direction, *NextScene, Progress * 100.0f));

    SetState(EUEBridgeState::Transitioning);
    OnTransitionReady.Broadcast(Direction, NextScene, Progress);
}


void UUEBridgeSubsystem::HandleFinaleState(const TSharedPtr<FJsonObject>& JsonObj)
{
    const TSharedPtr<FJsonObject>* FinaleObjPtr;
    const TSharedPtr<FJsonObject>& FinaleData =
        JsonObj->TryGetObjectField(TEXT("finale"), FinaleObjPtr) ? *FinaleObjPtr : JsonObj;

    FString UsdPath = FinaleData->GetStringField(TEXT("usd_path"));
    FString Message = FinaleData->GetStringField(TEXT("message"));

    BridgeLog(FString::Printf(TEXT("FINALE: %s"), *Message));

    // Auto-parse the profile
    FUEBridgeProfile Profile = ParseCognitiveProfile(UsdPath);

    SetState(EUEBridgeState::Complete);
    OnProfileComplete.Broadcast(Profile, UsdPath);
}


// === USD NATIVE COMMUNICATION ===

bool UUEBridgeSubsystem::ProcessBridgeStateUsda()
{
    FString FilePath = GetBridgeFilePath(TEXT("bridge_state.usda"));
    FString Content;

    if (!FFileHelper::LoadFileToString(Content, *FilePath))
    {
        return false;
    }

    FString SyncStatus = ParseUsdaVariant(Content, TEXT("sync_status"));
    FString MessageType = ParseUsdaVariant(Content, TEXT("message_type"));

    if (bVerboseLogging)
    {
        BridgeLog(FString::Printf(TEXT("USD sync_status=%s, message_type=%s"), *SyncStatus, *MessageType));
    }

    if (MessageType == TEXT("ready"))
    {
        HandleUsdaReadyState(Content);
    }
    else if (MessageType == TEXT("question") && SyncStatus == TEXT("question_pending"))
    {
        HandleUsdaQuestionState(Content);
    }
    else if (MessageType == TEXT("transition"))
    {
        HandleUsdaTransitionState(Content);
    }
    else if (MessageType == TEXT("finale"))
    {
        HandleUsdaFinaleState(Content);
    }

    return true;
}


FString UUEBridgeSubsystem::ParseUsdaVariant(const FString& Content, const FString& VariantSetName)
{
    FString Pattern = FString::Printf(TEXT("string %s = \"([^\"]*)\""), *VariantSetName);
    FRegexPattern RegexPattern(Pattern);
    FRegexMatcher Matcher(RegexPattern, Content);

    if (Matcher.FindNext())
    {
        return Matcher.GetCaptureGroup(1);
    }
    return TEXT("");
}


FString UUEBridgeSubsystem::ParseUsdaAttribute(const FString& Content, const FString& PrimPath, const FString& AttrName)
{
    FString PrimPattern = FString::Printf(TEXT("def [^\"]*\"%s\"[^{]*\\{([^}]*)\\}"), *PrimPath);
    FRegexPattern PrimRegex(PrimPattern);
    FRegexMatcher PrimMatcher(PrimRegex, Content);

    FString PrimContent;
    if (PrimMatcher.FindNext())
    {
        PrimContent = PrimMatcher.GetCaptureGroup(1);
    }
    else
    {
        PrimContent = Content;
    }

    // Parse string attribute
    FString StringPattern = FString::Printf(TEXT("string %s = \"([^\"]*)\""), *AttrName);
    FRegexPattern StringRegex(StringPattern);
    FRegexMatcher StringMatcher(StringRegex, PrimContent);
    if (StringMatcher.FindNext())
    {
        return StringMatcher.GetCaptureGroup(1);
    }

    // Parse int attribute
    FString IntPattern = FString::Printf(TEXT("int %s = (-?\\d+)"), *AttrName);
    FRegexPattern IntRegex(IntPattern);
    FRegexMatcher IntMatcher(IntRegex, PrimContent);
    if (IntMatcher.FindNext())
    {
        return IntMatcher.GetCaptureGroup(1);
    }

    // Parse float/double attribute
    FString FloatPattern = FString::Printf(TEXT("(?:float|double) %s = ([\\d.]+)"), *AttrName);
    FRegexPattern FloatRegex(FloatPattern);
    FRegexMatcher FloatMatcher(FloatRegex, PrimContent);
    if (FloatMatcher.FindNext())
    {
        return FloatMatcher.GetCaptureGroup(1);
    }

    return TEXT("");
}


void UUEBridgeSubsystem::HandleUsdaReadyState(const FString& Content)
{
    int32 TotalQuestions = FCString::Atoi(*ParseUsdaAttribute(Content, TEXT("Ready"), TEXT("total_questions")));
    if (TotalQuestions <= 0) TotalQuestions = 8;

    BridgeLog(FString::Printf(TEXT("USD Ready: %d questions"), TotalQuestions));

    bUsingUsdMode = true;
    SetState(EUEBridgeState::Connected);
    OnBridgeReady.Broadcast(TotalQuestions);
}


void UUEBridgeSubsystem::HandleUsdaQuestionState(const FString& Content)
{
    CurrentQuestion = FUEBridgeQuestion();
    CurrentQuestion.Index = FCString::Atoi(*ParseUsdaAttribute(Content, TEXT("Message"), TEXT("index")));
    CurrentQuestion.Total = FCString::Atoi(*ParseUsdaAttribute(Content, TEXT("Message"), TEXT("total")));
    CurrentQuestion.QuestionId = ParseUsdaAttribute(Content, TEXT("Message"), TEXT("question_id"));
    CurrentQuestion.Text = ParseUsdaAttribute(Content, TEXT("Message"), TEXT("text"));
    CurrentQuestion.Scene = ParseUsdaAttribute(Content, TEXT("Message"), TEXT("scene"));

    for (int32 i = 0; i < 3; ++i)
    {
        FString OptionPrim = FString::Printf(TEXT("Option_%d"), i);
        FString Label = ParseUsdaAttribute(Content, OptionPrim, TEXT("label"));
        FString Direction = ParseUsdaAttribute(Content, OptionPrim, TEXT("direction"));

        if (!Label.IsEmpty())
        {
            CurrentQuestion.OptionLabels.Add(Label);
            CurrentQuestion.OptionDirections.Add(Direction);
        }
    }

    CurrentQuestion.DepthLabel = GetDepthLabelForIndex(CurrentQuestion.Index);

    BridgeLog(FString::Printf(TEXT("USD Question %d/%d [%s]: %s"),
        CurrentQuestion.Index + 1, CurrentQuestion.Total,
        *CurrentQuestion.DepthLabel, *CurrentQuestion.QuestionId));

    CurrentStateJson = BuildQuestionJson();
    SetState(EUEBridgeState::QuestionActive);
    OnQuestionReady.Broadcast(CurrentQuestion);
}


void UUEBridgeSubsystem::HandleUsdaTransitionState(const FString& Content)
{
    FString Direction = ParseUsdaAttribute(Content, TEXT("Transition"), TEXT("direction"));
    FString NextScene = ParseUsdaAttribute(Content, TEXT("Transition"), TEXT("next_scene"));
    float Progress = FCString::Atof(*ParseUsdaAttribute(Content, TEXT("Transition"), TEXT("progress")));

    BridgeLog(FString::Printf(TEXT("USD Transition: %s -> %s (%.0f%%)"),
        *Direction, *NextScene, Progress * 100.0f));

    SetState(EUEBridgeState::Transitioning);
    OnTransitionReady.Broadcast(Direction, NextScene, Progress);
}


void UUEBridgeSubsystem::HandleUsdaFinaleState(const FString& Content)
{
    FString UsdPath = ParseUsdaAttribute(Content, TEXT("Finale"), TEXT("usd_path"));
    FString Message = ParseUsdaAttribute(Content, TEXT("Finale"), TEXT("message"));

    BridgeLog(FString::Printf(TEXT("USD FINALE: %s"), *Message));

    FUEBridgeProfile Profile = ParseCognitiveProfile(UsdPath);

    SetState(EUEBridgeState::Complete);
    OnProfileComplete.Broadcast(Profile, UsdPath);
}


FString UUEBridgeSubsystem::BuildQuestionJson()
{
    TSharedPtr<FJsonObject> JsonObj = MakeShared<FJsonObject>();
    JsonObj->SetStringField(TEXT("type"), TEXT("question"));
    JsonObj->SetNumberField(TEXT("index"), CurrentQuestion.Index);
    JsonObj->SetNumberField(TEXT("total"), CurrentQuestion.Total);
    JsonObj->SetStringField(TEXT("id"), CurrentQuestion.QuestionId);
    JsonObj->SetStringField(TEXT("text"), CurrentQuestion.Text);
    JsonObj->SetStringField(TEXT("scene"), CurrentQuestion.Scene);

    TArray<TSharedPtr<FJsonValue>> OptionsArray;
    for (int32 i = 0; i < CurrentQuestion.OptionLabels.Num(); ++i)
    {
        TSharedPtr<FJsonObject> OptionObj = MakeShared<FJsonObject>();
        OptionObj->SetNumberField(TEXT("index"), i);
        OptionObj->SetStringField(TEXT("label"), CurrentQuestion.OptionLabels[i]);
        OptionObj->SetStringField(TEXT("direction"), CurrentQuestion.OptionDirections[i]);
        OptionsArray.Add(MakeShared<FJsonValueObject>(OptionObj));
    }
    JsonObj->SetArrayField(TEXT("options"), OptionsArray);

    FString OutputString;
    TSharedRef<TJsonWriter<>> Writer = TJsonWriterFactory<>::Create(&OutputString);
    FJsonSerializer::Serialize(JsonObj.ToSharedRef(), Writer);
    return OutputString;
}


FString UUEBridgeSubsystem::UpdateUsdaVariant(const FString& Content, const FString& VariantSetName, const FString& NewValue)
{
    FString SearchPattern = FString::Printf(TEXT("string %s = \""), *VariantSetName);
    int32 StartIdx = Content.Find(SearchPattern);
    if (StartIdx == INDEX_NONE)
    {
        return Content;
    }

    StartIdx += SearchPattern.Len();
    int32 EndIdx = Content.Find(TEXT("\""), ESearchCase::CaseSensitive, ESearchDir::FromStart, StartIdx);
    if (EndIdx == INDEX_NONE)
    {
        return Content;
    }

    return Content.Left(StartIdx) + NewValue + Content.Mid(EndIdx);
}


FString UUEBridgeSubsystem::UpdateUsdaAttribute(const FString& Content, const FString& PrimName, const FString& AttrName, const FString& NewValue, bool bIsString)
{
    FString Result = Content;

    if (bIsString)
    {
        FString SearchPattern = FString::Printf(TEXT("string %s = \""), *AttrName);
        int32 StartIdx = Result.Find(SearchPattern);
        if (StartIdx != INDEX_NONE)
        {
            StartIdx += SearchPattern.Len();
            int32 EndIdx = Result.Find(TEXT("\""), ESearchCase::CaseSensitive, ESearchDir::FromStart, StartIdx);
            if (EndIdx != INDEX_NONE)
            {
                FString EscapedValue = NewValue.Replace(TEXT("\\"), TEXT("\\\\")).Replace(TEXT("\""), TEXT("\\\""));
                Result = Result.Left(StartIdx) + EscapedValue + Result.Mid(EndIdx);
            }
        }
    }
    else
    {
        TArray<FString> TypePrefixes = { TEXT("int"), TEXT("float"), TEXT("double"), TEXT("bool") };

        for (const FString& TypePrefix : TypePrefixes)
        {
            FString SearchPattern = FString::Printf(TEXT("%s %s = "), *TypePrefix, *AttrName);
            int32 StartIdx = Result.Find(SearchPattern);
            if (StartIdx != INDEX_NONE)
            {
                StartIdx += SearchPattern.Len();
                int32 EndIdx = StartIdx;
                while (EndIdx < Result.Len())
                {
                    TCHAR C = Result[EndIdx];
                    if (C == '\n' || C == '\r' || C == ';' || C == ' ' || C == '\t')
                    {
                        break;
                    }
                    EndIdx++;
                }
                Result = Result.Left(StartIdx) + NewValue + Result.Mid(EndIdx);
                break;
            }
        }
    }

    return Result;
}


// === BEHAVIORAL SIGNALS ===

void UUEBridgeSubsystem::UpdateBehavioralSignals(FString& Content, float ResponseTimeMs)
{
    // Deterministic behavioral signal routing.
    // Fixed thresholds ensure same signals produce same expert selection.

    ResponseTimes.Add(ResponseTimeMs);

    float TotalTime = 0.0f;
    for (float Time : ResponseTimes)
    {
        TotalTime += Time;
    }
    float AvgResponseTime = ResponseTimes.Num() > 0 ? TotalTime / ResponseTimes.Num() : 0.0f;

    // Fixed thresholds (deterministic across all sessions)
    const float HESITATION_THRESHOLD_MS = 10000.0f;
    const float RAPID_CLICK_THRESHOLD_MS = 500.0f;
    const float DEPLETED_AVG_THRESHOLD_MS = 15000.0f;
    const int32 HESITATION_COUNT_THRESHOLD = 2;
    const int32 RAPID_CLICK_COUNT_THRESHOLD = 3;

    bool bLongHesitation = ResponseTimeMs > HESITATION_THRESHOLD_MS;
    if (bLongHesitation)
    {
        Signals.HesitationCount++;
    }

    bool bRapidClick = ResponseTimeMs < RAPID_CLICK_THRESHOLD_MS && ResponseTimes.Num() > 1;
    if (bRapidClick)
    {
        Signals.RapidClickCount++;
    }

    Signals.LastResponseTimeMs = ResponseTimeMs;
    Signals.AverageResponseTimeMs = AvgResponseTime;
    Signals.TotalResponsesRecorded = ResponseTimes.Num();

    // ADHD_MoE fixed priority routing
    FString DetectedState = TEXT("focused");
    FString RecommendedExpert = TEXT("Direct");
    FString BurnoutLevel = TEXT("GREEN");
    FString MomentumPhase = TEXT("rolling");

    if (Signals.RapidClickCount > RAPID_CLICK_COUNT_THRESHOLD)
    {
        DetectedState = TEXT("frustrated");
        RecommendedExpert = TEXT("Validator");
        BurnoutLevel = TEXT("RED");
        MomentumPhase = TEXT("crashed");
    }
    else if (bLongHesitation || Signals.HesitationCount > HESITATION_COUNT_THRESHOLD)
    {
        DetectedState = TEXT("stuck");
        RecommendedExpert = TEXT("Scaffolder");
        BurnoutLevel = TEXT("ORANGE");
        MomentumPhase = TEXT("declining");
    }
    else if (AvgResponseTime > DEPLETED_AVG_THRESHOLD_MS)
    {
        DetectedState = TEXT("depleted");
        RecommendedExpert = TEXT("Restorer");
        BurnoutLevel = TEXT("ORANGE");
        MomentumPhase = TEXT("crashed");
    }
    else if (ResponseTimes.Num() > 3 && ResponseTimeMs > AvgResponseTime * 2.0f)
    {
        DetectedState = TEXT("distracted");
        RecommendedExpert = TEXT("Refocuser");
        BurnoutLevel = TEXT("YELLOW");
        MomentumPhase = TEXT("declining");
    }
    else if (CurrentQuestion.Index == CurrentQuestion.Total - 1)
    {
        DetectedState = TEXT("completing");
        RecommendedExpert = TEXT("Celebrator");
        BurnoutLevel = TEXT("GREEN");
        MomentumPhase = TEXT("peak");
    }
    else if (ResponseTimes.Num() >= 2 && ResponseTimeMs > 3000.0f && ResponseTimeMs < 8000.0f)
    {
        DetectedState = TEXT("exploring");
        RecommendedExpert = TEXT("Socratic");
        BurnoutLevel = TEXT("GREEN");
        MomentumPhase = TEXT("building");
    }
    else
    {
        DetectedState = TEXT("focused");
        RecommendedExpert = TEXT("Direct");
        BurnoutLevel = TEXT("GREEN");
        MomentumPhase = (ResponseTimes.Num() > 5) ? TEXT("rolling") : TEXT("building");
    }

    Signals.DetectedState = DetectedState;
    Signals.RecommendedExpert = RecommendedExpert;
    Signals.BurnoutLevel = BurnoutLevel;
    Signals.MomentumPhase = MomentumPhase;

    // Write signals into USD content
    Content = UpdateUsdaAttribute(Content, TEXT("BehavioralSignals"), TEXT("last_response_time_ms"), FString::SanitizeFloat(ResponseTimeMs), false);
    Content = UpdateUsdaAttribute(Content, TEXT("BehavioralSignals"), TEXT("average_response_time_ms"), FString::SanitizeFloat(AvgResponseTime), false);
    Content = UpdateUsdaAttribute(Content, TEXT("BehavioralSignals"), TEXT("hesitation_count"), FString::FromInt(Signals.HesitationCount), false);
    Content = UpdateUsdaAttribute(Content, TEXT("BehavioralSignals"), TEXT("long_hesitation_detected"), bLongHesitation ? TEXT("true") : TEXT("false"), false);
    Content = UpdateUsdaAttribute(Content, TEXT("BehavioralSignals"), TEXT("rapid_click_count"), FString::FromInt(Signals.RapidClickCount), false);
    Content = UpdateUsdaAttribute(Content, TEXT("BehavioralSignals"), TEXT("detected_state"), DetectedState, true);
    Content = UpdateUsdaAttribute(Content, TEXT("BehavioralSignals"), TEXT("recommended_expert"), RecommendedExpert, true);
    Content = UpdateUsdaAttribute(Content, TEXT("BehavioralSignals"), TEXT("burnout_level"), BurnoutLevel, true);
    Content = UpdateUsdaAttribute(Content, TEXT("BehavioralSignals"), TEXT("momentum_phase"), MomentumPhase, true);

    if (bVerboseLogging)
    {
        BridgeLog(FString::Printf(TEXT("[MoE] State=%s Expert=%s Burnout=%s Momentum=%s"),
            *DetectedState, *RecommendedExpert, *BurnoutLevel, *MomentumPhase));
    }
}


// === DEPTH LABELS ===

FString UUEBridgeSubsystem::GetDepthLabelForIndex(int32 Index)
{
    switch (Index / 2)
    {
    case 0: return TEXT("SURFACE");
    case 1: return TEXT("PATTERNS");
    case 2: return TEXT("FEELINGS");
    case 3: return TEXT("CORE");
    default: return TEXT("CORE");
    }
}


// === COGNITIVE PROFILE PARSING ===

FUEBridgeProfile UUEBridgeSubsystem::ParseCognitiveProfile(const FString& UsdPath)
{
    FUEBridgeProfile Profile;

    FString Content;
    if (!FFileHelper::LoadFileToString(Content, *UsdPath))
    {
        BridgeLog(FString::Printf(TEXT("Could not read profile: %s"), *UsdPath));
        OnBridgeError.Broadcast(EBridgeErrorCode::ProfileParseFailure,
            FString::Printf(TEXT("Cannot read %s"), *UsdPath));
        return Profile;
    }

    BridgeLog(FString::Printf(TEXT("Parsing cognitive profile from: %s"), *UsdPath));
    Profile.UsdExportPath = UsdPath;
    Profile.GeneratorVersion = TEXT("2.1.0");

    // Parse checksum
    {
        FRegexPattern Pattern(TEXT("string checksum = \"([^\"]*)\""));
        FRegexMatcher Matcher(Pattern, Content);
        if (Matcher.FindNext())
        {
            Profile.Checksum = Matcher.GetCaptureGroup(1);
        }
    }

    // Parse anchor
    {
        FRegexPattern Pattern(TEXT("string anchor = \"([^\"]*)\""));
        FRegexMatcher Matcher(Pattern, Content);
        if (Matcher.FindNext())
        {
            Profile.Anchor = Matcher.GetCaptureGroup(1);
        }
    }

    // Parse anchor from customData (takes precedence)
    {
        FRegexPattern Pattern(TEXT("string translators_anchor = \"([^\"]*)\""));
        FRegexMatcher Matcher(Pattern, Content);
        if (Matcher.FindNext())
        {
            Profile.Anchor = Matcher.GetCaptureGroup(1);
        }
    }

    // Parse Profile dimensions
    TMap<FString, float> DimensionScores;
    TMap<FString, FString> TraitLabels;

    {
        int32 ProfileStart = Content.Find(TEXT("def Xform \"Profile\""));
        if (ProfileStart != INDEX_NONE)
        {
            int32 BlockStart = Content.Find(TEXT("{"), ESearchCase::CaseSensitive, ESearchDir::FromStart, ProfileStart);
            if (BlockStart != INDEX_NONE)
            {
                int32 BraceDepth = 1;
                int32 BlockEnd = BlockStart + 1;
                while (BlockEnd < Content.Len() && BraceDepth > 0)
                {
                    if (Content[BlockEnd] == TEXT('{')) BraceDepth++;
                    else if (Content[BlockEnd] == TEXT('}')) BraceDepth--;
                    BlockEnd++;
                }

                FString ProfileBlock = Content.Mid(BlockStart, BlockEnd - BlockStart);
                FRegexPattern Pattern(TEXT("float (\\w+) = ([\\d.]+)"));
                FRegexMatcher Matcher(Pattern, ProfileBlock);
                while (Matcher.FindNext())
                {
                    FString Name = Matcher.GetCaptureGroup(1);
                    float Value = FCString::Atof(*Matcher.GetCaptureGroup(2));
                    DimensionScores.Add(Name, Value);
                    Profile.Dimensions.Add(Name, Value);
                }
            }
        }
    }

    // Parse Traits section
    {
        int32 TraitsStart = Content.Find(TEXT("def Xform \"Traits\""));
        if (TraitsStart != INDEX_NONE)
        {
            int32 BlockStart = Content.Find(TEXT("{"), ESearchCase::CaseSensitive, ESearchDir::FromStart, TraitsStart);
            if (BlockStart != INDEX_NONE)
            {
                int32 BraceDepth = 1;
                int32 BlockEnd = BlockStart + 1;
                while (BlockEnd < Content.Len() && BraceDepth > 0)
                {
                    if (Content[BlockEnd] == TEXT('{')) BraceDepth++;
                    else if (Content[BlockEnd] == TEXT('}')) BraceDepth--;
                    BlockEnd++;
                }

                FString TraitsBlock = Content.Mid(BlockStart, BlockEnd - BlockStart);
                FRegexPattern Pattern(TEXT("string (\\w+) = \"([^\"]*)\""));
                FRegexMatcher Matcher(Pattern, TraitsBlock);
                while (Matcher.FindNext())
                {
                    TraitLabels.Add(Matcher.GetCaptureGroup(1), Matcher.GetCaptureGroup(2));
                }
            }
        }
    }

    // Map question IDs to dimension names
    TMap<FString, FString> QuestionToDimension;
    QuestionToDimension.Add(TEXT("load"), TEXT("cognitive_density"));
    QuestionToDimension.Add(TEXT("pace"), TEXT("processing_pace"));
    QuestionToDimension.Add(TEXT("uncertainty"), TEXT("uncertainty_tolerance"));
    QuestionToDimension.Add(TEXT("feedback"), TEXT("feedback_style"));
    QuestionToDimension.Add(TEXT("recovery"), TEXT("home_altitude"));
    QuestionToDimension.Add(TEXT("starting"), TEXT("guidance_frequency"));
    QuestionToDimension.Add(TEXT("completion"), TEXT("default_paradigm"));
    QuestionToDimension.Add(TEXT("essence"), TEXT("tangent_tolerance"));

    // Build traits from combined data
    for (const auto& Pair : TraitLabels)
    {
        FTranslatorsTrait Trait;
        Trait.Label = Pair.Value;

        FString* DimName = QuestionToDimension.Find(Pair.Key);
        if (DimName)
        {
            Trait.Dimension = *DimName;
            float* Score = DimensionScores.Find(*DimName);
            Trait.Score = Score ? *Score : 0.5f;
        }
        else
        {
            Trait.Dimension = Pair.Key;
            Trait.Score = 0.5f;
        }

        if (Trait.Score >= 0.7f)
        {
            Trait.Behavior = FString::Printf(TEXT("Strong %s tendency"), *Trait.Label);
        }
        else if (Trait.Score <= 0.3f)
        {
            Trait.Behavior = FString::Printf(TEXT("Measured %s approach"), *Trait.Label);
        }
        else
        {
            Trait.Behavior = FString::Printf(TEXT("Balanced %s style"), *Trait.Label);
        }

        Profile.Traits.Add(Trait);
    }

    // Generate insights
    for (const FTranslatorsTrait& Trait : Profile.Traits)
    {
        if (Trait.Score >= 0.7f)
        {
            Profile.Insights.Add(FString::Printf(TEXT("High %s (%s) suggests strong preference in this dimension"),
                *Trait.Dimension.Replace(TEXT("_"), TEXT(" ")), *Trait.Label));
        }
        else if (Trait.Score <= 0.3f)
        {
            Profile.Insights.Add(FString::Printf(TEXT("Low %s (%s) indicates a focused approach here"),
                *Trait.Dimension.Replace(TEXT("_"), TEXT(" ")), *Trait.Label));
        }
    }

    BridgeLog(FString::Printf(TEXT("Parsed profile: %d traits, %d insights, checksum=%s"),
        Profile.Traits.Num(), Profile.Insights.Num(), *Profile.Checksum));

    return Profile;
}
