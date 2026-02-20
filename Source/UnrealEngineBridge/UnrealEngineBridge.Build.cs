// UnrealEngineBridge.Build.cs
// Build configuration for the UnrealEngineBridge game module.
//
// Phase 4: Game flow logic migrated to UEBridgeRuntime plugin.
// This module now depends on the plugin for BridgeTypes.h and the subsystem.
// BridgeComponent is a thin relay to UUEBridgeSubsystem.

using UnrealBuildTool;

public class UnrealEngineBridge : ModuleRules
{
    public UnrealEngineBridge(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        // Core modules
        PublicDependencyModuleNames.AddRange(new string[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "InputCore"
        });

        // UEBridge plugin — subsystem, BridgeTypes, delegates
        PublicDependencyModuleNames.Add("UEBridgeRuntime");

        // Editor-only features
        // DirectoryWatcher migrated to UEBridgeEditor plugin module (Phase 3).
        if (Target.bBuildEditor)
        {
            // USD Stage Actor support (editor-only)
            // Note: USDA text parsing works without this module
            // This is only needed for live USD Stage manipulation
            PrivateDefinitions.Add("WITH_USD_SUPPORT=1");

            // Remote Control API (editor-only)
            // Enables REST API on localhost:30010 for external tool access
            PrivateDependencyModuleNames.Add("RemoteControl");
        }

        // UMG / Slate UI support (required for question display widgets)
        PrivateDependencyModuleNames.AddRange(new string[]
        {
            "Slate",
            "SlateCore",
            "UMG",
            "EnhancedInput"
        });

        // Enable IWYU (Include What You Use)
        IWYUSupport = IWYUSupport.Full;

        // Bridge version (matches plugin — defined in UEBridgeRuntime.Build.cs)
        // Kept here for legacy references; canonical version is BRIDGE_VERSION from the plugin.

        // Ensure generated headers are available
        PublicIncludePaths.Add(ModuleDirectory);
        PrivateIncludePaths.Add(ModuleDirectory + "/UI");
    }
}
