import os
import sys
import time
import subprocess
from datetime import datetime
from pathlib import Path
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
import agentops
import threading
from crewai.agents.parser import AgentAction, AgentFinish

# =====================================================================
# VISIBILITY LAYER - heartbeat + step-by-step agent trace
# =====================================================================

_last_activity  = [time.time()]
_heartbeat_stop = threading.Event()


def _heartbeat_worker(interval=15):
    while not _heartbeat_stop.wait(interval):
        idle = int(time.time() - _last_activity[0])
        ts   = datetime.now().strftime("%H:%M:%S")
        print(f"  [{ts}] ... still running (last agent activity {idle}s ago)", flush=True)


def start_heartbeat(interval=15):
    _heartbeat_stop.clear()
    t = threading.Thread(target=_heartbeat_worker, args=(interval,), daemon=True)
    t.start()
    return t


def stop_heartbeat():
    _heartbeat_stop.set()


def _touch():
    _last_activity[0] = time.time()


def make_step_callback(feature_id):
    """Returned function is called after every agent Thought/Action/Observation."""
    step_num = [0]
    def on_step(agent_output):
        _touch()
        step_num[0] += 1
        ts = datetime.now().strftime("%H:%M:%S")
        if isinstance(agent_output, AgentAction):
            tool_name  = getattr(agent_output, "tool", "?")
            tool_input = str(getattr(agent_output, "tool_input", ""))[:120].replace("\n", " ")
            print(f"  [{ts}] [{feature_id}] Step {step_num[0]:02d} | TOOL  -> {tool_name}({tool_input})", flush=True)
        elif isinstance(agent_output, AgentFinish):
            out = str(getattr(agent_output, "output", ""))[:150].replace("\n", " ")
            print(f"  [{ts}] [{feature_id}] Step {step_num[0]:02d} | DONE  -> {out}", flush=True)
        else:
            print(f"  [{ts}] [{feature_id}] Step {step_num[0]:02d} | STEP  -> {type(agent_output).__name__}", flush=True)
    return on_step


def make_task_callback(feature_id):
    """Returned function is called when each Task finishes."""
    def on_task(task_output):
        _touch()
        ts  = datetime.now().strftime("%H:%M:%S")
        out = str(task_output)[:200].replace("\n", " ")
        print(f"\n  [{ts}] [{feature_id}] TASK COMPLETE -> {out}\n", flush=True)
    return on_task


METROSTACK_DIR  = Path(r"C:\Users\USER\Desktop\MetroStack")
BACKEND_DIR     = METROSTACK_DIR / "backend"
TESTS_DIR       = METROSTACK_DIR / "tests" / "audit"
VENV_PYTHON     = METROSTACK_DIR / "venv" / "Scripts" / "python.exe"
AUDIT_REPORT    = METROSTACK_DIR / "audit_report.md"
SESSION_STATE   = METROSTACK_DIR / "audit_session_state.json"
MAX_RETRIES     = 3

TESTS_DIR.mkdir(parents=True, exist_ok=True)

senior_llm = LLM(
    model="llama-3.2-3b-instruct-q4_k_m.gguf",
    base_url="http://127.0.0.1:8081/v1",
    api_key="not-needed",
    temperature=0.1,
    max_tokens=8192,
    timeout=360,
)

junior_llm = LLM(
    model="stable-code-3b.Q4_K_M.gguf",
    base_url="http://127.0.0.1:8080/v1",
    api_key="not-needed",
    temperature=0.2,
    max_tokens=8192,
    timeout=360,
)

# AGENTOPS_KEY = os.environ.get("AGENTOPS_API_KEY", "214bffc9-2e26-4854-8118-ec5bc0e50391")
# agentops.init(api_key=AGENTOPS_KEY, default_tags=["metro-stack-crew", "local-llm", "audit-pipeline"])

@tool("read_file")
def read_file(relative_path: str) -> str:
    """Read a file from the MetroStack backend directory.
    Pass a path relative to the backend root e.g. 'routers/projects.py'
    Returns the full file contents."""
    target = BACKEND_DIR / relative_path.lstrip("/\\")
    if not target.exists():
        return f"ERROR: File not found: {target}"
    try:
        return target.read_text(encoding="utf-8")
    except Exception as e:
        return f"ERROR reading {target}: {e}"

@tool("list_directory")
def list_directory(relative_path: str = "") -> str:
    """List all files inside the MetroStack backend directory.
    Pass a path relative to backend root, or empty string for the root.
    Returns a file tree."""
    target = BACKEND_DIR / relative_path.lstrip("/\\")
    if not target.exists():
        return f"ERROR: Directory not found: {target}"
    lines = []
    for p in sorted(target.rglob("*")):
        if any(part in {".venv", "venv", "__pycache__", ".git", "node_modules"}
               for part in p.parts):
            continue
        indent = "  " * (len(p.relative_to(target).parts) - 1)
        lines.append(f"{indent}{p.name}{'/' if p.is_dir() else ''}")
    return "\n".join(lines) if lines else "(empty)"

@tool("write_test_file")
def write_test_file(filename: str, content: str) -> str:
    """Write a pytest test file into the audit tests directory.
    filename: just the filename e.g. 'test_projects.py'
    content: full Python source of the test file.
    Returns confirmation or error."""
    dest = TESTS_DIR / filename
    try:
        dest.write_text(content, encoding="utf-8")
        return f"OK: Written to {dest}"
    except Exception as e:
        return f"ERROR writing {dest}: {e}"

@tool("run_pytest")
def run_pytest(filename: str) -> str:
    """Run a pytest file from the audit tests directory using the MetroStack venv.
    filename: just the filename e.g. 'test_projects.py'
    Returns full pytest stdout+stderr."""
    test_file = TESTS_DIR / filename
    if not test_file.exists():
        return f"ERROR: Test file not found: {test_file}"
    try:
        result = subprocess.run(
            [str(VENV_PYTHON), "-m", "pytest", str(test_file), "-v", "--tb=short", "--no-header"],
            capture_output=True,
            text=True,
            cwd=str(METROSTACK_DIR),
            timeout=240,
        )
        output = result.stdout + result.stderr
        return output if output.strip() else "(no output)"
    except subprocess.TimeoutExpired:
        return "ERROR: pytest timed out after 120 seconds"
    except Exception as e:
        return f"ERROR running pytest: {e}"

AUDIT_FEATURES = [
    {
        "id":   "PROJ-01",
        "name": "Project Management",
        "description": """
Verify the following by reading source and writing tests:
  - Create a project (POST) with part_number, revision, description
  - List all projects (GET) returns correct schema
  - Update project fields (PATCH/PUT)
  - Delete a project (DELETE)
  - Project status field cycles: pending -> ready -> aligned -> analyzed
  - part_number, revision, description fields exist on the model
Key files: routers/projects.py, models.py or models/project.py, schemas.py or schemas/project.py
        """.strip(),
    },
    {
        "id":   "FILE-01",
        "name": "File Upload & Processing",
        "description": """
Verify the following by reading source and writing tests:
  - Upload endpoint accepts CAD formats: STL, OBJ, PLY, STEP, IGES
  - Upload endpoint accepts Scan formats: E57, LAS, LAZ, PLY, PCD, XYZ, CSV
  - File size validation enforces 2 GB limit
  - Mesh repair: fill holes, fix normals, remove degenerate faces
  - Background processing task created on upload
  - Status polling endpoint returns current processing state
Key files: routers/files.py or routers/upload.py, services/mesh_repair.py, tasks.py
        """.strip(),
    },
    {
        "id":   "ALIGN-01",
        "name": "Alignment",
        "description": """
Verify the following by reading source and writing tests:
  - ICP alignment (Point-to-Plane, 200 iterations) is implemented
  - FGR alignment using FPFH features is implemented
  - Datum-constrained alignment locks specified degrees of freedom
  - Quality metrics returned: RMSE, fitness score, inlier count
  - 4x4 transformation matrix stored to database
Key files: routers/alignment.py, services/alignment.py, models.py (transformation_matrix field)
        """.strip(),
    },
    {
        "id":   "DEV-01",
        "name": "Deviation Analysis",
        "description": """
Verify the following by reading source and writing tests:
  - Signed point-to-CAD distance computed (+ outside, - inside)
  - Statistics computed: Min, Max, Mean, RMS, P95, P99
  - Bulk PostgreSQL insert handles large point sets
  - Color scale bounds configurable (min_val, max_val parameters)
  - Heatmap data endpoint returns per-point deviation values
Key files: routers/deviation.py, services/deviation.py, models.py (deviation table)
        """.strip(),
    },
    {
        "id":   "GDT-01",
        "name": "GD&T Analysis",
        "description": """
Verify the following by reading source and writing tests:
  - All 11 characteristics implemented: Flatness, Straightness, Circularity,
    Cylindricity, Position, Parallelism, Perpendicularity, Angularity,
    Profile of Surface, Circular Runout, Total Runout
  - Minimum Zone fitting used (not least-squares)
  - Each characteristic returns: measured_value, tolerance, pass_fail boolean
Key files: routers/gdt.py, services/gdt.py or analysis/gdt/
        """.strip(),
    },
    {
        "id":   "WALL-01",
        "name": "Wall Thickness",
        "description": """
Verify the following by reading source and writing tests:
  - Ray-cast thickness measurement with configurable sample count (default 20k)
  - Statistics returned: Min, Max, Mean, Std Dev
  - Viridis colormap values computed per sample point
  - Open boundary detection implemented
Key files: routers/thickness.py, services/thickness.py or analysis/wall_thickness.py
        """.strip(),
    },
    {
        "id":   "VIZ-01",
        "name": "3D Visualization",
        "description": """
Verify the following by reading source and writing tests:
  - Backend endpoints serve mesh/point-cloud data for Three.js
  - Deviation heatmap data endpoint returns per-vertex color values
  - Wall thickness heatmap data endpoint returns per-point color values
  - Point cloud endpoint supports filtering to 500k points max
  - Mesh data returns vertices + faces in Three.js-compatible format
Key files: routers/visualization.py or routers/mesh.py, services/visualization.py
        """.strip(),
    },
]

auditor = Agent(
    role="Source Code Auditor",
    goal=(
        "Use list_directory and read_file tools to locate and read every relevant "
        "source file for the feature being audited. Produce a precise audit report: "
        "which sub-features are FOUND, MISSING, or PARTIAL with file:function evidence."
    ),
    backstory=(
        "A senior code reviewer specializing in FastAPI backends. Methodical and "
        "evidence-based. Every claim references a specific file and function name. "
        "Never assumes something works without reading the actual code."
    ),
    llm=senior_llm,
    tools=[read_file, list_directory],
    verbose=True,
    allow_delegation=False,
    max_iter=8,
)

tester = Agent(
    role="Test Engineer",
    goal=(
        "Using the auditor's findings, write a complete pytest file with write_test_file, "
        "run it with run_pytest, and report exact results. "
        "Tests import directly from backend source. Mock DB and external calls. "
        "If imports fail, use read_file to check actual paths and fix the test."
    ),
    backstory=(
        "A QA engineer expert in offline pytest suites for FastAPI. Uses TestClient, "
        "mocks SQLAlchemy sessions, patches external services. Only tests what the "
        "auditor confirmed exists in source."
    ),
    llm=junior_llm,
    tools=[write_test_file, run_pytest, read_file],
    verbose=True,
    allow_delegation=False,
    max_iter=6,
)

qa_gate = Agent(
    role="QA Gate",
    goal=(
        "Read pytest output from the tester. Output exactly:\n"
        "GATE: PASS\nCOVERAGE: <sub-features confirmed>\n"
        "or\nGATE: FAIL\nREASON: <one sentence>"
    ),
    backstory=(
        "A strict release gate. All tests must pass, no import errors, "
        "no collection errors, at least one test collected. "
        "A file that fails to import is always GATE: FAIL."
    ),
    llm=senior_llm,
    verbose=True,
    allow_delegation=False,
    max_iter=2,
)

def run_audit(feature: dict) -> dict:
    fid   = feature["id"]
    fname = feature["name"]
    fdesc = feature["description"]
    result = {
        "id": fid, "name": fname, "status": "flagged",
        "attempts": 0, "reason": "", "coverage": "", "output": "",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        result["attempts"] = attempt
        print(f"\n{'='*60}")
        print(f"  Auditing : {fid} - {fname}  |  Attempt {attempt}/{MAX_RETRIES}")
        print(f"{'='*60}\n")

        audit_task = Task(
            description=(
                f"Feature: {fid} - {fname}\nBackend: {BACKEND_DIR}\n\n"
                f"1. Call list_directory('') to get the full file tree.\n"
                f"2. Read every relevant file.\n"
                f"3. For each sub-feature state FOUND/MISSING/PARTIAL with file:function.\n\n"
                f"Requirements:\n{fdesc}\n\nAttempt {attempt}/{MAX_RETRIES}."
            ),
            expected_output="Line-by-line audit: FOUND/MISSING/PARTIAL with evidence.",
            agent=auditor,
        )

        test_filename = f"test_{fid.lower().replace('-', '_')}.py"
        test_task = Task(
            description=(
                f"Feature: {fid} - {fname}\nTest file: {test_filename}\n\n"
                f"1. Call write_test_file('{test_filename}', <content>) with a complete pytest file.\n"
                f"   - Import from backend modules (insert sys.path if needed)\n"
                f"   - Mock SQLAlchemy with unittest.mock.MagicMock\n"
                f"   - Use FastAPI TestClient for endpoint tests\n"
                f"   - One test per FOUND/PARTIAL sub-feature only\n"
                f"2. Call run_pytest('{test_filename}') and report the full output.\n"
                f"3. If imports fail, read_file to check paths, fix, and rerun.\n\n"
                f"Attempt {attempt}/{MAX_RETRIES}."
            ),
            expected_output="Full pytest output with pass/fail counts and any errors.",
            agent=tester,
            context=[audit_task],
        )

        gate_task = Task(
            description=(
                f"Feature: {fid} - {fname}\n\n"
                f"Review the pytest output above. PASS criteria:\n"
                f"  1. All tests passed (exit code 0)\n"
                f"  2. No ImportError or ModuleNotFoundError\n"
                f"  3. No collection errors\n"
                f"  4. At least one test ran\n\n"
                f"Respond with exactly:\n"
                f"GATE: PASS\nCOVERAGE: <comma-separated confirmed sub-features>\n"
                f"or\nGATE: FAIL\nREASON: <one sentence>\n\n"
                f"Attempt {attempt}/{MAX_RETRIES}."
            ),
            expected_output="GATE: PASS with COVERAGE, or GATE: FAIL with REASON.",
            agent=qa_gate,
            context=[audit_task, test_task],
        )

        crew = Crew(
            agents=[auditor, tester, qa_gate],
            tasks=[audit_task, test_task, gate_task],
            process=Process.sequential,
            verbose=True,
            full_output=True,
        )

        try:
            output = str(crew.kickoff())
            result["output"] = output
            passed = "GATE: PASS" in output
            for line in output.splitlines():
                if line.startswith("COVERAGE:"):
                    result["coverage"] = line.replace("COVERAGE:", "").strip()
                if line.startswith("REASON:"):
                    result["reason"] = line.replace("REASON:", "").strip()
            if passed:
                result["status"] = "passed"
                print(f"\n  GATE PASSED - {fid} verified on attempt {attempt}\n")
                break
            else:
                print(f"\n  GATE FAILED (attempt {attempt}) - {result['reason']}\n")
                if attempt == MAX_RETRIES:
                    result["status"] = "flagged"
                    print(f"  Flagged after {MAX_RETRIES} attempts - moving on\n")
        except Exception as exc:
            result["output"] = result["reason"] = str(exc)
            print(f"\n  Crew error on attempt {attempt}: {exc}\n")
            if attempt == MAX_RETRIES:
                result["status"] = "flagged"

        time.sleep(2)

    return result

def write_audit_report(results: list) -> None:
    passed  = [r for r in results if r["status"] == "passed"]
    flagged = [r for r in results if r["status"] == "flagged"]
    lines = [
        "# MetroStack - Existing Feature Audit Report",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Backend:** `{BACKEND_DIR}`",
        "",
        "## Summary",
        f"| | Count |",
        f"|---|---|",
        f"| Features audited | {len(results)} |",
        f"| Verified | {len(passed)} |",
        f"| Flagged | {len(flagged)} |",
        "",
        "## Results",
        "",
    ]
    for r in results:
        icon = "PASS" if r["status"] == "passed" else "FLAGGED"
        lines.append(f"### [{icon}] {r['id']} - {r['name']}")
        lines.append(f"- Attempts: {r['attempts']}/{MAX_RETRIES}")
        if r["coverage"]:
            lines.append(f"- Verified: {r['coverage']}")
        if r["reason"]:
            lines.append(f"- Reason: {r['reason']}")
        lines.append("")
    report = "\n".join(lines)
    AUDIT_REPORT.write_text(report, encoding="utf-8")
    print(f"\n[+] Report: {AUDIT_REPORT}\n")
    print(report)

# =====================================================================
# SESSION STATE — survives restarts
# =====================================================================

def load_session_state() -> dict:
    """
    Load previous run state from disk.
    Returns dict keyed by feature id:
      { "PROJ-01": {"status": "passed", "attempts": 1, ...}, ... }
    """
    if SESSION_STATE.exists():
        try:
            import json
            return json.loads(SESSION_STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_session_state(results: list) -> None:
    """Persist current results to disk so restarts resume from here."""
    import json
    state = {r["id"]: r for r in results}
    SESSION_STATE.write_text(
        json.dumps(state, indent=2, default=str),
        encoding="utf-8"
    )


# =====================================================================
# ENTRY POINT
# =====================================================================

if __name__ == "__main__":
    import json

    print("\n[+] MetroStack Audit Pipeline")
    print(f"    Backend  : {BACKEND_DIR}")
    print(f"    Tests    : {TESTS_DIR}")
    print(f"    Features : {len(AUDIT_FEATURES)}")

    # ── Load any previous session state ───────────────────────────
    previous = load_session_state()

    if previous:
        done    = [fid for fid, r in previous.items() if r["status"] == "passed"]
        flagged = [fid for fid, r in previous.items() if r["status"] == "flagged"]
        print(f"\n[+] Resuming previous session:")
        print(f"    Already passed  : {done    or 'none'}")
        print(f"    Previously flagged (will retry) : {flagged or 'none'}")
    else:
        print("\n[+] No previous session found — starting fresh.")

    # ── Decide which features to run ──────────────────────────────
    # Skip features that already passed.
    # Re-run features that were flagged (in case code has been fixed).
    features_to_run = []
    audit_results   = []

    for feature in AUDIT_FEATURES:
        fid = feature["id"]
        if fid in previous and previous[fid]["status"] == "passed":
            print(f"    SKIPPING {fid} — already passed in previous session")
            audit_results.append(previous[fid])   # carry forward the result
        else:
            if fid in previous:
                print(f"    QUEUED   {fid} — was flagged, will retry")
            else:
                print(f"    QUEUED   {fid} — not yet run")
            features_to_run.append(feature)

    print(f"\n[+] Running {len(features_to_run)} feature(s) this session.\n")

    try:
        for feature in features_to_run:
            result = run_audit(feature)
            audit_results.append(result)
            save_session_state(audit_results)   # save after EVERY feature
            time.sleep(3)

        print("\n[+] All features processed.")
        write_audit_report(audit_results)
        agentops.end_session("Success")

    except KeyboardInterrupt:
        print("\n[!] Interrupted — progress saved.")
        save_session_state(audit_results)
        if audit_results:
            write_audit_report(audit_results)
        agentops.end_session("Fail")
        sys.exit(0)

    except Exception as exc:
        print(f"\n[!] Crashed: {exc} — progress saved.")
        save_session_state(audit_results)
        if audit_results:
            write_audit_report(audit_results)
        agentops.end_session("Fail")
        raise
