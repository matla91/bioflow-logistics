"""Priority 2 skeleton: train only on simulated labels; report held-out scores."""

from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, brier_score_loss
from sklearn.model_selection import train_test_split


def train(features, labels, seed=1):
    if len(set(labels)) < 2:
        raise ValueError("Training labels need both outcomes")
    x_train, x_test, y_train, y_test = train_test_split(
        features, labels, random_state=seed, stratify=labels
    )
    model = HistGradientBoostingClassifier(random_state=seed).fit(x_train, y_train)
    probability = model.predict_proba(x_test)[:, 1]
    return model, {
        "held_out_accuracy": accuracy_score(y_test, probability >= 0.5),
        "brier_score": brier_score_loss(y_test, probability),
        "limitation": "trained on simulation; no claim of real-world accuracy",
    }
