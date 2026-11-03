import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_root_route():
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "SentinelReview" in response.text
    # Check security headers
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"

def test_samples_endpoint():
    response = client.get("/api/samples")
    assert response.status_code == 200
    data = response.json()
    assert "samples" in data
    assert len(data["samples"]) == 3
    for s in data["samples"]:
        assert s["label"].startswith("SAMPLE:")
        assert len(s["code"]) > 20
        assert s["language"] in ("Python", "JavaScript")

def test_sample_a_sql_injection():
    samples = client.get("/api/samples").json()["samples"]
    sample_a = samples[0]
    res = client.post("/api/review", json={
        "code": sample_a["code"],
        "language": sample_a["language"],
        "is_diff": False
    })
    assert res.status_code == 200
    data = res.json()
    assert data["counts"]["high"] >= 1
    assert any(f["cwe"] == "CWE-89" for f in data["findings"])
    assert data["provider_used"] in ("sast-only", "groq", "gemini")

def test_sample_b_js_forgotten_await():
    samples = client.get("/api/samples").json()["samples"]
    sample_b = samples[1]
    res = client.post("/api/review", json={
        "code": sample_b["code"],
        "language": sample_b["language"],
        "is_diff": False
    })
    assert res.status_code == 200
    data = res.json()
    assert any(f["cwe"] == "CWE-670" or "await" in f["explanation"].lower() for f in data["findings"])

def test_sample_c_hidden_prompt_injection():
    samples = client.get("/api/samples").json()["samples"]
    sample_c = samples[2]
    res = client.post("/api/review", json={
        "code": sample_c["code"],
        "language": sample_c["language"],
        "is_diff": False
    })
    assert res.status_code == 200
    data = res.json()
    # Must flag BOTH injection scan and dynamic eval vulnerability
    sources = [f["source"] for f in data["findings"]]
    cwes = [f.get("cwe") for f in data["findings"]]
    assert "injection-scan" in sources
    assert "CWE-95" in cwes or any("eval" in f["explanation"].lower() for f in data["findings"])

def test_unified_diff_review():
    diff_payload = """diff --git a/vuln.py b/vuln.py
index 0000000..1111111 100644
--- a/vuln.py
+++ b/vuln.py
@@ -1,3 +1,3 @@
 def run_query(cursor, param):
-    # safe implementation
-    cursor.execute("SELECT 1")
+    # newly added injection
+    cursor.execute(f"SELECT * FROM items WHERE name = '{param}'")
"""
    res = client.post("/api/review", json={
        "code": diff_payload,
        "language": "Python",
        "is_diff": True
    })
    assert res.status_code == 200
    data = res.json()
    assert data["counts"]["high"] >= 1
    assert any(f["cwe"] == "CWE-89" for f in data["findings"])

def test_empty_payload_validation():
    res = client.post("/api/review", json={
        "code": "   ",
        "language": "Python",
        "is_diff": False
    })
    assert res.status_code == 400

def test_oversized_payload_rejection():
    oversized = "a = 1\n" * 120_000  # > 500KB
    res = client.post("/api/review", json={
        "code": oversized,
        "language": "Python",
        "is_diff": False
    })
    assert res.status_code == 413
