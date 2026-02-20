// UnrealEngineBridge.Target.cs
// Game target configuration

using UnrealBuildTool;

public class UnrealEngine_BridgeTarget : TargetRules
{
    public UnrealEngine_BridgeTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.Latest;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("UnrealEngineBridge");
    }
}
