from flask import Flask, request, render_template, send_file, jsonify
import requests, json, io, os

app = Flask(__name__)

# ===== KEYS (Render will inject these) =====
OPENAI_KEY = os.getenv("OPENAI_KEY")
PDFCO_KEY = os.getenv("PDFCO_KEY")
STRIPE_SECRET = os.getenv("STRIPE_SECRET")
PRICE_ID = "YOUR_PRICE_ID" # <--- CHANGE THIS IN STEP 13

# ===== HOME PAGE =====
@app.route("/")
def home():
    return render_template("index.html", stripe_pk=os.getenv("STRIPE_PUBLISHABLE"))

# ===== STRIPE CHECKOUT SESSION =====
@app.route("/create-checkout", methods=["POST"])
def create_checkout():
    import stripe
    stripe.api_key = STRIPE_SECRET
    session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=[{
            'price': PRICE_ID,
            'quantity': 1
        }],
        mode='payment',
        success_url=request.host_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=request.host_url
    )
    return jsonify(sessionId=session.id)

# ===== FILL PDF =====
@app.route("/fill", methods=["POST"])
def fill_w9():
    data = request.json
    # 1. Call GPT-4o-mini
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

    # 2. Fill PDF with PDF.co
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
