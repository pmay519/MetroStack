"""
app/services/ingest.py
File ingestion pipeline — loads CAD meshes and point clouds,
validates them, runs mesh repair, and extracts metadata.
"""

from __future__ import annotations

import logging
from pathlib import Path
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)

# Supported formats
CAD_FORMATS  = {".stl", ".obj", ".ply", ".off", ".glb", ".gltf"}
SCAN_FORMATS = {".ply", ".pcd", ".xyz", ".xyzn", ".xyzrgb",
                ".pts", ".csv", ".las", ".laz", ".e57"}
STEP_FORMATS = {".step", ".stp", ".iges", ".igs"}  # requires pythonocc


@dataclass
class MeshInfo:
    vertex_count: int
    face_count: int
    is_watertight: bool
    bbox_min: tuple[float, float, float]
    bbox_max: tuple[float, float, float]
    repair_log: str
    mesh: object  # trimesh.Trimesh — avoid import at module level


@dataclass
class CloudInfo:
    point_count: int
    has_normals: bool
    has_intensity: bool
    has_rgb: bool
    bbox_min: tuple[float, float, float]
    bbox_max: tuple[float, float, float]
    units: str | None
    cloud: object  # open3d.geometry.PointCloud


# ── CAD / Mesh ingestion ──────────────────────────────────────────────────────

def load_cad_mesh(filepath: str | Path) -> MeshInfo:
    """
    Load a CAD mesh file (STL / OBJ / PLY / OFF).
    Runs automatic repair and returns mesh metadata.

    Raises:
        ValueError: if file format unsupported or mesh has zero faces.
        RuntimeError: if trimesh cannot load the file.
    """
    import trimesh

    path = Path(filepath)
    ext  = path.suffix.lower()

    if ext in STEP_FORMATS:
        return _load_step_mesh(path)

    if ext not in CAD_FORMATS:
        raise ValueError(
            f"Unsupported CAD format: '{ext}'. "
            f"Supported: {sorted(CAD_FORMATS | STEP_FORMATS)}"
        )

    logger.info(f"Loading CAD mesh: {path.name}")

    try:
        loaded = trimesh.load(str(path), force="mesh", process=False)
    except Exception as exc:
        raise RuntimeError(f"trimesh failed to load '{path.name}': {exc}") from exc

    # force="mesh" may return Scene for multi-body files — flatten it
    if hasattr(loaded, "dump"):
        meshes = loaded.dump(concatenate=True)
    else:
        meshes = loaded

    if not isinstance(meshes, trimesh.Trimesh) or len(meshes.faces) == 0:
        raise ValueError(f"'{path.name}' contains no valid mesh geometry.")

    repair_notes: list[str] = []

    # ── Mesh repair pipeline ──────────────────────────────────────────────────

    # 1. Remove duplicate / degenerate faces
    before_faces = len(meshes.faces)
    meshes.remove_duplicate_faces()
    meshes.remove_degenerate_faces()
    removed = before_faces - len(meshes.faces)
    if removed:
        repair_notes.append(f"Removed {removed} degenerate/duplicate faces.")

    # 2. Fix winding order consistency
    if not meshes.is_winding_consistent:
        trimesh.repair.fix_winding(meshes)
        repair_notes.append("Fixed inconsistent face winding.")

    # 3. Fix inverted normals (outward-pointing)
    trimesh.repair.fix_normals(meshes)

    # 4. Fill small holes (<=100 edge boundary loop)
    if not meshes.is_watertight:
        pass  # fill_holes disabled - can hang
        if meshes.is_watertight:
            repair_notes.append("Filled open boundary holes — mesh is now watertight.")
        else:
            repair_notes.append(
                "Mesh has open boundaries that could not be auto-repaired. "
                "Wall thickness analysis may be inaccurate."
            )

    bounds = meshes.bounds  # shape (2, 3): [[min_x,min_y,min_z],[max_x,max_y,max_z]]

    return MeshInfo(
        vertex_count = len(meshes.vertices),
        face_count   = len(meshes.faces),
        is_watertight = meshes.is_watertight,
        bbox_min     = tuple(bounds[0].tolist()),
        bbox_max     = tuple(bounds[1].tolist()),
        repair_log   = "; ".join(repair_notes) if repair_notes else "No repairs needed.",
        mesh         = meshes,
    )


def _load_step_mesh(path: Path) -> MeshInfo:
    """
    STEP / IGES via pythonocc-core → tessellate to trimesh.
    pythonocc is an optional heavy dependency — graceful fallback.
    """
    try:
        from OCC.Core.BRep import BRep_Builder
        from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
        from OCC.Core.STEPControl import STEPControl_Reader
        from OCC.Core.TopExp import TopExp_Explorer
        from OCC.Core.TopAbs import TopAbs_FACE
        from OCC.Extend.TopologyUtils import TopologyExplorer
        import trimesh
    except ImportError:
        raise RuntimeError(
            "STEP/IGES support requires pythonocc-core. "
            "Install it via conda: `conda install -c conda-forge pythonocc-core`"
        )

    reader = STEPControl_Reader()
    status = reader.ReadFile(str(path))
    if status != 1:
        raise RuntimeError(f"STEP reader failed on '{path.name}' (status={status})")

    reader.TransferRoots()
    shape = reader.OneShape()

    # Tessellate at 0.1mm linear deflection
    mesh_algo = BRepMesh_IncrementalMesh(shape, 0.1, False, 0.5)
    mesh_algo.Perform()

    # Extract triangles via topology explorer
    vertices, faces = [], []
    vert_offset = 0

    explorer = TopologyExplorer(shape)
    for face in explorer.faces():
        from OCC.Core.BRep import BRep_Tool
        from OCC.Core.TopLoc import TopLoc_Location
        location = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation_s(face, location)
        if triangulation is None:
            continue
        for i in range(1, triangulation.NbNodes() + 1):
            node = triangulation.Node(i)
            vertices.append([node.X(), node.Y(), node.Z()])
        for i in range(1, triangulation.NbTriangles() + 1):
            tri = triangulation.Triangle(i)
            n1, n2, n3 = tri.Get()
            faces.append([n1 - 1 + vert_offset,
                          n2 - 1 + vert_offset,
                          n3 - 1 + vert_offset])
        vert_offset += triangulation.NbNodes()

    import trimesh
    tm = trimesh.Trimesh(
        vertices=np.array(vertices),
        faces=np.array(faces),
        process=True
    )
    bounds = tm.bounds
    return MeshInfo(
        vertex_count  = len(tm.vertices),
        face_count    = len(tm.faces),
        is_watertight = tm.is_watertight,
        bbox_min      = tuple(bounds[0].tolist()),
        bbox_max      = tuple(bounds[1].tolist()),
        repair_log    = "Tessellated from STEP/IGES via pythonocc.",
        mesh          = tm,
    )


# ── Point Cloud ingestion ─────────────────────────────────────────────────────

def load_point_cloud(filepath: str | Path,
                     voxel_downsample_mm: float | None = None) -> CloudInfo:
    """
    Load a scan point cloud from any supported format.

    Args:
        filepath: path to the file.
        voxel_downsample_mm: if set, voxel-downsample large clouds.
            Automatically applied if point count > 5M.

    Raises:
        ValueError: unsupported format or empty cloud.
    """
    import open3d as o3d

    path = Path(filepath)
    ext  = path.suffix.lower()

    if ext not in SCAN_FORMATS:
        raise ValueError(
            f"Unsupported scan format: '{ext}'. "
            f"Supported: {sorted(SCAN_FORMATS)}"
        )

    logger.info(f"Loading point cloud: {path.name}")

    units = None

    if ext in {".las", ".laz"}:
        pcd, units = _load_las(path)
    elif ext == ".e57":
        pcd, units = _load_e57(path)
    elif ext in {".csv", ".pts"}:
        pcd = _load_csv_pts(path)
    else:
        # Open3D native: PLY, PCD, XYZ, XYZN, XYZRGB
        pcd = o3d.io.read_point_cloud(str(path))

    if pcd is None or len(pcd.points) == 0:
        raise ValueError(f"'{path.name}' loaded as empty point cloud.")

    pt_count = len(pcd.points)
    logger.info(f"Loaded {pt_count:,} points from {path.name}")

    # Auto-downsample very large clouds
    auto_voxel = None
    if pt_count > 5_000_000 and voxel_downsample_mm is None:
        auto_voxel = 0.2
        logger.info(f"Auto-downsampling large cloud (>{5_000_000:,}) at {auto_voxel}mm voxel")

    effective_voxel = voxel_downsample_mm or auto_voxel
    if effective_voxel:
        pcd = pcd.voxel_down_sample(voxel_size=effective_voxel)
        logger.info(f"After downsample: {len(pcd.points):,} points")

    # Estimate normals if missing (needed for Point-to-Plane ICP)
    has_normals = pcd.has_normals()
    if not has_normals:
        logger.info("Estimating normals via Open3D KDTree search...")
        pcd.estimate_normals(
            search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=2.0, max_nn=30)
        )
        pcd.orient_normals_consistent_tangent_plane(k=15)
        has_normals = True

    pts = np.asarray(pcd.points)
    bbox_min = tuple(pts.min(axis=0).tolist())
    bbox_max = tuple(pts.max(axis=0).tolist())

    return CloudInfo(
        point_count  = len(pcd.points),
        has_normals  = has_normals,
        has_intensity = False,   # updated below per format
        has_rgb      = pcd.has_colors(),
        bbox_min     = bbox_min,
        bbox_max     = bbox_max,
        units        = units,
        cloud        = pcd,
    )


def _load_las(path: Path):
    """LAS/LAZ → Open3D PointCloud via laspy."""
    import laspy
    import open3d as o3d

    las = laspy.read(str(path))
    scale = las.header.scale
    offset = las.header.offset

    x = las.x * scale[0] + offset[0]
    y = las.y * scale[1] + offset[1]
    z = las.z * scale[2] + offset[2]

    pts = np.column_stack([x, y, z])
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(pts)

    # Detect units from header
    units = "m"
    if hasattr(las.header, "vlrs"):
        for vlr in las.header.vlrs:
            desc = getattr(vlr, "description", "").lower()
            if "millimeter" in desc or "mm" in desc:
                units = "mm"

    return pcd, units


def _load_e57(path: Path):
    """E57 → Open3D PointCloud via pye57."""
    try:
        import pye57
    except ImportError:
        raise RuntimeError(
            "E57 support requires pye57. Install: pip install pye57"
        )
    import open3d as o3d

    e57 = pye57.E57(str(path))
    data = e57.read_scan(0, intensity=True, colors=True, ignore_missing_fields=True)

    pts = np.column_stack([data["cartesianX"], data["cartesianY"], data["cartesianZ"]])
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(pts)

    if "colorRed" in data:
        colors = np.column_stack([
            data["colorRed"] / 255.0,
            data["colorGreen"] / 255.0,
            data["colorBlue"] / 255.0,
        ])
        pcd.colors = o3d.utility.Vector3dVector(colors)

    return pcd, "m"


def _load_csv_pts(path: Path):
    """
    Generic CSV / PTS loader.
    Expects at minimum 3 columns: X Y Z
    Optional columns 4,5,6: NX NY NZ  or  R G B
    """
    import open3d as o3d

    try:
        data = np.loadtxt(str(path), comments=["#", "//"], max_rows=10_000_000)
    except Exception as exc:
        raise RuntimeError(f"Failed to parse CSV/PTS '{path.name}': {exc}") from exc

    if data.ndim == 1:
        data = data.reshape(1, -1)

    if data.shape[1] < 3:
        raise ValueError(f"'{path.name}' has fewer than 3 columns — need at least X Y Z.")

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(data[:, :3])

    if data.shape[1] >= 6:
        extra = data[:, 3:6]
        # Heuristic: if values are in 0–255 range → RGB; else normals
        if extra.max() > 1.1:
            pcd.colors = o3d.utility.Vector3dVector(extra / 255.0)
        else:
            pcd.normals = o3d.utility.Vector3dVector(extra)

    return pcd


# ── Utilities ─────────────────────────────────────────────────────────────────

def detect_format(filepath: str | Path) -> str:
    """Return 'cad', 'scan', or 'unknown'."""
    ext = Path(filepath).suffix.lower()
    if ext in CAD_FORMATS | STEP_FORMATS:
        return "cad"
    if ext in SCAN_FORMATS:
        return "scan"
    return "unknown"


def validate_file_size(filepath: str | Path, max_mb: int) -> None:
    size_mb = Path(filepath).stat().st_size / (1024 ** 2)
    if size_mb > max_mb:
        raise ValueError(
            f"File is {size_mb:.0f} MB — exceeds limit of {max_mb} MB."
        )
