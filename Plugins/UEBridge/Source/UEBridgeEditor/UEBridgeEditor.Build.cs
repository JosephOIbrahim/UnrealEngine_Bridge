// UEBridgeEditor.Build.cs
// Editor module — never ships in packaged builds.
// Owns DirectoryWatcher integration, MCP server lifecycle, Python bridge process,
// and detail panel customizations.

using UnrealBuildTool;
using System.IO;

public class UEBridgeEditor : ModuleRules
{
    public UEBridgeEditor(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        IWYUSupport = IWYUSupportMode.Full;

        PublicIncludePaths.AddRange(new string[]
        {
            Path.Combine(ModuleDirectory, "Public")
        });

        PrivateIncludePaths.AddRange(new string[]
        {
            Path.Combine(ModuleDirectory, "Private")
        });

        // Runtime module for BridgeTypes.h and BridgeComponent access
        PublicDependencyModuleNames.AddRange(new string[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "UEBridgeRuntime"
        });

        PrivateDependencyModuleNames.AddRange(new string[]
        {
            // Editor framework
            "UnrealEd",
            "EditorSubsystem",
            "ToolMenus",
            "PropertyEditor",

            // File watching (editor-only)
            "DirectoryWatcher",

            // Remote Control C++ integration (editor-only)
            "RemoteControl",

            // Slate for editor UI
            "Slate",
            "SlateCore"
        });

        PublicDefinitions.Add("WITH_USD_SUPPORT=1");
        PublicDefinitions.Add("BRIDGE_VERSION=TEXT(\"2.1.0\")");
    }
}
