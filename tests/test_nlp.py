"""NLP tests (no database needed):  python -m unittest tests.test_nlp -v"""
import unittest

from analysis.category_detector import detect_category
from analysis.preprocessing import clean_text, fingerprint, preprocess_for_model
from analysis.priority import calculate_priority
from analysis.sentiment_analyzer import get_analyzer


class PreprocessingTests(unittest.TestCase):
    def test_cleaning(self):
        raw = "I ordered this product 5 days ago!!! It still hasn't arrived 😡 https://example.com"
        cleaned = clean_text(raw)
        self.assertNotIn("http", cleaned)
        self.assertIn("has not arrived", cleaned)
        self.assertIn("5 days ago", cleaned)

    def test_html_mentions_repeats(self):
        self.assertEqual(clean_text("<b>@support</b> sooooo bad #Refund"), "soo bad refund")

    def test_negation_kept(self):
        self.assertIn("not", preprocess_for_model("It is not working"))

    def test_fingerprint_ignores_formatting(self):
        self.assertEqual(fingerprint("Not WORKING!!"), fingerprint("not working"))


class ModelTests(unittest.TestCase):
    def test_negative_complaint(self):
        text = "The product stopped working after only two days. I am very disappointed."
        s = get_analyzer().predict(text)
        self.assertEqual(s["sentiment"], "Negative")
        self.assertAlmostEqual(sum(s["probabilities"].values()), 1.0, places=2)
        c = detect_category(text)
        p = calculate_priority(text, s["sentiment"], s["confidence"], c["category"])
        self.assertEqual(c["category"], "Product")
        self.assertEqual(p["priority"], "High")

    def test_payment_complaint(self):
        text = "My payment was deducted twice for the same order."
        s = get_analyzer().predict(text)
        self.assertEqual(detect_category(text)["category"], "Payment")
        self.assertEqual(s["sentiment"], "Negative")
        self.assertEqual(calculate_priority(text, s["sentiment"], s["confidence"], "Payment")["priority"], "High")

    def test_positive_is_low_priority(self):
        text = "The customer support team solved my issue quickly."
        s = get_analyzer().predict(text)
        self.assertEqual(s["sentiment"], "Positive")
        self.assertEqual(calculate_priority(text, s["sentiment"], s["confidence"], "Customer Service")["priority"], "Low")

    def test_confidence_is_deterministic(self):
        a = get_analyzer().predict("Delivery was late")["confidence"]
        b = get_analyzer().predict("Delivery was late")["confidence"]
        self.assertEqual(a, b)

    def test_no_keywords_is_other(self):
        self.assertEqual(detect_category("hello there")["category"], "Other")


if __name__ == "__main__":
    unittest.main()
