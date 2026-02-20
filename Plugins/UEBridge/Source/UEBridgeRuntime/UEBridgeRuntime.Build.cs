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
        IWYUSupport = IWYUSupportMode.Full;

        PublicIncludePaths.AddRange(new string[]
        {
            Path.Combine(ModuleDirectory, "Public"),
            Path.Combine(ModuleDirectory, "Public", "UI")
        });

        PrivateIncludePaths.AddRange(new string[]
        {
            Path.Combine(ModuleDirectory, "Private"),
            Path.Combine(ModuleDirectory, "Private", "UI")
        });

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

        // Version definition — single source of truth
        PublicDefinitions.Add("BRIDGE_VERSION=TEXT(\"2.1.0\")");

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
