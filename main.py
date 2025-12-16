import os
import stripe
import requests, json, io
from flask import Flask, request, render_template, send_file, jsonify

app = Flask(__name__)

# ===== KEYS FROM RENDER ENVIRONMENT =====
OPENAI_KEY = os.environ.get("OPENAI_KEY")
PDFCO_KEY = os.environ.get("PDFCO_KEY")
STRIPE_SECRET = os.environ.get("STRIPE_SECRET")
STRIPE_PUBLISHABLE = os.environ.get("STRIPE_PUBLISHABLE")
PRICE_ID = "price_1SezD3QqfvtCQZDRvXvitWNi"  # REPLACE with your real one

# Initialize Stripe
stripe.api_key = STRIPE_SECRET

@app.route("/")
def home():
    return render_template("index.html", stripe_pk=STRIPE_PUBLISHABLE)

@app.route("/create-checkout", methods=["POST"])
def create_checkout():
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{"price": PRICE_ID, "quantity": 1}],
        mode='payment',
        success_url=request.host_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=request.host_url
    )
    return jsonify(sessionId=session.id)

@app.route("/fill", methods=["POST"])
def fill_w9():
    data = request.json
    prompt = f"""You are a W-9 formatting robot. Return ONLY raw JSON.
Keys: name, business_name, address, city_state_zip, ssn, ein, llc_checked (boolean).
Rules: SSN xxx-xx-xxxx, EIN xx-xxxxxxx, ALL CAPS.
Profile: {data}"""
    
    openai_resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_KEY}"},
        json={"model": "gpt-4o-mini", "temperature": 0, "messages": [{"role": "user", "content": prompt}]}
    )
    fields = json.loads(openai_resp.json()['choices'][0]['message']['content'])

    pdfco_payload = {
        "async": False,
        "name": "w9_filled",
        "url": f"{request.host_url}static/fw9.pdf",
        "fields": [
            {"fieldName": "name_field", "pages": "1", "text": fields["name"]},
            {"fieldName": "business_name", "pages": "1", "text": fields["business_name"]},
            {"fieldName": "address_field", "pages": "1", "text": fields["address"]},
            {"fieldName": "city_state_zip", "pages": "1", "text": fields["city_state_zip"]},
            {"fieldName": "ssn_field", "pages": "1", "text": fields["ssn"]},
            {"fieldName": "ein_field", "pages": "1", "text": fields["ein"]},
            {"fieldName": "llc_checkbox", "pages": "1", "text": "✔" if fields["llc_checked"] else ""}
        ]
    }

    pdf_resp = requests.post(
        "https://api.pdf.co/v1/pdf/edit/add",
        headers={"x-api-key": PDFCO_KEY, "Content-Type": "application/json"},
        json=pdfco_payload
    )
    pdf_url = pdf_resp.json()['url']
    download = requests.get(pdf_url)

    return send_file(io.BytesIO(download.content), as_attachment=True, download_name="w9_filled.pdf")

@app.route("/debug")
def debug():
    return jsonify({
        "price_id_set": PRICE_ID is not None,
        "price_id_value": PRICE_ID,
        "stripe_secret_set": STRIPE_SECRET is not None,
        "openai_key_set": OPENAI_KEY is not None,
        "pdfco_key_set": PDFCO_KEY is not None
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
