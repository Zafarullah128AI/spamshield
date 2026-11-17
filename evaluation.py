"""Standalone evaluation for SpamShield (also used by the website's Evaluate page).

Trains a fresh model on data.csv, then scores 20 labeled test messages that
do NOT appear in the training file, so the accuracy here is an honest
held-out result. Run it directly:

    python evaluation.py
"""

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.model import SpamModel  # noqa: E402

# 20 labeled test messages, written separately from data.csv (no overlap).
TEST_MESSAGES = [
    # --- spam (10) ---
    {"label": "spam", "text": "You have won a luxury car! To claim, call this number within 24 hours."},
    {"label": "spam", "text": "Your bank account is frozen. Click here to verify your CNIC and restore access."},
    {"label": "spam", "text": "Get a free laptop by completing a short survey. Limited offer, apply now!"},
    {"label": "spam", "text": "Earn 10000 per week from home. No skills required, start today!"},
    {"label": "spam", "text": "Your tax refund of 32000 is ready. Enter your account details to receive it."},
    {"label": "spam", "text": "Congratulations! You won a holiday package for two. Reply CLAIM to book."},
    {"label": "spam", "text": "Urgent: your electricity connection will be cut today unless you pay now."},
    {"label": "spam", "text": "You are selected for a free shopping spree worth 50000. Click to redeem!"},
    {"label": "spam", "text": "Double your money with our investment plan. Guaranteed profit in 7 days!"},
    {"label": "spam", "text": "Share this OTP with our agent to unlock your prize of 20000."},
    # --- ham (10) ---
    {"label": "ham", "text": "The teacher shared the slides in the class group."},
    {"label": "ham", "text": "I will bring the documents to the office tomorrow morning."},
    {"label": "ham", "text": "Please remind me to buy tickets for the show."},
    {"label": "ham", "text": "Your appointment is scheduled for Monday at 10 am."},
    {"label": "ham", "text": "The match was amazing, let's discuss it tomorrow."},
    {"label": "ham", "text": "Can you send me the photo from yesterday's event?"},
    {"label": "ham", "text": "I have reached the station, waiting for the bus."},
    {"label": "ham", "text": "The fee challan has been submitted to the bank."},
    {"label": "ham", "text": "Let's meet at the canteen during the break."},
    {"label": "ham", "text": "Your balance after this transaction is 4500."},
]


def main():
    base = os.path.dirname(os.path.abspath(__file__))
    texts, labels = [], []
    with open(os.path.join(base, "data.csv"), newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            texts.append(row["message"])
            labels.append(row["label"])
    model = SpamModel()
    metrics = model.train(texts, labels)
    print(f"Training messages: {len(texts)} | hold-out metrics: {metrics}")

    correct = 0
    for item in TEST_MESSAGES:
        pred = model.predict(item["text"])
        ok = pred["label"] == item["label"]
        correct += ok
        mark = "OK " if ok else "MISS"
        print(f"{mark} expected={item['label']:4} predicted={pred['label']:4} "
              f"spam_prob={pred['spam_probability']:.2f} | {item['text']}")
    print(f"\nHeld-out test set: {correct}/{len(TEST_MESSAGES)} correct "
          f"= {correct / len(TEST_MESSAGES):.1%}")


if __name__ == "__main__":
    main()
