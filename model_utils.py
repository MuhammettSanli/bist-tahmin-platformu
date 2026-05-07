"""Paylaşımlı model yardımcıları — model_egitimi.py ve app.py tarafından import edilir."""
import numpy as np
from sklearn.isotonic import IsotonicRegression


class CalibreliModel:
    """Ham modelin olasılıklarını isotonic regression ile kalibre eder."""
    def __init__(self, model, cal):
        self.model = model
        self.cal   = cal
        if hasattr(model, "feature_importances_"):
            self.feature_importances_ = model.feature_importances_

    def predict_proba(self, X):
        ham = self.model.predict_proba(X)[:, 1]
        kal = np.clip(self.cal.predict(ham), 0.0, 1.0)
        return np.column_stack([1 - kal, kal])

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= 0.5).astype(int)
