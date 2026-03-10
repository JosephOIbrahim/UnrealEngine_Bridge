# CRT Cleanup & Fix — Agent Team Dispatch
# Sprint: CRT-CLEANUP
# Date: 2026-03-09
# Status: EXECUTING

## Agent Roster

| Agent | Icon | MOE Role | Scope |
|-------|------|----------|-------|
| RESTORE | ◆ | Git & Asset Recovery | Revert destroyed materials from git, reload in editor |
| PERF | ⟡ | Performance Diagnostics | Reset screen percentage, diagnose 3 FPS, apply fixes |
| TYPO | ◈ | Typography & Visual | Fix blown-out text readability |
| JANITOR | ⬡ | Asset Hygiene | Delete orphaned assets from failed dot grid attempts |

## Phases

### Phase 1: Stabilize (RESTORE + PERF parallel)
- RESTORE: git checkout bcb332e -- Content/Materials/M_CRT_Screen.uasset Content/Materials/M_CRT_Frame.uasset, then reimport in editor
- PERF: r.ScreenPercentage 100, stat fps, stat unit, stat scenerendering — diagnose and fix

### Phase 2: Fix & Clean (TYPO + JANITOR parallel, after Phase 1)
- TYPO: Reduce WorldSize to 40, lower emissive to 0.15, verify readable text
- JANITOR: Delete M_PP_CRT_DotGrid, M_CRT_DotGrid_Overlay, T_CRT_DotPattern, MI_CRT_Screen_Tuned

### Phase 3: Verify (viewport capture)
- Capture viewport, confirm text readable, materials restored, FPS acceptable
