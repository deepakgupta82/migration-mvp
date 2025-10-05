# Phase 2: Migration-Focused Adaptive Extraction - IN PROGRESS

**Status**: 2 of 4 files complete (50%)

## Completed Components

### 1. ✅ schema_discovery.py (Commit 27be8aa5)

**Changes**:
- Made `project_id` parameter **REQUIRED** (was optional)
- Replaced generic `domain` parameter with `document_domain` using 6 migration types
- Added `_build_migration_schema_prompt()` with document-type-specific templates

**Migration Document Templates**:

| Document Type | Entity Focus | Relationship Focus |
|---------------|-------------|-------------------|
| `infrastructure_inventory` | Server, VM, Database, Network Device | HOSTS, DEPENDS_ON, CONNECTS_TO |
| `dependency_mapping` | Application, Service, API, Integration | DEPENDS_ON, INTEGRATES_WITH, CALLS |
| `assessment_questionnaire` | System, Application, Risk, Requirement | SUPPORTS, REQUIRES, IMPACTS |
| `architecture_document` | Component, Layer, Service, Technology | IMPLEMENTS, USES, DEPLOYED_ON |
| `migration_strategy` | Migration Wave, Application Group, Risk | PART_OF, BLOCKS, ENABLES |
| `technical_specification` | System, Component, SLA, Metric | REQUIRES, MEASURED_BY, COMPLIES_WITH |

**Impact**:
- Schema discovery now tailored to migration assessment workflows
- Better entity type detection for infrastructure inventories
- Improved attribute discovery for migration metadata

---

### 2. ✅ adaptive_entity_extractor.py (Commit 1436c4a8)

**Changes**:
- Made `project_id` parameter **REQUIRED** in `extract_entities()`
- Updated LLM orchestrator to use `adaptive_extraction` process type (new in Phase 1)
- Added `_build_migration_extraction_prompt()` with domain-specific extraction guidance

**Migration Extraction Guidance**:

| Document Type | Extraction Priorities |
|---------------|----------------------|
| `infrastructure_inventory` | Hostnames, IP addresses, OS versions, environments (Dev/Test/Prod) |
| `dependency_mapping` | Application dependencies, integration points, data flows, API connections |
| `assessment_questionnaire` | Migration readiness scores, technical debt, risks, compliance requirements |
| `architecture_document` | Architectural components, technology stack, deployment patterns, scalability |
| `migration_strategy` | Migration waves, priorities, patterns (rehost/replatform), timelines, costs |
| `technical_specification` | SLA requirements, infrastructure specs (CPU/memory), compliance, baselines |

**Entity Enhancement**:
- Entities now include migration-specific attributes:
  - `environment`: Dev, Test, Staging, Production
  - `migration_priority`: High, Medium, Low
  - `owner`: Team or person responsible
  - `deployment_type`: Container, VM, bare-metal

---

## Remaining Components (Phase 2)

### 3. ⏸️ adaptive_prompts.py

**TODO**:
- Remove hardcoded DOMAIN_TEMPLATES dictionary
- Prepare prompt structure for JSON loading (Phase 3A)
- Update all prompt-building methods to use migration document types
- Add migration-specific prompt variations

**Files to Modify**:
- `services/graph-service/app/core/adaptive_prompts.py`

**Estimated Changes**: ~150 lines

---

### 4. ⏸️ graphs.py (API Endpoints)

**TODO**:
- Update `/extract` endpoints to require `project_id` parameter
- Update `/schema-discovery` endpoints to require `project_id`
- Update request/response models to include `document_domain`
- Pass `project_id` to schema_discovery and adaptive_entity_extractor

**Files to Modify**:
- `services/graph-service/app/routers/graphs.py`

**Estimated Changes**: ~80 lines

---

## Git Commits (Phase 2)

| Commit | Component | Changes |
|--------|-----------|---------|
| `27be8aa5` | schema_discovery.py | Migration-focused schema discovery with 6 document type templates |
| `1436c4a8` | adaptive_entity_extractor.py | Migration-focused entity extraction with domain-specific guidance |
| ⏸️ TBD | adaptive_prompts.py | Remove hardcoded prompts, prepare for JSON loading |
| ⏸️ TBD | graphs.py | Update API endpoints to require project_id |

---

## Next Steps

1. **Complete Phase 2** (2 files remaining):
   - Update `adaptive_prompts.py`
   - Update `graphs.py` API endpoints

2. **Phase 2 Final Commit**:
   - Create comprehensive commit for all Phase 2 changes
   - Update documentation in `docs/services/graph-service.md`

3. **Phase 3A**: Prompt Management Integration
   - Create 15 JSON prompt files
   - Implement `prompt_loader.py`
   - Integrate with Settings UI

---

## Testing Plan (Phase 2)

After completion, test with:

1. **Infrastructure Inventory**: Excel server list
   - Verify hostname, IP, OS extraction
   - Check environment classification

2. **Dependency Mapping**: Application dependency diagram
   - Verify dependency relationships
   - Check integration point detection

3. **Assessment Questionnaire**: Migration readiness form
   - Verify risk and requirement extraction
   - Check readiness score capture

4. **Architecture Document**: Technical architecture PDF
   - Verify component extraction
   - Check layer and technology stack detection

---

## Success Metrics

- ✅ All extraction calls require `project_id`
- ✅ Schema discovery uses migration document types
- ✅ Entity extraction includes migration metadata
- ⏸️ API endpoints enforce `project_id` requirement
- ⏸️ All prompts use migration-specific guidance

**Overall Phase 2 Progress**: 50% complete
