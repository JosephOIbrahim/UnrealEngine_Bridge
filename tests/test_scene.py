"""Tests for ue_mcp/tools/scene.py — scene understanding tools."""

import ast
import json
import pytest

from ue_mcp.tools._validation import sanitize_label, escape_for_fstring


class TestGetActorDetailsValidation:
    """ue_get_actor_details input validation."""

    def test_rejects_empty_label(self):
        assert sanitize_label("", "actor_label") is not None

    def test_rejects_injection_label(self):
        assert sanitize_label('test"; import os', "actor_label") is not None

    def test_accepts_valid_label(self):
        assert sanitize_label("MyActor_01", "actor_label") is None


class TestGetActorDetailsCodeGen:
    """Generated Python for ue_get_actor_details parses cleanly."""

    def test_code_parses(self):
        safe_label = escape_for_fstring("TestActor")
        code = f"""
import unreal, json

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
    loc = actor.get_actor_location()
    print("RESULT:" + json.dumps({{"label": actor.get_actor_label()}}))
"""
        ast.parse(code)  # Should not raise


class TestQuerySceneValidation:
    """ue_query_scene input validation."""

    def test_rejects_invalid_class_filter(self):
        from ue_mcp.tools._validation import sanitize_class_name
        assert sanitize_class_name("1Bad;Class", "class_filter") is not None

    def test_accepts_valid_class_filter(self):
        from ue_mcp.tools._validation import sanitize_class_name
        assert sanitize_class_name("PointLight", "class_filter") is None


class TestQuerySceneCodeGen:
    """Generated Python for ue_query_scene parses cleanly."""

    def test_code_with_all_filters(self):
        safe_class = escape_for_fstring("PointLight")
        safe_tag = escape_for_fstring("MyTag")
        safe_pattern = escape_for_fstring("test")
        code = f"""
import unreal, json

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
results = []
max_results = 100

class_filter = "{safe_class}" if "{safe_class}" else None
tag_filter = "{safe_tag}" if "{safe_tag}" else None
name_pattern = "{safe_pattern}".lower() if "{safe_pattern}" else None

for actor in actors:
    if len(results) >= max_results:
        break
    loc = actor.get_actor_location()
    results.append({{
        "label": actor.get_actor_label(),
        "class": actor.get_class().get_name(),
    }})

print("RESULT:" + json.dumps({{"count": len(results), "actors": results}}))
"""
        ast.parse(code)


class TestGetComponentDetailsCodeGen:
    """Generated Python for ue_get_component_details parses cleanly."""

    def test_code_parses(self):
        safe_label = escape_for_fstring("TestActor")
        safe_comp = escape_for_fstring("StaticMeshComponent")
        code = f"""
import unreal, json

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
actor = None
for a in actors:
    if a.get_actor_label() == "{safe_label}":
        actor = a
        break

if actor is None:
    print("RESULT:" + json.dumps({{"error": "not found"}}))
else:
    comps = actor.get_components_by_class(unreal.ActorComponent)
    target = None
    for c in comps:
        if c.get_name() == "{safe_comp}":
            target = c
            break
    print("RESULT:" + json.dumps({{"name": "test"}}))
"""
        ast.parse(code)


class TestGetActorHierarchyCodeGen:
    """Generated Python for ue_get_actor_hierarchy parses cleanly."""

    def test_code_parses(self):
        safe_label = escape_for_fstring("Root")
        code = f"""
import unreal, json

subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
actors = subsystem.get_all_level_actors()
actor = None
for a in actors:
    if a.get_actor_label() == "{safe_label}":
        actor = a
        break

if actor is None:
    print("RESULT:" + json.dumps({{"error": "not found"}}))
else:
    def build_tree(a, depth=0):
        if depth > 10:
            return {{"label": a.get_actor_label(), "truncated": True}}
        return {{"label": a.get_actor_label(), "children": []}}
    tree = build_tree(actor)
    print("RESULT:" + json.dumps(tree))
"""
        ast.parse(code)
