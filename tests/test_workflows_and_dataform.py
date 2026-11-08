from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_parent_orchestrator_yaml_structure():
    path = ROOT / "workflows" / "parent_orchestrator.yaml"
    assert path.exists(), "parent_orchestrator.yaml must exist"
    content = yaml.safe_load(path.read_text())
    assert "main" in content
    steps = content["main"]["steps"]
    step_names = [list(s.keys())[0] for s in steps]
    assert "query_active_tenants" in step_names
    assert "fan_out_tenants" in step_names


def test_tenant_child_workflow_yaml_structure():
    path = ROOT / "workflows" / "tenant_child_workflow.yaml"
    assert path.exists(), "tenant_child_workflow.yaml must exist"
    raw_text = path.read_text()
    content = yaml.safe_load(raw_text)
    assert "main" in content
    assert "compilationResults" in raw_text
    assert "workflowInvocations" in raw_text
    assert "serviceAccount" in raw_text
    assert "run_log" in raw_text
