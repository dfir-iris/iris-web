# Investigation Graph — design and API contract

Status: implementation in progress on `feature/investigation-graph` (iris-backend, iris-frontend, iris-web).

This document replaces the v3.0.0-beta case graph — a read-only, client-side projection of timeline
events — with a persisted, directed, collaborative property graph of the case. It is the **contract**
between backend and frontend: field names, routes and payloads below are normative.

## 1. Why

User feedback on the beta graph: *not interactive enough*, *directions cannot be seen*, *nodes cannot
be added manually*. Root causes found in the beta implementation:

| # | Defect | Fixed by |
|---|---|---|
| 1 | Asset↔asset edges dropped (`fromIsAsset === toIsAsset` skip) — lateral movement invisible | server-side derivation (§3.3) |
| 2 | `ioc_asset_link` and `parent_event_id` ignored | derived edges (§3.3) |
| 3 | Nodes matched by name/value instead of id — homonyms merge, renames disappear | id-based assembly |
| 4 | Only the first 500 assets / IOCs loaded — silent truncation | server-side assembly, no cap |
| 5 | Pair de-duplication keeps one event per edge | `event_ids[]` on every edge |
| 6 | Opening the detail rail resizes the canvas and `fit()` resets the zoom | new graph component resizes without fitting |
| 7 | Every filter keystroke clears and re-adds the dataset, losing positions | incremental diffing |
| 8 | No direction exists anywhere in the data model | event-link roles + stored directed edges |
| 9 | Nothing to add nodes to — the graph is not stored | stored nodes / edges / views |

The unused v1 tables `case_graph_assets` and `case_graph_links` are dropped.

## 2. Concepts

* **Node key** — every node is addressed by a string `"<kind>:<id>"`.
  Kinds: `asset`, `ioc`, `event`, `evidence`, `task`, `note`, `alert`, `node` (free node, §3.2),
  `case` (another case, cross-case pivot — read-only).
  Example: `asset:12`, `ioc:5`, `node:3`, `case:42`.
* **Stored edge** — a row in `case_graph_edge`, created by an analyst, a module, an import or the AI.
* **Derived edge** — computed on read from existing case data (timeline events, IOC↔asset links,
  parent events). Read-only. When a stored edge links the same ordered pair with the same relation,
  the derived edge is merged into it (its `event_ids` are unioned) instead of being emitted twice.
* **Relation type** — managed catalogue entry (`connected_to`, `lateral_movement`, …) carrying label,
  default direction, colour, line style and STIX mapping.
* **View** — a saved presentation: positions, pinned/hidden/collapsed nodes, filters, layout, viewport,
  time window, optional PNG snapshot (used by reports).

## 3. Data model (alembic revision, one per logical step is fine)

### 3.1 `case_graph_relation_type`

| column | type | notes |
|---|---|---|
| `id` | Integer PK | |
| `name` | String(64) unique, not null | slug, e.g. `lateral_movement` |
| `label` | Text not null | `Lateral movement` |
| `description` | Text | |
| `directed` | Boolean not null default true | default for new edges |
| `color` | String(16) not null default `'slate'` | tailwind palette name, same convention as `asset_flag.color` |
| `line_style` | String(16) not null default `'solid'` | `solid` \| `dashed` \| `dotted` |
| `stix_relationship` | String(64) null | STIX 2.1 relationship_type for export |
| `is_system` | Boolean not null default false | system rows cannot be deleted (label/colour editable) |
| `sort_order` | Integer not null default 0 | |
| `created_at` | DateTime server_default now() | |

Seeded (`is_system = true`), in this order:

| name | label | directed | color | line_style | stix |
|---|---|---|---|---|---|
| `related_to` | Related to | false | slate | dashed | related-to |
| `co_occurs` | Seen together | false | slate | dashed | related-to |
| `connected_to` | Connected to | true | sky | solid | communicates-with |
| `authenticated_to` | Authenticated to | true | indigo | solid | related-to |
| `lateral_movement` | Lateral movement | true | red | solid | related-to |
| `executed_on` | Executed on | true | orange | solid | related-to |
| `dropped` | Dropped | true | amber | solid | drops |
| `downloaded_from` | Downloaded from | true | amber | solid | downloads |
| `resolves_to` | Resolves to | true | teal | solid | resolves-to |
| `beacons_to` | Beacons to | true | rose | solid | beacons-to |
| `exfiltrated_to` | Exfiltrated to | true | fuchsia | solid | exfiltrates-to |
| `owns_account` | Owns account | true | violet | solid | related-to |
| `same_as` | Same as | false | emerald | dotted | duplicate-of |
| `parent_of` | Parent of | true | zinc | dotted | related-to |
| `involved_in` | Involved in | true | slate | dotted | related-to |

`co_occurs`, `parent_of`, `same_as` (when derived) and `involved_in` are the relations used by
derived edges.

### 3.2 `case_graph_node` (free nodes)

Ad-hoc entities that are not (yet) an asset or IOC: an unknown actor, a user account, an
out-of-scope host, a sticky note, a group frame.

| column | type | notes |
|---|---|---|
| `node_id` | BigInteger PK | |
| `node_uuid` | UUID not null, server default `gen_random_uuid()` | |
| `case_id` | FK `cases.case_id` ON DELETE CASCADE, not null, indexed | |
| `label` | Text not null | |
| `node_type` | String(32) not null default `'other'` | `actor` \| `account` \| `infrastructure` \| `malware` \| `note` \| `group` \| `other` |
| `description` | Text | markdown |
| `icon` | String(64) | lucide icon name |
| `color` | String(16) | palette name |
| `tlp_id` | FK `tlp.tlp_id` null | |
| `custom_attributes` | JSONB | |
| `created_by_id` | FK `user.id` null | |
| `created_at`, `updated_at` | DateTime | |

### 3.3 `case_graph_edge`

| column | type | notes |
|---|---|---|
| `edge_id` | BigInteger PK | |
| `edge_uuid` | UUID not null | |
| `case_id` | FK cascade, not null, indexed | |
| `source_kind`, `target_kind` | String(16) not null | node kinds of §2 except `case` |
| `source_id`, `target_id` | BigInteger not null | |
| `relation_type_id` | FK `case_graph_relation_type.id` not null | |
| `directed` | Boolean not null | |
| `label` | Text null | overrides the relation label on the canvas |
| `description` | Text | markdown |
| `confidence` | SmallInteger null | 0–100 |
| `first_seen`, `last_seen` | DateTime null | if null, computed from linked events on read |
| `tlp_id` | FK null | |
| `origin` | String(16) not null default `'manual'` | `manual` \| `ai` \| `module` \| `import` \| `suggestion` |
| `review_state` | String(16) not null default `'accepted'` | `accepted` \| `pending` \| `rejected` |
| `custom_attributes` | JSONB | |
| `created_by_id`, `created_at`, `updated_at` | | |

Constraint: not (`source_kind = target_kind` and `source_id = target_id`).
Index on (`case_id`, `source_kind`, `source_id`) and (`case_id`, `target_kind`, `target_id`).

`case_graph_edge_event` — (`edge_id` FK cascade, `event_id` FK `cases_events.event_id` cascade), PK both.

Referential integrity: when an asset / IOC / event / evidence / task / note / free node is deleted, stored
edges touching it are deleted (business layer, in the same transaction as the delete — the polymorphic
reference cannot be a real FK).

`case_graph_dismissed_suggestion` — (`case_id` FK cascade, `suggestion_key` String(255)), PK both,
plus `dismissed_by_id`, `dismissed_at`.

### 3.4 Event-link roles

Add `role` (String(16), not null, server default `'involved'`) to `case_events_assets` and
`case_events_ioc`. Values: `source` \| `target` \| `involved`.

Events v2 API: `event_assets_roles` and `event_iocs_roles` — objects `{ "<asset_id>": "source", … }` —
are accepted on create/update (optional; ids not listed default to `involved`) and returned on read
alongside the existing `event_assets` / `event_iocs` arrays. Each element of the existing `assets` /
`iocs` read arrays also gains a `role` field.

### 3.5 Derivation rules (read-time)

For every event with `event_in_graph` not false, let S = entities with role `source`, T = `target`,
I = `involved` (entities = linked assets + IOCs):

1. If S and T are both non-empty: a **directed** edge s → t for every (s, t) ∈ S×T. Relation is chosen
   from the event category name (case-insensitive contains): `lateral movement` → `lateral_movement`,
   `exfiltration` → `exfiltrated_to`, `command and control` → `beacons_to`, `execution` → `executed_on`,
   `credential access` / `initial access` with an account → `authenticated_to`; otherwise `connected_to`.
   Entities in I get an undirected `co_occurs` edge to every entity of S ∪ T.
2. Otherwise (no direction information): undirected `co_occurs` edges between every pair of assets;
   each IOC to each asset; IOC↔IOC pairs **only** when the event has no asset (keeps fan-outs from
   exploding into cliques).
3. Edges are keyed by (source key, target key, relation, directed); for undirected edges the pair is
   sorted. Every event contributing to a key is appended to `event_ids`; `first_seen` / `last_seen` are
   min / max of those events' dates.

Additionally:

* `ioc_asset_link` → undirected `related_to` edge `ioc:x — asset:y` with origin `ioc_asset_link`.
* `parent_event_id` → when `include` contains `events`: directed `parent_of` edge `event:parent → event:child`.
* When `include` contains `events`: an `involved_in` edge from each linked entity to `event:<id>`
  (direction entity → event, or event → entity for role `target`).
* Asset IP equal to an IOC value → **suggestion** (§6), never an automatic edge.

## 4. REST API

All routes are under `/api/v2/cases/<int:case_identifier>/graph`. Reads require case `read_only` or
`full_access`; writes require `full_access`. Responses use the standard `response_api_*` envelope.
Every route carries `@api_doc(tags=['Case graph'], summary=...)` and the generated OpenAPI is committed.

### 4.1 `GET /graph`

Query: `include` — comma list among `events,evidences,tasks,notes,alerts,cross_case,suggestions`
(default: none → assets, IOCs, free nodes only). `review_state` — `accepted` (default) or `all`.

```jsonc
{
  "nodes": [
    {
      "key": "asset:12", "kind": "asset", "id": 12,
      "label": "DC01", "subtitle": "10.0.0.5",              // asset ip / ioc type / event date…
      "type": "Windows - DC",                                 // asset type or ioc type name, free node_type
      "icon": "/static/assets/img/graph/windows_server.png",  // asset type icon, compromised variant if compromised
      "compromised": true,                                    // assets only, else null
      "analysis_status": "Started",                           // assets only
      "flags": [{"id": 1, "name": "Isolated", "color": "red", "kind": "status"}],
      "tags": ["dc", "tier0"],
      "tlp": "amber",
      "criticality": "critical",                              // from linked managed asset, null otherwise
      "description": "…",
      "first_seen": "2026-10-01T10:00:00", "last_seen": "…", // from linked events
      "event_count": 4,
      "cross_case_count": 2,                                  // other cases where the same IOC value / managed asset appears (readable or not)
      "enrichment": {"score": 87},                            // optional summary when enrichment exists
      "url": "/case/3/assets/12"                              // frontend route, null for free nodes
    }
  ],
  "edges": [
    {
      "key": "e:57",                     // stored: "e:<edge_id>"; derived: "d:<hash>"
      "id": 57,                          // stored edge id, null when derived
      "source": "asset:4", "target": "asset:12",
      "relation": {"id": 5, "name": "lateral_movement", "label": "Lateral movement",
                   "color": "red", "line_style": "solid"},
      "directed": true,
      "label": null, "description": null, "confidence": 80, "tlp": null,
      "origin": "manual",                // manual|ai|module|import|suggestion|event|ioc_asset_link|parent_event|alert|cross_case
      "review_state": "accepted",
      "first_seen": "…", "last_seen": "…",
      "event_ids": [101, 108],
      "count": 2,                        // number of supporting events (min 1)
      "editable": true                   // false for derived edges
    }
  ],
  "events": [
    {"event_id": 101, "title": "RDP logon", "date": "2026-10-01T10:00:00", "category": "Lateral Movement",
     "color": "#ff0000", "keys": ["asset:4", "asset:12"]}
  ],
  "relation_types": [ /* §3.1 rows */ ],
  "suggestions": [ /* §6, only when include=suggestions */ ],
  "meta": {"node_count": 34, "edge_count": 51, "generated_at": "…"}
}
```

Extra fields and the `case:<id>` / `alert:<id>` nodes added by the implementation are listed in §9.

No silent caps. If the graph exceeds `IRIS_CASE_GRAPH_MAX_NODES` (config, default 5000) the response
is still complete but `meta.warning` is set.

### 4.2 Exploration

* `GET /graph/neighbours?node=<key>&hops=1` (hops 1–3) → `{nodes, edges}` subset.
* `GET /graph/paths?source=<key>&target=<key>&directed=true&max_paths=5&max_length=8`
  → `{paths: [{node_keys: [...], edge_keys: [...]}], shortest_length}`. Simple paths, BFS ordered
  by length. `directed=false` ignores direction.

### 4.3 Stored edges

* `POST /graph/edges` body:
  `{source, target, relation_type_id | relation, directed?, label?, description?, confidence?, first_seen?, last_seen?, tlp_id?, event_ids?: [], custom_attributes?}`
  (`relation` is the name, alternative to the id; `directed` defaults to the relation's default).
  Both endpoints must exist in the case (or be free nodes of the case). → 201 edge object (§4.1 shape).
* `PUT /graph/edges/<edge_id>` partial update, same fields (+ `review_state`).
* `DELETE /graph/edges/<edge_id>` → 204.
* `POST /graph/edges/<edge_id>/review` `{decision: "accept"|"reject"}`.
* `POST /graph/edges/<edge_id>/reverse` swaps source/target.

### 4.4 Free nodes

* `POST /graph/nodes` `{label, node_type?, description?, icon?, color?, tlp_id?, custom_attributes?}` → 201 node.
* `PUT /graph/nodes/<node_id>`, `DELETE /graph/nodes/<node_id>` (deletes its edges).
* `POST /graph/nodes/<node_id>/promote` `{kind: "asset"|"ioc", ...creation fields of that object}`
  → creates the asset/IOC via the existing business functions, rewires every stored edge from
  `node:<id>` to the new key, deletes the free node; returns `{key, node}`.

### 4.5 Batch / paste

* `POST /graph/paste` `{text, ioc_tlp_id?, link_to?: <key>, relation?: <name>}` — extracts IPv4/IPv6,
  domains, URLs, emails, MD5/SHA1/SHA256 from free text, creates the missing IOCs (type auto-detected
  against the IOC type catalogue, existing ones in the case reused), optionally links each to `link_to`.
  → `{created: [keys], existing: [keys], edges: [edges], ignored: [strings]}`.

### 4.6 Views

* `GET /graph/views` → list of views visible to the caller (own + shared), without `snapshot`.
* `POST /graph/views` `{name, description?, is_shared?, state, snapshot?}` → 201.
* `GET|PUT|DELETE /graph/views/<view_id>` — only the owner (or case full-access users for shared
  views) may modify.
* `state` is opaque to the backend (JSONB), validated only for size (≤ 1 MB). Frontend shape:
  `{layout, positions: {key: {x, y}}, pinned: [], hidden: [], collapsed: [], filters: {...},
  viewport: {zoom, pan: {x, y}}, time: {from, to} | null, include: []}`.
* `snapshot` — PNG data URL, ≤ 4 MB. `is_report_default` boolean: the shared view whose snapshot is
  embedded in reports (at most one per case).

Table `case_graph_view`: `view_id`, `view_uuid`, `case_id` (cascade), `name`, `description`,
`owner_id` FK user, `is_shared`, `is_report_default`, `state` JSONB, `snapshot` Text, timestamps.

### 4.7 Import / export

* `GET /graph/export?format=json|stix|graphml` — `json` is the §4.1 payload + views (no snapshots);
  `stix` a STIX 2.1 bundle (IOCs → `indicator`/SCOs, assets → `infrastructure`, free nodes by type →
  `threat-actor` / `user-account` / `malware` / `infrastructure` / `note`, edges → `relationship`
  using `stix_relationship`); `graphml` for Gephi/yEd.
* `POST /graph/import` `{format: "json"|"stix", content}` → creates missing IOCs / free nodes and
  stored edges with origin `import`; returns a summary `{nodes_created, edges_created, skipped}`.

### 4.8 Intelligence (§6)

* `GET /graph/suggestions` → `[{key, kind, source, target, relation, directed, reason, event_ids, score}]`.
* `POST /graph/suggestions/accept` `{keys: []}` → stored edges with origin `suggestion`.
* `POST /graph/suggestions/dismiss` `{keys: []}`.
* `POST /graph/suggestions/ai` — asks the configured LLM (only when the chatbot/LLM is enabled) to
  propose edges from timeline events; results are stored as edges with origin `ai`, review_state
  `pending`. → `{edges: [...]}`. 409 when no LLM is configured.
* `GET /graph/gaps` → `[{code, severity, node_keys, edge_keys, message}]`. Codes:
  `initial_access_unknown` (compromised asset with no incoming directed edge),
  `isolated_ioc` (IOC with no edge), `unsupported_edge` (stored edge with no event and no description),
  `compromised_without_event`, `unanalysed_compromised` (compromised asset with analysis status not done).
* `POST /graph/explain` `{view_id?, node_keys?}` → `{markdown}` LLM narrative of the attack path.
  409 when no LLM is configured.

### 4.9 Relation type catalogue

`/api/v2/manage/graph-relation-types` — `GET` (any authenticated user), `POST`, `PUT /<id>`,
`DELETE /<id>`, `POST /reorder` (server administrator). Deleting a type in use → 400.
See §9.6 for the body and response details.

### 4.10 War-room graph

`GET /api/v2/war-rooms/<war_room_id>/graph` — union of the graphs of the cases attached to the war
room that the caller can read (same rules as the war-room board: unreadable cases appear only as
`case:<id>` nodes with `accessible: false`, nothing else about them is loaded). Node keys are prefixed
with the case: `c<case_id>/asset:12`. Identical IOC values across cases and assets linked to the same
managed asset are joined by `same_as` edges.

## 5. Real-time

Socket.IO, default namespace. Client emits `join-case-graph` `{case_id}` (read access checked) and
joins room `case_graph_<case_id>`; `leave-case-graph` to leave. After every committed graph mutation
(stored edge, free node, view, and — so the graph refreshes — asset/IOC/event create/update/delete)
the server emits `case-graph-changed` `{case_id, entity: "edge"|"node"|"view"|"case_object",
action: "created"|"updated"|"deleted", key?, by_user_id}` to the room. Clients refetch, debounced.
Presence (optional): `case-graph-presence` `{case_id, user, selected_key}` relayed to the room.
See §9.7 for the namespaces and acks.

## 6. Intelligence

Heuristic suggestions (deterministic keys so dismissals stick):

* `text_mention` — an IOC value or asset name/IP appears in an event's title/content/raw but the
  entity is not linked to that event → suggest `co_occurs` with the event's entities.
* `ip_match` — asset IP equals an IOC value → `same_as`.
* `alert_link` — an alert merged into the case links assets and IOCs together → `co_occurs`.
* `enrichment_resolution` — IOC enrichment contains a resolution to another IOC value of the case → `resolves_to`.

## 7. Integrations

* **Module hooks**: `on_postload_graph_edge_create`, `on_postload_graph_edge_update`,
  `on_postload_graph_edge_delete`, `on_postload_graph_node_create` (seeded in `iris_hooks`) — modules can
  enrich or expand the graph.
* **MCP tools**: `iris_case_graph_get`, `iris_case_graph_edge_create`, `iris_case_graph_paths`,
  `iris_case_graph_gaps`.
* **Reports**: the case report context gains `graph` (`nodes`, `edges` of §4.1) and
  `graph_snapshot` (base64 PNG of the report-default view, or null).
* **Activity log**: every stored edge / free node / view change writes a case activity entry.

## 8. Frontend

* Rendering engine: **Cytoscape.js** (+ fcose, dagre, edgehandles) behind a generic
  `CytoscapeGraph` component (`src/lib/components/common/CytoscapeGraph/`) with incremental diffing,
  themed stylesheet, no `fit()` on resize. The alert-cluster and alert-related graphs are migrated to
  it and `VisNetwork` is removed.
* Case graph page (`/case/[case_id]/graph`):
  * **Authoring** — canvas context menu (add asset/IOC/free node, paste indicators), drag from a node
    handle to another node to create an edge (relation picker), edit/reverse/delete edges, promote
    free nodes, drag assets/IOCs from a side palette, undo/redo (Ctrl+Z / Ctrl+Shift+Z).
  * **Reading** — arrows, relation labels (on hover / at zoom ≥ 1), line style by origin
    (manual solid, derived dashed, AI pending dotted amber), width by `count`, colour by relation,
    multi-edges bundled with a count badge.
  * **Layouts** — force (fcose), hierarchical (dagre, top→bottom, follows direction), chronological
    (x = first_seen), radial around selection, grouped (by type / compromise status / subnet / domain),
    grid. Pin, lock, persist positions.
  * **Exploration** — expand/collapse neighbours, hide, focus mode (N hops), path finder between two
    nodes, collapse IOC fan-outs, lasso multi-select with bulk actions (tag, flag, create task,
    hide), attribute search (`type:ip tag:c2 compromised:true kind:ioc`), minimap, keyboard shortcuts.
  * **Time** — slider replaying edges in `first_seen` order; two-way sync with the timeline page.
  * **Overlays** — compromise, flags, criticality, analysis status, TLP, enrichment score, cross-case badge.
  * **Detail rail** — editable object card, supporting events, linked objects, actions (open, create
    task, open in timeline, expand). Opening it never refits the canvas.
  * **Views** — save/load/share, report default, PNG/SVG export, JSON/STIX/GraphML export, import.
  * **Table view** — nodes / edges as tables, accessible alternative and bulk editing.
  * **Collaboration** — live refresh on `case-graph-changed`, presence of other analysts.
  * **Intelligence** — suggestion review panel, AI proposals (accept/reject), gaps panel, “Explain”.
* Timeline event form: role selector (source / target / involved) per linked asset / IOC.
* Settings → Case objects: relation-type catalogue management.
* War room: Graph tab using §4.10.

## 9. Backend implementation notes (deviations and extensions)

What the backend (`feature/investigation-graph`) does beyond, or differently from, §3–§7. Everything
not listed here follows the contract as written.

### 9.1 Data model

* The legacy, unused v2 graph tables are dropped by the same alembic revision
  (`a3f6c1d8e2b4`, with a downgrade). The system relation types are seeded by that revision.
* Edges are polymorphic (`source_kind`/`source_id`, `target_kind`/`target_id`), so there is no
  foreign key to the case objects. Edges touching an asset, IOC, event, evidence, task, note or free node
  are deleted in the same transaction as that object. Case deletion removes every graph row of the case.
* Case transfer (export/import of a case) carries relation types (looked up by name), free nodes, stored
  edges, edge↔event links, views and the event-link roles. View state keys (`asset:12`…) are remapped to
  the new ids, and entries of objects that did not travel are dropped. **Not transferred**: dismissed
  suggestions, and edges with an `alert:` endpoint (alerts do not travel with a case).

### 9.2 Event roles (§3.4)

* Request: keys may be strings or integers. Values outside `source|target|involved` → 400.
  Omitting `event_assets_roles` on update keeps the current roles of the assets that stay linked.
* Response keys are **strings** (JSON object keys): `"event_assets_roles": {"12": "source", "13": "involved"}`.
  Every linked asset / IOC is listed. Unlisted ones default to `involved`.

### 9.3 `GET /graph` (§4.1)

* Node extra fields: `color` (events, free nodes), `tlp_id` (free nodes), `custom_attributes` (free
  nodes), `accessible` (`case:` nodes only). Nodes of a kind that is not included still appear when a
  stored edge reaches them. Stored edges whose endpoint no longer exists are skipped.
* Edge extra fields (stored edges only): `tlp_id`, `custom_attributes`, `created_by_id`.
* `events[]` items also carry `parent_event_id`. Events with `event_in_graph = false` are left out of
  the derivation, the nodes and `events[]`.
* `include=alerts` adds `alert:<id>` nodes (alerts merged into the case) and undirected `related_to`
  edges, origin `alert`, to their assets / IOCs.
* `include=cross_case` adds `case:<id>` nodes and undirected `same_as` edges, origin `cross_case`, from
  every IOC / asset that appears in another case. `cross_case_count` is always computed, with or
  without the include. Unreadable cases are shown with no name:

```jsonc
{"key": "case:7", "kind": "case", "id": 7, "label": "Restricted case", "accessible": false, "url": null, /* other node fields null/empty */}
{"key": "case:5", "kind": "case", "id": 5, "label": "#5 - Phishing wave", "accessible": true, "url": "/case/5", /* … */}
```

* Accounts (for `authenticated_to`): an asset or IOC whose type name contains `account`.
* A derived edge with the same pair and relation as a stored edge (same direction if directed, either
  way round if undirected) is folded into the stored edge: its `event_ids` are added to the stored
  edge's. The stored edge's `first_seen`/`last_seen` stay as set; when they are null, they are computed
  from those events.
* A free-node `url` is null. A derived edge is `{"id": null, "editable": false, "label": null, "tlp_id": null, ...}`.
* `meta.generated_at` is UTC ISO without offset. The `meta.warning` text names `IRIS_CASE_GRAPH_MAX_NODES`.
* Errors: `review_state` other than `accepted|all` → 400. Unknown `include` values are ignored.

### 9.4 Writes (§4.3–§4.6)

* `POST /graph/edges`: a duplicate (same endpoints and relation, and same direction, or either way round for undirected edges) → 400.
  `origin` and `review_state` cannot be set by the body: manual edges are `manual` / `accepted`.
  `source == target` → 400. An endpoint from another case, or one that does not exist → 400.
  `PUT` may also change `source` / `target` and `event_ids`.
* Edge or node of another case → 404.
* `GET /graph/nodes/<node_id>` (not in §4.4) returns the free node.
* `node_type`: one of `actor|account|infrastructure|malware|note|group|other` (default `other`). `icon` is
  a slug (`[a-z0-9-]`), and `color` is a palette name (the asset-flag colours).
* `POST /graph/nodes/<id>/promote` → **201** `{key, node}`. The creation fields default from the node:
  `asset_name` / `ioc_value` ← `label`, `asset_description` / `ioc_description` ← `description`, and
  `ioc_tlp_id` ← `tlp_id`. The IOC type (`ioc_type_id`) and asset type (`asset_type_id`) are still
  required.
* `POST /graph/paste` → 200. `ioc_tlp_id` defaults to `amber`, and `relation` to `related_to`. At most 1000
  indicators per paste. A file name such as `payload.exe` is not taken for a domain. A link that already
  exists is not duplicated.
* Views: `GET /graph/views` returns a plain array. Only the owner can change `is_shared`. A non-owner
  with full access may edit a shared view. `is_report_default` requires a shared view (400 otherwise),
  and setting it clears the flag on the other views of the case.

### 9.5 Import / export (§4.7)

* `GET /graph/export` → 200 `{format, filename, content}` (JSON envelope). `content` is an object for
  `json` / `stix`, and a string (the XML document) for `graphml`. `filename` is `case-<id>-graph.json`,
  `case-<id>-graph.stix.json` or `case-<id>-graph.graphml`. Optional `include=` as in §4.1.
* STIX: IOCs whose type maps to an SCO (ip, domain/hostname, url/uri, email, md5/sha1/sha256/sha512)
  are exported as SCOs with deterministic ids. Other IOCs become `indicator`s (pattern
  `[x-iris-ioc:value = '…']`). Free nodes of type `group` / `other` become `x-iris-graph-node`. A note
  without neighbours becomes `x-iris-graph-node` too, since STIX notes need `object_refs`. `case:` nodes
  and their edges are left out. Every object carries `x_iris_key`. Relationships carry
  `x_iris_relation`, `x_iris_directed` and `x_iris_origin`.
* GraphML: keys `n_<field>` / `e_<field>`, `edgedefault="directed"`, and a per-edge `directed` attribute.
* `POST /graph/import` → 200 `{nodes_created, edges_created, skipped: <int>, skipped_details: [str]}`
  (`skipped_details` holds at most 200 entries). IOCs and free nodes are matched on value, label and
  type, and reused. Imported assets (`infrastructure` with an `asset:` key, or JSON asset nodes) are
  matched by name; when there is no match they become `infrastructure` free nodes, never assets.
  Derived edges (`editable: false`) in a JSON export are skipped. Relations resolve by
  `x_iris_relation`, then by `stix_relationship`, then fall back to `related_to`.

### 9.6 Relation types (§4.9)

* Body: `{name, label, description?, directed?, color?, line_style?, stix_relationship?}`. `name` must
  be 2–64 characters of `[a-z0-9_]` and unique. `color` is a palette name and `line_style` is
  `solid|dashed|dotted`.
* A system type cannot be deleted or renamed, but its other fields can be edited.
* List rows add `edge_count`. `POST /reorder {ids: [...]}` must list every type exactly once and returns
  the reordered list. `DELETE` → 204.

### 9.7 Real-time (§5)

* `case-graph-changed` is emitted in **both** the `/notifications` namespace (the authenticated one
  the SPA keeps open) and the default namespace, to room `case_graph_<case_id>`. `join-case-graph`,
  `leave-case-graph` and `case-graph-presence` are handled in both namespaces.
* `join-case-graph {case_id}` acks `{ok: true|false}` (false when the user has no read access or
  `case_id` is invalid). `leave-case-graph` has no ack and needs no access check.
* Presence: send `case-graph-presence {case_id, selected_key}`. `selected_key` is a string of at most
  256 characters, or null. You must have joined the room first; the ack is `{ok}`. Other members receive
  `{case_id, user: {id, name, login}, selected_key}`, and the sender does not get its own presence back.
* Paste and import emit a single `edge`/`created` with no `key`. Asset, IOC and event changes emit
  `case_object`.

### 9.8 Heuristic suggestions (§4.8, §6)

* `GET /graph/suggestions` returns the same array as `GET /graph?include=suggestions` (without the
  include, `suggestions` is `[]`). Each item also carries `alert_ids` (the alerts behind an
  `alert_link`; `[]` otherwise). Order: `score` descending, then kind
  (`text_mention`, `ip_match`, `alert_link`, `enrichment_resolution`), then `key`.
* `key` = `s:` + the first 16 hex digits of `sha1("<kind>|<source>|<target>|<relation>")`. The
  endpoints of an undirected suggestion are sorted first, so the key does not depend on the direction.
* `score`: base `ip_match` 90, `enrichment_resolution` 80, `alert_link` 60, `text_mention` 50, plus 10
  for every further event / alert that gives the same suggestion, capped at 95.
* Excluded: a suggestion whose pair (either way round) and relation already exist as a stored edge
  **in any review state** (rejected and pending included) or as an edge of the default graph (derived
  edges too), and a dismissed key. Two heuristics giving the same pair and relation keep the best one.
* `text_mention`: the terms are the asset names, the asset IPs (an `asset_ip` field may hold several,
  separated by spaces, `,`, `;` or `|`) and the IOC values, at least 3 characters long. Matching is
  case-insensitive on whole tokens: the term may not touch a letter, a digit, `_` or `-`, nor a `.`
  that continues the token (`10.0.0.1` does not match in `10.0.0.12` or `110.0.0.1`, but does match
  in `to 10.0.0.1.`). Events hidden from the graph (`event_in_graph = false`) are skipped. A mentioned
  entity is paired with every entity linked to the event **and with the other entities mentioned in
  it** (so an event that is linked to nothing still gives suggestions).
* `alert_link`: alerts with more than 30 linked assets/IOCs are skipped (a pair per two entities would
  flood the list).
* `enrichment_resolution`: strings at any depth under an IOC enrichment key that looks like a
  resolution, and equal to another IOC value of the case (case-insensitive, trailing `.` ignored). A key
  qualifies when one of its tokens (split on non-alphanumerics) is `resolution(s)`, `resolve(s|d|r)`,
  `dns`, `a`, `aaaa`, `cname`, `record(s)`, `ip(s)`, `ipv4`, `ipv6`, `address(es)`, `host(s)`,
  `hostname(s)`, `domain(s)`, `fqdn` or `passive`, or starts with `resol`. The edge goes from
  the name to the address (`domain → ip`) whichever IOC holds the enrichment. The walk stops at depth
  8 or 5000 items.
* `POST /graph/suggestions/accept {keys}` → 200 `{edges: [...§4.1 edges], unknown_keys: [...]}`. Only
  the suggestions that are still current are stored, with origin `suggestion`, review state
  `accepted`, `description` = the `reason` and `confidence` = the `score`. Keys that are no longer
  suggested, or whose edge could not be created, are listed in `unknown_keys` (not an error).
* `POST /graph/suggestions/dismiss {keys}` → 200 `{dismissed: <number of keys newly dismissed>}`.
  Any well-formed key is stored, even if it is not currently suggested.
* Both need full case access and take 1 to 1000 keys matching `s:[0-9a-f]{16}` (duplicates ignored);
  otherwise 400. Both write one case activity entry.

### 9.9 AI suggestions and explain (§4.8)

* The LLM is the chatbot provider resolved for the case (`app/iris_engine/llm`, same policy,
  enablement and restriction rules as the chatbot). Disabled or unconfigured → **409**.
* Each call is audited as an `ai_workflow_llm_call` row with no `run_id` and
  `request_snapshot.feature = "case_graph"`. It counts toward the chatbot daily token budgets (per
  user and organisation). An exhausted budget → 400. The chatbot redaction settings (IPs, e-mails,
  hashes) apply to the prompt. A provider error → 400 (the audit row keeps the error).
* The prompt sends the graph (linkable nodes, existing edges in every review state, relation names)
  and at most 150 events (content cut to 1500 characters) inside an untrusted-data fence. The system
  prompt says to treat it as data only.
* `POST /graph/suggestions/ai` (full access) → 200 `{edges, proposed, dropped}`. `proposed` is the
  number of edges the model returned, and `dropped` the number rejected. An edge is rejected when an
  endpoint is not an asset / IOC / event / evidence / task / note / free-node key of the graph, when
  `source == target`, when the relation is unknown, when it duplicates another proposal (same pair and relation), or when
  it already exists. At most **25** edges are kept. `event_ids` are filtered to events of the case,
  `confidence` is clamped to 0–100, and `rationale` becomes the `description` (1000 characters max).
  Stored with origin `ai`, review state `pending`, and one case activity entry.
* `POST /graph/explain` needs **read** access (it writes nothing to the case) → 200 `{markdown}`
  (20000 characters max; a surrounding code fence is removed). `view_id` must be one of the caller's
  views or a shared view (404 otherwise). The view's `state.include` (but `suggestions`) is applied
  and its `state.hidden` nodes are removed. `node_keys` keeps only those nodes; an unknown key → 400.
  An empty graph → 400. A non-integer `view_id` or a `node_keys` that is not a list of strings → 400.

### 9.10 Gaps (§4.8)

* `GET /graph/gaps` (read access) is computed on the default graph (`include` empty, accepted
  edges, derived edges included). Severity: `initial_access_unknown` high;
  `compromised_without_event` and `unanalysed_compromised` medium; `unsupported_edge` and
  `isolated_ioc` low. Sorted by severity, then code (`initial_access_unknown`,
  `compromised_without_event`, `unanalysed_compromised`, `unsupported_edge`, `isolated_ioc`), then graph
  order.
* "Compromised" means compromise status *compromised*. `unanalysed_compromised`: analysis status
  other than `Done` (including none). `isolated_ioc`: an IOC with no edge at all, derived edges
  included. `unsupported_edge` only looks at stored edges (no event and an empty description).
  `initial_access_unknown` needs an incoming **directed** edge, stored or derived.

### 9.11 War-room graph (§4.10)

* Needs war-room read access (`war_rooms_read` and membership, as for the other war-room routes).
  Unknown war room → 404. Same query parameters as §4.1, but only `events`, `evidences`, `tasks`,
  `notes`, `alerts` are honoured for `include` (`cross_case` and `suggestions` are ignored);
  `suggestions` is always `[]`. `review_state` other than `accepted|all` → 400.
* There is one `case:<id>` node per attached case (not prefixed), with the case name and
  `accessible: true`, or `Restricted case` and `accessible: false`. The per-case `case:` nodes and the
  edges to them are left out. Every other node, edge and event carries `case_id`. Edge keys are
  prefixed too (`c5/e:12`, `c5/d:…`), and so are `events[].keys`. `events` is sorted by date.
* `same_as` joins: IOCs with the same value (trimmed, case-insensitive) **and the same IOC type**,
  and assets linked to the same managed asset. A group of N nodes gives a star of N−1 edges from its
  first member, never between two nodes of the same case. These edges are derived
  (`origin: "cross_case"`, `editable: false`, undirected).
* `meta` adds `case_ids` (attached, in attachment order) and `readable_case_ids`. `meta.warning`
  works as in §4.1, on the total node count.

### 9.12 Integrations (§7)

* Module hooks are seeded by the alembic revision `b8d2e5f1a7c3` (downgrade removes them). `data` is
  always a list: the committed `CaseGraphEdge` / `CaseGraphNode` objects, but for
  `on_postload_graph_edge_delete`, which gets the deleted edge ids. Batch operations (paste, import,
  suggestion accept, AI suggestions) fire one hook call with all the created objects. Reverse and
  review fire `on_postload_graph_edge_update`. Node promotion moves edges without firing hooks.
  Failing hooks are logged and never fail the request (the change is already committed).
* Webhooks: the new hook names map to the object types `graph_edge` and `graph_node`. The payload id
  key is `edge_id` / `node_id`, and the UI link is `/case/<case_id>/graph`.
* MCP tools are not in the default (MVP) tool set: enable them through the MCP allowlist.
  `iris_case_graph_get`, `iris_case_graph_paths` and `iris_case_graph_gaps` are read-only (read case
  access); `iris_case_graph_edge_create` is a write tool (full access).
  * `iris_case_graph_get {case_identifier, include?: [..], review_state?, view?: "summary"|"full"}`.
    The default `summary` keeps the node fields `key, kind, label, type, compromised, analysis_status, tags,
    event_count, first_seen, last_seen, cross_case_count` and the edge fields `key, source, target,
    relation (name), directed, origin, review_state, event_ids, first_seen, last_seen, description,
    confidence`, and `relation_types` as a list of names. `full` returns the §4.1 payload. The usual MCP
    40 KB result budget applies.
  * `iris_case_graph_edge_create`: the `POST /graph/edges` body. The result is the edge, with `relation` as a name.
  * `iris_case_graph_paths {source, target, directed? = true, max_paths? = 5 (1–50), max_length? = 8 (1–12)}`.
  * `iris_case_graph_gaps` → `{total, data}`.
  * Validation errors are JSON-RPC `invalid params` errors.
* Reports: `graph` is `{nodes, edges}` of the default graph. `graph_snapshot` is the raw base64 of the
  report-default view's PNG (without the `data:image/png;base64,` prefix), or `None`.
