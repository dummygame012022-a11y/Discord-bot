import os
from dotenv import load_dotenv
from flask import Flask, jsonify, request

load_dotenv()
API_KEY = os.getenv("API_KEY")
app = Flask(__name__)


@app.before_request
def check_key():
    k = request.headers.get("X-API-Key")
    if not API_KEY or k != API_KEY:
        return jsonify({"error": "unauthorized"}), 401

PRODUCTS = [
    {"name": "Wireless Mouse", "price": 15.99, "stock": 42},
    {"name": "Mechanical Keyboard", "price": 49.50, "stock": 12},
    {"name": "USB-C Hub", "price": 24.00, "stock": 0},
    {"name": "Laptop Stand", "price": 19.75, "stock": 30},
    {"name": "Webcam HD", "price": 34.90, "stock": 8},
]


@app.route("/api/membership/<uid>")
def membership(uid):
    if int(uid) % 2 == 0:
        return jsonify({"active": True, "plan": "Pro", "expires": "2027-01-01"})
    return jsonify({"active": False}), 404


@app.route("/api/products")
def products():
    q = request.args.get("q", "").lower()
    found = [p for p in PRODUCTS if q in p["name"].lower()]
    return jsonify({"count": len(found), "items": found[:5]})


app.run(host="127.0.0.1", port=5060)
