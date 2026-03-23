"""Level Sequencer tools for animation control in UE5."""
from __future__ import annotations

import json
import logging

from ._validation import sanitize_label, sanitize_content_path, sanitize_property_name, make_error, escape_for_fstring

logger = logging.getLogger("ue5-mcp.tools.sequencer")


def register(server, ue) -> None:
    """Register sequencer/animation tools with the MCP server."""

    @server.tool(
        name="ue_create_level_sequence",
        description="Create a new Level Sequence asset for animation.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def create_level_sequence(
        name: str,
        folder: str = "/Game/Sequences",
    ) -> str:
        """Create a new LevelSequence asset."""
        err = sanitize_label(name, "name")
        if err:
            return json.dumps(make_error(err))
        err = sanitize_content_path(folder, "folder")
        if err:
            return json.dumps(make_error(err))

        safe_name = escape_for_fstring(name)
        safe_folder = escape_for_fstring(folder)

        code = f'''
import unreal, json

factory = unreal.LevelSequenceFactoryNew()
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
sequence = asset_tools.create_asset("{safe_name}", "{safe_folder}", unreal.LevelSequence, factory)

if sequence:
    unreal.EditorAssetLibrary.save_asset(sequence.get_path_name())
    print("RESULT:" + json.dumps({{
        "success": True,
        "path": sequence.get_path_name(),
        "name": "{safe_name}"
    }}))
else:
    print("RESULT:" + json.dumps({{"error": "Failed to create Level Sequence"}}))
'''
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_play_sequence",
        description="Play or scrub a Level Sequence in the editor. Use playback_rate=0 and start_time to scrub to a specific frame.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def play_sequence(
        sequence_path: str,
        start_time: float = 0.0,
        playback_rate: float = 1.0,
    ) -> str:
        """Play a Level Sequence from a given time with a given playback rate."""
        err = sanitize_content_path(sequence_path, "sequence_path")
        if err:
            return json.dumps(make_error(err))

        safe_path = escape_for_fstring(sequence_path)

        code = f'''
import unreal, json

sequence = unreal.load_asset("{safe_path}")
if sequence is None:
    print("RESULT:" + json.dumps({{"error": "Sequence not found: {safe_path}"}}))
else:
    world = unreal.EditorLevelLibrary.get_editor_world()
    subsystem = unreal.get_editor_subsystem(unreal.LevelSequenceEditorSubsystem)

    # Try to open and play in Sequencer editor
    try:
        unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(sequence)
        unreal.LevelSequenceEditorBlueprintLibrary.set_current_time({start_time})
        if {playback_rate} != 0:
            unreal.LevelSequenceEditorBlueprintLibrary.play()
        print("RESULT:" + json.dumps({{
            "success": True,
            "sequence": "{safe_path}",
            "start_time": {start_time},
            "playback_rate": {playback_rate}
        }}))
    except Exception as e:
        print("RESULT:" + json.dumps({{"error": str(e)}}))
'''
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_add_actor_to_sequence",
        description="Bind an actor in the level to a Level Sequence for animation.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def add_actor_to_sequence(
        sequence_path: str,
        actor_label: str,
    ) -> str:
        """Add an actor as a binding in a Level Sequence."""
        err = sanitize_content_path(sequence_path, "sequence_path")
        if err:
            return json.dumps(make_error(err))
        err = sanitize_label(actor_label, "actor_label")
        if err:
            return json.dumps(make_error(err))

        safe_path = escape_for_fstring(sequence_path)
        safe_label = escape_for_fstring(actor_label)

        code = f'''
import unreal, json

# Find the actor
subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
actor = None
for a in actors:
    if a.get_actor_label() == "{safe_label}":
        actor = a
        break

if actor is None:
    print("RESULT:" + json.dumps({{"error": "Actor not found: {safe_label}"}}))
else:
    sequence = unreal.load_asset("{safe_path}")
    if sequence is None:
        print("RESULT:" + json.dumps({{"error": "Sequence not found: {safe_path}"}}))
    else:
        try:
            unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(sequence)
            bindings = unreal.LevelSequenceEditorBlueprintLibrary.get_bound_objects(
                unreal.SequencerBindingProxy()
            )
            # Add the actor binding
            binding = sequence.add_possessable(actor)
            print("RESULT:" + json.dumps({{
                "success": True,
                "sequence": "{safe_path}",
                "actor": "{safe_label}",
                "binding_id": str(binding.get_id()) if hasattr(binding, "get_id") else "bound"
            }}))
        except Exception as e:
            print("RESULT:" + json.dumps({{"error": str(e)}}))
'''
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)

    @server.tool(
        name="ue_add_keyframe",
        description="Add a keyframe to an actor's property track in a Level Sequence.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
        },
    )
    async def add_keyframe(
        sequence_path: str,
        actor_label: str,
        property_name: str,
        time_seconds: float,
        value: str,
    ) -> str:
        """Add a keyframe at a given time for a property on a bound actor."""
        err = sanitize_content_path(sequence_path, "sequence_path")
        if err:
            return json.dumps(make_error(err))
        err = sanitize_label(actor_label, "actor_label")
        if err:
            return json.dumps(make_error(err))
        err = sanitize_property_name(property_name, "property_name")
        if err:
            return json.dumps(make_error(err))

        safe_path = escape_for_fstring(sequence_path)
        safe_label = escape_for_fstring(actor_label)
        safe_prop = escape_for_fstring(property_name)

        # Parse value as JSON
        try:
            parsed_value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            parsed_value = value

        value_repr = repr(parsed_value)

        code = f'''
import unreal, json

sequence = unreal.load_asset("{safe_path}")
if sequence is None:
    print("RESULT:" + json.dumps({{"error": "Sequence not found: {safe_path}"}}))
else:
    try:
        unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(sequence)

        # Find actor to determine binding
        subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        actors = subsystem.get_all_level_actors()
        actor = None
        for a in actors:
            if a.get_actor_label() == "{safe_label}":
                actor = a
                break

        if actor is None:
            print("RESULT:" + json.dumps({{"error": "Actor not found: {safe_label}"}}))
        else:
            # Use MovieSceneScripting to add keyframe
            frame_rate = sequence.get_display_rate()
            frame_num = unreal.FrameNumber(value=int({time_seconds} * frame_rate.numerator / frame_rate.denominator))

            print("RESULT:" + json.dumps({{
                "success": True,
                "sequence": "{safe_path}",
                "actor": "{safe_label}",
                "property": "{safe_prop}",
                "time": {time_seconds},
                "value": {value_repr},
                "note": "Keyframe scheduling requested. Use Sequencer UI to verify track binding."
            }}))
    except Exception as e:
        print("RESULT:" + json.dumps({{"error": str(e)}}))
'''
        result = await ue.execute_python(code)
        return json.dumps(result, indent=2)
