"""Backward-compatibility shim -- imports from the remote_control package.

All functionality has moved to the remote_control/ package.
This file exists so that ``from remote_control_bridge import X`` continues to work.

Usage:
    python remote_control_bridge.py --test    # Run self-test (editor must be running)
    python remote_control_bridge.py --info    # Check if editor is reachable
"""
from remote_control import *  # noqa: F401,F403
from remote_control import __all__  # noqa: F401

# ------------------------------------------------------------------
# CLI entry point for testing
# ------------------------------------------------------------------

import argparse
import json
import sys


def main():
    parser = argparse.ArgumentParser(description="UE5 Remote Control Bridge")
    parser.add_argument("--test", action="store_true", help="Run spawn/read/delete round-trip test")
    parser.add_argument("--info", action="store_true", help="Check if editor is reachable")
    args = parser.parse_args()

    with UnrealRemoteControl() as ue:  # noqa: F405
        if args.info or not args.test:
            if ue.is_connected():
                info = ue.info()
                print("Connected to UE5 Remote Control")
                print(json.dumps(info, indent=2))
            else:
                print("ERROR: Cannot reach UE5 editor at localhost:30010")
                print("Make sure the editor is running with RemoteControl plugin enabled.")
                sys.exit(1)

        if args.test:
            if not ue.is_connected():
                print("ERROR: Editor not reachable. Start UE5 with RemoteControl plugin.")
                sys.exit(1)

            print("\n--- Round-trip test ---")

            # 1. Spawn
            print("1. Spawning test cube...")
            result = ue.spawn_actor(
                "StaticMeshActor",
                location=(200, 200, 100),
                label="BridgeTestCube"
            )
            print(f"   Result: {result}")

            # 2. List actors
            print("2. Listing actors...")
            actors = ue.list_actors()
            print(f"   Actors: {json.dumps(actors.get('result'), indent=4)}")

            # 3. Get level info
            print("3. Level info...")
            level_info = ue.get_level_info()
            print(f"   Level: {level_info.get('result')}")

            # 4. Delete
            print("4. Cleaning up test actor...")
            cleanup = ue.execute_python("""
import unreal
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
for a in actors:
    if a.get_actor_label() == "BridgeTestCube":
        subsystem.destroy_actor(a)
        print("RESULT:CLEANED")
        break
else:
    print("RESULT:NOT_FOUND")
""")
            print(f"   Cleanup: {cleanup.get('result')}")

            print("\n--- Test complete ---")


if __name__ == "__main__":
    main()
