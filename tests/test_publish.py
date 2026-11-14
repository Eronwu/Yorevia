"""The publish helper is tested without using credentials or touching GitHub."""
import importlib.util
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location('publish',Path(__file__).parents[1]/'scripts/publish_github.py')
publish=importlib.util.module_from_spec(spec);spec.loader.exec_module(publish)

def test_publish_allows_only_project_assets():
    publish.check_staged_paths(['README.md','engine/yorevia/vault.py','models/manifest.json','src-tauri/icons/icon.png','docs/screenshots/timeline-demo.png'])

@pytest.mark.parametrize('path',['YoreviaVault/vault.sqlite','engine/private.jpg','models/model.onnx','docs/personal.png','scripts/.env','my-photographs.png'])
def test_publish_rejects_private_or_unexpected_data(path):
    with pytest.raises(RuntimeError):publish.check_staged_paths([path])
