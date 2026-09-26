bl_info = {
    "name": "BlenderShelf",
    "author": "DenisZakharov",
    "version": (0, 1, 5),
    "blender": (4, 1, 0),
    "location": "3D Viewport, floating overlay near the top edge",
    "description": "A floating shelf of custom buttons in the 3D viewport (Maya-shelf style)",
    "category": "Interface",
    "doc_url": "https://blendershelf.github.io/BlenderShelf/",
    "tracker_url": "https://blendershelf.github.io/BlenderShelf/#feedback",
}

import os
import re
import json
import math
import time
import ast
import bpy
import bmesh
import gpu
import blf
import rna_keymap_ui
import bpy.utils.previews
from gpu_extras.batch import batch_for_shader

ADDON_DIR = os.path.dirname(__file__)
ICON_DIR = os.path.join(ADDON_DIR, "icons")
CONFIG_FILE = os.path.join(ADDON_DIR, "shelf_config.json")

BASE_BTN = 40
BASE_PAD = 10
DEFAULT_TOP_MARGIN = 40
DEFAULT_LEFT_MARGIN_PCT = 0.03
PRESET_EDGE_MARGIN = 20

VERSIONS_JSON_URL = "https://blendershelf.github.io/BlenderShelf/versions.json"
DOWNLOAD_PAGE_URL = "https://blendershelf.github.io/BlenderShelf/#download"

_icon_textures = {}


def _get_icon_texture(path):
    if not path:
        return None
    if path not in _icon_textures:
        try:
            img = bpy.data.images.load(path, check_existing=True)
            _icon_textures[path] = gpu.texture.from_image(img)
        except Exception:
            _icon_textures[path] = None
    return _icon_textures[path]


# ---------------------------------------------------------------------------
# Button actions
# ---------------------------------------------------------------------------

def make_roundcube_bmesh(cuts=3, radius=1.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=radius * 2)
    for _ in range(cuts):
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, use_grid_fill=True)
    for v in bm.verts:
        v.co = v.co.normalized() * radius
    return bm


# ---------------------------------------------------------------------------
# Shelf command execution
# ---------------------------------------------------------------------------
# Third-party addon operators (HardOps' Radial Array etc.) are often
# Python-implemented and define their own modal() -- their real behavior
# only runs when invoked (invoke()/modal()), not when called bare. exec()
# calls bpy.ops under the implicit EXEC_DEFAULT context, which skips
# invoke() entirely: the operator's execute() runs (if it has one) with no
# arguments and no interactive state, so it silently does nothing. This
# proxy makes bare bpy.ops calls to such operators use INVOKE_DEFAULT
# automatically, unless the command already specifies a context itself.
#
# 'modal' in cls.__dict__ only catches Python-implemented operators --
# built-in C operators (most bpy.ops.transform.* drag tools, e.g.
# transform.edge_bevelweight) have no Python-visible class in bpy.types at
# all (confirmed live: true for every built-in op, modal or not). But the
# operator *callable* itself (bpy.ops.<cat>.<name>, as opposed to
# get_rna_type()) exposes bl_options directly for both C and Python ops --
# verified live across 20 built-ins: every known interactive/drag operator
# (mesh.bevel, mesh.inset, transform.rotate/trackball/shrink_fatten/
# vert_slide/edge_slide/shear/tosphere, mesh.knife_tool, transform.
# edge_bevelweight/edge_crease) carries 'BLOCKING' or 'GRAB_CURSOR' in
# op.bl_options; every known non-interactive one (primitive_cube_add,
# select_all, mesh.delete/merge, modifier_add, shade_smooth, flip_normals,
# brush.asset_activate) carries neither. That's the generic C-operator
# signal EXEC_DEFAULT breaks -- no hardcoded list needed.
# ponytail: known gap -- macro operators (mesh.loopcut_slide,
# object.duplicate_move) don't carry the flag on the macro itself (it's on
# their sub-operators), so they're invisible to this check; loopcut_slide's
# separate breakage is handled via _OPERATOR_OVERRIDES instead, since its
# real bug is a captured one-shot edge_index, not just a missing INVOKE.

_OP_CONTEXT_STRS = {
    'INVOKE_DEFAULT', 'INVOKE_REGION_WIN', 'INVOKE_REGION_CHANNELS',
    'INVOKE_REGION_PREVIEW', 'INVOKE_AREA', 'INVOKE_SCREEN',
    'EXEC_DEFAULT', 'EXEC_REGION_WIN', 'EXEC_REGION_CHANNELS',
    'EXEC_REGION_PREVIEW', 'EXEC_AREA', 'EXEC_SCREEN',
}

_MODAL_BL_OPTIONS = {'BLOCKING', 'GRAB_CURSOR', 'GRAB_CURSOR_X', 'GRAB_CURSOR_Y'}


def _op_is_modal(op):
    try:
        if _MODAL_BL_OPTIONS & set(op.bl_options):
            return True
        cls = getattr(bpy.types, op.get_rna_type().identifier, None)
        if cls is None:
            return False
        return 'modal' in cls.__dict__
    except Exception:
        return False


class _ShelfOpsCategory:
    def __init__(self, category):
        self._category = category

    def __getattr__(self, name):
        op = getattr(self._category, name)
        if not _op_is_modal(op):
            return op

        def wrapper(*args, **kwargs):
            if args and isinstance(args[0], str) and args[0] in _OP_CONTEXT_STRS:
                return op(*args, **kwargs)
            return op('INVOKE_DEFAULT', *args, **kwargs)
        return wrapper


class _ShelfOps:
    def __getattr__(self, name):
        return _ShelfOpsCategory(getattr(bpy.ops, name))


class _ShelfBpy:
    ops = _ShelfOps()

    def __getattr__(self, name):
        return getattr(bpy, name)


_shelf_bpy = _ShelfBpy()


def _exec_shelf_command(command):
    exec(command, {"bpy": _shelf_bpy, "__name__": "__main__"})


class BLENDERSHELF_OT_add_roundcube(bpy.types.Operator):
    """Add a subdivided-cube sphere (RoundCube)"""
    bl_idname = "mesh.blendershelf_add_roundcube"
    bl_label = "Add Round Cube"
    bl_options = {'REGISTER', 'UNDO'}

    cuts: bpy.props.IntProperty(name="Subdivisions", default=3, min=1, max=6)
    radius: bpy.props.FloatProperty(name="Radius", default=1.0, min=0.01)

    def execute(self, context):
        bm = make_roundcube_bmesh(self.cuts, self.radius)
        mesh = bpy.data.meshes.new("RoundCube")
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()
        obj = bpy.data.objects.new("RoundCube", mesh)
        context.collection.objects.link(obj)
        obj.location = context.scene.cursor.location
        for o in context.selected_objects:
            o.select_set(False)
        obj.select_set(True)
        context.view_layer.objects.active = obj
        return {'FINISHED'}


# ---------------------------------------------------------------------------
# Preferences -- persistent, user-editable shelf button list.
# Each button is {label, icon_path, command, enabled}; "command" is a Python
# snippet exec'd on click (same mechanism "Add to Shelf" already used).
# ---------------------------------------------------------------------------

BLENDER_ICON_DIR = os.path.join(ICON_DIR, "blender")

# ---------------------------------------------------------------------------
# Auto-icon lookup: instead of hand-maintaining an operator->icon table, ask
# Blender's own registered menus what icon they draw next to each operator.
# A fake UILayout stub records (operator_id, icon) pairs as every known Menu
# subclass's draw() runs against it -- no real UI is ever shown. This also
# picks up icons from the user's other installed addons for free.
# ---------------------------------------------------------------------------

_operator_icon_map = None


def _build_operator_icon_map():
    """Scan every registered Menu subclass and return {operator_id: icon_path}
    for operators whose menu icon has a matching PNG in BLENDER_ICON_DIR."""
    global _operator_icon_map
    _operator_icon_map = {}
    visited = set()

    def scan(idname, depth=0):
        if idname in visited or depth > 6:
            return
        visited.add(idname)
        cls = getattr(bpy.types, idname, None)
        if cls is None or not hasattr(cls, "draw"):
            return

        class _Layout:
            def operator(self, opname, text="", icon='NONE', **kwargs):
                if icon != 'NONE' and opname not in _operator_icon_map:
                    _operator_icon_map[opname] = icon
                return type("_Props", (), {"__setattr__": lambda s, n, v: None})()

            def menu(self, menu_idname, *a, **k):
                scan(menu_idname, depth + 1)

            def menu_contents(self, menu_idname, *a, **k):
                scan(menu_idname, depth + 1)

            def __getattr__(self, name):
                return lambda *a, **k: self

            def __setattr__(self, name, value):
                object.__setattr__(self, name, value)

        fake_self = type("_FakeMenu", (), {})()
        fake_self.layout = _Layout()
        try:
            cls.draw(fake_self, bpy.context)
        except Exception:
            pass

    def collect(cls):
        idn = getattr(cls, "bl_idname", None) or cls.__name__
        scan(idn)
        for sub in cls.__subclasses__():
            collect(sub)

    collect(bpy.types.Menu)

    available = {f[:-4] for f in os.listdir(BLENDER_ICON_DIR) if f.endswith(".png")}
    resolved = {
        op_id: os.path.join(BLENDER_ICON_DIR, icon + ".png")
        for op_id, icon in _operator_icon_map.items()
        if icon in available
    }
    _operator_icon_map = resolved
    return _operator_icon_map


def _lookup_icon_for_operator(op_id):
    global _operator_icon_map
    if _operator_icon_map is None:
        _build_operator_icon_map()
    return _operator_icon_map.get(op_id)


# ---------------------------------------------------------------------------
# Generic fix for the whole "one operator, many rows via operator_enum()/
# operator_menu_enum()" bug class (SKIP_SAVE -- see the long comment above
# _OPERATOR_OVERRIDES): rather than hand-writing a label_fn/command_fn pair
# per affected operator as they're reported one at a time, scan the Add menu
# tree itself (same fake-layout technique as the icon map) for every
# operator_enum()/operator_menu_enum() call, recording which property each
# one varies. Anything found this way -- built-in or from a third-party
# addon (Extra Curve Objects' Spirals/Profiles, Cablerator, etc.) -- gets
# its label/command rebuilt directly from that property instead of via the
# clipboard capture that silently drops it. _OPERATOR_OVERRIDES still wins
# for anything hand-written there (more nuanced cases, multiple properties).
# ---------------------------------------------------------------------------

_ENUM_MENU_SCAN_ROOTS = ("VIEW3D_MT_add",)
_enum_menu_prop_map = None


def _build_enum_menu_prop_map():
    global _enum_menu_prop_map
    _enum_menu_prop_map = {}
    visited = set()

    def scan(idname, depth=0):
        if idname in visited or depth > 6:
            return
        visited.add(idname)
        cls = getattr(bpy.types, idname, None)
        if cls is None or not hasattr(cls, "draw"):
            return

        class _Layout:
            def operator(self, opname, text="", icon='NONE', **kwargs):
                return type("_Props", (), {"__setattr__": lambda s, n, v: None})()

            def operator_enum(self, opname, propname, *a, **k):
                _enum_menu_prop_map.setdefault(opname, propname)

            def operator_menu_enum(self, opname, propname, *a, **k):
                _enum_menu_prop_map.setdefault(opname, propname)

            def menu(self, menu_idname, *a, **k):
                scan(menu_idname, depth + 1)

            def menu_contents(self, menu_idname, *a, **k):
                scan(menu_idname, depth + 1)

            def __getattr__(self, name):
                return lambda *a, **k: self

            def __setattr__(self, name, value):
                object.__setattr__(self, name, value)

        fake_self = type("_FakeMenu", (), {})()
        fake_self.layout = _Layout()
        try:
            cls.draw(fake_self, bpy.context)
        except Exception:
            pass

    for root in _ENUM_MENU_SCAN_ROOTS:
        scan(root)
    return _enum_menu_prop_map


def _enum_prop_for_operator(op_id):
    global _enum_menu_prop_map
    if _enum_menu_prop_map is None:
        _build_enum_menu_prop_map()
    return _enum_menu_prop_map.get(op_id)


def _enum_menu_label_and_command(op_id, op, prop_name):
    value = getattr(op, prop_name, None)
    if value is None:
        return None, None
    try:
        label = op.bl_rna.properties[prop_name].enum_items[value].name
    except (KeyError, AttributeError, TypeError):
        label = str(value)
    return label, f"bpy.ops.{op_id}({prop_name}={value!r})"


# Operators whose "type" enum value matches a real icon file 1:1 by Blender's
# own naming convention (e.g. modifier_add(type='ARRAY') <-> MOD_ARRAY.png).
# Exact, not a guess -- covers the one real gap the menu-scan can't (a single
# operator id shared by every modifier type). Constraint types were tried and
# dropped: object.constraint_add's "type" enum isn't introspectable outside a
# real UI context and its Add menu isn't a plain Menu subclass either, so
# there's no reliable identifier<->icon rule to verify here -- constraints
# fall through to the menu-scan/fuzzy tiers instead.
_TYPE_ICON_PREFIX = {
    "object.modifier_add": "MOD_",
    "object.light_add": "LIGHT_",
    "object.lightprobe_add": "LIGHTPROBE_",
    "object.effector_add": "FORCE_",
}

# A handful of (op_id, type-value) pairs where the icon file uses an older/
# different word for the same enum value than {prefix}{type_id}.png would
# produce -- checked before the plain prefix concatenation above.
_TYPE_ICON_VALUE_OVERRIDES = {
    ("object.lightprobe_add", "SPHERE"): "LIGHTPROBE_CUBEMAP",
    ("object.lightprobe_add", "PLANE"): "LIGHTPROBE_PLANAR",
    ("object.lightprobe_add", "VOLUME"): "LIGHTPROBE_GRID",
    ("object.effector_add", "MAGNET"): "FORCE_MAGNETIC",
    ("object.effector_add", "LENNARDJ"): "FORCE_LENNARDJONES",
}


def _icon_from_type_prop(op_id, op):
    type_id = getattr(op, "type", None)
    if not type_id:
        return None
    override = _TYPE_ICON_VALUE_OVERRIDES.get((op_id, type_id))
    if override:
        candidate = os.path.join(BLENDER_ICON_DIR, f"{override}.png")
        if os.path.exists(candidate):
            return candidate
    prefix = _TYPE_ICON_PREFIX.get(op_id)
    if not prefix:
        return None
    candidate = os.path.join(BLENDER_ICON_DIR, f"{prefix}{type_id}.png")
    return candidate if os.path.exists(candidate) else None


def _tokenize(text):
    # Split camelCase boundaries first ("UnBevel" -> "Un Bevel") -- addon
    # button labels are often one un-separated word, and without this a
    # real word like "bevel" is invisible, glued inside "unbevel".
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)
    # len > 2 drops filler words ("up", "on", "to"...) that would otherwise
    # false-match against unrelated icons sharing only a common short word.
    return set(w for w in re.split(r"[^a-zA-Z0-9]+", text.lower()) if len(w) > 2)


# Prefixes that are unambiguously "thing" icons (mesh/modifier/constraint/...)
# rather than UI chrome, even when nothing captured by the menu-scan happens
# to use them -- e.g. MOD_ARRAY.png exists but no reachable menu draws it
# with an icon (HardOps' newer array tool draws its own GPU overlay instead
# of a plain bpy.types.Menu, so the scan can't see it at all). Forcing these
# prefixes into the fuzzy candidate pool closes that gap without having to
# hand-curate all ~670 icon files.
_SAFE_ICON_PREFIXES = ("MOD_", "CON_", "MESH_", "CURVE_", "SURFACE_", "META_", "FORCE_", "GP_", "NODE_")


def _fuzzy_candidate_icons():
    global _operator_icon_map
    if _operator_icon_map is None:
        _build_operator_icon_map()
    names = {os.path.splitext(os.path.basename(p))[0] for p in _operator_icon_map.values()}
    for fname in os.listdir(BLENDER_ICON_DIR):
        if fname.endswith(".png") and fname.startswith(_SAFE_ICON_PREFIXES):
            names.add(fname[:-4])
    return names


# Concept words that many addons never attach a real icon to (icon='NONE'
# in their own draw() code, confirmed live for the Pivot Transform addon's
# Loc./Rot./Sca. buttons) but that this icon pack still has a reasonable
# visual stand-in for. Checked before the generic word-overlap guesser since
# these abbreviations ("loc", "rot", "sca") don't share any substring with
# their matching icon's own name, so plain tokenizing would never find them.
_CONCEPT_ICONS = (
    (("loc", "location", "locate", "translate", "translation", "position", "origin"), "OBJECT_ORIGIN"),
    (("rot", "rotate", "rotation"), "CON_ROTLIKE"),
    (("sca", "scale", "scaling"), "CON_SIZELIKE"),
    (("transform",), "CON_TRANSFORM"),
    (("pivot",), "PIVOT_ACTIVE"),
    (("orient", "orientation", "direction"), "ORIENTATION_GIMBAL"),
    # Pre-seeded common action words (same reasoning: the word itself never
    # appears in a matching icon's own name, so the generic guesser alone
    # would never find these). Grown from real mismatches as they're found,
    # not written as an exhaustive catalog of all ~670 icons.
    (("add", "new", "create"), "ADD"),
    (("delete", "remove", "erase"), "REMOVE"),
    (("unlock",), "UNLOCKED"),
    (("lock",), "LOCKED"),
    (("show", "unhide", "reveal"), "HIDE_OFF"),
    (("hide",), "HIDE_ON"),
    (("snap",), "SNAP_ON"),
    (("duplicate", "clone"), "DUPLICATE"),
    (("copy",), "COPYDOWN"),
    (("paste",), "PASTEDOWN"),
    (("unlink",), "UNLINKED"),
    (("link",), "LINKED"),
    (("group",), "GROUP"),
)


def _concept_icon_from_label(label):
    if not label:
        return None
    tokens = _tokenize(label)
    for keywords, icon_name in _CONCEPT_ICONS:
        if tokens & set(keywords):
            candidate = os.path.join(BLENDER_ICON_DIR, icon_name + ".png")
            if os.path.exists(candidate):
                return candidate
    return None


def _guess_icon_from_label(label):
    """Last-resort fallback: score candidate icons by word overlap with the
    button's label. A guess, not a lookup -- only used once type/menu
    matches have both failed."""
    if not label:
        return None
    label_tokens = _tokenize(label)
    if not label_tokens:
        return None
    best_icon, best_score = None, 0
    for icon_name in _fuzzy_candidate_icons():
        score = len(label_tokens & _tokenize(icon_name))
        if score > best_score:
            best_score, best_icon = score, icon_name
    return os.path.join(BLENDER_ICON_DIR, best_icon + ".png") if best_icon else None


def _resolve_icon(op_id, op, label):
    return (
        _icon_from_type_prop(op_id, op)
        or _lookup_icon_for_operator(op_id)
        or _concept_icon_from_label(label)
        or _guess_icon_from_label(label)
    )


DEFAULT_BUTTONS = [
    {"label": "Cube", "icon": os.path.join(BLENDER_ICON_DIR, "MESH_CUBE.png"),
     "command": "bpy.ops.mesh.primitive_cube_add()"},
    {"label": "CubeSphere", "icon": os.path.join(BLENDER_ICON_DIR, "MESH_UVSPHERE.png"),
     "command": "bpy.ops.mesh.blendershelf_add_roundcube()"},
    {"label": "Cyl", "icon": os.path.join(BLENDER_ICON_DIR, "MESH_CYLINDER.png"),
     "command": "bpy.ops.mesh.primitive_cylinder_add()"},
]


class BLENDERSHELF_button_item(bpy.types.PropertyGroup):
    label: bpy.props.StringProperty(name="Label", default="Button",
                                     update=lambda self, context: _on_prefs_changed())
    icon_path: bpy.props.StringProperty(name="Icon", default="",
                                         update=lambda self, context: _on_prefs_changed())
    command: bpy.props.StringProperty(
        name="Command", default="",
        description="Python executed on click, e.g. bpy.ops.mesh.primitive_cube_add()",
        update=lambda self, context: _on_prefs_changed())
    enabled: bpy.props.BoolProperty(name="Enabled", default=True,
                                     update=lambda self, context: _on_prefs_changed())
    show_in_pie: bpy.props.BoolProperty(name="Show in Pie Menu", default=True,
                                         update=lambda self, context: _on_prefs_changed())
    is_separator: bpy.props.BoolProperty(name="Separator", default=False,
                                          update=lambda self, context: _on_prefs_changed())


class BLENDERSHELF_command_param(bpy.types.PropertyGroup):
    # .name (built-in on every PropertyGroup) holds the keyword itself,
    # e.g. "radius" -- value holds its Python source text, e.g. "1.5".
    value: bpy.props.StringProperty(name="Value", default="")


def get_prefs():
    addon = bpy.context.preferences.addons.get(__name__)
    return addon.preferences if addon else None


# ---------------------------------------------------------------------------
# Three button lists share one PropertyGroup (BLENDERSHELF_button_item): the
# shelf itself, and (in Split pie mode) one independent pie list per context
# category -- Object/Edit always available, Sculpt/UV Editor/Node Editor
# opt-in via their own checkbox in Preferences. Operators take a `target` so
# the same add/remove/move/edit/copy code drives all of them instead of
# being duplicated per list.
# ---------------------------------------------------------------------------

_PIE_TARGETS = {
    'SHELF': ("buttons", "active_index"),
    'PIE_OBJECT': ("pie_buttons_object", "pie_active_index_object"),
    'PIE_EDIT': ("pie_buttons_edit", "pie_active_index_edit"),
    'PIE_SCULPT': ("pie_buttons_sculpt", "pie_active_index_sculpt"),
    'PIE_UV': ("pie_buttons_uv", "pie_active_index_uv"),
    'PIE_NODE_SHADER': ("pie_buttons_node_shader", "pie_active_index_node_shader"),
    'PIE_NODE_GEO': ("pie_buttons_node_geo", "pie_active_index_node_geo"),
}
_TARGET_LABELS = {
    'SHELF': "Shelf",
    'PIE_OBJECT': "Pie: Object Mode",
    'PIE_EDIT': "Pie: Edit Mode",
    'PIE_SCULPT': "Pie: Sculpt Mode",
    'PIE_UV': "Pie: UV Editor",
    'PIE_NODE_SHADER': "Pie: Shader Editor",
    'PIE_NODE_GEO': "Pie: Geometry Nodes",
}
_TARGET_ITEMS = tuple((k, v, "") for k, v in _TARGET_LABELS.items())


def _target_collection(prefs, target):
    coll_name, idx_name = _PIE_TARGETS[target]
    return getattr(prefs, coll_name), idx_name


def _tag_viewports_redraw():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()


def _find_view3d_region():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'VIEW_3D':
                for region in area.regions:
                    if region.type == 'WINDOW':
                        return region
    return None


# ---------------------------------------------------------------------------
# Pie menu hotkey -- registered unbound (type='NONE') in the addon keyconfig;
# the user assigns/edits the actual key in this addon's preferences UI via
# rna_keymap_ui, which edits the *user* keyconfig's copy of this item.
# ---------------------------------------------------------------------------

addon_keymaps = []

# Registered in every editor space that can host an optional pie context, not
# just 3D View -- unbound (type='NONE') by default, same as before; the
# hotkey editor row for Node Editor / Image Editor is only shown in the
# Preferences UI once its "Optional Contexts" checkbox is on, but the
# keymap item itself always exists so there's nothing to (un)register live
# when that checkbox is toggled.
_PIE_KEYMAP_SPACES = (('3D View', 'VIEW_3D'), ('Node Editor', 'NODE_EDITOR'), ('Image', 'IMAGE_EDITOR'))


def _register_keymap():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc is None:
        return
    for name, space_type in _PIE_KEYMAP_SPACES:
        km = kc.keymaps.new(name=name, space_type=space_type, region_type='WINDOW')
        kmi = km.keymap_items.new('wm.call_menu_pie', 'NONE', 'PRESS')
        kmi.properties.name = BLENDERSHELF_MT_pie.bl_idname
        addon_keymaps.append((km, kmi))


def _unregister_keymap():
    for km, kmi in addon_keymaps:
        try:
            km.keymap_items.remove(kmi)
        except (RuntimeError, ReferenceError):
            pass
    addon_keymaps.clear()


def _pie_hotkey_assigned():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.user
    km = kc.keymaps.get('3D View') if kc else None
    if km is None:
        return False
    for kmi in km.keymap_items:
        if kmi.idname == 'wm.call_menu_pie' and kmi.properties.name == BLENDERSHELF_MT_pie.bl_idname:
            return kmi.active and kmi.type != 'NONE'
    return False


def _should_draw_shelf():
    prefs = get_prefs()
    mode = prefs.display_mode if prefs else 'BOTH'
    if mode == 'PIE':
        return not _pie_hotkey_assigned()
    return True


def _export_button_enabled():
    prefs = get_prefs()
    return prefs.show_export_button if prefs else True


def _total_slots(items):
    # FBX takes slot 0 inside the panel when enabled. If there's nothing at
    # all to show (no buttons, FBX off), keep one empty slot so the panel
    # itself stays visible as an anchor instead of disappearing entirely.
    return max(len(items) + (1 if _export_button_enabled() else 0), 1)


def _portable_icon_path(icon_path):
    # icon_path is normally an absolute path baked from ADDON_DIR at
    # button-creation time (os.path.dirname(__file__)) -- fine on the machine
    # that created it, but that exact string travels verbatim through
    # shelf_config.json and Export/Import Settings. On a different PC/Windows
    # login the addon lives under a different absolute path, so the button
    # silently loses its icon on import (confirmed by user report, 2026-09-25:
    # exported from home, imported at work, all shelf icons gone). For any
    # icon that lives inside this addon's own icons/ folder, store it
    # relative to that folder instead -- it resolves correctly wherever the
    # addon itself is installed. An icon picked from outside icons/ (a custom
    # user file) has no such anchor and stays absolute; it's inherently
    # machine-specific since the file itself doesn't travel with the config.
    if not icon_path:
        return icon_path
    try:
        rel = os.path.relpath(icon_path, ICON_DIR)
    except ValueError:
        return icon_path  # different drive on Windows -- can't relativize
    if rel.startswith(".."):
        return icon_path
    return rel.replace("\\", "/")


def _resolve_icon_path(stored):
    # Reverse of _portable_icon_path. Also self-heals configs that were
    # already exported/imported before this fix existed: if a stored
    # absolute path doesn't exist on this machine, fall back to a same-
    # basename lookup in this install's own icons/blender/ -- covers the
    # common case (a bundled icon that just moved to a different absolute
    # prefix) without requiring the user to re-export from the source PC.
    if not stored:
        return stored
    if not os.path.isabs(stored):
        return os.path.join(ICON_DIR, *stored.split("/"))
    if os.path.exists(stored):
        return stored
    fallback = os.path.join(BLENDER_ICON_DIR, os.path.basename(stored))
    return fallback if os.path.exists(fallback) else stored


def _serialize_items(coll):
    return [{"label": b.label, "icon_path": _portable_icon_path(b.icon_path), "command": b.command,
              "enabled": b.enabled, "show_in_pie": b.show_in_pie, "is_separator": b.is_separator} for b in coll]


def _deserialize_items(coll, data_list):
    coll.clear()
    for d in data_list:
        item = coll.add()
        item.label = d.get("label", "Button")
        item.icon_path = _resolve_icon_path(d.get("icon_path", ""))
        item.command = d.get("command", "")
        item.enabled = d.get("enabled", True)
        item.show_in_pie = d.get("show_in_pie", True)
        item.is_separator = d.get("is_separator", False)


def _config_to_dict(prefs):
    return {
        "version": list(bl_info["version"]),
        "top_margin": prefs.top_margin,
        "left_margin_pct": prefs.left_margin_pct,
        "label_font_size": prefs.label_font_size,
        "shelf_scale": prefs.shelf_scale,
        "icon_opacity": prefs.icon_opacity,
        "label_color": list(prefs.label_color),
        "btn_color": list(prefs.btn_color),
        "bg_color": list(prefs.bg_color),
        "separator_color": list(prefs.separator_color),
        "show_label": prefs.show_label,
        "show_number": prefs.show_number,
        "show_export_button": prefs.show_export_button,
        "label_placement": prefs.label_placement,
        "orientation": prefs.orientation,
        "display_mode": prefs.display_mode,
        "pie_mode": prefs.pie_mode,
        "pie_context_sculpt": prefs.pie_context_sculpt,
        "pie_context_uv": prefs.pie_context_uv,
        "pie_context_node_shader": prefs.pie_context_node_shader,
        "pie_context_node_geo": prefs.pie_context_node_geo,
        "buttons": _serialize_items(prefs.buttons),
        "pie_buttons_object": _serialize_items(prefs.pie_buttons_object),
        "pie_buttons_edit": _serialize_items(prefs.pie_buttons_edit),
        "pie_buttons_sculpt": _serialize_items(prefs.pie_buttons_sculpt),
        "pie_buttons_uv": _serialize_items(prefs.pie_buttons_uv),
        "pie_buttons_node_shader": _serialize_items(prefs.pie_buttons_node_shader),
        "pie_buttons_node_geo": _serialize_items(prefs.pie_buttons_node_geo),
    }


def _save_config_to_path(prefs, path):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_config_to_dict(prefs), f, indent=2)
        return True
    except OSError:
        return False


def _save_config():
    # Blender's AddonPreferences only round-trips through userpref.blend on
    # a full Blender restart -- disabling the addon and re-enabling it
    # within the same session drops it back to class defaults. So the addon
    # keeps its own on-disk copy, independent of Blender's addon lifecycle,
    # and that copy is what register() actually trusts. Deleting the addon
    # folder (e.g. to reinstall from a fresh zip) takes this file down with
    # it -- Export/Import Settings in Preferences saves the same shape to a
    # path of the user's choosing, for backup/sharing/moving to another PC.
    prefs = get_prefs()
    if prefs is None:
        return
    _save_config_to_path(prefs, CONFIG_FILE)


def _migrate_config(data, saved_version):
    # Hook for upgrading old on-disk config shapes, mirroring Pie Menu
    # Editor's version-gated fix_X_Y_Z chain. No format changes have shipped
    # since the version numbering was reset to a pre-release 0.x scheme, so
    # this is a no-op again -- add a migration step here (keyed on
    # saved_version) whenever a future release changes a field's shape.
    return data


def _load_config_from_path(prefs, path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return False
    saved_version = tuple(data.get("version", (0, 0, 0)))
    if saved_version < bl_info["version"]:
        data = _migrate_config(data, saved_version)
    prefs.top_margin = data.get("top_margin", DEFAULT_TOP_MARGIN)
    prefs.left_margin_pct = data.get("left_margin_pct", DEFAULT_LEFT_MARGIN_PCT)
    prefs.label_font_size = data.get("label_font_size", 7)
    prefs.shelf_scale = data.get("shelf_scale", 1.0)
    prefs.icon_opacity = data.get("icon_opacity", 1.0)
    prefs.label_color = data.get("label_color", [1.0, 1.0, 1.0, 0.9])
    prefs.btn_color = data.get("btn_color", [0.32, 0.32, 0.32, 1.0])
    prefs.bg_color = data.get("bg_color", [0.10, 0.10, 0.10, 0.9])
    prefs.separator_color = data.get("separator_color", [1.0, 1.0, 1.0, 0.4])
    prefs.show_label = data.get("show_label", True)
    prefs.show_number = data.get("show_number", True)
    prefs.show_export_button = data.get("show_export_button", True)
    prefs.label_placement = data.get("label_placement", 'INSIDE')
    prefs.orientation = data.get("orientation", 'HORIZONTAL')
    prefs.display_mode = data.get("display_mode", 'BOTH')
    prefs.pie_mode = data.get("pie_mode", 'MIRROR')
    prefs.pie_context_sculpt = data.get("pie_context_sculpt", False)
    prefs.pie_context_uv = data.get("pie_context_uv", False)
    prefs.pie_context_node_shader = data.get("pie_context_node_shader", False)
    prefs.pie_context_node_geo = data.get("pie_context_node_geo", False)
    _deserialize_items(prefs.buttons, data.get("buttons", []))
    _deserialize_items(prefs.pie_buttons_object, data.get("pie_buttons_object", []))
    _deserialize_items(prefs.pie_buttons_edit, data.get("pie_buttons_edit", []))
    _deserialize_items(prefs.pie_buttons_sculpt, data.get("pie_buttons_sculpt", []))
    _deserialize_items(prefs.pie_buttons_uv, data.get("pie_buttons_uv", []))
    _deserialize_items(prefs.pie_buttons_node_shader, data.get("pie_buttons_node_shader", []))
    _deserialize_items(prefs.pie_buttons_node_geo, data.get("pie_buttons_node_geo", []))
    return True


def _load_config(prefs):
    return _load_config_from_path(prefs, CONFIG_FILE)


def _on_prefs_changed():
    # update= callback for widgets edited directly in the Preferences UI
    # (typing in a field, dragging a slider) -- operator-driven changes call
    # _save_prefs() instead, which also does the heavier wm.save_userpref().
    _tag_viewports_redraw()
    _save_config()


def _save_prefs():
    # Property changes made by an operator (as opposed to a plain UI widget
    # edit inside the Preferences editor) don't trigger Blender's
    # auto-save-preferences, so every operator that mutates BlenderShelf's
    # AddonPreferences must save explicitly or the change is lost on restart.
    try:
        bpy.ops.wm.save_userpref()
    except Exception:
        pass
    _save_config()


def _position(region):
    if _drag_live_margins is not None:
        return _drag_live_margins
    prefs = get_prefs()
    if prefs is None:
        return DEFAULT_TOP_MARGIN, DEFAULT_LEFT_MARGIN_PCT * region.width
    return prefs.top_margin, prefs.left_margin_pct * region.width


def _enabled_items():
    prefs = get_prefs()
    if prefs is None:
        return []
    return [b for b in prefs.buttons if b.enabled]


def _visible_real_indices(coll):
    """_enabled_items() is filtered; this maps each visible slot's position
    (0..N-1, same order as _enabled_items()/shelf_geometry()'s rects) back to
    its real index in the full prefs.buttons collection."""
    return [i for i, b in enumerate(coll) if b.enabled]


def _gap_under_mouse(rects, mx, my, vertical):
    """Which of the N+1 gaps between visible slots the cursor is nearest to,
    as an insertion index (0 = before the first slot, N = after the last).
    rects is already in visual reading order for both orientations (left-to-
    right horizontal, top-to-bottom vertical -- see shelf_geometry())."""
    if vertical:
        return sum(1 for (x0, y0, x1, y1) in rects if (y0 + y1) / 2.0 > my)
    return sum(1 for (x0, y0, x1, y1) in rects if (x0 + x1) / 2.0 < mx)


def _gap_target_real_index(real_indices, gap, coll_len):
    if not real_indices:
        return 0
    if gap >= len(real_indices):
        return min(real_indices[-1] + 1, coll_len - 1)
    return real_indices[gap]


def _seed_default_buttons(prefs):
    if len(prefs.buttons):
        return
    for d in DEFAULT_BUTTONS:
        item = prefs.buttons.add()
        item.label = d["label"]
        item.icon_path = d["icon"]
        item.command = d["command"]
        item.enabled = True


class BLENDERSHELF_OT_pref_add(bpy.types.Operator):
    """Add a new, empty button to the given list"""
    bl_idname = "blender_shelf.pref_add_button"
    bl_label = "Add Button"
    target: bpy.props.EnumProperty(items=_TARGET_ITEMS, default='SHELF')

    def execute(self, context):
        prefs = get_prefs()
        coll, idx_attr = _target_collection(prefs, self.target)
        item = coll.add()
        item.label = "New"
        item.icon_path = os.path.join(BLENDER_ICON_DIR, "MESH_MONKEY.png")
        setattr(prefs, idx_attr, len(coll) - 1)
        _save_prefs()
        return {'FINISHED'}


class BLENDERSHELF_OT_pref_remove(bpy.types.Operator):
    """Remove the selected button from the given list"""
    bl_idname = "blender_shelf.pref_remove_button"
    bl_label = "Remove Button"
    target: bpy.props.EnumProperty(items=_TARGET_ITEMS, default='SHELF')

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        prefs = get_prefs()
        coll, idx_attr = _target_collection(prefs, self.target)
        idx = getattr(prefs, idx_attr)
        if coll:
            coll.remove(idx)
            setattr(prefs, idx_attr, max(0, idx - 1))
            _save_prefs()
        return {'FINISHED'}


class BLENDERSHELF_OT_pref_move(bpy.types.Operator):
    """Reorder the selected button within the given list"""
    bl_idname = "blender_shelf.pref_move_button"
    bl_label = "Move Button"
    direction: bpy.props.EnumProperty(items=(('UP', "Up", ""), ('DOWN', "Down", "")))
    target: bpy.props.EnumProperty(items=_TARGET_ITEMS, default='SHELF')

    def execute(self, context):
        prefs = get_prefs()
        coll, idx_attr = _target_collection(prefs, self.target)
        idx = getattr(prefs, idx_attr)
        new_idx = idx - 1 if self.direction == 'UP' else idx + 1
        if 0 <= new_idx < len(coll):
            coll.move(idx, new_idx)
            setattr(prefs, idx_attr, new_idx)
            _save_prefs()
        return {'FINISHED'}


class BLENDERSHELF_OT_start_move_button(bpy.types.Operator):
    """Enter shelf-button move mode: the button follows the cursor until the
    next click, which drops it into whichever gap the cursor is over"""
    bl_idname = "blender_shelf.start_move_button"
    bl_label = "Move"
    target: bpy.props.EnumProperty(items=_TARGET_ITEMS, default='SHELF')

    def execute(self, context):
        global _moving_index, _move_insert_gap
        prefs = get_prefs()
        coll, idx_attr = _target_collection(prefs, self.target)
        _moving_index = getattr(prefs, idx_attr)
        _move_insert_gap = None
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}


class BLENDERSHELF_OT_add_separator(bpy.types.Operator):
    """Add a visual separator, then drag it to where you want it -- same
    mechanic as Move, since it's really just a special item being placed"""
    bl_idname = "blender_shelf.add_separator"
    bl_label = "Add Separator"
    target: bpy.props.EnumProperty(items=_TARGET_ITEMS, default='SHELF')

    def execute(self, context):
        global _moving_index, _move_insert_gap
        prefs = get_prefs()
        coll, idx_attr = _target_collection(prefs, self.target)
        item = coll.add()
        item.label = "Separator"
        item.is_separator = True
        item.enabled = True
        _moving_index = len(coll) - 1
        _move_insert_gap = None
        _save_prefs()
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        return {'FINISHED'}


class BLENDERSHELF_MT_shelf_button_context(bpy.types.Menu):
    """Right-click menu for a single shelf button (viewport overlay, not the
    Preferences list). Relies on the caller having already pointed the
    shelf's active_index at the right-clicked button before popping this."""
    bl_idname = "BLENDERSHELF_MT_shelf_button_context"
    bl_label = "Shelf Button"

    def draw(self, context):
        layout = self.layout
        # Buttons drawn inside a popup menu run EXEC_DEFAULT by default --
        # without this, Delete's own invoke_confirm() is silently skipped
        # and it deletes immediately (confirmed live: this exact symptom).
        layout.operator_context = 'INVOKE_DEFAULT'
        layout.operator("blender_shelf.start_move_button", text="Move", icon='ARROW_LEFTRIGHT').target = 'SHELF'
        layout.operator("blender_shelf.add_separator", text="Add Separator", icon='REMOVE').target = 'SHELF'
        layout.separator()
        layout.operator("blender_shelf.pref_remove_button", text="Delete", icon='TRASH').target = 'SHELF'


_copy_destination_items_cache = []  # kept referenced -- Blender frees dynamic enum strings otherwise


def _copy_destination_items(self, context):
    prefs = get_prefs()
    keys = ['SHELF', 'PIE_OBJECT', 'PIE_EDIT']
    if prefs:
        if prefs.pie_context_sculpt:
            keys.append('PIE_SCULPT')
        if prefs.pie_context_uv:
            keys.append('PIE_UV')
        if prefs.pie_context_node_shader:
            keys.append('PIE_NODE_SHADER')
        if prefs.pie_context_node_geo:
            keys.append('PIE_NODE_GEO')
    global _copy_destination_items_cache
    _copy_destination_items_cache = [(k, _TARGET_LABELS[k], "") for k in keys if k != self.source]
    return _copy_destination_items_cache


class BLENDERSHELF_OT_copy_button(bpy.types.Operator):
    """Copy the selected button into another, currently-enabled list"""
    bl_idname = "blender_shelf.copy_button"
    bl_label = "Copy To..."
    bl_options = {'REGISTER'}

    source: bpy.props.EnumProperty(items=_TARGET_ITEMS, default='SHELF')
    destination: bpy.props.EnumProperty(items=_copy_destination_items, name="Copy To")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.column().prop(self, "destination", expand=True)

    def execute(self, context):
        prefs = get_prefs()
        src_coll, src_idx_attr = _target_collection(prefs, self.source)
        idx = getattr(prefs, src_idx_attr)
        if not (0 <= idx < len(src_coll)):
            self.report({'WARNING'}, "Nothing selected to copy")
            return {'CANCELLED'}
        item = src_coll[idx]
        dst_coll, _ = _target_collection(prefs, self.destination)
        new_item = dst_coll.add()
        new_item.label = item.label
        new_item.icon_path = item.icon_path
        new_item.command = item.command
        new_item.enabled = item.enabled
        new_item.show_in_pie = item.show_in_pie
        _save_prefs()
        self.report({'INFO'}, f"Copied '{item.label}' to {_TARGET_LABELS[self.destination]}")
        return {'FINISHED'}


def _button_script_name(target, index, label):
    # Name-based lookup in bpy.data.texts, not a PointerProperty on the
    # button item -- AddonPreferences (and PropertyGroups nested in it via
    # CollectionProperty) can't hold an ID-block pointer, since preferences
    # live in userpref.blend, outside any particular .blend's Main database;
    # registering one there silently breaks the whole `buttons` collection.
    return f"BlenderShelf Script {target} {index} - {label}"[:63]


class BLENDERSHELF_OT_edit_script(bpy.types.Operator):
    """Open the button's Command as multi-line text -- in an existing Text
    Editor area if one is visible, otherwise in a new floating window (the
    closest thing Blender has to a multi-line paste dialog; there is no
    multi-line string widget for popups, only the Text Editor space)"""
    bl_idname = "blender_shelf.edit_script"
    bl_label = "Edit as Script"
    target: bpy.props.EnumProperty(items=_TARGET_ITEMS, default='SHELF')

    def execute(self, context):
        prefs = get_prefs()
        coll, idx_attr = _target_collection(prefs, self.target)
        item = coll[getattr(prefs, idx_attr)]
        name = _button_script_name(self.target, getattr(prefs, idx_attr), item.label)
        txt = bpy.data.texts.get(name)
        if txt is None:
            txt = bpy.data.texts.new(name)
            txt.use_fake_user = True
            txt.write(item.command)
        for area in context.screen.areas:
            if area.type == 'TEXT_EDITOR':
                area.spaces.active.text = txt
                return {'FINISHED'}
        bpy.ops.wm.window_new()
        area = context.window_manager.windows[-1].screen.areas[0]
        area.type = 'TEXT_EDITOR'
        area.spaces.active.text = txt
        self.report({'INFO'}, "Edit the script, then click Apply from Script back in Preferences.")
        return {'FINISHED'}


class BLENDERSHELF_OT_apply_script(bpy.types.Operator):
    """Copy the linked Text block's content back into the button's Command"""
    bl_idname = "blender_shelf.apply_script"
    bl_label = "Apply from Script"
    target: bpy.props.EnumProperty(items=_TARGET_ITEMS, default='SHELF')

    def execute(self, context):
        prefs = get_prefs()
        coll, idx_attr = _target_collection(prefs, self.target)
        item = coll[getattr(prefs, idx_attr)]
        name = _button_script_name(self.target, getattr(prefs, idx_attr), item.label)
        txt = bpy.data.texts.get(name)
        if txt is None:
            self.report({'ERROR'}, "No script linked -- click Edit as Script first.")
            return {'CANCELLED'}
        item.command = txt.as_string()
        _save_prefs()
        self.report({'INFO'}, f"Command updated ({len(item.command)} chars)")
        return {'FINISHED'}


def _parse_command_call(command):
    """Split a captured `bpy.ops.x.y(k=v, ...)` command into (prefix, [(key,
    value_src), ...]), or None if it isn't that shape (multi-line script,
    positional args, **kwargs spread) -- those still need manual/script
    editing, this only covers the common single-call case."""
    try:
        call = ast.parse(command.strip(), mode='eval').body
    except SyntaxError:
        return None
    if not isinstance(call, ast.Call) or call.args or any(kw.arg is None for kw in call.keywords):
        return None
    prefix = ast.unparse(call.func)
    params = [(kw.arg, ast.unparse(kw.value)) for kw in call.keywords]
    return prefix, params


def _operator_rna_params(op_id):
    """List (name, default_value_src) for an operator's own user-facing
    properties, read from its live RNA. WM_operator_pystring only ever
    writes out properties that differ from their default, so a captured
    command with zero explicit kwargs (e.g. a bare "primitive_cube_add()")
    is completely normal -- without this, Edit Parameters would have
    nothing to show for the majority of buttons."""
    try:
        category, name = op_id.split(".")
        rna = getattr(getattr(bpy.ops, category), name).get_rna_type()
    except Exception:
        return []
    params = []
    for prop in rna.properties:
        if prop.is_hidden:
            continue
        if getattr(prop, 'is_array', False):
            default_src = repr(tuple(prop.default_array))
        else:
            default_src = repr(prop.default)
        params.append((prop.identifier, default_src))
    return params


class BLENDERSHELF_OT_edit_params(bpy.types.Operator):
    """Edit a captured command's keyword arguments as plain fields, e.g.
    tweak a primitive's radius/vertex count without touching Python. Stands
    in for Blender's own 'Adjust Last Operation' panel, which never appears
    for shelf/pie buttons since they run via exec(), not a native UI click --
    see FEEDBACK.md for why that panel can't be made to show up normally"""
    bl_idname = "blender_shelf.edit_params"
    bl_label = "Edit Parameters"
    bl_options = {'REGISTER'}

    target: bpy.props.EnumProperty(items=_TARGET_ITEMS, default='SHELF')
    prefix: bpy.props.StringProperty(options={'HIDDEN'})
    params: bpy.props.CollectionProperty(type=BLENDERSHELF_command_param)

    def invoke(self, context, event):
        prefs = get_prefs()
        coll, idx_attr = _target_collection(prefs, self.target)
        item = coll[getattr(prefs, idx_attr)]
        parsed = _parse_command_call(item.command)
        if parsed is None:
            self.report({'WARNING'}, "Not a single 'op(key=value, ...)' call -- edit it as text/script instead.")
            return {'CANCELLED'}
        self.prefix, explicit = parsed
        explicit_map = dict(explicit)

        # Prefer the operator's live RNA properties (with their real
        # defaults) over the bare captured kwargs, so there's something to
        # edit even when nothing was explicitly written to the command --
        # then fold in whatever WAS captured, and keep any leftover captured
        # kwarg that isn't a normal RNA property (custom/override-built
        # commands) so a round trip never silently drops it.
        rna_params = _operator_rna_params(self.prefix.removeprefix("bpy.ops."))
        rna_names = {name for name, _ in rna_params}
        all_params = rna_params + [kv for kv in explicit if kv[0] not in rna_names]
        if not all_params:
            self.report({'INFO'}, "This command takes no keyword arguments to edit.")
            return {'CANCELLED'}

        self.params.clear()
        for name, default_src in all_params:
            p = self.params.add()
            p.name = name
            p.value = explicit_map.get(name, default_src)
        return context.window_manager.invoke_props_dialog(self, width=350)

    def draw(self, context):
        layout = self.layout
        layout.label(text=self.prefix)
        for p in self.params:
            row = layout.row()
            row.label(text=p.name)
            row.prop(p, "value", text="")

    def execute(self, context):
        rebuilt = self.prefix + "(" + ", ".join(f"{p.name}={p.value}" for p in self.params) + ")"
        try:
            ast.parse(rebuilt, mode='eval')
        except SyntaxError as e:
            self.report({'ERROR'}, f"Invalid value, not saved: {e}")
            return {'CANCELLED'}
        prefs = get_prefs()
        coll, idx_attr = _target_collection(prefs, self.target)
        coll[getattr(prefs, idx_attr)].command = rebuilt
        _save_prefs()
        self.report({'INFO'}, "Parameters updated")
        return {'FINISHED'}


class BLENDERSHELF_OT_pref_preset_position(bpy.types.Operator):
    """Reset the shelf to its default top-center position"""
    bl_idname = "blender_shelf.pref_preset_position"
    bl_label = "Reset Position"

    def execute(self, context):
        region = _find_view3d_region()
        if region is None:
            self.report({'WARNING'}, "No 3D Viewport found")
            return {'CANCELLED'}
        prefs = get_prefs()
        items = _enabled_items()
        total_slots = _total_slots(items)
        # _panel_size() involves _btn_size()/_pad_size(), which are floats --
        # top_margin is an IntProperty (a bare float raises), left_margin_pct
        # is a fraction of region.width so it survives a resize/split.
        vertical = _is_vertical()
        panel_w, panel_h = _panel_size(total_slots, vertical)

        center_x = max(0.0, (region.width - panel_w) / 2.0)
        left_px = center_x if vertical else max(0.0, center_x - _aux_reserve())
        prefs.left_margin_pct = max(0.0, min(1.0, left_px / region.width)) if region.width else 0.0
        prefs.top_margin = PRESET_EDGE_MARGIN + _min_top_margin()

        _tag_viewports_redraw()
        _save_prefs()
        return {'FINISHED'}


class BLENDERSHELF_OT_reset_appearance(bpy.types.Operator):
    """Reset colors and icon opacity to their defaults -- size, margins and
    label placement are untouched"""
    bl_idname = "blender_shelf.reset_appearance"
    bl_label = "Reset Colors to Default"

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        prefs = get_prefs()
        if prefs is None:
            return {'CANCELLED'}
        for prop in ("label_color", "btn_color", "bg_color", "separator_color", "icon_opacity"):
            prefs.property_unset(prop)
        _tag_viewports_redraw()
        _save_prefs()
        return {'FINISHED'}


class BLENDERSHELF_OT_pick_icon(bpy.types.Operator):
    """Browse the addon's icons folder and assign the picked PNG to the selected button"""
    bl_idname = "blender_shelf.pick_icon"
    bl_label = "Browse Icons"

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default="*.png", options={'HIDDEN'})
    target: bpy.props.EnumProperty(items=_TARGET_ITEMS, default='SHELF')

    def invoke(self, context, event):
        self.filepath = os.path.join(ICON_DIR, "")
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        prefs = get_prefs()
        coll, idx_attr = _target_collection(prefs, self.target)
        idx = getattr(prefs, idx_attr)
        if not (0 <= idx < len(coll)):
            self.report({'WARNING'}, "Select a button first")
            return {'CANCELLED'}
        coll[idx].icon_path = self.filepath
        _save_prefs()
        return {'FINISHED'}


class BLENDERSHELF_OT_check_update(bpy.types.Operator):
    """Check the BlenderShelf website for a newer release"""
    bl_idname = "blender_shelf.check_update"
    bl_label = "Check for Updates"

    def execute(self, context):
        import urllib.request

        prefs = get_prefs()
        if prefs is None:
            self.report({'ERROR'}, "Preferences not found")
            return {'CANCELLED'}

        try:
            with urllib.request.urlopen(VERSIONS_JSON_URL, timeout=5) as resp:
                versions = json.loads(resp.read())
            latest = max(
                tuple(int(part) for part in v["addon_version"].split("."))
                for v in versions
            )
        except Exception as e:
            prefs.update_available = False
            prefs.update_status = f"Check failed: {e}"
            self.report({'WARNING'}, prefs.update_status)
            return {'CANCELLED'}

        current = bl_info["version"]
        if latest > current:
            prefs.update_available = True
            prefs.update_status = "Update available: " + ".".join(map(str, latest))
        else:
            prefs.update_available = False
            prefs.update_status = "You're up to date (" + ".".join(map(str, current)) + ")"
        self.report({'INFO'}, prefs.update_status)
        return {'FINISHED'}


class BLENDERSHELF_OT_export_settings(bpy.types.Operator):
    """Save all BlenderShelf settings (shelf, pie lists, appearance) to a JSON file -- for backup, sharing, or moving to another PC"""
    bl_idname = "blender_shelf.export_settings"
    bl_label = "Export Settings"

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default="*.json", options={'HIDDEN'})

    def invoke(self, context, event):
        self.filepath = "blendershelf_settings.json"
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        prefs = get_prefs()
        if prefs is None:
            self.report({'ERROR'}, "Preferences not found")
            return {'CANCELLED'}
        path = self.filepath if self.filepath.lower().endswith(".json") else self.filepath + ".json"
        if _save_config_to_path(prefs, path):
            self.report({'INFO'}, f"Exported to {path}")
            return {'FINISHED'}
        self.report({'ERROR'}, "Failed to write file")
        return {'CANCELLED'}


class BLENDERSHELF_OT_import_settings(bpy.types.Operator):
    """Load BlenderShelf settings from a previously exported JSON file, replacing the current shelf/pie setup"""
    bl_idname = "blender_shelf.import_settings"
    bl_label = "Import Settings"

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    filter_glob: bpy.props.StringProperty(default="*.json", options={'HIDDEN'})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        prefs = get_prefs()
        if prefs is None:
            self.report({'ERROR'}, "Preferences not found")
            return {'CANCELLED'}
        if not _load_config_from_path(prefs, self.filepath):
            self.report({'ERROR'}, "Failed to read/parse that file")
            return {'CANCELLED'}
        _save_prefs()
        _tag_viewports_redraw()
        self.report({'INFO'}, "Settings imported")
        return {'FINISHED'}


class BLENDERSHELF_OT_run_command(bpy.types.Operator):
    """Run a shelf button's command -- used by the pie menu"""
    bl_idname = "blender_shelf.run_command"
    bl_label = "Run Shelf Command"
    bl_options = {'REGISTER', 'UNDO'}

    command: bpy.props.StringProperty()
    label: bpy.props.StringProperty()

    def execute(self, context):
        if self.command:
            try:
                _exec_shelf_command(self.command)
            except Exception as e:
                self.report({'ERROR'}, f"'{self.label}' failed: {e}")
                return {'CANCELLED'}
        return {'FINISHED'}


_icon_previews = None  # bpy.utils.previews.ImagePreviewCollection, created in register()


def _get_pie_icon_id(path):
    if not path or _icon_previews is None:
        return 0
    entry = _icon_previews.get(path)
    if entry is not None:
        return entry.icon_id
    try:
        return _icon_previews.load(path, path, 'IMAGE').icon_id
    except Exception:
        return 0


_PIE_CLOCKWISE_ORDER = (3, 5, 1, 7, 2, 6, 0, 4)  # N, NE, E, SE, S, SW, W, NW


def _split_pie_target(context, prefs):
    # In Split pie mode, which target list a given invocation routes to.
    # Object/Edit are always on; Sculpt/UV Editor/Shader Editor/Geometry
    # Nodes only route to their own list once their Preferences checkbox is
    # enabled -- until then (or in any other context: Pose, Edit Curve,
    # plain Image Editor, Compositor, ...) this returns None and the caller
    # falls back to mirroring the shelf, same as Mirror mode. Shader Editor
    # and Geometry Nodes share one editor space (area.type == 'NODE_EDITOR')
    # but are otherwise-incompatible node systems, so they're split by
    # space_data.tree_type into two independent lists, not one.
    area = context.area
    if area and area.type == 'NODE_EDITOR':
        tree_type = getattr(context.space_data, "tree_type", "")
        if tree_type == 'ShaderNodeTree' and prefs.pie_context_node_shader:
            return 'PIE_NODE_SHADER'
        if tree_type == 'GeometryNodeTree' and prefs.pie_context_node_geo:
            return 'PIE_NODE_GEO'
    if area and area.type == 'IMAGE_EDITOR' and area.ui_type == 'UV' and prefs.pie_context_uv:
        return 'PIE_UV'
    if context.mode == 'SCULPT' and prefs.pie_context_sculpt:
        return 'PIE_SCULPT'
    if context.mode == 'OBJECT':
        return 'PIE_OBJECT'
    if context.mode == 'EDIT_MESH':
        return 'PIE_EDIT'
    return None


def _draw_pie_slots(pie, items):
    # menu_pie() always fills slots in this fixed compass order:
    # W, E, S, N, NW, NE, SW, SE. Remap so item 1 lands at the top and the
    # rest follow clockwise -- close to a reading order instead of
    # Blender's raw W/E/S/N sequence -- and spell out the number too, since
    # the compass layout alone still won't match a left-to-right (or
    # vertical) list exactly.
    slots = [None] * 8
    for pos, (idx, item) in enumerate(items[:8]):
        slots[_PIE_CLOCKWISE_ORDER[pos]] = (idx, item)
    for slot in slots:
        if slot is None:
            pie.separator()
            continue
        idx, item = slot
        text = f"{idx + 1}. {item.label}"
        icon_id = _get_pie_icon_id(item.icon_path)
        if icon_id:
            op = pie.operator("blender_shelf.run_command", text=text, icon_value=icon_id)
        else:
            op = pie.operator("blender_shelf.run_command", text=text)
        op.command = item.command
        op.label = item.label


class BLENDERSHELF_MT_pie(bpy.types.Menu):
    bl_idname = "BLENDERSHELF_MT_pie"
    bl_label = "BlenderShelfPie"

    def draw(self, context):
        pie = self.layout.menu_pie()
        prefs = get_prefs()
        items = None
        if prefs and prefs.pie_mode == 'SPLIT':
            target = _split_pie_target(context, prefs)
            if target is not None:
                coll, _ = _target_collection(prefs, target)
                items = [(i, b) for i, b in enumerate(coll) if b.enabled]
                if not items:
                    pie.label(text="Not configured yet", icon='INFO')
                    return
        if items is None:
            # Mirror mode, or Split mode in a context with no dedicated
            # list (Sculpt, Pose, Edit Curve, ...): mirror the shelf, same
            # as before this pie ever had categories. Keep each item's
            # real shelf index (1-based label) even after filtering out
            # show_in_pie=False ones, so the number shown here still
            # matches its number on the shelf, not its position in this
            # (possibly sparser) pie list.
            items = [(i, b) for i, b in enumerate(_enabled_items()) if b.show_in_pie]
        _draw_pie_slots(pie, items)


class BLENDERSHELF_UL_buttons(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        row = layout.row(align=True)
        row.prop(item, "enabled", text="")
        if item.is_separator:
            row.label(text=f"──── {item.label or 'Separator'} ────")
            return
        row.prop(item, "label", text="", emboss=False)


class BlenderShelfPreferences(bpy.types.AddonPreferences):
    bl_idname = __name__

    buttons: bpy.props.CollectionProperty(type=BLENDERSHELF_button_item)
    active_index: bpy.props.IntProperty(default=0)
    pie_buttons_object: bpy.props.CollectionProperty(type=BLENDERSHELF_button_item)
    pie_active_index_object: bpy.props.IntProperty(default=0)
    pie_buttons_edit: bpy.props.CollectionProperty(type=BLENDERSHELF_button_item)
    pie_active_index_edit: bpy.props.IntProperty(default=0)
    pie_buttons_sculpt: bpy.props.CollectionProperty(type=BLENDERSHELF_button_item)
    pie_active_index_sculpt: bpy.props.IntProperty(default=0)
    pie_buttons_uv: bpy.props.CollectionProperty(type=BLENDERSHELF_button_item)
    pie_active_index_uv: bpy.props.IntProperty(default=0)
    pie_buttons_node_shader: bpy.props.CollectionProperty(type=BLENDERSHELF_button_item)
    pie_active_index_node_shader: bpy.props.IntProperty(default=0)
    pie_buttons_node_geo: bpy.props.CollectionProperty(type=BLENDERSHELF_button_item)
    pie_active_index_node_geo: bpy.props.IntProperty(default=0)
    pie_context_sculpt: bpy.props.BoolProperty(name="Sculpt Mode", default=False,
                                                update=lambda self, context: _on_prefs_changed())
    pie_context_uv: bpy.props.BoolProperty(name="UV Editor", default=False,
                                            update=lambda self, context: _on_prefs_changed())
    pie_context_node_shader: bpy.props.BoolProperty(name="Shader Editor", default=False,
                                                      update=lambda self, context: _on_prefs_changed())
    pie_context_node_geo: bpy.props.BoolProperty(name="Geometry Nodes", default=False,
                                                  update=lambda self, context: _on_prefs_changed())
    pie_mode: bpy.props.EnumProperty(
        name="Pie Menu Mode",
        items=(('MIRROR', "Shelf = Pie", "The pie menu always duplicates the shelf buttons"),
               ('SPLIT', "Split by Context", "Build independent pie menus for Object Mode and Edit Mode; "
                                              "the shelf itself is unaffected")),
        default='MIRROR',
        update=lambda self, context: _on_prefs_changed())
    top_margin: bpy.props.IntProperty(name="Top Margin", default=DEFAULT_TOP_MARGIN, min=0,
                                       update=lambda self, context: _on_prefs_changed())
    left_margin_pct: bpy.props.FloatProperty(
        name="Left Margin", default=DEFAULT_LEFT_MARGIN_PCT, min=0.0, max=1.0, subtype='FACTOR',
        description="Distance from the viewport's left edge, as a fraction of its width -- "
                    "stays in the same relative spot when the viewport is resized or split",
        update=lambda self, context: _on_prefs_changed())
    label_font_size: bpy.props.IntProperty(name="Label Font Size", default=8, min=5, max=16,
                                            update=lambda self, context: _on_prefs_changed())
    shelf_scale: bpy.props.FloatProperty(name="Shelf Size", default=1.0, min=0.5, max=3.0, subtype='FACTOR',
                                          update=lambda self, context: _on_prefs_changed())
    icon_opacity: bpy.props.FloatProperty(name="Icon Opacity", default=1.0, min=0.0, max=1.0, subtype='FACTOR',
                                           update=lambda self, context: _on_prefs_changed())
    label_color: bpy.props.FloatVectorProperty(
        name="Label Color", subtype='COLOR', size=4,
        default=(0.8713645935058594, 0.672469973564148, 0.11010005325078964, 0.8999999761581421),
        min=0.0, max=1.0, update=lambda self, context: _on_prefs_changed())
    btn_color: bpy.props.FloatVectorProperty(
        name="Button Color", subtype='COLOR', size=4,
        default=(0.0, 0.0, 0.0, 0.6457144021987915),
        min=0.0, max=1.0, update=lambda self, context: _on_prefs_changed())
    bg_color: bpy.props.FloatVectorProperty(
        name="Background Color", subtype='COLOR', size=4,
        default=(0.32777780294418335, 0.32777780294418335, 0.32777780294418335, 0.5685714483261108),
        min=0.0, max=1.0, update=lambda self, context: _on_prefs_changed())
    separator_color: bpy.props.FloatVectorProperty(
        name="Separator Color", subtype='COLOR', size=4,
        default=(1.0, 1.0, 1.0, 0.4),
        min=0.0, max=1.0, update=lambda self, context: _on_prefs_changed())
    show_label: bpy.props.BoolProperty(name="Show Label", default=True,
                                        update=lambda self, context: _on_prefs_changed())
    show_number: bpy.props.BoolProperty(name="Show Number", default=False,
                                         update=lambda self, context: _on_prefs_changed())
    show_export_button: bpy.props.BoolProperty(name="Show FBX Export Button", default=False,
                                                update=lambda self, context: _on_prefs_changed())
    label_placement: bpy.props.EnumProperty(
        name="Label Placement",
        items=(('ABOVE', "Above", "Label drawn above the button"),
               ('LEFT', "Left", "Label drawn to the left of the button"),
               ('INSIDE', "Inside", "Label drawn inside the button, at the bottom"),
               ('RIGHT', "Right", "Label drawn to the right of the button"),
               ('BELOW', "Below", "Label drawn below the button")),
        default='INSIDE',
        update=lambda self, context: _on_prefs_changed())
    orientation: bpy.props.EnumProperty(
        name="Orientation",
        items=(('HORIZONTAL', "Horizontal", ""), ('VERTICAL', "Vertical", "")),
        default='HORIZONTAL',
        update=lambda self, context: _on_prefs_changed())
    display_mode: bpy.props.EnumProperty(
        name="Display Mode",
        items=(('SHELF', "Shelf Only", "Always show the floating shelf overlay"),
               ('PIE', "Pie Menu Only", "Hide the shelf; open a pie menu with the hotkey instead "
                                        "(falls back to the shelf if no hotkey is assigned)"),
               ('BOTH', "Shelf + Pie Menu", "Show the shelf, and also allow opening the pie menu with the hotkey")),
        default='BOTH',
        update=lambda self, context: _on_prefs_changed())
    # UI navigation only -- which Preferences tab is showing. Not saved to
    # shelf_config.json (it's not addon behavior, just where the panel is
    # scrolled to), so no update= callback and no _save_config()/.get() entry.
    prefs_tab: bpy.props.EnumProperty(
        items=(('SHELF', "Shelf", ""), ('PIE', "Pie Menu", "")),
        default='SHELF')
    # Session-only, never persisted to shelf_config.json -- result of the last
    # "Check for Updates" click, cleared on Blender restart.
    update_status: bpy.props.StringProperty(default="")
    update_available: bpy.props.BoolProperty(default=False)

    def draw(self, context):
        layout = self.layout

        # Boxed + labeled so it reads as a separate group from the Shelf/Pie
        # Menu tabs below, instead of blending into the same visual block.
        general_box = layout.box()
        general_box.label(text="Backup & Updates")
        row = general_box.row(align=True)
        row.operator("blender_shelf.export_settings", icon='EXPORT')
        row.operator("blender_shelf.import_settings", icon='IMPORT')

        row = general_box.row(align=True)
        row.operator("blender_shelf.check_update", icon='FILE_REFRESH')
        if self.update_status:
            row.label(text=self.update_status)
        if self.update_available:
            general_box.operator("wm.url_open", text="Open BlenderShelf website", icon='URL').url = DOWNLOAD_PAGE_URL

        layout.separator()

        # Two top-level sections, each self-contained: everything about the
        # floating shelf (appearance/position + its button list), and
        # everything about the pie menu (hotkey + mode + its button lists).
        # Shown as tab pages (Zen UV-style prop(expand=True) row) rather than
        # stacked collapsible panels, so only one section is visible at once.
        layout.row().prop(self, "prefs_tab", expand=True)

        if self.prefs_tab == 'SHELF':
            header, panel = layout.panel("blendershelf_appearance", default_closed=True)
            header.label(text="Appearance & Position")
            if panel:
                panel.row().operator("blender_shelf.pref_preset_position")
                row = panel.row()
                row.prop(self, "top_margin")
                row.prop(self, "left_margin_pct", slider=True)
                panel.row().prop(self, "shelf_scale", slider=True)
                panel.row().prop(self, "icon_opacity", slider=True)

                label_box = panel.box()
                label_box.label(text="Label")
                row = label_box.row()
                row.prop(self, "show_label")
                row.prop(self, "label_font_size")
                label_box.row().prop(self, "label_placement", expand=True)

                row = panel.row()
                row.prop(self, "label_color")
                row.prop(self, "btn_color")
                row.prop(self, "bg_color")
                row.prop(self, "separator_color")
                panel.row().operator("blender_shelf.reset_appearance", icon='LOOP_BACK')

                row = panel.row()
                row.prop(self, "show_number")
                row.prop(self, "show_export_button")
                panel.row().prop(self, "orientation", expand=True)

            layout.label(text="Shelf buttons -- order determines button 1..N in the viewport:")
            _draw_button_list(layout, self, 'SHELF', show_pie_flag=True)

        elif self.prefs_tab == 'PIE':
            layout.prop(self, "display_mode")
            if self.display_mode == 'PIE':
                layout.label(text="(falls back to the shelf if no key is assigned below)", icon='INFO')
            box = layout.box()
            box.label(text="Pie Menu Hotkey (3D Viewport):")
            _draw_pie_hotkey(box, context, '3D View')

            layout.row().prop(self, "pie_mode", expand=True)
            if self.pie_mode == 'SPLIT':
                layout.label(text="Object Mode Pie:")
                _draw_button_list(layout, self, 'PIE_OBJECT')
                layout.label(text="Edit Mode Pie:")
                _draw_button_list(layout, self, 'PIE_EDIT')

                extra_box = layout.box()
                extra_box.label(text="Optional Contexts:")

                def draw_sculpt():
                    extra_box.prop(self, "pie_context_sculpt")
                    if self.pie_context_sculpt:
                        extra_box.label(text="Sculpt Mode Pie (uses the 3D Viewport hotkey above):")
                        _draw_button_list(extra_box, self, 'PIE_SCULPT')

                def draw_uv():
                    extra_box.prop(self, "pie_context_uv")
                    if self.pie_context_uv:
                        uv_box = extra_box.box()
                        uv_box.label(text="UV Editor Hotkey:")
                        _draw_pie_hotkey(uv_box, context, 'Image')
                        extra_box.label(text="UV Editor Pie:")
                        _draw_button_list(extra_box, self, 'PIE_UV')

                def draw_node_shader():
                    extra_box.prop(self, "pie_context_node_shader")
                    if self.pie_context_node_shader:
                        node_box = extra_box.box()
                        node_box.label(text="Node Editor Hotkey (shared with Geometry Nodes):")
                        _draw_pie_hotkey(node_box, context, 'Node Editor')
                        extra_box.label(text="Shader Editor Pie:")
                        _draw_button_list(extra_box, self, 'PIE_NODE_SHADER')

                def draw_node_geo():
                    extra_box.prop(self, "pie_context_node_geo")
                    if self.pie_context_node_geo:
                        node_box = extra_box.box()
                        node_box.label(text="Node Editor Hotkey (shared with Shader Editor):")
                        _draw_pie_hotkey(node_box, context, 'Node Editor')
                        extra_box.label(text="Geometry Nodes Pie:")
                        _draw_button_list(extra_box, self, 'PIE_NODE_GEO')

                # Enabled contexts float to the top, disabled ones sink to
                # the bottom -- sorted() is stable, so within each of those
                # two groups the original Sculpt/UV/Shader/Geo order holds.
                blocks = [
                    (self.pie_context_sculpt, draw_sculpt),
                    (self.pie_context_uv, draw_uv),
                    (self.pie_context_node_shader, draw_node_shader),
                    (self.pie_context_node_geo, draw_node_geo),
                ]
                for _, draw_block in sorted(blocks, key=lambda b: not b[0]):
                    draw_block()


def _draw_pie_hotkey(layout, context, keymap_name):
    wm = context.window_manager
    kc = wm.keyconfigs.user
    km = kc.keymaps.get(keymap_name) if kc else None
    found_kmi = None
    if km:
        for kmi in km.keymap_items:
            if kmi.idname == 'wm.call_menu_pie' and kmi.properties.name == BLENDERSHELF_MT_pie.bl_idname:
                found_kmi = kmi
                break
    if found_kmi:
        layout.context_pointer_set('keymap', km)
        rna_keymap_ui.draw_kmi([], kc, km, found_kmi, layout, 0)
    else:
        layout.label(text="Keymap not found -- try disabling/re-enabling the addon.")


def _draw_button_list(layout, prefs, target, show_pie_flag=False):
    coll_name, idx_name = _PIE_TARGETS[target]
    coll = getattr(prefs, coll_name)
    idx = getattr(prefs, idx_name)

    row = layout.row()
    row.template_list("BLENDERSHELF_UL_buttons", target, prefs, coll_name, prefs, idx_name, rows=4)
    col = row.column(align=True)
    col.operator("blender_shelf.pref_add_button", icon='ADD', text="").target = target
    col.operator("blender_shelf.pref_remove_button", icon='REMOVE', text="").target = target
    col.separator()
    op = col.operator("blender_shelf.pref_move_button", icon='TRIA_UP', text="")
    op.target, op.direction = target, 'UP'
    op = col.operator("blender_shelf.pref_move_button", icon='TRIA_DOWN', text="")
    op.target, op.direction = target, 'DOWN'

    if 0 <= idx < len(coll):
        item = coll[idx]
        box = layout.box()
        if item.is_separator:
            box.prop(item, "label", text="Separator Label")
            return
        if show_pie_flag:
            box.prop(item, "show_in_pie")
        box.prop(item, "label")
        row = box.row(align=True)
        row.prop(item, "icon_path")
        row.operator("blender_shelf.pick_icon", text="", icon='FILE_FOLDER').target = target
        box.prop(item, "command")
        box.operator("blender_shelf.edit_params", icon='PROPERTIES').target = target
        row = box.row(align=True)
        row.operator("blender_shelf.edit_script", icon='TEXT').target = target
        row.operator("blender_shelf.apply_script", icon='FILE_REFRESH').target = target
        # Copy To only makes sense with independent per-context pie lists --
        # in Mirror mode the pie always duplicates the shelf, so there's
        # nothing separate to copy into.
        if prefs.pie_mode == 'SPLIT':
            box.operator("blender_shelf.copy_button", icon='DUPLICATE', text="Copy To...").source = target


# ---------------------------------------------------------------------------
# "Add to Shelf" on any Blender button's right-click context menu
# (technique borrowed from the SwiftPie addon: context.button_operator +
# the built-in "Copy Python Command" operator for a faithful repro command)
# ---------------------------------------------------------------------------

# A handful of Blender operators are one class shared across many distinct
# actions, picked by a property instead of by operator id (unlike e.g.
# mesh.primitive_cube_add, which is its own class) -- op.bl_rna.name is just
# the generic class label ("Add Node") for all of them, and the normal
# copy_python_command_button() capture below was observed (live, via the
# Blender MCP) to silently drop the button's properties for these too,
# falling back to a bare "bpy.ops.node.add_node()" that adds nothing when
# run. Each entry here builds both the real label AND the real command
# directly from the button's already-configured operator properties instead
# of trusting either the generic class label or the clipboard capture.
#
# WHY this happens (so new cases can be predicted, not just discovered by a
# bug report): Blender's WM_operator_pystring (the C code behind
# copy_python_command_button()) skips any property flagged SKIP_SAVE when
# building the repro string -- SKIP_SAVE exists so a one-off value doesn't
# get remembered as the operator's "last used" setting for its next call,
# but the exact property that differentiates one menu entry from another
# of the same shared operator class (clear=True/False, type='X', name='Y')
# is often flagged SKIP_SAVE for that very reason. Net effect: the property
# that matters most for a faithful repro is the one most likely to be
# silently dropped.
#
# How to recognize a new instance of this bug class BEFORE it's reported:
#   1. Multiple distinct menu entries calling the SAME op_id (not separate
#      classes) with only a property differing -- e.g. Blender's Merge menu
#      is all bpy.ops.mesh.merge(type=...), not separate operators per entry.
#   2. Confirm live (Python console or Blender MCP):
#      bpy.types.<CLASS>.bl_rna.properties['<prop>'].is_skip_save
#      True -> pre-emptively add an override below, don't wait for a report.
#   3. How to recognize it FROM a report, without re-deriving this each time:
#      the tell is "every variant I add ends up behaving like the same one"
#      (e.g. Clear Sharp saved but runs as Mark Sharp) -- that symptom alone
#      is this bug class; go straight to adding an override, no need to
#      re-diagnose copy_python_command_button() from scratch.
#   4. Override template: label_fn reads the differentiating property via
#      getattr(op, "<prop>", <default>) and derives a human label from it;
#      command_fn rebuilds the full bpy.ops.<id>(...) call from the same
#      properties, never from the clipboard capture.
def _add_node_label(op):
    node_type = getattr(op, "type", "")
    node_cls = getattr(bpy.types, node_type, None)
    return node_cls.bl_rna.name if node_cls else node_type


def _add_node_command(op):
    node_type = getattr(op, "type", "")
    use_transform = getattr(op, "use_transform", True)
    return f'bpy.ops.node.add_node(type={node_type!r}, use_transform={use_transform})'


def _add_group_label(op):
    return getattr(op, "name", "") or "Add Group"


def _add_group_command(op):
    return f'bpy.ops.node.add_group(name={getattr(op, "name", "")!r})'


def _activate_brush_label(op):
    # relative_asset_identifier is "<blend-file-relative-path>/Brush/<name>"
    # (Blender's own asset-identifier convention) -- the last path segment
    # is the brush's real, human-readable name. On Windows this comes
    # through with backslashes, not forward slashes (confirmed live -- a
    # plain rsplit("/") left the whole path un-split there), so normalize
    # both separators before taking the last segment.
    ident = getattr(op, "relative_asset_identifier", "") or ""
    return ident.replace("\\", "/").rsplit("/", 1)[-1] or "Activate Brush Asset"


def _activate_brush_command(op):
    # relative_asset_identifier is a filesystem path (backslashes on
    # Windows) -- embed it via repr(), not a manual f-string quote, or a
    # path segment that happens to look like an escape (\n, \t, ...) would
    # corrupt the generated command when it's exec()'d back.
    lib_type = getattr(op, "asset_library_type", "ESSENTIALS")
    lib_id = getattr(op, "asset_library_identifier", "")
    rel_id = getattr(op, "relative_asset_identifier", "")
    return (f'bpy.ops.brush.asset_activate(asset_library_type={lib_type!r}, '
            f'asset_library_identifier={lib_id!r}, relative_asset_identifier={rel_id!r})')


def _activate_brush_icon(op):
    # Per-brush preview baking was tried and dropped -- Blender's brush
    # previews are procedurally rendered, not backed by any real file on
    # disk, and only reliably populated for whichever brush happens to
    # already be visible/active, so it can't be resolved as a simple path.
    # A fixed, real "brush" icon from the addon's own curated pack (pulled
    # from the same nikogoli/Blender_UI_icons_png set the rest of the pack
    # already uses) is simpler and always available.
    return os.path.join(BLENDER_ICON_DIR, "BRUSH_DATA.png")


def _mark_sharp_label(op):
    # The Edge menu has 4 distinct entries on this one operator id, not 2 --
    # "Mark/Clear Sharp" (edges) and "Mark/Clear Sharp from Vertices"
    # (use_verts=True). The original override only read `clear`, so the
    # vertex variants silently collapsed onto the edge ones (same bug class
    # as Set/Select by Face Strength -- confirmed by reading Blender's own
    # menu source, space_view3d.py, not guessed). use_verts is SKIP_SAVE too.
    clear = getattr(op, "clear", False)
    use_verts = getattr(op, "use_verts", False)
    if use_verts:
        return "Clear Sharp from Vertices" if clear else "Mark Sharp from Vertices"
    return "Clear Sharp" if clear else "Mark Sharp"


def _mark_sharp_command(op):
    clear = getattr(op, "clear", False)
    use_verts = getattr(op, "use_verts", False)
    return f'bpy.ops.mesh.mark_sharp(clear={clear}, use_verts={use_verts})'


def _mark_seam_label(op):
    return "Clear Seam" if getattr(op, "clear", False) else "Mark Seam"


def _mark_seam_command(op):
    return f'bpy.ops.mesh.mark_seam(clear={getattr(op, "clear", False)})'


def _merge_label(op):
    merge_type = getattr(op, "type", "CENTER")
    try:
        return op.bl_rna.properties["type"].enum_items[merge_type].name
    except (KeyError, AttributeError):
        return f"Merge ({merge_type})"


def _merge_command(op):
    merge_type = getattr(op, "type", "CENTER")
    uvs = getattr(op, "uvs", False)
    return f'bpy.ops.mesh.merge(type={merge_type!r}, uvs={uvs})'


def _modifier_add_label(op):
    mod_type = getattr(op, "type", "")
    try:
        return op.bl_rna.properties["type"].enum_items[mod_type].name
    except (KeyError, AttributeError):
        return mod_type or "Add Modifier"


def _modifier_add_command(op):
    mod_type = getattr(op, "type", "SUBSURF")
    use_selected = getattr(op, "use_selected_objects", False)
    return f'bpy.ops.object.modifier_add(type={mod_type!r}, use_selected_objects={use_selected})'


def _bevel_label(op):
    return "Bevel Vertices" if getattr(op, "affect", "EDGES") == 'VERTICES' else "Bevel Edges"


def _bevel_command(op):
    # "Bevel Vertices"/"Bevel Edges" (space_view3d.py) both explicitly set
    # `affect` on the button -- same "one op id, several menu presets" shape
    # as mark_sharp/mod_weighted_strength/select_all above. User-reported
    # symptom (2026-09-25): both buttons behaved identically once added,
    # the signature for this bug class per the project's own diagnostic
    # note -- fixed the same way, without re-diagnosing which exact
    # mechanism drops the property this time.
    affect = getattr(op, "affect", "EDGES")
    return f'bpy.ops.mesh.bevel(affect={affect!r})'


_SELECT_ACTION_LABELS = {
    'SELECT': "Select All", 'DESELECT': "Deselect All",
    'INVERT': "Invert Selection", 'TOGGLE': "Toggle Selection",
}


def _select_all_label(op):
    return _SELECT_ACTION_LABELS.get(getattr(op, "action", "TOGGLE"), "Select All")


def _select_all_command(op):
    # Generic override shared by every *.select_all-shaped operator (mesh,
    # object, curve, pose, particle, armature, grease pencil, paint face/
    # vert, node, uv, ...) -- they all define the same `action` property via
    # Blender's own WM_operator_properties_select_action() C helper, which
    # sets SKIP_SAVE on it. op_id is read from the button itself rather than
    # hardcoded, since one function pair covers every operator sharing this
    # shape (registered under each op id in _OPERATOR_OVERRIDES below).
    identifier = op.bl_rna.identifier  # e.g. "MESH_OT_select_all"
    op_id = identifier.replace("_OT_", ".").lower()
    action = getattr(op, "action", "TOGGLE")
    return f'bpy.ops.{op_id}(action={action!r})'


def _loopcut_slide_label(op):
    return "Loop Cut and Slide"


def _loopcut_slide_command(op):
    # MESH_OT_loopcut needs a real edge_index picked by hovering the mouse
    # over an edge ring -- copy_python_command_button() instead captures
    # whatever edge_index (often -1, "unset") was live at capture time, which
    # cancels on replay against any other geometry/session. Verified live:
    # the captured form returns {'CANCELLED'}, no cut. INVOKE_DEFAULT with no
    # baked kwargs re-picks the ring from the live mouse position, same as
    # the built-in Ctrl+R hotkey.
    return "bpy.ops.mesh.loopcut_slide('INVOKE_DEFAULT')"


def _face_strength_label(op):
    strength = getattr(op, "face_strength", "MEDIUM")
    try:
        name = op.bl_rna.properties["face_strength"].enum_items[strength].name
    except (KeyError, AttributeError):
        name = strength
    # Same operator id serves two different menus: "Set Face Strength"
    # (set=True, assigns) and "Select by Face Strength" (set=False, selects
    # matching faces instead) -- the button's own `set` value is what tells
    # them apart, not just face_strength.
    action = "Set" if getattr(op, "set", False) else "Select by"
    return f"{action} Face Strength: {name}"


def _face_strength_command(op):
    # face_strength defaults to 'MEDIUM' and set defaults to False -- when a
    # button's value matches a property's default, copy_python_command_button()
    # omits it from the generated string entirely (same effect as SKIP_SAVE:
    # the distinguishing value silently doesn't make it into the captured
    # command). Always writing both explicitly sidesteps that regardless of
    # which mechanism drops it. `set` itself must be read from the button
    # (not hardcoded) or "Select by Face Strength" collapses onto "Set Face
    # Strength" for the same strength value -- identical generated commands
    # made BlenderShelf's own duplicate-command check reject the second one
    # as "already added" (confirmed live, 2026-09-25).
    strength = getattr(op, "face_strength", "MEDIUM")
    set_value = getattr(op, "set", False)
    return f'bpy.ops.mesh.mod_weighted_strength(set={set_value!r}, face_strength={strength!r})'


_OPERATOR_OVERRIDES = {
    "node.add_node": (_add_node_label, _add_node_command, None),
    "node.add_group": (_add_group_label, _add_group_command, None),
    "brush.asset_activate": (_activate_brush_label, _activate_brush_command, _activate_brush_icon),
    "object.modifier_add": (_modifier_add_label, _modifier_add_command, None),
    "mesh.mark_sharp": (_mark_sharp_label, _mark_sharp_command, None),
    "mesh.mark_seam": (_mark_seam_label, _mark_seam_command, None),
    "mesh.merge": (_merge_label, _merge_command, None),
    "mesh.loopcut_slide": (_loopcut_slide_label, _loopcut_slide_command, None),
    "mesh.mod_weighted_strength": (_face_strength_label, _face_strength_command, None),
    "mesh.bevel": (_bevel_label, _bevel_command, None),
    # *.select_all family -- every one of these is reachable from the shelf's
    # own SpaceView3D overlay (any 3D-viewport mode) or from the pie's Node
    # Editor / Image Editor keymaps; SKIP_SAVE confirmed live for mesh/object,
    # the rest share the identical WM_operator_properties_select_action()
    # definition in Blender's own C code, and overriding a safe one costs
    # nothing even if it turns out not to have needed it.
    "mesh.select_all": (_select_all_label, _select_all_command, None),
    "object.select_all": (_select_all_label, _select_all_command, None),
    "curve.select_all": (_select_all_label, _select_all_command, None),
    "curves.select_all": (_select_all_label, _select_all_command, None),
    "armature.select_all": (_select_all_label, _select_all_command, None),
    "pose.select_all": (_select_all_label, _select_all_command, None),
    "particle.select_all": (_select_all_label, _select_all_command, None),
    "mball.select_all": (_select_all_label, _select_all_command, None),
    "lattice.select_all": (_select_all_label, _select_all_command, None),
    "grease_pencil.select_all": (_select_all_label, _select_all_command, None),
    "paint.face_select_all": (_select_all_label, _select_all_command, None),
    "paint.vert_select_all": (_select_all_label, _select_all_command, None),
    "node.select_all": (_select_all_label, _select_all_command, None),
    "uv.select_all": (_select_all_label, _select_all_command, None),
}


def _capture_button_command(context):
    if not (hasattr(context, "button_operator") and context.button_operator):
        return None, None, None, None
    op = context.button_operator
    identifier = op.bl_rna.identifier  # e.g. "MESH_OT_primitive_cube_add"
    op_id = identifier.replace("_OT_", ".").lower()
    label = op.bl_rna.name or op_id

    override = _OPERATOR_OVERRIDES.get(op_id)
    if override:
        label_fn, command_fn, icon_fn = override
        try:
            label = label_fn(op) or label
        except Exception:
            pass
        icon_path = None
        if icon_fn:
            try:
                icon_path = icon_fn(op)
            except Exception:
                icon_path = None
        icon_path = icon_path or _resolve_icon(op_id, op, label)
        try:
            return op_id, label, command_fn(op), icon_path
        except Exception:
            return op_id, label, f"bpy.ops.{op_id}()", icon_path

    enum_prop = _enum_prop_for_operator(op_id)
    if enum_prop:
        enum_label, enum_command = _enum_menu_label_and_command(op_id, op, enum_prop)
        if enum_command:
            label = enum_label or label
            return op_id, label, enum_command, _resolve_icon(op_id, op, label)

    command = ""
    try:
        bpy.ops.ui.copy_python_command_button()
        command = context.window_manager.clipboard
    except Exception:
        command = ""
    if not (command and op_id in command):
        command = f"bpy.ops.{op_id}()"
    return op_id, label, command, _resolve_icon(op_id, op, label)


class BLENDERSHELF_OT_add_from_context(bpy.types.Operator):
    """Add the right-clicked button's action as a new shelf button"""
    bl_idname = "blender_shelf.add_from_context"
    bl_label = "Add to Shelf"
    bl_options = {'REGISTER'}

    def execute(self, context):
        op_id, label, command, icon_path = _capture_button_command(context)
        if not op_id:
            self.report({'WARNING'}, "No operator found on this button")
            return {'CANCELLED'}
        prefs = get_prefs()
        if any(b.command == command for b in prefs.buttons):
            self.report({'INFO'}, f"'{label}' is already on the shelf")
            return {'CANCELLED'}

        item = prefs.buttons.add()
        item.label = label
        item.command = command
        item.icon_path = icon_path or os.path.join(BLENDER_ICON_DIR, "MESH_MONKEY.png")
        item.enabled = True
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
        _save_prefs()
        self.report({'INFO'}, f"Added '{label}' to shelf")
        return {'FINISHED'}


_pie_category_items_cache = []  # kept referenced -- Blender frees dynamic enum strings otherwise


def _pie_category_items(self, context):
    prefs = get_prefs()
    items = [('PIE_OBJECT', "Object Mode", ''), ('PIE_EDIT', "Edit Mode", '')]
    if prefs:
        if prefs.pie_context_sculpt:
            items.append(('PIE_SCULPT', "Sculpt Mode", ''))
        if prefs.pie_context_uv:
            items.append(('PIE_UV', "UV Editor", ''))
        if prefs.pie_context_node_shader:
            items.append(('PIE_NODE_SHADER', "Shader Editor", ''))
        if prefs.pie_context_node_geo:
            items.append(('PIE_NODE_GEO', "Geometry Nodes", ''))
    global _pie_category_items_cache
    _pie_category_items_cache = items
    return _pie_category_items_cache


class BLENDERSHELF_OT_add_to_pie(bpy.types.Operator):
    """Add the right-clicked button's action to one of the Split-mode pie lists"""
    bl_idname = "blender_shelf.add_to_pie"
    bl_label = "Add to ShelfPie"
    bl_options = {'REGISTER'}

    category: bpy.props.EnumProperty(name="Category", items=_pie_category_items)
    captured_label: bpy.props.StringProperty(options={'HIDDEN'})
    captured_command: bpy.props.StringProperty(options={'HIDDEN'})
    captured_icon_path: bpy.props.StringProperty(options={'HIDDEN'})

    def invoke(self, context, event):
        # context.button_operator only exists while this runs from the
        # right-click menu itself -- invoke_props_dialog() re-enters via a
        # fresh event loop, so execute() no longer sees it. Capture now and
        # carry the result through as plain string props.
        op_id, label, command, icon_path = _capture_button_command(context)
        if not op_id:
            self.report({'WARNING'}, "No operator found on this button")
            return {'CANCELLED'}
        self.captured_label = label
        self.captured_command = command
        self.captured_icon_path = icon_path or ""
        prefs = get_prefs()
        target = _split_pie_target(context, prefs) if prefs else None
        valid = {item[0] for item in _pie_category_items(self, context)}
        self.category = target if target in valid else 'PIE_OBJECT'
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        self.layout.label(text=self.captured_label)
        self.layout.prop(self, "category", expand=True)

    def execute(self, context):
        prefs = get_prefs()
        coll, _ = _target_collection(prefs, self.category)
        if any(b.command == self.captured_command for b in coll):
            self.report({'INFO'}, f"'{self.captured_label}' is already in that pie category")
            return {'CANCELLED'}

        item = coll.add()
        item.label = self.captured_label
        item.command = self.captured_command
        item.icon_path = self.captured_icon_path or os.path.join(BLENDER_ICON_DIR, "MESH_MONKEY.png")
        item.enabled = True
        _save_prefs()
        self.report({'INFO'}, f"Added '{self.captured_label}' to {_TARGET_LABELS[self.category]}")
        return {'FINISHED'}


def _shelf_context_menu_draw(self, context):
    if hasattr(context, "button_operator") and context.button_operator:
        self.layout.separator()
        self.layout.operator(BLENDERSHELF_OT_add_from_context.bl_idname, icon='ADD')
        prefs = get_prefs()
        if prefs and prefs.pie_mode == 'SPLIT':
            self.layout.operator(BLENDERSHELF_OT_add_to_pie.bl_idname, icon='ADD')


# ---------------------------------------------------------------------------
# Geometry, draw, click handling
# ---------------------------------------------------------------------------

def _is_vertical():
    prefs = get_prefs()
    return prefs.orientation == 'VERTICAL' if prefs else False


def _shelf_scale():
    prefs = get_prefs()
    manual = prefs.shelf_scale if prefs else 1.0
    # ui_scale tracks the OS DPI setting and Blender's own Resolution Scale,
    # so the shelf matches Blender's UI size automatically across monitors;
    # shelf_scale (the "Shelf Size" slider) is a manual multiplier on top.
    return bpy.context.preferences.system.ui_scale * manual


def _btn_size():
    return BASE_BTN * _shelf_scale()


def _pad_size():
    return BASE_PAD * _shelf_scale()


def _panel_size(n, vertical):
    btn, pad = _btn_size(), _pad_size()
    if vertical:
        return btn + pad * 2, pad * 2 + n * btn + (n - 1) * pad
    return pad * 2 + n * btn + (n - 1) * pad, btn + pad * 2


def _sidebar_bounds(area, window_region):
    # The Toolbar (T) and Sidebar (N) are overlays drawn on top of the
    # viewport's own WINDOW region -- they don't shrink it, so region.width
    # alone can't tell us they're there. Read their real rects directly so
    # the shelf can stay clear of them instead of rendering underneath.
    left, right = 0.0, float(window_region.width)
    if area is None:
        return left, right
    for r in area.regions:
        if r.width <= 1:
            continue  # collapsed/closed
        rel_x0 = r.x - window_region.x
        if r.type == 'TOOLS':
            left = max(left, rel_x0 + r.width)
        elif r.type == 'UI':
            right = min(right, rel_x0)
    return left, right


def shelf_geometry(region):
    items = _enabled_items()
    top_margin, left_margin = _position(region)
    show_fbx = _export_button_enabled()
    total_slots = _total_slots(items)
    vertical = _is_vertical()
    panel_w, panel_h = _panel_size(total_slots, vertical)
    btn, pad = _btn_size(), _pad_size()
    # Anchored from the left/top edges now (not right), so the aux group
    # (orientation toggle + drag handle) sits at a fixed screen position and
    # the panel grows/shrinks away from it as buttons are added/removed --
    # previously the panel was right-anchored while aux derived from its
    # (moving) left edge, so aux drifted every time the button count changed
    # in horizontal mode (confirmed live, 2026-09-26; vertical mode was
    # unaffected since its panel width doesn't depend on button count).
    reserve = _aux_reserve()
    edge_left, edge_right = _sidebar_bounds(bpy.context.area, region)
    y = region.height - top_margin - panel_h
    if vertical:
        x = left_margin
        lo = max(0.0, edge_left)
        hi = max(lo, min(region.width, edge_right) - panel_w)
        x = max(lo, min(x, hi))
        y = max(0.0, min(y, max(0.0, region.height - panel_h - reserve)))
    else:
        x = left_margin + reserve
        lo = max(reserve, edge_left + reserve)
        hi = max(lo, min(region.width, edge_right) - panel_w)
        x = max(lo, min(x, hi))
        y = max(0.0, min(y, max(0.0, region.height - panel_h)))
    # FBX (when shown) takes slot 0. In vertical it's simply the topmost
    # slot beyond the highest item index, so item rects need no shift; in
    # horizontal, slot 0 is leftmost, so items shift right by one slot.
    h_offset = 1 if (show_fbx and not vertical) else 0
    if vertical:
        # button 1 at the top of the stack, reading down
        rects = [(x + pad, y + pad + (len(items) - 1 - i) * (btn + pad),
                  x + pad + btn, y + pad + (len(items) - 1 - i) * (btn + pad) + btn)
                 for i in range(len(items))]
    else:
        rects = [(x + pad + (i + h_offset) * (btn + pad), y + pad,
                  x + pad + (i + h_offset) * (btn + pad) + btn, y + pad + btn)
                 for i in range(len(items))]
    return x, y, panel_w, panel_h, rects


AUX_GAP = 4
AUX_SIZE_RATIO = 0.6  # orientation/drag box size, relative to a main button


def _aux_size():
    return _btn_size() * AUX_SIZE_RATIO


def _aux_reserve():
    # room the aux group needs beyond the panel, in whichever direction it
    # stacks: a 1-wide/2-tall column to the left in horizontal shelf mode,
    # a 2-wide/1-tall row above in vertical shelf mode -- either way the
    # dimension that matters is a single box's thickness plus the gap.
    return AUX_GAP + _aux_size()


def _min_top_margin():
    # in VERTICAL orientation the aux row (orientation+drag) sits above the
    # panel, so the shelf's true top edge is higher than the button panel's
    # top edge by that row's height -- positioning code must budget for it
    # or those buttons clip off the top of the viewport. Callers assign this
    # straight into an IntProperty, hence round().
    return round(_aux_reserve()) if _is_vertical() else 0


def fbx_button_rect(region):
    # FBX's pseudo-slot: slot 0 inside the panel (leftmost horizontal, or
    # the topmost slot above the highest item index vertically).
    x, y, panel_w, panel_h, _ = shelf_geometry(region)
    btn, pad = _btn_size(), _pad_size()
    if _is_vertical():
        n_items = len(_enabled_items())
        y0 = y + pad + n_items * (btn + pad)
        return x + pad, y0, x + pad + btn, y0 + btn
    return x + pad, y + pad, x + pad + btn, y + pad + btn


def _aux_group_rects(region):
    # orientation icon + drag handle as one 2-box group: stacked vertically
    # (arrow on top, dots below) to the left of the panel in horizontal
    # shelf mode; side by side (dots left, arrow right) above the panel in
    # vertical shelf mode -- so the group always reads left-to-right/
    # top-to-bottom the same way the shelf itself does.
    x, y, panel_w, panel_h, _ = shelf_geometry(region)
    size = _aux_size()
    if _is_vertical():
        row_w = size * 2 + AUX_GAP
        gx = x + panel_w / 2.0 - row_w / 2.0
        gy = y + panel_h + AUX_GAP
        drag_rect = (gx, gy, gx + size, gy + size)
        orient_rect = (gx + size + AUX_GAP, gy, gx + size + AUX_GAP + size, gy + size)
    else:
        stack_h = size * 2 + AUX_GAP
        gx = x - AUX_GAP - size
        gy = y + panel_h / 2.0 - stack_h / 2.0
        drag_rect = (gx, gy, gx + size, gy + size)
        orient_rect = (gx, gy + size + AUX_GAP, gx + size, gy + 2 * size + AUX_GAP)
    return orient_rect, drag_rect


def orientation_button_rect(region):
    orient_rect, _ = _aux_group_rects(region)
    return orient_rect


def drag_handle_rect(region):
    _, drag_rect = _aux_group_rects(region)
    return drag_rect


def _quad(shader, x0, y0, x1, y1, color):
    verts = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=((0, 1, 2), (2, 3, 0)))
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


BTN_RADIUS = 4
PANEL_RADIUS = 6
AUX_RADIUS = 6  # orientation/drag buttons -- double the old radius of 3
_ROUND_SEGMENTS = 5


def _round_quad(shader, x0, y0, x1, y1, color, radius):
    radius = max(0.0, min(radius, (x1 - x0) / 2, (y1 - y0) / 2))
    if radius < 0.5:
        _quad(shader, x0, y0, x1, y1, color)
        return
    verts = []
    for cx, cy, a0 in ((x1 - radius, y0 + radius, -90),   # bottom-right
                       (x1 - radius, y1 - radius, 0),      # top-right
                       (x0 + radius, y1 - radius, 90),      # top-left
                       (x0 + radius, y0 + radius, 180)):    # bottom-left
        for s in range(_ROUND_SEGMENTS + 1):
            a = math.radians(a0 + 90 * s / _ROUND_SEGMENTS)
            verts.append((cx + radius * math.cos(a), cy + radius * math.sin(a)))
    indices = [(0, i, i + 1) for i in range(1, len(verts) - 1)]
    batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=indices)
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def _draw_grip_dots(shader, x0, y0, x1, y1, color):
    # three dots stacked vertically in the drag handle box
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    dot_r = 1.3
    spacing = 6
    n = 3
    offsets = [(-((n - 1) / 2.0) + i) * spacing for i in range(n)]
    for o in offsets:
        _round_quad(shader, cx - dot_r, cy + o - dot_r, cx + dot_r, cy + o + dot_r, color, dot_r)


def _draw_thick_line(shader, x0, y0, x1, y1, thickness, color):
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return
    nx, ny = -dy / length * thickness / 2.0, dx / length * thickness / 2.0
    verts = ((x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny))
    batch = batch_for_shader(shader, 'TRIS', {"pos": verts}, indices=((0, 1, 2), (2, 3, 0)))
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def _draw_orientation_icon(shader, x0, y0, x1, y1, color, vertical):
    # a ">" chevron showing the current layout: pointing right for
    # horizontal, rotated to point down for vertical -- click switches to
    # the other one
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    r = min(x1 - x0, y1 - y0) / 2.0 * 0.35
    thickness = 2.0
    if vertical:
        tip = (cx, cy - r)
        a = (cx - r, cy + r)
        b = (cx + r, cy + r)
    else:
        tip = (cx + r, cy)
        a = (cx - r, cy + r)
        b = (cx - r, cy - r)
    _draw_thick_line(shader, a[0], a[1], tip[0], tip[1], thickness, color)
    _draw_thick_line(shader, tip[0], tip[1], b[0], b[1], thickness, color)


DEFAULT_BTN_COLOR = (0.32, 0.32, 0.32, 1.0)
DEFAULT_BG_COLOR = (0.10, 0.10, 0.10, 0.9)
PRESSED_BORDER = (0.95, 0.55, 0.15, 1.0)
BORDER_THICKNESS = 2


def _shade(color, delta):
    r, g, b, a = color
    c = lambda v: max(0.0, min(1.0, v + delta))
    return (c(r), c(g), c(b), a)


def _button_colors():
    prefs = get_prefs()
    base = tuple(prefs.btn_color) if prefs else DEFAULT_BTN_COLOR
    return base, _shade(base, 0.13), _shade(base, -0.10)  # normal, hover, pressed


def _border(shader, x0, y0, x1, y1, color, t=BORDER_THICKNESS):
    _quad(shader, x0, y0, x1, y0 + t, color)  # bottom
    _quad(shader, x0, y1 - t, x1, y1, color)  # top
    _quad(shader, x0, y0, x0 + t, y1, color)  # left
    _quad(shader, x1 - t, y0, x1, y1, color)  # right


def _fit_text(font_id, text, max_w):
    while text and blf.dimensions(font_id, text)[0] > max_w:
        text = text[:-1]
    return text


MAX_LABEL_LINES = 2


def _wrap_label(font_id, text, max_w):
    if not text or max_w <= 0:
        return []
    words = text.split(" ")
    lines = []
    idx = 0
    while idx < len(words) and len(lines) < MAX_LABEL_LINES:
        word = words[idx]
        if blf.dimensions(font_id, word)[0] > max_w:
            # word alone doesn't fit -- break it mid-word and carry the rest over
            line = _fit_text(font_id, word, max_w) or word[:1]
            words[idx] = word[len(line):]
            if not words[idx]:
                idx += 1
        else:
            line = word
            idx += 1
            while idx < len(words):
                candidate = line + " " + words[idx]
                if blf.dimensions(font_id, candidate)[0] > max_w:
                    break
                line = candidate
                idx += 1
        lines.append(line)
    return lines


def _draw_tooltip(shader, region, text, mx, my):
    if not text:
        return
    font_id = 0
    blf.size(font_id, 12)
    text_w, text_h = blf.dimensions(font_id, text)
    pad = 5
    box_w = text_w + pad * 2
    box_h = text_h + pad * 2
    x0 = mx + 14
    y0 = my - box_h - 10
    if x0 + box_w > region.width:
        x0 = region.width - box_w - 4
    if y0 < 0:
        y0 = my + 14
    gpu.state.blend_set('ALPHA')
    _round_quad(shader, x0, y0, x0 + box_w, y0 + box_h, (0.03, 0.03, 0.03, 0.95), 3)
    gpu.state.blend_set('NONE')
    blf.color(font_id, 1, 1, 1, 1.0)
    blf.position(font_id, x0 + pad, y0 + pad, 0)
    blf.draw(font_id, text)


def _draw_separator_bar(shader, x0, y0, x1, y1, color):
    # a thin divider centered in its slot, perpendicular to the shelf's
    # layout direction -- the slot's own empty space around it is what
    # reads as "small margins", no separate narrow-slot geometry needed.
    cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
    if _is_vertical():
        bar_w = (x1 - x0) * 0.6
        _round_quad(shader, cx - bar_w / 2.0, cy - 1.5, cx + bar_w / 2.0, cy + 1.5, color, 1.5)
    else:
        bar_h = (y1 - y0) * 0.6
        _round_quad(shader, cx - 1.5, cy - bar_h / 2.0, cx + 1.5, cy + bar_h / 2.0, color, 1.5)


def draw_shelf():
    region = bpy.context.region
    if region is None:
        return
    items = _enabled_items()

    color_shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    image_shader = gpu.shader.from_builtin('IMAGE_COLOR')
    gpu.state.blend_set('ALPHA')

    prefs = get_prefs()
    bg_color = tuple(prefs.bg_color) if prefs else DEFAULT_BG_COLOR
    btn_normal, btn_hover, btn_pressed = _button_colors()
    show_export_button = prefs.show_export_button if prefs else True
    icon_color = (1.0, 1.0, 1.0, prefs.icon_opacity if prefs else 1.0)

    rects = []
    draw_panel = _should_draw_shelf()
    moving_slot_i = None
    if draw_panel and prefs is not None and _moving_index is not None:
        real_indices = _visible_real_indices(prefs.buttons)
        if _moving_index in real_indices:
            moving_slot_i = real_indices.index(_moving_index)

    if draw_panel:
        x, y, panel_w, panel_h, rects = shelf_geometry(region)
        _round_quad(color_shader, x, y, x + panel_w, y + panel_h, bg_color, PANEL_RADIUS)

        for i, (x0, y0, x1, y1) in enumerate(rects):
            btn = items[i]
            if i == moving_slot_i:
                # left behind as a faint placeholder -- the real button is
                # drawn following the cursor instead, see below.
                dim = (btn_normal[0], btn_normal[1], btn_normal[2], btn_normal[3] * 0.25)
                _round_quad(color_shader, x0, y0, x1, y1, dim, BTN_RADIUS)
                continue
            if btn.is_separator:
                if i == _pressed_index or i == _hover_index:
                    _round_quad(color_shader, x0, y0, x1, y1, (1.0, 1.0, 1.0, 0.12), BTN_RADIUS)
                _draw_separator_bar(color_shader, x0, y0, x1, y1,
                                     tuple(prefs.separator_color) if prefs else (1.0, 1.0, 1.0, 0.4))
                continue
            if i == _pressed_index:
                bg = btn_pressed
            elif i == _hover_index:
                bg = btn_hover
            else:
                bg = btn_normal
            _round_quad(color_shader, x0, y0, x1, y1, bg, BTN_RADIUS)

            tex = _get_icon_texture(btn.icon_path)
            if tex is not None:
                verts = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
                uvs = ((0, 0), (1, 0), (1, 1), (0, 1))
                batch = batch_for_shader(image_shader, 'TRI_FAN', {"pos": verts, "texCoord": uvs})
                image_shader.bind()
                image_shader.uniform_sampler("image", tex)
                image_shader.uniform_float("color", icon_color)
                batch.draw(image_shader)

            if i == _pressed_index:
                _border(color_shader, x0, y0, x1, y1, PRESSED_BORDER)

        if _moving_index is not None and moving_slot_i is not None:
            moving_btn = prefs.buttons[_moving_index]
            btn_sz = _btn_size()
            half = btn_sz / 2.0
            gx0, gy0 = _mouse_x - half, _mouse_y - half
            gx1, gy1 = _mouse_x + half, _mouse_y + half
            _round_quad(color_shader, gx0, gy0, gx1, gy1, btn_pressed, BTN_RADIUS)
            if moving_btn.is_separator:
                _draw_separator_bar(color_shader, gx0, gy0, gx1, gy1,
                                     tuple(prefs.separator_color) if prefs else (1.0, 1.0, 1.0, 0.4))
            else:
                ghost_tex = _get_icon_texture(moving_btn.icon_path)
                if ghost_tex is not None:
                    verts = ((gx0, gy0), (gx1, gy0), (gx1, gy1), (gx0, gy1))
                    uvs = ((0, 0), (1, 0), (1, 1), (0, 1))
                    batch = batch_for_shader(image_shader, 'TRI_FAN', {"pos": verts, "texCoord": uvs})
                    image_shader.bind()
                    image_shader.uniform_sampler("image", ghost_tex)
                    image_shader.uniform_float("color", icon_color)
                    batch.draw(image_shader)
            _border(color_shader, gx0, gy0, gx1, gy1, PRESSED_BORDER, t=1)

            if _move_insert_gap is not None and rects:
                vertical = _is_vertical()
                g = _move_insert_gap
                pad = _pad_size()
                sep_color = (1.0, 0.85, 0.2, 0.95)
                if vertical:
                    if g <= 0:
                        sep_y = rects[0][3] + pad / 2.0
                    elif g >= len(rects):
                        sep_y = rects[-1][1] - pad / 2.0
                    else:
                        sep_y = (rects[g - 1][1] + rects[g][3]) / 2.0
                    _round_quad(color_shader, rects[0][0], sep_y - 1.5, rects[0][2], sep_y + 1.5, sep_color, 1.5)
                else:
                    if g <= 0:
                        sep_x = rects[0][0] - pad / 2.0
                    elif g >= len(rects):
                        sep_x = rects[-1][2] + pad / 2.0
                    else:
                        sep_x = (rects[g - 1][2] + rects[g][0]) / 2.0
                    _round_quad(color_shader, sep_x - 1.5, rects[0][1], sep_x + 1.5, rects[0][3], sep_color, 1.5)

        if show_export_button:
            ex0, ey0, ex1, ey1 = fbx_button_rect(region)
            if _export_pressed:
                ebg = btn_pressed
            elif _export_hover:
                ebg = btn_hover
            else:
                ebg = btn_normal
            _round_quad(color_shader, ex0, ey0, ex1, ey1, ebg, BTN_RADIUS)
            if _export_pressed:
                _border(color_shader, ex0, ey0, ex1, ey1, PRESSED_BORDER)

    if draw_panel:
        ox0, oy0, ox1, oy1 = orientation_button_rect(region)
        obg = btn_hover if _orient_hover else btn_normal
        _round_quad(color_shader, ox0, oy0, ox1, oy1, obg, AUX_RADIUS)
        _draw_orientation_icon(color_shader, ox0, oy0, ox1, oy1, (1, 1, 1, 0.9), _is_vertical())

        dx0, dy0, dx1, dy1 = drag_handle_rect(region)
        if _dragging_shelf:
            dbg = btn_pressed
        elif _drag_hover:
            dbg = btn_hover
        else:
            dbg = btn_normal
        _round_quad(color_shader, dx0, dy0, dx1, dy1, dbg, AUX_RADIUS)
        if _dragging_shelf:
            _border(color_shader, dx0, dy0, dx1, dy1, PRESSED_BORDER, t=1)
        _draw_grip_dots(color_shader, dx0, dy0, dx1, dy1, (1, 1, 1, 0.6))
    gpu.state.blend_set('NONE')

    font_id = 0
    show_number = prefs.show_number if prefs else True
    show_label = prefs.show_label if prefs else True

    if show_number:
        blf.color(font_id, 1, 1, 1, 0.9)
        blf.size(font_id, 11)
        for i, (x0, y0, x1, y1) in enumerate(rects):
            if i == moving_slot_i or items[i].is_separator:
                continue
            blf.position(font_id, x0 + 2, y1 - 13, 0)
            blf.draw(font_id, str(i + 1))

    if show_label:
        label_font_size = prefs.label_font_size if prefs else 7
        label_color = prefs.label_color if prefs else (1.0, 1.0, 1.0, 0.9)
        label_placement = prefs.label_placement if prefs else 'INSIDE'
        blf.size(font_id, label_font_size)
        blf.color(font_id, *label_color)
        line_h = label_font_size + 2
        for i, (x0, y0, x1, y1) in enumerate(rects):
            if i == moving_slot_i or items[i].is_separator:
                continue
            lines = _wrap_label(font_id, items[i].label, (x1 - x0) - 4)
            n = len(lines)
            for li, line in enumerate(lines):
                if label_placement == 'ABOVE':
                    x_pos = x0 + 2
                    y_pos = (y1 + 2) + (n - 1 - li) * line_h
                elif label_placement == 'BELOW':
                    x_pos = x0 + 2
                    y_pos = (y0 - 2) - (li + 1) * line_h
                elif label_placement in ('LEFT', 'RIGHT'):
                    mid_y = (y0 + y1) / 2.0
                    top_of_block = mid_y + (n * line_h) / 2.0
                    y_pos = top_of_block - (li + 1) * line_h
                    if label_placement == 'LEFT':
                        x_pos = x0 - 2 - blf.dimensions(font_id, line)[0]
                    else:  # RIGHT
                        x_pos = x1 + 2
                else:  # INSIDE
                    x_pos = x0 + 2
                    y_pos = (y0 + 2) + (n - 1 - li) * line_h
                blf.position(font_id, x_pos, y_pos, 0)
                blf.draw(font_id, line)

    if draw_panel and show_export_button:
        ex0, ey0, ex1, ey1 = fbx_button_rect(region)
        blf.color(font_id, 1, 1, 1, 0.9)
        blf.size(font_id, 9)
        blf.position(font_id, ex0 + 3, ey1 - 16, 0)
        blf.draw(font_id, "FBX")
        blf.position(font_id, ex0 + 3, ey0 + 6, 0)
        blf.draw(font_id, "sel")

    tooltip_text = None
    if _moving_index is not None:
        tooltip_text = "Click to drop here, right-click/Esc to cancel"
    elif _hover_index is not None and 0 <= _hover_index < len(items):
        tooltip_text = items[_hover_index].label
    elif _export_hover and show_export_button:
        tooltip_text = "Export Selected to FBX"
    elif _orient_hover:
        tooltip_text = ("Click: switch to Horizontal" if _is_vertical()
                         else "Click: switch to Vertical")
    elif _drag_hover or _dragging_shelf:
        tooltip_text = "Drag to move the shelf"
    if tooltip_text:
        _draw_tooltip(color_shader, region, tooltip_text, _mouse_x, _mouse_y)


_draw_handle = None
_modal_running = False
_modal_stop = False
_restart_requested = False  # like _modal_stop but for a live restart, not
                             # addon shutdown -- see _start_modal(). Confirmed
                             # live (patched modal() to log every event that
                             # reached it): after switching workspace tabs,
                             # the running instance keeps getting its own
                             # TIMER events forever (with context.area/region
                             # both None) but NEVER another MOUSEMOVE/click
                             # again -- a zombie that looks alive by any
                             # heartbeat, since it's still ticking, but is
                             # permanently cut off from real input. Only a
                             # clean cancel + fresh INVOKE_DEFAULT (bound to
                             # the now-current window/area) fixes it.
_last_alive = 0.0  # time.time() of the last modal() call, any event -- a
                    # heartbeat independent of _modal_running, which has
                    # proven unreliable: it's only ever cleared from inside
                    # modal() itself, so if the instance gets silently
                    # orphaned by Blender instead of going through our own
                    # _modal_stop shutdown, the flag stays stuck "running"
                    # forever with nothing left alive to ever clear it. Only
                    # catches a truly dead instance, not the zombie case
                    # above (see _restart_requested) -- both are needed.
_hover_index = None
_pressed_index = None
_export_hover = False
_export_pressed = False
_orient_hover = False
_drag_hover = False
_dragging_shelf = False
_drag_start_mouse = (0.0, 0.0)
_drag_start_margins = (0.0, 0.0)
_drag_live_margins = None  # (top_margin_px, left_margin_px) while dragging, else None
_drag_region_width = 1.0  # region.width captured at drag-start, for px<->fraction conversion
_mouse_x = 0
_mouse_y = 0
_last_screen_ptr = None  # win.screen.as_pointer() as of the last _start_modal
                          # tick, to detect a workspace-tab switch and force
                          # a clean restart -- see _restart_requested above.

_moving_index = None  # real prefs.buttons index of the button being moved, or None
_move_insert_gap = None  # 0..N gap position (in _enabled_items() order) under the cursor while moving


# ---------------------------------------------------------------------------
# Click handling -- a single persistent modal operator, started on register
# ---------------------------------------------------------------------------

class BLENDERSHELF_OT_modal(bpy.types.Operator):
    bl_idname = "blender_shelf.modal"
    bl_label = "BlenderShelf Input"

    def modal(self, context, event):
        global _modal_running, _hover_index, _pressed_index, _mouse_x, _mouse_y
        global _export_hover, _export_pressed, _orient_hover, _drag_hover
        global _dragging_shelf, _drag_start_mouse, _drag_start_margins, _drag_live_margins, _drag_region_width
        global _last_alive, _restart_requested
        global _moving_index, _move_insert_gap
        _last_alive = time.time()  # proof of life, independent of _modal_running
        if _modal_stop or _restart_requested:
            _modal_running = False
            _restart_requested = False
            try:
                context.window_manager.event_timer_remove(self._timer)
            except Exception:
                pass
            return {'CANCELLED'}

        in_viewport = context.region and context.region.type == 'WINDOW' and context.area and context.area.type == 'VIEW_3D'

        if _moving_index is not None and event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            _moving_index = None
            _move_insert_gap = None
            if context.area:
                context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        if event.type == 'MOUSEMOVE':
            mx, my = event.mouse_region_x, event.mouse_region_y
            if _moving_index is not None:
                _mouse_x, _mouse_y = mx, my
                if in_viewport and _should_draw_shelf():
                    _, _, _, _, rects = shelf_geometry(context.region)
                    _move_insert_gap = _gap_under_mouse(rects, mx, my, _is_vertical())
                if context.area:
                    context.area.tag_redraw()
                return {'RUNNING_MODAL'}  # consume it -- don't hover/orbit while moving

            if _dragging_shelf:
                _mouse_x, _mouse_y = mx, my
                dx = mx - _drag_start_mouse[0]
                dy = my - _drag_start_mouse[1]
                start_top, start_left = _drag_start_margins
                _drag_live_margins = (max(0.0, start_top - dy), max(0.0, start_left + dx))
                if context.area:
                    context.area.tag_redraw()
                return {'RUNNING_MODAL'}  # consume the drag, don't also orbit/pan the viewport

            new_hover = None
            new_export_hover = False
            new_orient_hover = False
            new_drag_hover = False
            if in_viewport:
                _mouse_x, _mouse_y = mx, my
                if _should_draw_shelf():
                    _, _, _, _, rects = shelf_geometry(context.region)
                    for i, (x0, y0, x1, y1) in enumerate(rects):
                        if x0 <= mx <= x1 and y0 <= my <= y1:
                            new_hover = i
                            break
                    if _export_button_enabled():
                        ex0, ey0, ex1, ey1 = fbx_button_rect(context.region)
                        new_export_hover = ex0 <= mx <= ex1 and ey0 <= my <= ey1
                    ox0, oy0, ox1, oy1 = orientation_button_rect(context.region)
                    new_orient_hover = ox0 <= mx <= ox1 and oy0 <= my <= oy1
                    gx0, gy0, gx1, gy1 = drag_handle_rect(context.region)
                    new_drag_hover = gx0 <= mx <= gx1 and gy0 <= my <= gy1
            # redraw on any state change, and continuously while hovering so
            # the tooltip box tracks the cursor
            should_redraw = (new_hover != _hover_index or new_export_hover != _export_hover
                              or new_orient_hover != _orient_hover or new_drag_hover != _drag_hover
                              or new_hover is not None or new_export_hover or new_orient_hover or new_drag_hover)
            _hover_index = new_hover
            _export_hover = new_export_hover
            _orient_hover = new_orient_hover
            _drag_hover = new_drag_hover
            if should_redraw and context.area:
                context.area.tag_redraw()
            return {'PASS_THROUGH'}

        if _moving_index is not None and event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            prefs = get_prefs()
            if prefs is not None and _move_insert_gap is not None:
                coll, idx_attr = _target_collection(prefs, 'SHELF')
                real_indices = _visible_real_indices(coll)
                target = _gap_target_real_index(real_indices, _move_insert_gap, len(coll))
                if target != _moving_index:
                    coll.move(_moving_index, target)
                    setattr(prefs, idx_attr, target)
                    _save_prefs()
            _moving_index = None
            _move_insert_gap = None
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
            return {'RUNNING_MODAL'}

        if event.type == 'RIGHTMOUSE' and event.value == 'PRESS' and in_viewport:
            mx, my = event.mouse_region_x, event.mouse_region_y
            if _should_draw_shelf():
                _, _, _, _, rects = shelf_geometry(context.region)
                for i, (x0, y0, x1, y1) in enumerate(rects):
                    if x0 <= mx <= x1 and y0 <= my <= y1:
                        prefs = get_prefs()
                        real_indices = _visible_real_indices(prefs.buttons)
                        if i < len(real_indices):
                            prefs.active_index = real_indices[i]
                            # explicit INVOKE_DEFAULT -- called from a script/
                            # modal context (not a real UI button click), so
                            # without it every operator drawn inside the menu
                            # (Delete's own invoke_confirm included) silently
                            # runs EXEC-only and skips its invoke()/dialog.
                            bpy.ops.wm.call_menu('INVOKE_DEFAULT', name="BLENDERSHELF_MT_shelf_button_context")
                        return {'RUNNING_MODAL'}
            return {'PASS_THROUGH'}

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS' and in_viewport:
            mx, my = event.mouse_region_x, event.mouse_region_y
            if _should_draw_shelf():
                items = _enabled_items()
                _, _, _, _, rects = shelf_geometry(context.region)
                for i, (x0, y0, x1, y1) in enumerate(rects):
                    if x0 <= mx <= x1 and y0 <= my <= y1:
                        _pressed_index = i
                        btn = items[i]
                        if btn.command:
                            try:
                                _exec_shelf_command(btn.command)
                            except Exception as e:
                                self.report({'ERROR'}, f"Shelf button {i + 1} ({btn.label}) failed: {e}")
                        for area in context.screen.areas:
                            if area.type == 'VIEW_3D':
                                area.tag_redraw()
                        return {'RUNNING_MODAL'}

                if _export_button_enabled():
                    ex0, ey0, ex1, ey1 = fbx_button_rect(context.region)
                    if ex0 <= mx <= ex1 and ey0 <= my <= ey1:
                        _export_pressed = True
                        try:
                            bpy.ops.export_scene.fbx('INVOKE_DEFAULT', use_selection=True)
                        except Exception as e:
                            self.report({'ERROR'}, f"Export FBX failed: {e}")
                        for area in context.screen.areas:
                            if area.type == 'VIEW_3D':
                                area.tag_redraw()
                        return {'RUNNING_MODAL'}

                ox0, oy0, ox1, oy1 = orientation_button_rect(context.region)
                if ox0 <= mx <= ox1 and oy0 <= my <= oy1:
                    prefs = get_prefs()
                    if prefs is not None:
                        prefs.orientation = 'HORIZONTAL' if prefs.orientation == 'VERTICAL' else 'VERTICAL'
                    for area in context.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()
                    return {'RUNNING_MODAL'}

                gx0, gy0, gx1, gy1 = drag_handle_rect(context.region)
                if gx0 <= mx <= gx1 and gy0 <= my <= gy1:
                    _dragging_shelf = True
                    _drag_start_mouse = (mx, my)
                    _drag_region_width = context.region.width
                    _drag_start_margins = _position(context.region)
                    _drag_live_margins = _drag_start_margins
                    for area in context.screen.areas:
                        if area.type == 'VIEW_3D':
                            area.tag_redraw()
                    return {'RUNNING_MODAL'}

            return {'PASS_THROUGH'}

        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and _dragging_shelf:
            _dragging_shelf = False
            prefs = get_prefs()
            if prefs is not None and _drag_live_margins is not None:
                top, left_px = _drag_live_margins
                prefs.top_margin = round(top)  # IntProperty -- rejects a bare float
                if _drag_region_width:
                    prefs.left_margin_pct = max(0.0, min(1.0, left_px / _drag_region_width))
            _drag_live_margins = None
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
            return {'PASS_THROUGH'}

        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE' and (
                _pressed_index is not None or _export_pressed):
            _pressed_index = None
            _export_pressed = False
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
            return {'PASS_THROUGH'}

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        global _modal_running, _last_alive
        context.window_manager.modal_handler_add(self)
        # Guarantees a steady stream of events even with the mouse idle, so
        # the _modal_stop check above always gets a near-immediate chance to
        # run -- without this, disabling the addon while the mouse hasn't
        # moved could leave this instance alive when unregister_class() runs
        # on its class, which crashes Blender.
        self._timer = context.window_manager.event_timer_add(0.1, window=context.window)
        _modal_running = True
        _last_alive = time.time()
        return {'RUNNING_MODAL'}


_MODAL_HEARTBEAT_TIMEOUT = 1.5  # seconds without a modal() call before an instance counts as dead


def _modal_is_alive():
    return _modal_running and (time.time() - _last_alive) < _MODAL_HEARTBEAT_TIMEOUT


def _unregister_modal_when_stopped():
    if _modal_is_alive():
        return 0.05
    try:
        bpy.utils.unregister_class(BLENDERSHELF_OT_modal)
    except (RuntimeError, ValueError):
        pass
    return None


def _start_modal():
    # a recurring watchdog, not a one-shot. Two distinct failure modes were
    # found in the wild after switching workspace tabs:
    #  1. the instance dies outright (rare) -- caught by the _last_alive
    #     heartbeat below, independent of _modal_running (which is only ever
    #     cleared from inside modal() itself, so a silently-orphaned instance
    #     left it stuck "running" forever with nothing left alive to clear
    #     it).
    #  2. the instance survives as a *zombie* (the common case, confirmed by
    #     temporarily patching modal() to log every event that reached it):
    #     it keeps getting its own bound TIMER events forever (context.area/
    #     region both None on them), so any heartbeat looks perfectly healthy,
    #     but it never receives another MOUSEMOVE/click again -- permanently
    #     cut off from real input. Only a clean cancel + fresh INVOKE_DEFAULT
    #     fixes this, and nothing about the instance's own state reveals it's
    #     a zombie; only a changed win.screen identity does.
    global _modal_running, _last_screen_ptr, _restart_requested
    if _modal_stop:
        return None  # addon is unregistering -- stop watching for good
    win = bpy.context.window
    screen_ptr = win.screen.as_pointer() if win is not None else None
    screen_changed = _last_screen_ptr is not None and screen_ptr != _last_screen_ptr
    _last_screen_ptr = screen_ptr
    if screen_changed and _modal_running:
        # ask the (possibly zombied) instance to cancel; its own timer still
        # fires every 0.1s even when zombied, so it will see this shortly --
        # next tick will find _modal_running False and start a fresh one.
        _restart_requested = True
        return 0.15
    if _modal_is_alive():
        return 0.5
    _modal_running = False
    # unconditional and defensive: hasattr(bpy.types, "BLENDERSHELF_OT_modal")
    # turned out to be an unreliable way to check this (observed returning
    # False for classes that were, in fact, still registered -- confirmed via
    # bpy.ops.blender_shelf.modal.get_rna_type() succeeding regardless), so a
    # guarded "register only if missing" check was itself the bug: it kept
    # calling register_class on an already-registered class every 0.5s,
    # raising ValueError (Blender does NOT raise RuntimeError for this, only
    # the old comment assumed so), uncaught, permanently killing this timer
    # on its very first tick. Just try it and swallow either exception type.
    try:
        bpy.utils.register_class(BLENDERSHELF_OT_modal)
    except (RuntimeError, ValueError):
        pass
    win = bpy.context.window
    if win is None:
        return 0.5
    for area in win.screen.areas:
        if area.type == 'VIEW_3D':
            for region in area.regions:
                if region.type == 'WINDOW':
                    try:
                        with bpy.context.temp_override(window=win, area=area, region=region):
                            bpy.ops.blender_shelf.modal('INVOKE_DEFAULT')
                    except Exception:
                        return 0.5
                    return 0.5
    return 0.5


classes = (
    BLENDERSHELF_OT_add_roundcube,
    BLENDERSHELF_button_item,
    BLENDERSHELF_command_param,
    BLENDERSHELF_UL_buttons,
    BlenderShelfPreferences,
    BLENDERSHELF_OT_pref_add,
    BLENDERSHELF_OT_pref_remove,
    BLENDERSHELF_OT_pref_move,
    BLENDERSHELF_OT_start_move_button,
    BLENDERSHELF_OT_add_separator,
    BLENDERSHELF_MT_shelf_button_context,
    BLENDERSHELF_OT_copy_button,
    BLENDERSHELF_OT_edit_script,
    BLENDERSHELF_OT_apply_script,
    BLENDERSHELF_OT_edit_params,
    BLENDERSHELF_OT_pref_preset_position,
    BLENDERSHELF_OT_reset_appearance,
    BLENDERSHELF_OT_pick_icon,
    BLENDERSHELF_OT_check_update,
    BLENDERSHELF_OT_export_settings,
    BLENDERSHELF_OT_import_settings,
    BLENDERSHELF_OT_run_command,
    BLENDERSHELF_MT_pie,
    BLENDERSHELF_OT_modal,
    BLENDERSHELF_OT_add_from_context,
    BLENDERSHELF_OT_add_to_pie,
)


def register():
    global _draw_handle, _modal_stop, _icon_previews, _last_alive, _last_screen_ptr, _restart_requested
    _icon_previews = bpy.utils.previews.new()
    for cls in classes:
        try:
            bpy.utils.register_class(cls)
        except (RuntimeError, ValueError):
            # a stale registration survived (a previous disable's modal loop
            # hasn't fully unregistered yet -- see _unregister_modal_when_stopped
            # -- or some other leftover from an earlier reload/disable cycle).
            # Previously only RuntimeError was caught here and only for the
            # modal class; Blender actually raises ValueError for "already
            # registered", so any OTHER class hitting this uncaught aborted
            # registration of everything after it in this loop -- a single
            # stale class silently broke the whole shelf, not just itself.
            pass
    prefs = get_prefs()
    if prefs is not None:
        if not _load_config(prefs):
            _seed_default_buttons(prefs)
    _register_keymap()
    _draw_handle = bpy.types.SpaceView3D.draw_handler_add(draw_shelf, (), 'WINDOW', 'POST_PIXEL')
    _modal_stop = False
    # a stale _last_alive surviving a quick disable/re-enable (module globals
    # aren't reset unless Blender fully re-imports the file) could otherwise
    # make _modal_is_alive() report "alive" for up to _MODAL_HEARTBEAT_TIMEOUT
    # seconds before any instance in *this* session has actually run.
    _last_alive = 0.0
    _last_screen_ptr = None
    _restart_requested = False
    # persistent=True -- without it Blender silently drops this timer on the
    # next "load a new file/scene in this window" (File > New, opening a
    # different .blend, ...), since bpy.app.timers are tied to the current
    # file session by default. register() only runs once per addon-enable,
    # not per file load, so losing the timer here also permanently loses
    # the one thing that self-heals the modal operator if THAT dies on the
    # same file load (which it does, the same way it already does on a
    # workspace-tab switch -- see _start_modal()'s own docstring). Net
    # effect without this flag: shelf hangs unresponsive after loading a
    # new scene, since the draw handler itself (registered on the Space
    # *type*, not per-file) keeps rendering it, but nothing is left alive
    # to notice or restart the dead click-handling modal underneath it.
    bpy.app.timers.register(_start_modal, first_interval=0.2, persistent=True)
    if hasattr(bpy.types, "UI_MT_button_context_menu"):
        bpy.types.UI_MT_button_context_menu.append(_shelf_context_menu_draw)


def unregister():
    global _draw_handle, _modal_stop, _hover_index, _pressed_index
    global _export_hover, _export_pressed, _icon_previews
    global _orient_hover, _drag_hover, _dragging_shelf, _drag_live_margins
    global _moving_index, _move_insert_gap
    _modal_stop = True
    _hover_index = None
    _pressed_index = None
    _export_hover = False
    _export_pressed = False
    _orient_hover = False
    _drag_hover = False
    _dragging_shelf = False
    _drag_live_margins = None
    _moving_index = None
    _move_insert_gap = None
    _unregister_keymap()
    if hasattr(bpy.types, "UI_MT_button_context_menu"):
        try:
            bpy.types.UI_MT_button_context_menu.remove(_shelf_context_menu_draw)
        except ValueError:
            pass
    if _draw_handle is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, 'WINDOW')
        _draw_handle = None
    for cls in reversed(classes):
        if cls is BLENDERSHELF_OT_modal:
            continue  # only safe to unregister once its instance has actually stopped
        try:
            bpy.utils.unregister_class(cls)
        except (RuntimeError, ValueError):
            pass
    if _modal_is_alive():
        bpy.app.timers.register(_unregister_modal_when_stopped, first_interval=0.05)
    else:
        try:
            bpy.utils.unregister_class(BLENDERSHELF_OT_modal)
        except (RuntimeError, ValueError):
            pass
    _icon_textures.clear()
    if _icon_previews is not None:
        bpy.utils.previews.remove(_icon_previews)
        _icon_previews = None
