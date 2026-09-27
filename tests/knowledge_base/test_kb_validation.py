import glob
import json
import pytest

def load_json(path):
    with open(path, 'r') as f:
        return json.load(f)

# Load global data once for parametrization
services_files = glob.glob('service_catalog/services/**/*.json', recursive=True)
evidence_files = glob.glob('service_catalog/research/evidence/**/*.json', recursive=True)
registry_path = 'service_catalog/schemas/document_registry.json'

services_data = [(f, load_json(f)) for f in services_files]
evidence_data = {load_json(f)['evidence_id']: load_json(f) for f in evidence_files}
registry_data = load_json(registry_path) if glob.glob(registry_path) else {'documents': []}

def get_all_refs():
    all_refs = set()
    for _, svc in services_data:
        for req in svc.get('requirements', []):
            if req.get('type') == 'ALTERNATIVE_GROUP':
                for doc in req.get('documents', []):
                    all_refs.update(doc.get('evidence_refs', []))
            elif req.get('type') in ['CONDITIONAL', 'REQUIRED']:
                all_refs.update(req.get('evidence_refs', []))
        for fee in svc.get('fees', []):
            all_refs.update(fee.get('evidence_refs', []))
            all_refs.update(fee.get('conflicts', []))
        pt = svc.get('processing_time')
        if pt:
            all_refs.update(pt.get('evidence_refs', []))
            all_refs.update(pt.get('conflicts', []))
        for dep in svc.get('document_dependencies', []):
            all_refs.update(dep.get('evidence_refs', []))
        for flow in svc.get('officer_workflow', []):
            all_refs.update(flow.get('evidence_refs', []))
    for doc in registry_data.get('documents', []):
        all_refs.update(doc.get('evidence_refs', []))
    return all_refs

ALL_REFS = get_all_refs()
VALID_DOC_CODES = {d['code']: d for d in registry_data.get('documents', [])}



import jsonschema

@pytest.mark.parametrize("file_path, svc", services_data)
def test_json_schema_validity(file_path, svc):
    schema_path = 'service_catalog/schemas/service_schema.json'
    try:
        schema = load_json(schema_path)
        jsonschema.validate(instance=svc, schema=schema)
    except FileNotFoundError:
        pytest.skip(f"Schema file {schema_path} not found")



@pytest.mark.parametrize("doc", registry_data.get('documents', []))
def test_document_registry_integrity(doc):
    assert 'code' in doc, "Document missing code"
    assert 'display_name' in doc, "Document missing display_name"
    assert 'status' in doc, "Document missing status"


@pytest.mark.parametrize("doc", registry_data.get('documents', []))
def test_document_registry_provenance(doc):
    if doc.get('status') == 'VERIFIED':
        assert len(doc.get('evidence_refs', [])) > 0, f"Registry document {doc['code']} needs provenance"
    else:
        assert doc.get('status') == 'NOT_VERIFIED', f"Registry document {doc['code']} has invalid status"


@pytest.mark.parametrize("ref", ALL_REFS)
def test_evidence_references_exist(ref):
    assert ref in evidence_data, f"Orphan evidence reference: {ref}"


@pytest.mark.parametrize("ev_id, ev_data", evidence_data.items())
def test_unused_evidence(ev_id, ev_data):
    if ev_id not in ALL_REFS:
        assert ev_data.get('research_only') is True, f"Unused evidence: {ev_id}"


def test_dependency_cycles():
    # Graph cycle detection
    graph = {}
    for _, svc in services_data:
        for dep in svc.get('document_dependencies', []):
            f = dep.get('from_service')
            t = dep.get('to_service')
            if f and t:
                graph.setdefault(f, []).append(t)
    
    visited = set()
    stack = set()
    def visit(node):
        if node in stack:
            return True
        if node in visited:
            return False
        visited.add(node)
        stack.add(node)
        for neighbor in graph.get(node, []):
            if visit(neighbor):
                return True
        stack.remove(node)
        return False
        
    for n in graph:
        assert not visit(n), f"Cycle detected involving {n}"


@pytest.mark.parametrize("file_path, svc", services_data)
def test_self_dependencies(file_path, svc):
    svc_code = svc.get('service_code')
    for dep in svc.get('document_dependencies', []):
        assert dep.get('from_service') != svc_code, f"Self dependency found in {svc_code}"


@pytest.mark.parametrize("file_path, svc", services_data)
def test_conditional_requirement_integrity(file_path, svc):
    for req in svc.get('requirements', []):
        if req.get('type') == 'CONDITIONAL':
            assert req.get('condition_description'), f"CONDITIONAL missing description in {file_path}"
            assert len(req.get('evidence_refs', [])) > 0, f"CONDITIONAL missing evidence in {file_path}"
            assert req.get('document') in VALID_DOC_CODES, f"Document {req.get('document')} not in registry in {file_path}"


@pytest.mark.parametrize("file_path, svc", services_data)
def test_alternative_group_integrity(file_path, svc):
    for req in svc.get('requirements', []):
        if req.get('type') == 'ALTERNATIVE_GROUP':
            docs = req.get('documents', [])
            assert len(docs) >= 2, f"ALTERNATIVE_GROUP needs >= 2 docs in {file_path}"
            min_req = req.get('minimum_required', 0)
            assert min_req >= 1, f"minimum_required must be >= 1 in {file_path}"
            assert min_req <= len(docs), f"minimum_required <= len(docs) in {file_path}"
            
            seen = set()
            for doc in docs:
                assert doc['document'] not in seen, f"Duplicate doc in group in {file_path}"
                seen.add(doc['document'])
                assert len(doc.get('evidence_refs', [])) > 0, f"Alt doc missing evidence in {file_path}"
                assert doc['document'] in VALID_DOC_CODES, f"Document {doc['document']} not in registry in {file_path}"


@pytest.mark.parametrize("file_path, svc", services_data)
def test_unknown_quarantine(file_path, svc):
    for req in svc.get('requirements', []):
        if req.get('type') == 'UNKNOWN':
            assert req.get('citizen_exposure') == 'DO_NOT_EXPOSE', f"UNKNOWN must be DO_NOT_EXPOSE in {file_path}"
            assert not req.get('mandatory', False), f"UNKNOWN cannot be mandatory in {file_path}"


@pytest.mark.parametrize("file_path, svc", services_data)
def test_not_verified_quarantine(file_path, svc):
    for req in svc.get('requirements', []):
        if req.get('type') == 'NOT_VERIFIED':
            assert req.get('citizen_exposure') == 'DO_NOT_EXPOSE', f"NOT_VERIFIED must be DO_NOT_EXPOSE in {file_path}"
            assert not req.get('mandatory', False), f"NOT_VERIFIED cannot be mandatory in {file_path}"


@pytest.mark.parametrize("file_path, svc", services_data)
def test_fee_provenance(file_path, svc):
    for fee in svc.get('fees', []):
        if fee.get('status') != 'NOT_VERIFIED':
            assert len(fee.get('evidence_refs', [])) > 0, f"Fee requires evidence in {file_path}"


@pytest.mark.parametrize("file_path, svc", services_data)
def test_processing_time_provenance(file_path, svc):
    pt = svc.get('processing_time')
    if pt and pt.get('status') != 'NOT_VERIFIED':
        assert len(pt.get('evidence_refs', [])) > 0, f"Processing time requires evidence in {file_path}"


@pytest.mark.parametrize("ev_id, ev_data", evidence_data.items())
def test_conflict_references(ev_id, ev_data):
    for conflict in ev_data.get('conflicts_with', []):
        assert conflict in evidence_data, f"Evidence {ev_id} conflicts with missing {conflict}"


@pytest.mark.parametrize("ev_id, ev_data", evidence_data.items())
def test_jurisdiction_metadata(ev_id, ev_data):
    assert ev_data.get('jurisdiction'), f"Evidence {ev_id} missing jurisdiction"


@pytest.mark.parametrize("ev_id, ev_data", evidence_data.items())
def test_evidence_temporal_metadata(ev_id, ev_data):
    assert ev_data.get('date_accessed'), f"Evidence {ev_id} missing date_accessed"


@pytest.mark.parametrize("doc", registry_data.get('documents', []))
def test_no_deprecated_registrar_permission(doc):
    assert doc['code'] != 'written_permission_registrar', "Deprecated document code used"

@pytest.mark.parametrize("file_path, svc", services_data)
def test_district_evidence_cannot_populate_statewide_fee(file_path, svc):
    svc_state = svc.get('jurisdiction', {}).get('state')
    svc_district = svc.get('jurisdiction', {}).get('district')
    
    for fee in svc.get('fees', []):
        for ref in fee.get('evidence_refs', []):
            ev = evidence_data.get(ref)
            if ev:
                ev_jur = ev.get('jurisdiction', '')
                if 'district' in ev_jur.lower():
                    # If evidence is district level, service must be district level
                    assert svc_district is not None, f"Statewide service {svc['service_code']} uses district evidence {ref} for fee"

@pytest.mark.parametrize("file_path, svc", services_data)
def test_district_evidence_cannot_populate_statewide_req(file_path, svc):
    svc_state = svc.get('jurisdiction', {}).get('state')
    svc_district = svc.get('jurisdiction', {}).get('district')
    
    for req in svc.get('requirements', []):
        refs = req.get('evidence_refs', [])
        if req.get('type') == 'ALTERNATIVE_GROUP':
            for doc in req.get('documents', []):
                refs.extend(doc.get('evidence_refs', []))
                
        for ref in refs:
            ev = evidence_data.get(ref)
            if ev:
                ev_jur = ev.get('jurisdiction', '')
                if 'district' in ev_jur.lower():
                    # If evidence is district level, service must be district level
                    assert svc_district is not None, f"Statewide service {svc['service_code']} uses district evidence {ref} for requirement"

def test_every_income_alternative_has_evidence():
    inc = dict(services_data).get('service_catalog/services/karnataka/income_certificate.json')
    if inc:
        for req in inc.get('requirements', []):
            if req.get('type') == 'ALTERNATIVE_GROUP' and req.get('group_id') == 'income_proof_options':
                for doc in req.get('documents', []):
                    assert len(doc.get('evidence_refs', [])) > 0, f"Income proof {doc['document']} missing evidence"

@pytest.mark.parametrize("file_path, svc", services_data)
def test_current_authority_temporally_valid(file_path, svc):
    for workflow in svc.get('officer_workflow', []):
        auth = workflow.get('authority', '')
        if auth:
            assert 'Judicial Magistrate' not in auth, f"Deprecated Judicial Magistrate found in {file_path}"

def test_namespace_collision():
    svc_codes = [svc.get('service_code') for _, svc in services_data]
    assert "driving_license" in svc_codes, "driving_license service is missing"
    
    assert "prior_driving_license" in VALID_DOC_CODES, "prior_driving_license document missing"
    assert "driving_license" not in VALID_DOC_CODES, "driving_license document should be removed to avoid collision"
    
    ll = dict(services_data).get('service_catalog/services/karnataka/learner_license.json')
    if ll:
        for req in ll.get('requirements', []):
            assert req.get('document') != "driving_license", "learner_license requires driving_license document"

def test_service_dependencies_registry():
    dep_path = 'service_catalog/schemas/service_dependencies.json'
    assert glob.glob(dep_path), "service_dependencies.json missing"
    data = load_json(dep_path)
    assert 'dependencies' in data
    svc_codes = [svc.get('service_code') for _, svc in services_data]
    for dep in data['dependencies']:
        assert dep['from_service'] in svc_codes, f"Unknown from_service: {dep['from_service']}"
        assert dep['to_service'] in svc_codes, f"Unknown to_service: {dep['to_service']}"
        assert dep['relationship'] == 'DEPENDS_ON'
        for ev in dep['evidence_refs']:
            assert ev in evidence_data, f"Missing evidence ref in dependency: {ev}"

