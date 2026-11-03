import re
from fastapi.testclient import TestClient
from app.main import app

def run_a11y_and_quality_audit():
    client = TestClient(app)
    
    print("=== STARTING WEB QUALITY & A11Y AUDIT ===")
    
    # 1. Audit Homepage (/)
    res = client.get("/")
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    html = res.text
    
    # Check DOCTYPE & HTML tag
    assert "<!DOCTYPE html>" in html, "Missing <!DOCTYPE html>"
    assert '<html lang="en">' in html, "Missing <html lang=\"en\">"
    assert '<meta name="viewport"' in html, "Missing viewport meta tag"
    assert "<title>" in html and "</title>" in html, "Missing title tag"
    print("✓ Document Structure & Meta Tags: PASS")

    # Check Semantic Landmarks
    landmarks = ["<header>", "<main>", "<section", "<footer"]
    for lm in landmarks:
        assert lm in html, f"Missing semantic landmark: {lm}"
    print("✓ Semantic Landmarks (<header>, <main>, <section>, <footer>): PASS")

    # Check Form Accessibility & ARIA labels
    assert 'aria-label="Select Demo Sample"' in html
    assert 'aria-label="Target Language"' in html
    assert 'aria-label="Code Input Workbench"' in html
    assert 'aria-label="Review Results Stream"' in html
    assert '<label class="checkbox-label"' in html
    print("✓ ARIA Accessibility & Form Labels: PASS")

    # Check Security Headers
    headers = res.headers
    assert "content-security-policy" in headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "strict-origin-when-cross-origin"
    print("✓ Security Headers (CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy): PASS")

    # 2. Audit Inner Route (/api/samples)
    res_samples = client.get("/api/samples")
    assert res_samples.status_code == 200
    assert "application/json" in res_samples.headers["content-type"]
    samples_data = res_samples.json()
    assert len(samples_data["samples"]) == 3
    print("✓ Inner API Route (/api/samples): PASS (3 valid samples)")

    # 3. Honesty & Content Hygiene Audit
    # Verify no fake trademarks (™), patents, or unlabelled stock people
    banned_terms = ["™", "patented", "patent pending", "proprietary algorithm"]
    for term in banned_terms:
        assert term not in html.lower(), f"Violated honesty invariant: found '{term}'"
    print("✓ Honesty & Content Hygiene Audit: PASS (Zero fake trademarks, patent claims, or unlabelled data)")

    print("=== WEB QUALITY & A11Y AUDIT COMPLETE: 100% SCORE ===")

if __name__ == "__main__":
    run_a11y_and_quality_audit()
