# CLAUDE.md

## Workflow Rules
- NEVER commit, push, or create PRs unless explicitly asked to do so.
- Always wait for explicit user confirmation before any git operations that affect the repository.
- Always run `uv run ruff check src/ tests/` and `uv run mypy src/` before committing. Fix any errors before creating the commit.

## Project Structure
- Monorepo: Python backend (`src/uipath/dev/`) + React frontend (`src/uipath/dev/server/frontend/`)
- Frontend: Vite + React 19 + React Flow v11 + Tailwind v4 + Zustand
- Backend: FastAPI + WebSocket, serves static frontend build
- Graph layout: ELK (elkjs) for layered/hierarchical graph visualization
- Build: `npm run build` in `frontend/` outputs to `../static/`

## React Flow + ELK Integration

### Node Types
- Never use `"default"` as a custom node type name — React Flow's built-in CSS (`.react-flow__node-default`) renders a white box behind it. Use `"defaultNode"` instead.
- All fallback types in `runElkLayout` must match registered `nodeTypes` keys exactly.

### Handles
- Handles are hidden via CSS (`opacity: 0, width: 0, height: 0`). This breaks `smoothstep`/`bezier` edge types.
- Always use the custom `"elk"` edge type that draws from explicit coordinates. Never fall back to `"smoothstep"`.

### Edge Rendering
- ELK provides `sections` (startPoint, bendPoints, endPoint) for edge routes.
- For compound node edges, section coords are relative to the compound node — add parent `(x, y)` offset.
- Build a `nodeRects` lookup after layout for fallback: source bottom-center → target top-center when ELK doesn't provide sections.
- Don't mix ELK bendPoints with manually computed endpoints — use ELK sections as-is or compute everything from scratch.

### Subgraph / Compound Nodes
- ELK child IDs: `${parentId}/${childId}` to avoid collisions. Same for edge IDs.
- React Flow: children use `parentNode` + `extent: "parent"`, positions relative to parent.
- Group node must come before its children in the nodes array.
- Delete `width`/`height` on compound ELK nodes — let ELK compute from children + padding.

### Tailwind CSS Conflicts
- Tailwind preflight sets `svg { overflow: hidden }` which clips React Flow's edge SVG layer.
- Fix: `.react-flow__edges { overflow: visible !important }`.

### Node Sizing
- Width: `Math.max(80, label.length * 8 + 32)` — no max cap.
- All custom nodes must use `overflow-hidden` + `text-ellipsis` on the outer div.

### ELK Options
```
algorithm: layered, direction: DOWN, edgeRouting: ORTHOGONAL
crossingMinimization: LAYER_SWEEP, nodePlacement: NETWORK_SIMPLEX
portAlignment: CENTER, considerModelOrder: NODES_AND_EDGES
```
