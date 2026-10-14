# Customer Complaint Sentiment Analyzer

A web-based customer-support analytics system that automatically analyzes customer complaints using NLP, detects sentiment, identifies complaint categories, calculates priority, stores complaint information, and provides interactive analytics for customer-support teams. (BCA final-year project)

## 1. Problem statement
Support teams receive hundreds of complaints by email, web forms and chat. Reading each one to decide how urgent it is and who should handle it is slow and inconsistent. This system reads each complaint automatically, labels it, ranks it, and shows the whole picture on a dashboard.

## 2. Objectives
- Collect complaints (form, CSV, REST API)
- Classify sentiment (Positive / Negative / Neutral) with a real confidence score
- Detect the complaint category and calculate a Complaint Priority
- Track status (New, In Progress, Resolved, Closed) with history and notes
- Provide analytics, search, filters, customer view and CSV reports

## 3. Features
Dashboard · Complaint list with search/filters/pagination · Complaint detail with history and admin notes · Add complaint (instant analysis result) · CSV upload with processed/failed/duplicate counts · Customer pages · Sentiment, category, status, priority charts · Trends (daily/weekly/monthly + filters) · Reports with CSV export · REST API · Settings (password, API key, category auto-detect, model retraining) · Login with hashed passwords, CSRF protection, login rate limit.

## 4. Technology stack
Python 3.13, Flask, Flask-SQLAlchemy / SQLAlchemy, SQLite, Flask-Login, pandas, NumPy, scikit-learn, Bootstrap 5, Chart.js, Docker.
(Bootstrap and Chart.js are loaded from a CDN, so the browser needs internet access.)

## 5. System architecture
```
Browser / external system
        |  HTTP / JSON
   routes/ (Flask blueprints)      <- only HTTP handling
        |
   services/complaint_service.py   <- the complaint pipeline
        |                    \
   analysis/ (NLP, analytics)   models/ (SQLAlchemy) -> SQLite
```

## 6. Complaint processing workflow
Complaint -> validate -> clean text -> sentiment -> category -> priority -> save (customer, complaint, sentiment result, history) -> dashboard/analytics.
The same function (`process_and_save`) is used by the form, the CSV upload and `POST /api/complaints`.

## 7. NLP preprocessing (`analysis/preprocessing.py`)
Lowercase, HTML/URL/mention removal, hashtag symbol removal (word kept), emoji/symbol removal, contraction expansion (`hasn't` -> `has not`), repeated-character reduction (`sooo` -> `soo`), whitespace normalising, tokenizing and stop-word removal. Negation words (not, no, never) are deliberately kept because they flip sentiment. A hash of the cleaned text is used for duplicate detection.

## 8. Sentiment analysis (`analysis/sentiment_analyzer.py`)
TF-IDF (1-2 word n-grams) + Logistic Regression, trained on `data/training_data.csv` (147 labelled sentences written for this project). Confidence is the model's real predicted probability (`predict_proba`); nothing is hard-coded or random. The model is trained automatically on first run (and at Docker build) and saved to `analysis/sentiment_model.joblib`. To use a better model, train any scikit-learn pipeline with `predict_proba`, save it to the same path (or replace `SentimentAnalyzer`), and nothing else changes. Settings -> "Retrain model" retrains after you add rows to the CSV.

## 9. Category detection (`analysis/category_detector.py`)
Weighted keyword/phrase scoring for Product, Delivery, Payment, Refund, Customer Service, Account, Technical Issue, Pricing, Quality, Other. Confidence = top score / (sum of scores + 0.5); no match -> Other with confidence 0. A category chosen by the user always wins; otherwise the detected one is used (can be switched off in Settings). "Product Quality" in the brief is covered by the two categories Product and Quality.

## 10. Priority calculation (`analysis/priority.py`)
Points: negative sentiment +2 (+1 if confidence >= 85%), positive -2, category weight (Payment/Refund/Account +2, others +1 or 0), impact keywords +1, urgent keywords +2, repeat complaint from the same customer in the same category within 30 days +1. Score >= 4 High, >= 2 Medium, else Low. The reasons are shown after submitting a complaint.

## 11. Database (`database/customer_complaints.db`)
`customers`, `complaints`, `sentiment_results`, `categories`, `complaint_history` (status changes and notes), plus `users` and `settings`. Average resolution time = creation time to the first Resolved/Closed history entry.
"Customer Satisfaction" on the dashboard = share of complaints with Positive sentiment.

## 12. Installation and local run (Windows)
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000. On first run the console prints the generated admin username and password **once**. To choose your own, set environment variables first (`set ADMIN_PASSWORD=YourPassword`, optionally `ADMIN_USERNAME`, `SECRET_KEY`, `API_KEY`). Then: Upload Complaints -> "Import sample_complaints.csv".

## 13. Docker
```bash
docker build -t customer-complaint-analyzer .
docker run -d --name complaint-system -p 5000:5000 customer-complaint-analyzer
docker logs complaint-system        # shows the generated admin password on first start
```
Open http://localhost:5000. To pick credentials: add `-e ADMIN_PASSWORD=... -e SECRET_KEY=...`. To keep data between container re-creations: `-v complaint-data:/app/database`. The container uses Flask's built-in server, fine for demos; use gunicorn behind HTTPS for real deployment.

## 14. API documentation
Send the key from Settings in the `X-API-Key` header. GET endpoints also work with a logged-in browser session. All responses are JSON.

| Method | Endpoint | Purpose |
|---|---|---|
| POST | /api/complaints | Submit + analyze + save a complaint |
| GET | /api/complaints | List (filters: q, sentiment, priority, status, category, product, platform, date_range, page, per_page) |
| GET | /api/complaints/<id> | One complaint with history |
| PUT | /api/complaints/<id> | Update category, priority, platform, product, reference_id, status, note |
| POST | /api/analyze | Analyze text only (nothing saved) |
| GET | /api/sentiment | Sentiment counts and percentages |
| GET | /api/categories | Category counts |
| GET | /api/analytics | Summary, distributions, trend (`period=daily/weekly/monthly`) |
| GET | /api/customers | Customers with complaint counts |

```bash
curl -X POST http://localhost:5000/api/complaints -H "Content-Type: application/json" -H "X-API-Key: YOUR_KEY" \
 -d '{"customer_name":"Rahul Patel","customer_email":"rahul@example.com","product":"Wireless Headphones","complaint_text":"The headphones stopped working after two days.","platform":"Website","timestamp":"2026-10-01 10:30:00"}'
```
Returns `{"success": true, "complaint_id": ..., "sentiment": ..., "confidence": ..., "category": ..., "priority": ...}` (201). Errors: 400 invalid input, 401 bad key, 409 duplicate. The API is ready for future integrations (website forms, e-commerce, CRM, webhooks) but **no such integration is built in**.

## 15. CSV format
`customer_name,customer_email,product,complaint_text,category,platform,timestamp`
Required: customer_name, customer_email, complaint_text. Blank category = auto-detect; blank timestamp = now. Optional extra columns: customer_phone, reference_id. Max 2 MB / 5000 rows.

## 16. Testing
```bash
python -m unittest tests.test_nlp -v     # NLP tests (no database needed)
python -m unittest tests.test_app -v     # full app tests using a temporary database
```
Manual checks: add "The product stopped working after only two days. I am very disappointed." and "My payment was deducted twice for the same order."; upload the sample CSV twice (second time reports duplicates); try search/filters, status changes, notes, reports, API with curl.

## 17. Limitations
- The sentiment model is trained on a small (147 sentence) dataset; cross-validated accuracy on it is only about 60-65%, so expect mistakes on unusual wording. Add more labelled data and retrain.
- English text only. Category detection is keyword-based.
- Priority rules are simple and not validated against real support data.
- Timestamps are stored in server local time without time zones.
- Single admin role; login rate limiting is in memory; Flask development server.
- No integrations with real company systems; no PDF reports (CSV only).

## 18. Future enhancements
Larger training data or a transformer model, multi-language support, multiple users/roles and assignment, email/webhook intake, SLA timers and alerts, PDF reports, PostgreSQL, gunicorn + HTTPS.
