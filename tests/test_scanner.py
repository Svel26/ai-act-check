import os
import json
import pytest
from ai_act_check.scanner import scan_repository

def test_biometric_detection(tmp_path):
    """
    Creates a temporary Python file with biometric imports
    and verifies the scanner flags it as High Risk.
    """
    # 1. Create a fake high-risk file
    d = tmp_path / "src"
    d.mkdir()
    p = d / "biometric_model.py"
    p.write_text("import face_recognition\nimport cv2")

    # 2. Run the scanner on this temp directory
    results = scan_repository(str(d))

    # 3. Assertions (The "Audit")
    design_specs = results["section_2_b_design_specifications"]
    detected_libs = design_specs["detected_libraries"]
    risks = design_specs["risk_classification_detected"]

    # Debug print if test fails
    print(f"Detected: {detected_libs}")

    assert any(lib.startswith("face_recognition") for lib in detected_libs)
    assert any("Biometrics" in r for r in risks)

def test_clean_repo(tmp_path):
    """
    Verifies that a benign file returns zero risks.
    """
    d = tmp_path / "src"
    d.mkdir()
    p = d / "hello.py"
    p.write_text("import math\nprint('Hello World')")

    results = scan_repository(str(d))
    
    design_specs = results["section_2_b_design_specifications"]
    assert len(design_specs["detected_libraries"]) == 0
    assert len(design_specs["risk_classification_detected"]) == 0