"""
setup_translators_ui.py

UE5.7 Editor Utility Script for The Translators Card
Run this script in the UE5 Python console to verify setup.

Usage:
    import setup_translators_ui
    setup_translators_ui.run_setup()

Or run individual functions:
    setup_translators_ui.check_plugins()
    setup_translators_ui.find_bridge_component()
    setup_translators_ui.create_directories()
"""

import unreal
from pathlib import Path


# === CONFIGURATION ===
BRIDGE_DIR = Path.home() / ".translators"
PROJECT_CONTENT_DIR = "/Game/UnrealEngineBridge"


def log(message: str, level: str = "info"):
    """Log with [TranslatorsSetup] prefix"""
    prefix = "[TranslatorsSetup]"
    if level == "warning":
        unreal.log_warning(f"{prefix} {message}")
    elif level == "error":
        unreal.log_error(f"{prefix} {message}")
    else:
        unreal.log(f"{prefix} {message}")


def check_plugins() -> dict:
    """
    Verify required plugins are enabled.
    Returns dict with plugin status.
    """
    log("Checking required plugins...")

    results = {
        "USDImporter": False,
        "PythonScriptPlugin": True,  # Must be true if this script runs
    }

    # Check USD Importer
    try:
        # If we can find USD-related classes, the plugin is loaded
        usd_classes = unreal.EditorAssetLibrary.list_assets(
            "/Engine/Plugins/USD", recursive=False
        )
        results["USDImporter"] = True
        log("  USD Importer: ENABLED")
    except:
        log("  USD Importer: NOT FOUND - Enable in Edit > Plugins", "warning")

    log("  Python Script Plugin: ENABLED (you're running this script)")

    return results


def create_directories():
    """
    Create project directories for Translators assets.
    """
    log("Creating asset directories...")

    directories = [
        f"{PROJECT_CONTENT_DIR}/UI",
        f"{PROJECT_CONTENT_DIR}/Materials",
        f"{PROJECT_CONTENT_DIR}/Fonts",
        f"{PROJECT_CONTENT_DIR}/Audio",
    ]

    for dir_path in directories:
        if not unreal.EditorAssetLibrary.does_directory_exist(dir_path):
            unreal.EditorAssetLibrary.make_directory(dir_path)
            log(f"  Created: {dir_path}")
        else:
            log(f"  Exists: {dir_path}")

    # Also ensure the bridge directory exists on disk
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    log(f"  Bridge directory: {BRIDGE_DIR}")


def find_bridge_component() -> bool:
    """
    Search for BridgeComponent in the current level.
    Returns True if found.
    """
    log("Searching for BridgeComponent...")

    # Get all actors in level
    actors = unreal.EditorLevelLibrary.get_all_level_actors()

    for actor in actors:
        # Check if actor has BridgeComponent
        components = actor.get_components_by_class(unreal.ActorComponent)
        for component in components:
            class_name = component.get_class().get_name()
            if "BridgeComponent" in class_name:
                log(f"  FOUND: {actor.get_name()} has BridgeComponent")
                return True

    log("  NOT FOUND - Add an Actor with BridgeComponent to your level", "warning")
    return False


def find_usd_stage_actor() -> bool:
    """
    Search for USD Stage Actor in the current level.
    Returns True if found.
    """
    log("Searching for USD Stage Actor...")

    actors = unreal.EditorLevelLibrary.get_all_level_actors()

    for actor in actors:
        class_name = actor.get_class().get_name()
        if "UsdStageActor" in class_name:
            log(f"  FOUND: {actor.get_name()}")
            return True

    log("  NOT FOUND - Add a USD Stage Actor to your level", "warning")
    return False


def print_setup_instructions():
    """
    Print instructions for manual setup steps.
    """
    log("=" * 60)
    log("TRANSLATORS CARD SETUP INSTRUCTIONS")
    log("=" * 60)

    instructions = """
1. CREATE WIDGET BLUEPRINTS:
   - Right-click in Content Browser > User Interface > Widget Blueprint
   - For each widget, select the C++ parent class:
     * WBP_QuestionDisplay (parent: W_QuestionDisplay)
     * WBP_OptionButton (parent: W_OptionButton)
     * WBP_ProgressIndicator (parent: W_ProgressIndicator)

2. DESIGN THE WIDGETS:
   WBP_QuestionDisplay needs:
   - TextBlock named "QuestionText"
   - TextBlock named "ProgressText"
   - VerticalBox named "OptionsContainer"
   - Border named "BackgroundBorder" (optional)

   WBP_OptionButton needs:
   - Button named "OptionButton"
   - TextBlock named "OptionLabel"
   - Border named "ButtonBorder" (optional)

3. SET UP LEVEL:
   - Add an empty Actor to your level
   - Add BridgeComponent to that Actor
   - Add USD Stage Actor (Place Actors > USD)
   - Point USD Stage to: ~/.translators/cognitive_substrate.usda

4. SET GAME MODE:
   - World Settings > Game Mode Override > TranslatorsGameMode
   - Or create a Blueprint child of TranslatorsGameMode

5. TEST:
   - Run: python ~/.claude/bridges/ue5_translators_bridge.py
   - Press Play in Editor
   - Questions should appear when bridge connects
"""
    print(instructions)
    log("Instructions printed above")


def create_simple_material():
    """
    Create a simple unlit material for 8-bit aesthetic.
    """
    log("Creating 8-bit material...")

    material_path = f"{PROJECT_CONTENT_DIR}/Materials/M_8Bit_Base"

    # Check if already exists
    if unreal.EditorAssetLibrary.does_asset_exist(material_path):
        log(f"  Material already exists: {material_path}")
        return

    # Create material asset
    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()

    try:
        factory = unreal.MaterialFactoryNew()
        material = asset_tools.create_asset(
            "M_8Bit_Base",
            f"{PROJECT_CONTENT_DIR}/Materials",
            unreal.Material,
            factory
        )

        if material:
            # Set to unlit (no lighting calculations)
            material.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
            log(f"  Created: {material_path}")
        else:
            log("  Failed to create material", "warning")

    except Exception as e:
        log(f"  Error creating material: {e}", "error")


def run_setup():
    """
    Run complete setup verification.
    """
    log("=" * 60)
    log("TRANSLATORS CARD SETUP VERIFICATION")
    log("=" * 60)

    # Check plugins
    plugins = check_plugins()

    # Create directories
    create_directories()

    # Find components
    has_bridge = find_bridge_component()
    has_usd = find_usd_stage_actor()

    # Summary
    log("")
    log("=" * 60)
    log("SETUP SUMMARY")
    log("=" * 60)

    all_good = True

    if plugins.get("USDImporter"):
        log("  [OK] USD Importer enabled")
    else:
        log("  [!!] USD Importer - ENABLE in Edit > Plugins", "warning")
        all_good = False

    if has_bridge:
        log("  [OK] BridgeComponent found in level")
    else:
        log("  [!!] BridgeComponent - ADD to an Actor in level", "warning")
        all_good = False

    if has_usd:
        log("  [OK] USD Stage Actor found in level")
    else:
        log("  [!!] USD Stage Actor - ADD from Place Actors > USD", "warning")
        all_good = False

    log("")
    if all_good:
        log("All checks passed! Ready to test.")
        log("Run: python ~/.claude/bridges/ue5_translators_bridge.py")
        log("Then: Press Play in Editor")
    else:
        log("Some items need attention. See warnings above.")
        print_setup_instructions()


# Auto-run when imported (optional)
if __name__ == "__main__":
    run_setup()
