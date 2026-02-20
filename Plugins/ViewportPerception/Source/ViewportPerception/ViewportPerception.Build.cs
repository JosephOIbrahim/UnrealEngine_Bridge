// ViewportPerception.Build.cs
// Build configuration for the Viewport Perception plugin.
// Editor-only plugin that captures the viewport backbuffer and serves
// perception packets (frame + metadata) to the MCP bridge.

using UnrealBuildTool;

public class ViewportPerception : ModuleRules
{
    public ViewportPerception(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new string[]
        {
            "Core",
            "CoreUObject",
            "Engine",
            "InputCore"
        });

        PrivateDependencyModuleNames.AddRange(new string[]
        {
            // Rendering pipeline access (backbuffer hook, ReadSurfaceData)
            "RHI",
            "RenderCore",
            "Renderer",

            // Slate viewport access
            "Slate",
            "SlateCore",

            // Image encode (JPEG/PNG)
            "ImageWrapper",
            "ImageCore",

            // Editor subsystem + viewport queries
            "UnrealEd",
            "EditorSubsystem",
            "LevelEditor",

            // HTTP endpoint (server-side route handling)
            "HTTPServer",
            "Json",
            "JsonUtilities"
        });

        // IWYU
        IWYUSupport = IWYUSupport.Full;
    }
}
