// UEBridgeRuntime.Build.cs
// Runtime module — ships in packaged builds.
// Owns BridgeComponent, data types, UMG widgets, and polling-based file bridge.

using UnrealBuildTool;
using System.IO;

public class UEBridgeRuntime : ModuleRules
{
    public UEBridgeRuntime(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicIncludePaths.Add(Path.Combine(ModuleDirectory, "Public"));
        PrivateIncludePaths.Add(Path.Combine(ModuleDirectory, "Private"));

        // Core runtime dependencies — ship in packaged builds
        PublicDependencyModuleNames.AddRange(new string[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "InputCore",
            "Json",
            "JsonUtilities"
        });

        // UMG / Slate for gameplay widgets
        PublicDependencyModuleNames.AddRange(new string[]
        {
            "Slate",
            "SlateCore",
            "UMG"
        });

        // HTTP for runtime Remote Control communication
        PrivateDependencyModuleNames.Add("HTTP");

        // Projects — IPluginManager, to resolve the plugin's Resources/ for the
        // brand icon brush registered in FUEBridgeStyle.
        PrivateDependencyModuleNames.Add("Projects");

        // Version definition — single source of truth
        PublicDefinitions.Add("BRIDGE_VERSION=TEXT(\"0.2.0\")");

        // USD support flag: editor-only via pxr, runtime uses text-based USDA parser
        if (Target.bBuildEditor)
        {
            PublicDefinitions.Add("WITH_USD_SUPPORT=1");
        }
        else
        {
            PublicDefinitions.Add("WITH_USD_SUPPORT=0");
        }
    }
}
