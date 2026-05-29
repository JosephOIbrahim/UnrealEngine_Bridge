// UEBridgeEditor.cpp
// Editor module: the "UE Bridge" toolbar button + Tools-menu entry + dockable
// control panel — the recognizable in-editor home for the plugin.

#include "UEBridgeEditor.h"
#include "UEBridgeRuntime.h"
#include "UEBridgeStyle.h"
#include "BridgeEditorSubsystem.h"

#include "Modules/ModuleManager.h"
#include "ToolMenus.h"
#include "Framework/Commands/UIAction.h"
#include "Framework/Docking/TabManager.h"
#include "Framework/Application/SlateApplication.h"
#include "Textures/SlateIcon.h"
#include "Styling/AppStyle.h"
#include "Editor.h"

#include "Widgets/Docking/SDockTab.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Text/STextBlock.h"
#include "Widgets/Input/SButton.h"
#include "Input/Reply.h"

#define LOCTEXT_NAMESPACE "UEBridgeEditor"

const FName FUEBridgeEditorModule::BridgeTabName(TEXT("UEBridgePanel"));

namespace
{
    /** The editor subsystem that owns the Python bridge process + file watcher. */
    UBridgeEditorSubsystem* GetBridgeSubsystem()
    {
        return GEditor ? GEditor->GetEditorSubsystem<UBridgeEditorSubsystem>() : nullptr;
    }
}

void FUEBridgeEditorModule::StartupModule()
{
    UE_LOG(LogUEBridge, Log, TEXT("UEBridge Editor module loaded"));

    // Ensure the shared style (brand colours + Icon128 brush) exists. Idempotent;
    // the runtime module normally registers it first and owns its teardown.
    FUEBridgeStyle::Initialize();

    // Dockable "UE Bridge" tab — discoverable under Window > Tools.
    FGlobalTabmanager::Get()->RegisterNomadTabSpawner(
            BridgeTabName,
            FOnSpawnTab::CreateRaw(this, &FUEBridgeEditorModule::OnSpawnBridgeTab))
        .SetDisplayName(LOCTEXT("BridgeTabTitle", "UE Bridge"))
        .SetTooltipText(LOCTEXT("BridgeTabTooltip", "Open the UE Bridge control panel"))
        .SetGroup(FGlobalTabmanager::Get()->GetLocalWorkspaceMenuRoot())
        .SetIcon(FSlateIcon(FUEBridgeStyle::GetStyleSetName(), "UEBridge.Icon.Small"));

    // Toolbar button + Tools-menu entry — registered once ToolMenus is ready.
    UToolMenus::RegisterStartupCallback(
        FSimpleMulticastDelegate::FDelegate::CreateRaw(this, &FUEBridgeEditorModule::RegisterMenus));
}

void FUEBridgeEditorModule::ShutdownModule()
{
    UToolMenus::UnRegisterStartupCallback(this);
    UToolMenus::UnregisterOwner(this);

    if (FSlateApplication::IsInitialized())
    {
        FGlobalTabmanager::Get()->UnregisterNomadTabSpawner(BridgeTabName);
    }

    // NOTE: do not Shutdown FUEBridgeStyle here — it is shared with (and owned by)
    // the runtime module, which unregisters it on its own shutdown.

    UE_LOG(LogUEBridge, Log, TEXT("UEBridge Editor module unloaded"));
}

void FUEBridgeEditorModule::OpenBridgeTab()
{
    FGlobalTabmanager::Get()->TryInvokeTab(FTabId(BridgeTabName));
}

void FUEBridgeEditorModule::RegisterMenus()
{
    FToolMenuOwnerScoped OwnerScoped(this);

    const FSlateIcon BridgeIcon(FUEBridgeStyle::GetStyleSetName(), "UEBridge.Icon");
    const FUIAction OpenAction(FExecuteAction::CreateRaw(this, &FUEBridgeEditorModule::OpenBridgeTab));

    // Tools menu entry — stable, always discoverable.
    if (UToolMenu* ToolsMenu = UToolMenus::Get()->ExtendMenu("LevelEditor.MainMenu.Tools"))
    {
        FToolMenuSection& Section = ToolsMenu->FindOrAddSection(
            "UEBridge", LOCTEXT("UEBridgeMenuSection", "UE Bridge"));
        Section.AddMenuEntry(
            "OpenUEBridgePanel",
            LOCTEXT("OpenBridgeMenuLabel", "UE Bridge"),
            LOCTEXT("OpenBridgeMenuTooltip", "Open the UE Bridge control panel"),
            BridgeIcon,
            OpenAction);
    }

    // Level-editor toolbar button. The exact toolbar path can shift between engine
    // versions, so this is guarded — if it is absent the Tools menu + Window tab
    // still provide entry points.
    if (UToolMenu* ToolbarMenu = UToolMenus::Get()->ExtendMenu("LevelEditor.LevelEditorToolBar.PlayToolBar"))
    {
        FToolMenuSection& Section = ToolbarMenu->FindOrAddSection("UEBridge");
        Section.AddEntry(FToolMenuEntry::InitToolBarButton(
            "OpenUEBridgePanel",
            OpenAction,
            LOCTEXT("BridgeToolbarLabel", "UE Bridge"),
            LOCTEXT("BridgeToolbarTooltip", "Open the UE Bridge control panel"),
            BridgeIcon));
    }
}

TSharedRef<SDockTab> FUEBridgeEditorModule::OnSpawnBridgeTab(const FSpawnTabArgs& Args)
{
    return SNew(SDockTab)
        .TabRole(ETabRole::NomadTab)
        [
            SNew(SBorder)
            .BorderImage(FAppStyle::Get().GetBrush("WhiteBrush"))
            .BorderBackgroundColor(FSlateColor(FUEBridgeStyle::GetColor("Color.BackgroundSolid")))
            .Padding(16.0f)
            [
                SNew(SVerticalBox)

                // Title
                + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 0.0f, 0.0f, 12.0f)
                [
                    SNew(STextBlock)
                    .Text(LOCTEXT("PanelTitle", "UE Bridge"))
                    .Font(FUEBridgeStyle::GetFont("Font.Heading"))
                    .ColorAndOpacity(FSlateColor(FUEBridgeStyle::GetColor("Color.Cyan")))
                ]

                // Live bridge-process status (gold when running, dim when stopped)
                + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 0.0f, 0.0f, 8.0f)
                [
                    SNew(STextBlock)
                    .Font(FUEBridgeStyle::GetFont("Font.Body"))
                    .Text_Lambda([]() -> FText
                    {
                        const UBridgeEditorSubsystem* Sub = GetBridgeSubsystem();
                        return (Sub && Sub->IsBridgeProcessRunning())
                            ? LOCTEXT("StatusRunning", "Bridge process: RUNNING")
                            : LOCTEXT("StatusStopped", "Bridge process: stopped");
                    })
                    .ColorAndOpacity_Lambda([]() -> FSlateColor
                    {
                        const UBridgeEditorSubsystem* Sub = GetBridgeSubsystem();
                        return (Sub && Sub->IsBridgeProcessRunning())
                            ? FSlateColor(FUEBridgeStyle::GetColor("Color.Gold"))
                            : FSlateColor(FUEBridgeStyle::GetColor("Color.TextDim"));
                    })
                ]

                // Remote Control endpoint info
                + SVerticalBox::Slot().AutoHeight().Padding(0.0f, 0.0f, 0.0f, 14.0f)
                [
                    SNew(STextBlock)
                    .Text(LOCTEXT("RCInfo", "Remote Control API: http://localhost:30010"))
                    .Font(FUEBridgeStyle::GetFont("Font.Caption"))
                    .ColorAndOpacity(FSlateColor(FUEBridgeStyle::GetColor("Color.TextSecondary")))
                ]

                // Start / Stop bridge controls
                + SVerticalBox::Slot().AutoHeight()
                [
                    SNew(SHorizontalBox)
                    + SHorizontalBox::Slot().AutoWidth().Padding(0.0f, 0.0f, 8.0f, 0.0f)
                    [
                        SNew(SButton)
                        .Text(LOCTEXT("StartBtn", "Start Bridge"))
                        .ToolTipText(LOCTEXT("StartBtnTip", "Launch bridge_orchestrator.py"))
                        .IsEnabled_Lambda([]() -> bool
                        {
                            const UBridgeEditorSubsystem* Sub = GetBridgeSubsystem();
                            return Sub && !Sub->IsBridgeProcessRunning();
                        })
                        .OnClicked_Lambda([]() -> FReply
                        {
                            if (UBridgeEditorSubsystem* Sub = GetBridgeSubsystem())
                            {
                                Sub->StartBridgeProcess();
                            }
                            return FReply::Handled();
                        })
                    ]
                    + SHorizontalBox::Slot().AutoWidth()
                    [
                        SNew(SButton)
                        .Text(LOCTEXT("StopBtn", "Stop Bridge"))
                        .ToolTipText(LOCTEXT("StopBtnTip", "Stop bridge_orchestrator.py"))
                        .IsEnabled_Lambda([]() -> bool
                        {
                            const UBridgeEditorSubsystem* Sub = GetBridgeSubsystem();
                            return Sub && Sub->IsBridgeProcessRunning();
                        })
                        .OnClicked_Lambda([]() -> FReply
                        {
                            if (UBridgeEditorSubsystem* Sub = GetBridgeSubsystem())
                            {
                                Sub->StopBridgeProcess();
                            }
                            return FReply::Handled();
                        })
                    ]
                ]
            ]
        ];
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FUEBridgeEditorModule, UEBridgeEditor)
