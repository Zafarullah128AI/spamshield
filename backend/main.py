"""SpamShield — SMS Spam Detection: FastAPI app serving its own website.

One terminal, one URL: http://127.0.0.1:8000
API docs (for testing endpoints directly): http://127.0.0.1:8000/docs

The site is a single-page app (frontend/index.html + styles.css + app.js)
served by FastAPI itself — no Streamlit, no second server, no React build.
"""

import csv
import io
import os
import threading
import time
import webbrowser

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from . import auth, database
from .model import MODEL

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = FastAPI(title="SpamShield - SMS Spam Detection")


# ---------------- startup: seed DB + train model + open browser ----------------

@app.on_event("startup")
def startup():
    database.init_db()
    texts, labels = database.all_labeled()
    MODEL.train(texts, labels)
    if not os.environ.get("SPAM_NO_BROWSER"):
        def _open():
            time.sleep(1.2)
            webbrowser.open("http://127.0.0.1:8000")
        threading.Thread(target=_open, daemon=True).start()


# ---------------- auth helpers ----------------

def _current_user(authorization: str = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        return None
    data = auth.decode_token(authorization.split(" ", 1)[1])
    if not data:
        return None
    return database.get_user_by_id(data["sub"])


def _require_user(user=Depends(_current_user)):
    if not user:
        raise HTTPException(status_code=401, detail="Login required.")
    return user


def _require_admin(user=Depends(_require_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only.")
    return user


# ---------------- request bodies ----------------

class RegisterBody(BaseModel):
    name: str
    email: str
    password: str


class LoginBody(BaseModel):
    email: str
    password: str


class PredictBody(BaseModel):
    text: str


class BulkBody(BaseModel):
    texts: list


class AddMessageBody(BaseModel):
    label: str
    text: str


# ---------------- auth endpoints ----------------

@app.post("/api/register")
def register(body: RegisterBody):
    email = body.email.strip().lower()
    if database.get_user_by_email(email):
        raise HTTPException(status_code=400, detail="This email is already registered.")
    if len(body.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters.")
    user_id = database.create_user(body.name.strip(), email, auth.hash_password(body.password))
    user = database.get_user_by_id(user_id)
    return {"token": auth.create_token(user["id"], user["role"]),
            "user": database.public_user(user)}


@app.post("/api/login")
def login(body: LoginBody):
    user = database.get_user_by_email(body.email.strip().lower())
    if not user or not auth.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Wrong email or password.")
    return {"token": auth.create_token(user["id"], user["role"]),
            "user": database.public_user(user)}


@app.get("/api/me")
def me(user=Depends(_require_user)):
    return database.public_user(user)


# ---------------- prediction endpoints ----------------

def _run_predict(text, user):
    result = MODEL.predict(text)
    pred_id = None
    if user:
        pred_id = database.add_prediction(
            user["id"], text, result["label"], result["spam_probability"]
        )
    return {"id": pred_id, "text": text, **result}


@app.post("/api/predict")
def predict(body: PredictBody, user=Depends(_current_user)):
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message text is empty.")
    return _run_predict(text, user)


@app.post("/api/predict_bulk")
def predict_bulk(body: BulkBody, user=Depends(_current_user)):
    texts = [str(t).strip() for t in (body.texts or []) if str(t).strip()]
    if not texts:
        raise HTTPException(status_code=400, detail="No messages provided.")
    if len(texts) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 messages at a time.")
    return {"results": [_run_predict(t, user) for t in texts]}


# ---------------- history / stats ----------------

@app.get("/api/history")
def history(user=Depends(_require_user)):
    return database.user_history(user["id"])


@app.get("/api/history/export")
def history_export(user=Depends(_require_user)):
    rows = database.user_history(user["id"], limit=1000)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["text", "predicted_label", "spam_probability", "checked_at"])
    for r in rows:
        writer.writerow([r["text"], r["label"], r["spam_probability"], r["created_at"]])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=spamshield_history.csv"},
    )


@app.get("/api/stats")
def stats(user=Depends(_require_user)):
    mine = database.prediction_stats(user["id"])
    data = {"mine": mine, "dataset": database.dataset_counts(),
            "model": MODEL.metrics}
    if user["role"] == "admin":
        data["all_predictions"] = database.prediction_stats()
    return data


# ---------------- dataset endpoints ----------------

@app.get("/api/dataset")
def dataset(label: str = None, q: str = None, limit: int = 200, offset: int = 0):
    rows, total = database.list_messages(label=label, search=q,
                                         limit=min(limit, 500), offset=offset)
    return {"messages": rows, "total": total, "counts": database.dataset_counts()}


@app.post("/api/dataset")
def add_message(body: AddMessageBody, user=Depends(_require_user)):
    label = (body.label or "").strip().lower()
    text = (body.text or "").strip()
    if label not in ("ham", "spam"):
        raise HTTPException(status_code=400, detail="Label must be 'ham' or 'spam'.")
    if not text:
        raise HTTPException(status_code=400, detail="Message text is empty.")
    msg_id = database.add_message(label, text, source="user", added_by=user["id"])
    texts, labels = database.all_labeled()
    metrics = MODEL.train(texts, labels)
    return {"id": msg_id, "retrained": True, "metrics": metrics}


@app.delete("/api/dataset/{msg_id}")
def remove_message(msg_id: int, user=Depends(_require_admin)):
    if not database.delete_message(msg_id):
        raise HTTPException(status_code=404, detail="Message not found.")
    texts, labels = database.all_labeled()
    metrics = MODEL.train(texts, labels)
    return {"deleted": msg_id, "retrained": True, "metrics": metrics}


@app.post("/api/dataset/upload")
def upload_dataset(file: UploadFile = File(...), user=Depends(_require_admin)):
    try:
        content = file.file.read().decode("utf-8-sig")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read the file as text.")
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames or "message" not in [f.strip().lower() for f in reader.fieldnames]:
        raise HTTPException(status_code=400,
                            detail="CSV must have 'label' and 'message' columns.")
    added, skipped = 0, 0
    field_map = {f.strip().lower(): f for f in reader.fieldnames}
    for row in reader:
        label = (row.get(field_map.get("label", "label")) or "").strip().lower()
        text = (row.get(field_map.get("message", "message")) or "").strip()
        if label in ("ham", "spam") and text:
            database.add_message(label, text, source="upload", added_by=user["id"])
            added += 1
        else:
            skipped += 1
    texts, labels = database.all_labeled()
    metrics = MODEL.train(texts, labels)
    return {"added": added, "skipped": skipped, "retrained": True, "metrics": metrics}


# ---------------- model / evaluation ----------------

@app.get("/api/metrics")
def metrics():
    return {"metrics": MODEL.metrics, "dataset": database.dataset_counts(),
            "trained": MODEL.trained}


@app.post("/api/train")
def retrain(user=Depends(_require_admin)):
    texts, labels = database.all_labeled()
    return {"retrained": True, "metrics": MODEL.train(texts, labels)}


@app.get("/api/evaluate")
def evaluate(user=Depends(_require_user)):
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "spamshield_evaluation", os.path.join(BASE_DIR, "evaluation.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    TEST_MESSAGES = module.TEST_MESSAGES

    results = []
    correct = 0
    for item in TEST_MESSAGES:
        pred = MODEL.predict(item["text"])
        ok = pred["label"] == item["label"]
        correct += ok
        results.append({"text": item["text"], "expected": item["label"],
                        "predicted": pred["label"],
                        "spam_probability": pred["spam_probability"],
                        "correct": ok})
    return {"total": len(results), "correct": correct,
            "accuracy": round(correct / len(results), 4) if results else 0,
            "results": results}


# ---------------- frontend ----------------

@app.get("/")
def index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


@app.get("/app.js")
def app_js():
    return FileResponse(os.path.join(FRONTEND_DIR, "app.js"),
                        media_type="application/javascript")


@app.get("/styles.css")
def styles():
    return FileResponse(os.path.join(FRONTEND_DIR, "styles.css"),
                        media_type="text/css")
