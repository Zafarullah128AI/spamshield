"""SMS spam classifier: TF-IDF (word unigrams + bigrams) + Multinomial Naive Bayes.

Trained on the labeled messages in the database (seeded from data.csv).
Reports honest metrics from a stratified 80/20 train/test split, and can
explain a prediction by showing which words pushed it toward spam or ham:
for each word in the message, the explanation score is
    log P(word | spam) - log P(word | ham)
taken straight from the trained Naive Bayes model.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB


class SpamModel:
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            lowercase=True, ngram_range=(1, 2), min_df=1, sublinear_tf=True
        )
        self.clf = MultinomialNB(alpha=0.5)
        self.trained = False
        self.metrics = {}
        self.n_train = 0
        self.n_test = 0

    def train(self, texts, labels):
        if len(texts) < 10 or len(set(labels)) < 2:
            raise ValueError("Need at least 10 messages covering both ham and spam.")
        X_train, X_test, y_train, y_test = train_test_split(
            texts, labels, test_size=0.2, random_state=42, stratify=labels
        )
        Xtr = self.vectorizer.fit_transform(X_train)
        self.clf.fit(Xtr, y_train)
        pred = self.clf.predict(self.vectorizer.transform(X_test))
        # confusion matrix with rows = actual [ham, spam], cols = predicted [ham, spam]
        cm = confusion_matrix(y_test, pred, labels=["ham", "spam"]).tolist()
        self.metrics = {
            "accuracy": round(float(accuracy_score(y_test, pred)), 4),
            "precision_spam": round(float(precision_score(y_test, pred, pos_label="spam", zero_division=0)), 4),
            "recall_spam": round(float(recall_score(y_test, pred, pos_label="spam", zero_division=0)), 4),
            "f1_spam": round(float(f1_score(y_test, pred, pos_label="spam", zero_division=0)), 4),
            "confusion_matrix": {"labels": ["ham", "spam"], "matrix": cm},
            "train_size": len(X_train),
            "test_size": len(X_test),
        }
        self.n_train = len(X_train)
        self.n_test = len(X_test)
        self.trained = True
        return self.metrics

    def predict(self, text):
        if not self.trained:
            raise RuntimeError("Model is not trained yet.")
        vec = self.vectorizer.transform([text])
        proba = self.clf.predict_proba(vec)[0]
        classes = list(self.clf.classes_)
        spam_idx = classes.index("spam")
        ham_idx = classes.index("ham")
        spam_prob = float(proba[spam_idx])
        label = "spam" if spam_prob >= 0.5 else "ham"

        # Explanation: per-word log-probability difference.
        log_prob = self.clf.feature_log_prob_
        diff = log_prob[spam_idx] - log_prob[ham_idx]
        vocab = self.vectorizer.vocabulary_
        scored = []
        for token in set(self.vectorizer.build_analyzer()(text)):
            idx = vocab.get(token)
            if idx is not None:
                scored.append((token, float(diff[idx])))
        scored.sort(key=lambda item: item[1], reverse=True)
        spam_words = [t for t, v in scored if v > 0][:6]
        ham_words = [t for t, v in scored if v < 0][-6:]
        ham_words.reverse()
        return {
            "label": label,
            "spam_probability": round(spam_prob, 4),
            "ham_probability": round(float(proba[ham_idx]), 4),
            "spam_words": spam_words,
            "ham_words": ham_words,
        }


# Single shared instance used by the API.
MODEL = SpamModel()
