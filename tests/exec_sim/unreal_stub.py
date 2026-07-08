r"""Fake ``unreal`` module for exec-simulating generated UE5 editor Python.

``make_unreal_stub()`` builds a fresh module object that is installed as
``sys.modules["unreal"]`` while a generated script executes (``exec_generated``).

Strict by default: any top-level symbol not in the curated table raises
AttributeError -- that is how phantom-API bugs surface. The table was seeded by
grepping ``unreal\.<symbol>`` across ue_mcp/tools/ and remote_control/codegen.py.

Deliberately-phantom symbols (absent because the real UE 5.7 Python API does
not expose them -- do NOT add these):

- ``EditorLevelLibrary.editor_undo`` / ``editor_redo``
- ``SystemLibrary.transaction_undo`` / ``transaction_redo``
- ``<actor>.is_hidden()``  (actors expose the ``hidden`` *attribute* instead)

Scriptable outcomes (honesty tests force failure paths)::

    stub = make_unreal_stub(load_level=False)
    stub.configure(ground_hit=False)

Default world: three level actors are seeded, labelled ``SENTINEL_LBL_9Q``
(tagged ``SENTINEL_TAG_9Q``), ``SENTINEL_LBL_B2`` and ``Cube_1`` -- matching
the sentinel kwargs in registry.py so tool success branches actually execute.
"""

from __future__ import annotations

import io
import sys
import types
from contextlib import contextmanager, redirect_stdout

# Product parser: keeps this harness aligned with the real RESULT-line grammar.
from remote_control.execution import _parse_result

# ---------------------------------------------------------------------------
# Value types (shared across stub instances -- they hold no config)
# ---------------------------------------------------------------------------


class Vector:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)

    def __sub__(self, o):
        return Vector(self.x - o.x, self.y - o.y, self.z - o.z)

    def __add__(self, o):
        return Vector(self.x + o.x, self.y + o.y, self.z + o.z)

    def length(self):
        return (self.x**2 + self.y**2 + self.z**2) ** 0.5

    def __repr__(self):
        return f"Vector({self.x}, {self.y}, {self.z})"


class Vector4:
    def __init__(self, x=0.0, y=0.0, z=0.0, w=0.0):
        self.x, self.y, self.z, self.w = float(x), float(y), float(z), float(w)


class Rotator:
    def __init__(self, pitch=0.0, yaw=0.0, roll=0.0):
        self.pitch, self.yaw, self.roll = float(pitch), float(yaw), float(roll)


class Quat:
    def __init__(self, x=0.0, y=0.0, z=0.0, w=1.0):
        self.x, self.y, self.z, self.w = float(x), float(y), float(z), float(w)

    def rotator(self):
        return Rotator()


class Transform:
    def __init__(self, translation=None, rotation=None, scale3d=None):
        self.translation = translation if translation is not None else Vector()
        self.rotation = rotation if rotation is not None else Quat()
        self.scale3d = scale3d if scale3d is not None else Vector(1.0, 1.0, 1.0)


class LinearColor:
    def __init__(self, r=0.0, g=0.0, b=0.0, a=1.0):
        self.r, self.g, self.b, self.a = float(r), float(g), float(b), float(a)


class Color:
    def __init__(self, r=0, g=0, b=0, a=255):
        self.r, self.g, self.b, self.a = int(r), int(g), int(b), int(a)


class Name:
    """Non-str name type, like unreal.Name. json.dumps must NOT accept it as a
    dict key -- exactly the trap that real parameter-name lists set."""

    def __init__(self, s: str):
        self._s = s

    def __str__(self):
        return self._s

    def __repr__(self):
        return f"Name({self._s!r})"

    def __eq__(self, other):
        return str(self) == str(other)

    def __hash__(self):
        return hash(self._s)


class _ClassInfo:
    """What actor.get_class() / comp.get_class() returns."""

    def __init__(self, name: str):
        self._name = name

    def get_name(self):
        return self._name


class _UEObject:
    """Base for seeded UE classes (factories, filters, proxies, CDOs...).

    Instances accept any ctor args and support the generic property protocol.
    Attribute access beyond this whitelist raises AttributeError (strict).
    """

    def __init__(self, *args, **kwargs):
        self._props: dict = {}

    def set_editor_property(self, name, value):
        self._props[str(name)] = value
        return True

    def get_editor_property(self, name):
        return self._props.get(str(name), 1.0)

    def get_name(self):
        return type(self).__name__

    def get_path_name(self):
        return f"/Game/Stub/{type(self).__name__}"

    def get_class(self):
        return _ClassInfo(type(self).__name__)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_CONFIG_DEFAULTS = {
    # EditorLevelLibrary.load_level return value.
    "load_level": True,
    # Whether load_asset / load_blueprint_class / does_asset_exist find things.
    "load_asset": True,
    # Whether SystemLibrary.line_trace_single hits anything.
    "ground_hit": True,
    # Whether unreal.LevelEditorSubsystem exists at all (viewport-focus path).
    "level_editor_subsystem": True,
    # Whether spawn_actor_from_class succeeds.
    "spawn_actor": True,
    # Whether AutomationLibrary.take_high_res_screenshot writes the file.
    "screenshot_writes_file": False,
}


class _Config:
    def __init__(self, **overrides):
        self.__dict__.update(_CONFIG_DEFAULTS)
        self.update(**overrides)

    def update(self, **kw):
        for k, v in kw.items():
            if k not in _CONFIG_DEFAULTS:
                raise TypeError(f"unknown stub config key: {k!r}")
            setattr(self, k, v)


# Default seeded level actors: (label, class_name, path, tags, location)
_ACTOR_SPECS = (
    (
        "SENTINEL_LBL_9Q",
        "StaticMeshActor",
        "/Game/Maps/TestMap.TestMap:PersistentLevel.SENTINEL_ACT_9Q",
        ("SENTINEL_TAG_9Q",),
        (0.0, 0.0, 0.0),
    ),
    (
        "SENTINEL_LBL_B2",
        "PointLight",
        "/Game/Maps/TestMap.TestMap:PersistentLevel.SENTINEL_ACT_B2",
        (),
        (100.0, 200.0, 300.0),
    ),
    (
        "Cube_1",
        "StaticMeshActor",
        "/Game/Maps/TestMap.TestMap:PersistentLevel.Cube_1",
        (),
        (50.0, 0.0, 0.0),
    ),
)

# UE class names the generated code references by attribute (spawnable classes,
# component classes, asset classes, factories, expression nodes, proxies).
_SEEDED_CLASS_NAMES = (
    # actors / spawnables
    "Actor", "Pawn", "Character", "StaticMeshActor", "PointLight", "SpotLight",
    "CameraActor", "NiagaraActor",
    "DirectionalLight", "SkyAtmosphere", "SkyLight", "ExponentialHeightFog",
    "VolumetricCloud", "PostProcessVolume",
    # components
    "ActorComponent", "SceneComponent", "StaticMeshComponent",
    "SkeletalMeshComponent", "PointLightComponent", "SpotLightComponent",
    "AudioComponent", "BoxComponent", "SphereComponent", "NiagaraComponent",
    "DecalComponent", "DirectionalLightComponent", "SkyLightComponent",
    "ExponentialHeightFogComponent",
    # asset classes
    "Material", "MaterialInstanceConstant", "LevelSequence",
    "MaterialExpressionConstant3Vector", "MaterialExpressionConstant",
    # factories / misc instantiables
    "MaterialFactoryNew", "MaterialInstanceConstantFactoryNew",
    "BlueprintFactory", "LevelSequenceFactoryNew", "ARFilter",
    "SequencerBindingProxy",
)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_unreal_stub(**overrides) -> types.ModuleType:
    """Build a fresh, isolated fake ``unreal`` module. See module docstring."""
    config = _Config(**overrides)

    # -- objects with per-stub state --------------------------------------

    class _Component(_UEObject):
        _PROPERTY_VALUES = {"intensity": 5000.0}

        def __init__(self, name="StaticMeshComponent", class_name=None):
            super().__init__()
            self._name = name
            self._class_name = class_name or name
            self.static_mesh = _Asset("/Game/Meshes/SM_StubMesh")
            self.intensity = 5000.0
            self.light_color = LinearColor(1.0, 1.0, 1.0, 1.0)

        def get_name(self):
            return self._name

        def get_class(self):
            return _ClassInfo(self._class_name)

        def get_editor_property(self, name):
            name = str(name)
            if name == "light_color":
                return LinearColor(1.0, 1.0, 1.0, 1.0)
            if name == "settings":
                return self._props.setdefault("settings", _UEObject())
            if name in self._PROPERTY_VALUES:
                return self._PROPERTY_VALUES[name]
            return super().get_editor_property(name)

        def get_num_materials(self):
            return 1

        def get_material(self, index):
            return _Asset("/Game/Materials/M_Stub")

        def set_material(self, index, material):
            return True

        def set_asset(self, asset):
            return True

        def k2_attach_to(self, parent, *args, **kwargs):
            return True

        def set_light_color(self, color):
            return True

        def recapture_sky(self):
            return True

        def recapture(self):
            return True

    class _Asset(_UEObject):
        """A loadable / creatable asset (material, blueprint, sequence...)."""

        def __init__(self, path="/Game/Stub/Asset"):
            super().__init__()
            self._path = path

        def get_path_name(self):
            return self._path

        def get_name(self):
            return self._path.rsplit("/", 1)[-1]

        def generated_class(self):
            return type(self.get_name() + "_C", (_UEObject,), {})

        def add_possessable(self, actor):
            return _Binding()

    class _Binding:
        def get_id(self):
            return "BIND-0000-STUB"

    class _Actor:
        """Level actor. STRICT: no ``is_hidden()`` -- ``hidden`` attr instead."""

        def __init__(self, label, class_name="StaticMeshActor", path=None,
                     tags=(), location=(0.0, 0.0, 0.0)):
            self._label = label
            self._class_name = class_name
            self._path = path or f"/Game/Maps/TestMap.TestMap:PersistentLevel.{label}"
            self.tags = [Name(t) for t in tags]
            self._location = Vector(*location)
            self._rotation = Rotator()
            self._scale = Vector(1.0, 1.0, 1.0)
            self._components = [_Component("StaticMeshComponent")]
            self.hidden = False
            self.root_component = self._components[0]
            self._props: dict = {}

        # identity
        def get_actor_label(self):
            return self._label

        def set_actor_label(self, label):
            self._label = str(label)

        def get_name(self):
            return self._label

        def get_path_name(self):
            return self._path

        def get_class(self):
            return _ClassInfo(self._class_name)

        # transform
        def get_actor_location(self):
            return self._location

        def set_actor_location(self, v, *args):
            self._location = v
            return True

        def get_actor_rotation(self):
            return self._rotation

        def set_actor_rotation(self, r, *args):
            self._rotation = r
            return True

        def get_actor_scale3d(self):
            return self._scale

        def set_actor_scale3d(self, v):
            self._scale = v
            return True

        def get_actor_transform(self):
            return Transform(self._location, Quat(), self._scale)

        def get_actor_bounds(self, only_colliding, *args):
            return (Vector(0.0, 0.0, 100.0), Vector(50.0, 50.0, 100.0))

        # components / hierarchy
        def get_components_by_class(self, cls):
            return list(self._components)

        def get_component_by_class(self, cls):
            return self._components[0]

        def get_attach_parent_actor(self):
            return None

        def get_attached_actors(self):
            return []

        # generic property protocol
        def set_editor_property(self, name, value):
            self._props[str(name)] = value
            return True

        def get_editor_property(self, name):
            name = str(name)
            if name == "settings":
                return self._props.setdefault("settings", _UEObject())
            return self._props.get(name, 1.0)

    world_actors = [_Actor(*spec) for spec in _ACTOR_SPECS]
    _selection: list = []

    def _find_actor_by_path(path):
        for a in world_actors:
            if a.get_path_name() == path:
                return a
        return None

    class _WorldSettings(_UEObject):
        def get_editor_property(self, name):
            if str(name) == "DefaultGameMode":
                return _ClassInfo("GameModeBase")
            return super().get_editor_property(name)

    class _World:
        def get_name(self):
            return "TestLevel"

        def get_path_name(self):
            return "/Game/Maps/TestMap.TestMap"

        def get_streaming_levels(self):
            return []

        def get_world_settings(self):
            return _WorldSettings()

    world = _World()

    class _HitResult:
        def __init__(self):
            self.impact_point = Vector(0.0, 0.0, 12.5)
            self.impact_normal = Vector(0.0, 0.0, 1.0)
            self.distance = 123.5
            self.hit_actor = world_actors[2]
            self.blocking_hit = True

    # -- subsystems (all-static so both class-level and instance-level calls
    #    work; get_editor_subsystem simply returns the class) ----------------

    class EditorActorSubsystem:
        @staticmethod
        def get_all_level_actors():
            return list(world_actors)

        @staticmethod
        def spawn_actor_from_class(cls, location, rotation, *args, **kwargs):
            if not config.spawn_actor:
                return None
            name = getattr(cls, "__name__", "Spawned")
            actor = _Actor(
                f"{name}_1", class_name=name,
                path=f"/Game/Maps/TestMap.TestMap:PersistentLevel.{name}_1",
            )
            world_actors.append(actor)
            return actor

        @staticmethod
        def destroy_actor(actor):
            if actor in world_actors:
                world_actors.remove(actor)
            return True

        @staticmethod
        def set_selected_level_actors(actors):
            _selection[:] = list(actors)

        @staticmethod
        def get_selected_level_actors():
            return list(_selection)

        @staticmethod
        def duplicate_selected_actors():
            return [_Actor(a.get_actor_label() + "2") for a in _selection] or [_Actor("Dup_1")]

    class UnrealEditorSubsystem:
        @staticmethod
        def get_editor_world():
            return world

        @staticmethod
        def get_level_viewport_camera_info():
            return (Vector(0.0, -500.0, 250.0), Rotator(-15.0, 90.0, 0.0))

    class LevelEditorSubsystem:
        @staticmethod
        def focus_on_selected_actors():
            return True

    class LevelSequenceEditorSubsystem:
        pass

    # -- static libraries (STRICT whitelists) ------------------------------

    class EditorLevelLibrary:
        # Deliberately ABSENT: editor_undo, editor_redo (phantom APIs).
        @staticmethod
        def get_editor_world():
            return world

        @staticmethod
        def save_current_level():
            return True

        @staticmethod
        def load_level(path):
            return config.load_level

        @staticmethod
        def set_selected_level_actors(actors):
            _selection[:] = list(actors)

        @staticmethod
        def get_actor_reference(path):
            return _find_actor_by_path(path) or world_actors[0]

    class SystemLibrary:
        # Deliberately ABSENT: transaction_undo, transaction_redo (phantom APIs).
        @staticmethod
        def execute_console_command(world_ctx, command):
            return None

        @staticmethod
        def line_trace_single(world_ctx, start, end, query, complex_trace,
                              ignore, draw, ret, *args, **kwargs):
            return _HitResult() if config.ground_hit else None

    class EditorAssetLibrary:
        @staticmethod
        def load_asset(path):
            return _Asset(str(path)) if config.load_asset else None

        @staticmethod
        def load_blueprint_class(path):
            if not config.load_asset:
                return None
            return type("StubBPClass", (_UEObject,), {})

        @staticmethod
        def does_asset_exist(path):
            return bool(config.load_asset)

        @staticmethod
        def save_asset(path, *args, **kwargs):
            return True

        @staticmethod
        def delete_asset(path):
            return True

    class _AssetTools:
        @staticmethod
        def create_asset(asset_name, package_path, asset_class, factory):
            return _Asset(f"{package_path}/{asset_name}")

    class AssetToolsHelpers:
        @staticmethod
        def get_asset_tools():
            return _AssetTools()

    class _AssetData:
        def __init__(self):
            self.asset_name = Name("SM_StubCube")
            self.package_name = Name("/Game/Meshes/SM_StubCube")
            self.asset_class_path = types.SimpleNamespace(asset_name=Name("StaticMesh"))

    class _AssetRegistry:
        @staticmethod
        def get_assets_by_package_name(name, *args, **kwargs):
            return []

        @staticmethod
        def get_all_assets(ar_filter, *args, **kwargs):
            return [_AssetData()]

    class AssetRegistryHelpers:
        @staticmethod
        def get_asset_registry():
            return _AssetRegistry()

    class BlueprintEditorLibrary:
        @staticmethod
        def compile_blueprint(bp):
            return True

    class MaterialEditingLibrary:
        @staticmethod
        def create_material_expression(material, expression_class, x=0, y=0):
            return _UEObject()

        @staticmethod
        def connect_material_property(node, output_name, material_property):
            return True

        @staticmethod
        def recompile_material(material):
            return True

        @staticmethod
        def set_material_instance_scalar_parameter_value(mi, name, value):
            return True

        @staticmethod
        def set_material_instance_vector_parameter_value(mi, name, value):
            return True

        @staticmethod
        def set_material_instance_texture_parameter_value(mi, name, value):
            return True

        # Parameter-name lists are unreal.Name objects in the real API (NOT str)
        # -- json.dumps on a dict keyed by them must raise, as in the editor.
        @staticmethod
        def get_scalar_parameter_names(asset):
            return [Name("StubScalarParam")]

        @staticmethod
        def get_vector_parameter_names(asset):
            return [Name("StubVectorParam")]

        @staticmethod
        def get_texture_parameter_names(asset):
            return [Name("StubTextureParam")]

        @staticmethod
        def get_material_instance_scalar_parameter_value(asset, name):
            return 0.5

        @staticmethod
        def get_material_instance_vector_parameter_value(asset, name):
            return LinearColor(0.1, 0.2, 0.3, 1.0)

        @staticmethod
        def get_material_instance_texture_parameter_value(asset, name):
            return _Asset("/Game/Textures/T_Stub")

        # Default-value getters (base Material family — real 5.x API names).
        @staticmethod
        def get_material_default_scalar_parameter_value(material, name):
            return 0.25

        @staticmethod
        def get_material_default_vector_parameter_value(material, name):
            return LinearColor(0.4, 0.5, 0.6, 1.0)

        @staticmethod
        def get_material_default_texture_parameter_value(material, name):
            return _Asset("/Game/Textures/T_StubDefault")

    class AutomationLibrary:
        @staticmethod
        def take_high_res_screenshot(width, height, path, *args, **kwargs):
            if config.screenshot_writes_file:
                with open(path, "wb") as f:
                    f.write(b"\xff\xd8stub-image-bytes\xff\xd9")
            return True

    class EditorUtilityLibrary:
        @staticmethod
        def get_selected_assets():
            return []

    class MathLibrary:
        @staticmethod
        def make_rot_from_z(v):
            return Rotator()

    class LevelSequenceEditorBlueprintLibrary:
        @staticmethod
        def open_level_sequence(seq):
            return True

        @staticmethod
        def set_current_time(t):
            return True

        @staticmethod
        def play():
            return True

        @staticmethod
        def get_bound_objects(binding_proxy):
            return []

    # -- module-level functions ---------------------------------------------

    def get_editor_subsystem(cls):
        return cls

    def find_class(name):
        return type(str(name), (_UEObject,), {})

    def load_class(outer, path):
        return type(str(path).rsplit(".", 1)[-1], (_UEObject,), {})

    def new_object(cls, outer=None, name=None, *args, **kwargs):
        return _Component(str(name) if name else getattr(cls, "__name__", "Comp"))

    def get_default_object(cls):
        return _UEObject()

    def load_asset(path):
        return EditorAssetLibrary.load_asset(path)

    def load_object(outer, path):
        return _find_actor_by_path(str(path)) or (_Asset(str(path)) if config.load_asset else None)

    def find_object(outer, path):
        return _find_actor_by_path(str(path))

    # -- assemble the module ------------------------------------------------

    mod = types.ModuleType("unreal")
    mod.__doc__ = "exec-sim stub for the UE5 editor Python API (tests/exec_sim)"

    for cls_name in _SEEDED_CLASS_NAMES:
        setattr(mod, cls_name, type(cls_name, (_UEObject,), {}))

    exported = {
        "Vector": Vector, "Vector4": Vector4, "Rotator": Rotator,
        "Quat": Quat, "Transform": Transform,
        "LinearColor": LinearColor, "Color": Color, "Name": Name,
        "EditorActorSubsystem": EditorActorSubsystem,
        "UnrealEditorSubsystem": UnrealEditorSubsystem,
        "LevelEditorSubsystem": LevelEditorSubsystem,
        "LevelSequenceEditorSubsystem": LevelSequenceEditorSubsystem,
        "EditorLevelLibrary": EditorLevelLibrary,
        "SystemLibrary": SystemLibrary,
        "EditorAssetLibrary": EditorAssetLibrary,
        "AssetToolsHelpers": AssetToolsHelpers,
        "AssetRegistryHelpers": AssetRegistryHelpers,
        "BlueprintEditorLibrary": BlueprintEditorLibrary,
        "MaterialEditingLibrary": MaterialEditingLibrary,
        "AutomationLibrary": AutomationLibrary,
        "EditorUtilityLibrary": EditorUtilityLibrary,
        "MathLibrary": MathLibrary,
        "LevelSequenceEditorBlueprintLibrary": LevelSequenceEditorBlueprintLibrary,
        "MaterialProperty": types.SimpleNamespace(
            MP_BASE_COLOR=0, MP_ROUGHNESS=1, MP_METALLIC=2, MP_EMISSIVE_COLOR=3,
        ),
        "TraceTypeQuery": types.SimpleNamespace(TRACE_TYPE_QUERY1=1, TRACE_TYPE_QUERY2=2),
        "DrawDebugTrace": types.SimpleNamespace(NONE=0),
        "get_editor_subsystem": get_editor_subsystem,
        "find_class": find_class,
        "load_class": load_class,
        "new_object": new_object,
        "get_default_object": get_default_object,
        "load_asset": load_asset,
        "load_object": load_object,
        "find_object": find_object,
    }
    for name, obj in exported.items():
        setattr(mod, name, obj)

    def configure(**kw):
        """Override scripted outcomes, e.g. stub.configure(load_level=False)."""
        config.update(**kw)
        if not config.level_editor_subsystem:
            if hasattr(mod, "LevelEditorSubsystem"):
                delattr(mod, "LevelEditorSubsystem")
        else:
            mod.LevelEditorSubsystem = LevelEditorSubsystem

    mod.configure = configure
    configure()  # apply presence toggles from overrides
    return mod


# ---------------------------------------------------------------------------
# Exec harness
# ---------------------------------------------------------------------------


@contextmanager
def installed(stub: types.ModuleType):
    """Temporarily install ``stub`` as sys.modules['unreal']."""
    prev = sys.modules.get("unreal")
    sys.modules["unreal"] = stub
    try:
        yield
    finally:
        if prev is None:
            sys.modules.pop("unreal", None)
        else:
            sys.modules["unreal"] = prev


def exec_generated(code: str, stub: types.ModuleType, name: str = "<generated>") -> str:
    """Compile + exec generated UE Python under the stub; return captured stdout.

    Raises SyntaxError if the code does not compile, and propagates any runtime
    exception from the generated script (NameError, AttributeError, TypeError...).
    """
    code_obj = compile(code, name, "exec")
    buf = io.StringIO()
    with installed(stub), redirect_stdout(buf):
        exec(code_obj, {"__name__": "__ue_generated__"})  # noqa: S102 -- the point of the harness
    return buf.getvalue()


def parse_result(stdout: str) -> dict:
    """Parse captured stdout with the product's RESULT-line grammar.

    Returns {"result": <parsed RESULT payload or None>, "output": str, "error": None}.
    """
    return _parse_result({"output": stdout, "error": None})


_FAILURE_STRINGS = {"SPAWN_FAILED", "NOT_FOUND", "CREATE_FAILED"}


def is_failure(result_data) -> bool:
    """Classify a parsed RESULT payload as a failure report.

    dict -> truthy "error" key; str -> known failure markers; list/other -> ok.
    """
    if isinstance(result_data, dict):
        return bool(result_data.get("error"))
    if isinstance(result_data, str):
        s = result_data.strip()
        return s in _FAILURE_STRINGS or s.startswith("CLASS_NOT_FOUND")
    return False


def has_result_line(stdout: str) -> bool:
    return any(line.startswith("RESULT:") for line in stdout.splitlines())
