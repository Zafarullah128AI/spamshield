# SpamShield — SMS Spam Detection

A complete, designed web application: paste any SMS and the model replies
**Spam** or **Ham** (not spam), with a confidence score and the words that
pushed the decision either way. The website is served by FastAPI itself —
no Streamlit, no second server, no React build.

## Run (one terminal, one URL)

```bash
pip install -r requirements.txt
uvicorn backend.main:app
```

Then open: **http://127.0.0.1:8000** (the browser opens automatically)

API docs (for testing endpoints directly): http://127.0.0.1:8000/docs

On Windows, you can also just double-click `run.bat`.

## Default accounts

- **Admin:** admin@spamshield.edu.pk / admin123
- **Demo user:** demo@spamshield.edu.pk / demo123
- **New users:** register from the website (role = user)

## Features

- **Check SMS:** single message → Spam/Ham + spam probability + explanation
  (spam-indicating words vs ham-indicating words, taken from the trained model)
- **Bulk Check:** up to 50 messages at once, with a results table
- **Dashboard:** your checks, spam caught, spam rate, model accuracy, history
- **Dataset:** browse/search the labeled messages, add your own labeled message
  (the model retrains instantly), admin CSV upload
- **Evaluate:** 20 labeled test messages that do NOT appear in training data —
  an honest held-out test with per-message results
- **Admin:** model metrics (accuracy, spam precision/recall/F1), confusion
  matrix, one-click retrain, dataset upload/delete
- **History:** logged-in users' checks are stored in SQLite and exportable as CSV
- 3 tables: users, messages, predictions

## How the model works

**TF-IDF + Multinomial Naive Bayes** (scikit-learn) — the standard,
well-understood baseline for SMS spam detection:

1. Each SMS is turned into word unigram + bigram features, weighted by TF-IDF.
2. Naive Bayes learns P(word | spam) and P(word | ham) from the labeled data.
3. A new message is classified by whichever class probability is higher.
4. The explanation shows, for each word in the message,
   log P(word | spam) − log P(word | ham): positive → spam evidence,
   negative → ham evidence.

Metrics are measured on a stratified 80/20 train/test split (random_state=42)
and shown on the Dashboard and Admin pages.

## Dataset note (for the report)

The built-in dataset (182 messages: 102 ham, 80 spam) is original sample data
written for this project. The app also accepts the standard public SMS Spam
Collection format — a CSV with `label,message` columns — through the admin
upload, so the model can be retrained on the full 5,572-message dataset for
the final demo. State the dataset size honestly in the report.

## Project structure

```
sms_spam_detection/
├── data.csv               # 182 labeled messages (102 ham, 80 spam)
├── evaluation.py          # Standalone evaluation (20 held-out test messages)
├── requirements.txt
├── README.md
├── run.bat / run.sh       # One-command start
├── frontend/
│   ├── index.html         # All pages (single-page app)
│   ├── styles.css         # Complete design
│   └── app.js             # API client + views
└── backend/
    ├── main.py            # FastAPI app — all endpoints + serves frontend
    ├── database.py        # SQLite schema + seeding (users + CSV)
    ├── auth.py            # PBKDF2 hashing + JWT (HS256)
    ├── model.py           # TF-IDF + Naive Bayes engine + explanations
    └── spamshield.db      # created automatically on first run
```

## Honest simplifications

- SQLite instead of Postgres, in-app history instead of email reports,
  custom HTML/CSS/JS instead of React — same trade-offs as the
  SupervisorMatch project, chosen so the whole app runs from one terminal.
