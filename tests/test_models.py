"""Real model initialization/inference smoke test; accuracy is not measured here."""
import os
import numpy as np
from PIL import Image
import pytest
from yorevia.faces import FaceEngine,model_status

def test_real_models_initialise_and_run(tmp_path):
    if not model_status()['installed']:
        if os.environ.get('YOREVIA_REQUIRE_MODELS')=='1':pytest.fail('CI requires verified model files')
        pytest.skip('Official model weights not installed: real inference not verified in this environment')
    engine=FaceEngine()
    blank=tmp_path/'blank.png';Image.new('RGB',(320,320),(128,128,128)).save(blank)
    assert engine.detect(blank)==[]
    vector=engine.recognizer.feature(np.full((112,112,3),128,dtype=np.uint8))
    assert vector.size==128
    assert np.isfinite(vector).all()
