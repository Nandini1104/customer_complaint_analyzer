"""Sentiment analysis: TF-IDF + Logistic Regression trained on data/training_data.csv.

* Confidence is the model's real predicted probability (predict_proba).
* The trained model is saved with joblib. To use a better model later, train
  your own scikit-learn Pipeline with a final classifier that supports
  predict_proba, save it to MODEL_PATH, and the rest of the app keeps working.
* Run `python -m analysis.sentiment_analyzer --train` to (re)train.
"""
import os
import sys

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline

from .preprocessing import preprocess_for_model

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRAINING_CSV = os.path.join(BASE_DIR, "data", "training_data.csv")
MODEL_PATH = os.path.join(BASE_DIR, "analysis", "sentiment_model.joblib")
LABELS = ["Positive", "Negative", "Neutral"]


class ModelError(Exception):
    """Raised when the sentiment model cannot be trained or used."""


def train_model(csv_path=TRAINING_CSV, model_path=MODEL_PATH):
    """Train the classifier, evaluate it with cross-validation and save it."""
    if not os.path.exists(csv_path):
        raise ModelError(f"Training data not found: {csv_path}")
    df = pd.read_csv(csv_path).dropna()
    texts = [preprocess_for_model(t) for t in df["text"]]
    labels = df["label"].tolist()
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)),
        ("clf", LogisticRegression(C=10, max_iter=2000)),
    ])
    folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_accuracy = float(cross_val_score(pipeline, texts, labels, cv=folds).mean())
    pipeline.fit(texts, labels)
    joblib.dump({"pipeline": pipeline, "cv_accuracy": cv_accuracy, "samples": len(texts)}, model_path)
    return {"cv_accuracy": round(cv_accuracy, 3), "samples": len(texts)}


class SentimentAnalyzer:
    """Loads the saved model (training it first if missing) and predicts sentiment."""

    def __init__(self, model_path=MODEL_PATH):
        self.model_path = model_path
        self.pipeline, self.meta = None, {}
        self._load()

    def _load(self):
        try:
            bundle = joblib.load(self.model_path)
            self.pipeline = bundle["pipeline"]
            self.meta = {"cv_accuracy": round(bundle.get("cv_accuracy", 0), 3),
                         "samples": bundle.get("samples", 0)}
        except Exception:                       # missing file or version mismatch
            self.meta = train_model(model_path=self.model_path)
            bundle = joblib.load(self.model_path)
            self.pipeline = bundle["pipeline"]

    def retrain(self):
        self.meta = train_model(model_path=self.model_path)
        self.pipeline = joblib.load(self.model_path)["pipeline"]
        return self.meta

    def predict(self, text):
        """Return {"sentiment", "confidence", "probabilities"} for one text."""
        processed = preprocess_for_model(text)
        if not processed:
            raise ModelError("Text has no analyzable words.")
        try:
            probs = self.pipeline.predict_proba([processed])[0]
        except Exception as exc:
            raise ModelError(f"Sentiment model failed: {exc}")
        classes = [str(c) for c in self.pipeline.classes_]
        distribution = {c: round(float(p), 4) for c, p in zip(classes, probs)}
        best = max(distribution, key=distribution.get)
        return {"sentiment": best, "confidence": round(distribution[best], 2),
                "probabilities": distribution}


_analyzer = None


def get_analyzer():
    """Create the analyzer once and reuse it."""
    global _analyzer
    if _analyzer is None:
        _analyzer = SentimentAnalyzer()
    return _analyzer


if __name__ == "__main__":
    if "--train" in sys.argv:
        print("Training result:", train_model())
    else:
        print(get_analyzer().predict(" ".join(sys.argv[1:]) or "The product stopped working"))
