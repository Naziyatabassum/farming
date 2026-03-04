import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_pymongo import PyMongo
from bson import ObjectId
from datetime import datetime
from flask_jwt_extended import (
    JWTManager,
    jwt_required,
    create_access_token,
    get_jwt_identity
)
import bcrypt
import pickle
import pandas as pd
from datetime import datetime
import google.generativeai as genai

# ------------------ LOAD ENV ------------------
load_dotenv()

app = Flask(__name__)

# ------------------ CORS ------------------
CORS(
    app,
    origins=[
        "http://localhost:3000",
        "https://farming-rho.vercel.app/"
    ],
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization"]
)

# ------------------ CONFIG ------------------
app.config["MONGO_URI"] = os.getenv("MONGO_URI")
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET")

mongo = PyMongo(app)
jwt = JWTManager(app)

# ------------------ GOOGLE AI (✅ FIXED) ------------------
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")

# ------------------ LOAD ML MODELS ------------------
crop_model = pickle.load(open("crop_model.pkl", "rb"))              # crop recommendation
fertilizer_model = pickle.load(open("fertilizer_model.pkl", "rb"))
label_encoders = pickle.load(open("fertilizer_label_encoders.pkl", "rb"))

dtr = pickle.load(open("dtr.pkl", "rb"))                             # crop yield
preprocessor = pickle.load(open("preprocessor.pkl", "rb"))

# ------------------ HOME ------------------
@app.route("/")
def home():
    return "Farming API is running!"

# ------------------ AUTH ------------------
@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json()

    if mongo.db.users.find_one({"email": data["email"]}):
        return jsonify({"msg": "User already exists"}), 409

    hashed_pw = bcrypt.hashpw(
        data["password"].encode("utf-8"),
        bcrypt.gensalt()
    )

    mongo.db.users.insert_one({
        "email": data["email"],
        "name": data.get("name"),
        "password": hashed_pw
    })

    return jsonify({"msg": "User created"}), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    user = mongo.db.users.find_one({"email": data["email"]})

    if user and bcrypt.checkpw(
        data["password"].encode("utf-8"),
        user["password"]
    ):
        token = create_access_token(identity=str(user["_id"]))
        return jsonify({
            "token": token,
            "user": {
                "name": user.get("name", "User"),
                "email": user["email"]
            }
        })

    return jsonify({"msg": "Invalid credentials"}), 401


# ------------------ HISTORY ENDPOINTS ------------------
def serialize_date(d):
    if isinstance(d, datetime):
        return d.isoformat()  # convert datetime to ISO string
    return str(d)

@app.route("/api/crop-predictions", methods=["GET"])
@jwt_required()
def crop_history():
    user_id = get_jwt_identity()
    data = list(mongo.db.crop_yield_predictions.find({"userId": user_id}))
    result = []
    for d in data:
        result.append({
            "_id": str(d["_id"]),
            "cropRecommendation": d.get("input", {}).get("Item", "Unknown"),
            "createdAt": serialize_date(d.get("createdAt"))
        })
    return jsonify(result)

@app.route("/api/fertilizer-recommendations", methods=["GET"])
@jwt_required()
def fertilizer_history():
    user_id = get_jwt_identity()
    data = list(mongo.db.fertilizer_predictions.find({"userId": user_id}))
    result = []
    for d in data:
        result.append({
            "_id": str(d["_id"]),
            "fertilizerType": d.get("recommended_fertilizer", "Unknown"),
            "crop": d.get("crop", "Unknown"),
            "createdAt": serialize_date(d.get("createdAt"))
        })
    return jsonify(result)

@app.route("/api/yield-predictions", methods=["GET"])
@jwt_required()
def yield_history():
    user_id = get_jwt_identity()
    data = list(mongo.db.crop_yield_predictions.find({"userId": user_id}))
    result = []
    for d in data:
        result.append({
            "_id": str(d["_id"]),
            "predictedYield": d.get("prediction", 0),
            "crop": d.get("input", {}).get("Item", "Unknown"),
            "createdAt": serialize_date(d.get("createdAt"))
        })
    return jsonify(result)



# ------------------ JWT ERRORS ------------------
@jwt.unauthorized_loader
def unauthorized(err):
    return jsonify({"error": "Missing or invalid JWT"}), 401

@jwt.invalid_token_loader
def invalid(err):
    return jsonify({"error": "Invalid JWT"}), 401

@jwt.expired_token_loader
def expired(jwt_header, jwt_payload):
    return jsonify({"error": "JWT expired"}), 401

# ------------------ SAVE HELPER ------------------
def save_prediction(collection, user_id, data):
    data.update({
        "userId": user_id,
        "createdAt": datetime.utcnow()
    })
    mongo.db[collection].insert_one(data)

# =========================================================
# ✅ 1️⃣ CROP YIELD PREDICTION
# =========================================================
@app.route("/predict-yield", methods=["POST"])
@jwt_required()
def predict_yield():
    user_id = get_jwt_identity()
    data = request.get_json()

    try:
        input_df = pd.DataFrame([{
            "Year": float(data["Year"]),
            "average_rain_fall_mm_per_year": float(data["average_rain_fall_mm_per_year"]),
            "pesticides_tonnes": float(data["pesticides_tonnes"]),
            "avg_temp": float(data["avg_temp"]),
            "Area": data["Area"],
            "Item": data["Item"]
        }])

        transformed = preprocessor.transform(input_df)
        prediction = dtr.predict(transformed)[0]

        save_prediction("crop_yield_predictions", user_id, {
            "input": data,
            "prediction": prediction
        })

        return jsonify({"prediction": round(float(prediction), 2)})

    except Exception as e:
        return jsonify({"error": str(e)}), 400

# =========================================================
# ✅ 2️⃣ CROP RECOMMENDATION
# =========================================================
@app.route("/predict-crop", methods=["POST"])
@jwt_required()
def predict_crop():
    data = request.get_json()

    try:
        df = pd.DataFrame([{
        "Nitrogen": float(data["N"]),
        "Phosphorus": float(data["P"]),
        "Potassium": float(data["K"]),
        "Temperature": float(data["temperature"]),
        "Humidity": float(data["humidity"]),
        "pH_Value": float(data["ph"]),
        "Rainfall": float(data["rainfall"])
}])


        crop = crop_model.predict(df)[0]
        return jsonify({"recommended_crop": crop})

    except Exception as e:
        return jsonify({"error": str(e)}), 400

# =========================================================
# ✅ 3️⃣ FERTILIZER
# =========================================================
@app.route("/fertilizer-predict", methods=["POST"])
@jwt_required()
def fertilizer_predict():
    data = request.get_json()

    try:
        encoded_soil = label_encoders["Soil_Type"].transform([data["soil_type"]])[0]
        encoded_crop = label_encoders["Crop_Type"].transform([data["crop_type"]])[0]

        df = pd.DataFrame([{
            "Temparature": float(data["temperature"]),
            "Humidity": float(data["humidity"]),
            "Moisture": float(data["moisture"]),
            "Soil_Type": encoded_soil,
            "Crop_Type": encoded_crop,
            "Nitrogen": float(data["nitrogen"]),
            "Potassium": float(data["potassium"]),
            "Phosphorous": float(data["phosphorous"])
        }])

        pred_encoded = fertilizer_model.predict(df)[0]
        fertilizer = label_encoders["Fertilizer"].inverse_transform([pred_encoded])[0]

        return jsonify({"recommended_fertilizer": fertilizer})

    except Exception as e:
        return jsonify({"error": str(e)}), 400

# ------------------ GOOGLE AI CHAT ------------------
@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    message = data.get("message", "").strip()
    language = data.get("language", "English")

    if not message:
        return jsonify({"reply": "Please enter a message"}), 400

    prompt = f"""You are a helpful agricultural assistant. 
Keep answers concise and practical.
Reply in {language}.

Query: {message}"""

    try:
        response = model.generate_content(prompt)
        return jsonify({"reply": response.text[:1000]})
    except Exception as e:
        if "quota" in str(e).lower() or "429" in str(e):
            return jsonify({"reply": "AI quota exceeded. Try again in 1 hour."}), 429
        elif "404" in str(e):
            return jsonify({"reply": "Model temporarily unavailable. Please restart app."}), 503
        else:
            return jsonify({"reply": f"Service error. Try again."}), 500

# ------------------ RUN ------------------
if __name__ == "__main__":  # ✅ Fixed __name__
    app.run(host="0.0.0.0", port=5000)