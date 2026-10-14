"""Full-stack tests (needs requirements installed):  python -m unittest tests.test_app -v
Uses a temporary SQLite file so your real data is untouched."""
import io
import os
import tempfile
import unittest

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_tmp, "test.db").replace("\\", "/")
os.environ["ADMIN_PASSWORD"] = "TestPass123"
os.environ["API_KEY"] = "test-api-key"

from app import create_app          # noqa: E402
from models import Complaint, db    # noqa: E402


class AppTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.client = cls.app.test_client()

    def csrf(self):
        self.client.get("/login")
        with self.client.session_transaction() as s:
            return s["csrf_token"]

    def login(self):
        token = self.csrf()
        r = self.client.post("/login", data={"username": "admin", "password": "TestPass123", "csrf_token": token})
        self.assertEqual(r.status_code, 302)
        with self.client.session_transaction() as s:
            return s["csrf_token"]

    def test_01_login_required_and_invalid_login(self):
        self.assertEqual(self.client.get("/").status_code, 302)
        token = self.csrf()
        r = self.client.post("/login", data={"username": "admin", "password": "wrong", "csrf_token": token})
        self.assertIn(b"Invalid username or password", r.data)

    def test_02_api_complaint_workflow(self):
        h = {"X-API-Key": "test-api-key"}
        body = {"customer_name": "Rahul Patel", "customer_email": "rahul@example.com", "product": "Wireless Headphones",
                "complaint_text": "The product stopped working after only two days. I am very disappointed."}
        r = self.client.post("/api/complaints", json=body, headers=h)
        self.assertEqual(r.status_code, 201)
        j = r.get_json()
        self.assertEqual((j["sentiment"], j["category"], j["priority"]), ("Negative", "Product", "High"))
        self.assertEqual(self.client.post("/api/complaints", json=body, headers=h).status_code, 409)   # duplicate
        self.assertEqual(self.client.post("/api/complaints", json=body).status_code, 401)              # no key
        bad = dict(body, complaint_text="  ")
        self.assertEqual(self.client.post("/api/complaints", json=bad, headers=h).status_code, 400)
        p = self.client.post("/api/complaints", headers=h, json={
            "customer_name": "Sneha", "customer_email": "s@example.com",
            "complaint_text": "My payment was deducted twice for the same order."}).get_json()
        self.assertEqual(p["category"], "Payment")
        analytics = self.client.get("/api/analytics", headers=h).get_json()
        self.assertEqual(analytics["summary"]["total"], 2)
        self.assertEqual(analytics["summary"]["negative"], 2)

    def test_03_pages_status_notes_csv(self):
        token = self.login()
        sample = open(os.path.join(os.path.dirname(__file__), "..", "data", "sample_complaints.csv"), "rb").read()
        r = self.client.post("/complaints/upload", data={"csrf_token": token, "file": (io.BytesIO(sample), "s.csv")},
                             content_type="multipart/form-data")
        self.assertIn(b"Upload result", r.data)
        r = self.client.post("/complaints/upload", data={"csrf_token": token, "file": (io.BytesIO(sample), "s.csv")},
                             content_type="multipart/form-data")
        self.assertIn(b"Duplicates", r.data)                                   # second upload = duplicates
        bad = io.BytesIO(b"a,b\n1,2\n")
        r = self.client.post("/complaints/upload", data={"csrf_token": token, "file": (bad, "bad.csv")},
                             content_type="multipart/form-data")
        self.assertIn(b"Missing required column", r.data)
        for path in ["/", "/complaints", "/complaints?q=refund&sentiment=Negative", "/customers", "/analytics",
                     "/categories", "/trends", "/reports", "/settings", "/complaints/add", "/complaints/upload"]:
            self.assertEqual(self.client.get(path).status_code, 200, path)
        with self.app.app_context():
            cid = Complaint.query.first().id
        self.client.post(f"/complaints/{cid}/status", data={"status": "Resolved", "csrf_token": token})
        self.client.post(f"/complaints/{cid}/note", data={"note": "Replacement approved.", "csrf_token": token})
        page = self.client.get(f"/complaints/{cid}").data
        self.assertIn(b"Replacement approved.", page)
        self.assertIn(b"Resolved", page)
        self.assertEqual(self.client.get("/reports/export/complaints.csv").status_code, 200)
        self.assertEqual(self.client.post(f"/complaints/{cid}/delete", data={}).status_code, 400)       # CSRF enforced


if __name__ == "__main__":
    unittest.main()
