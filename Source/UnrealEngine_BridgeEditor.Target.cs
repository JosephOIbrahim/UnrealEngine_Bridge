// UnrealEngineBridgeEditor.Target.cs
// Editor target configuration

using UnrealBuildTool;

public class UnrealEngine_BridgeEditorTarget : TargetRules
{
    public UnrealEngine_BridgeEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("UnrealEngineBridge");
    }
}
