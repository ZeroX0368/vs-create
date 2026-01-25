from flask import Flask, jsonify, request
from flask_cors import CORS
import requests, time, json, random, string, hashlib

app = Flask(__name__)
CORS(app)

# Cấu hình chung cho VSPhone
VSPHONE_HEADERS = {
    "accept": "*/*",
    "appversion": "1009001",
    "clienttype": "web",
    "channel": "vsagq956gu",
    "content-type": "application/json",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# Biến toàn cục cho Mail
EMAIL_USERNAME = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
EMAIL_DOMAIN = None
MAIL_TOKEN = None

def delay(): time.sleep(1)

def get_random_password():
    return ''.join(random.choices(string.digits, k=6))

# --- HÀM HỖ TRỢ MAIL ---
def get_mail_domain():
    while True:
        try:
            domains = requests.get("https://api.mail.tm/domains").json()["hydra:member"]
            return random.choice(domains)["domain"]
        except: delay()

def create_mail_account(password):
    global EMAIL_DOMAIN, MAIL_TOKEN
    EMAIL_DOMAIN = get_mail_domain()
    address = f"{EMAIL_USERNAME}@{EMAIL_DOMAIN}"
    payload = {"address": address, "password": password}
    while True:
        try:
            r = requests.post("https://api.mail.tm/accounts", json=payload)
            if r.status_code == 201:
                t = requests.post("https://api.mail.tm/token", json=payload).json()
                if "token" in t:
                    MAIL_TOKEN = t["token"]
                    return
            delay()
        except: delay()

def gen_email_alias():
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"{EMAIL_USERNAME}+{suffix}@{EMAIL_DOMAIN}"

# --- HÀM HỖ TRỢ VSPHONE ---
def send_sms(email_alias):
    data = {"smsType": 2, "mobilePhone": email_alias, "captchaVerifyParam": json.dumps({"data": ""})}
    while True:
        try:
            r = requests.post("https://api.vsphone.com/vsphone/api/sms/smsSend", json=data, headers=VSPHONE_HEADERS)
            if r.status_code == 200: return
            delay()
        except: delay()

def wait_for_code(alias):
    headers = {"Authorization": f"Bearer {MAIL_TOKEN}"}
    while True:
        try:
            msgs = requests.get("https://api.mail.tm/messages", headers=headers).json().get("hydra:member", [])
            for m in msgs:
                recipients = [to['address'] for to in m.get("to", [])]
                if any(alias.lower() == to.lower() for to in recipients) and "VSPhone" in m["subject"]:
                    msg = requests.get(f"https://api.mail.tm/messages/{m['id']}", headers=headers).json()
                    for line in msg.get("text", "").splitlines():
                        if line.strip().isdigit() and len(line.strip()) == 6:
                            return line.strip()
            delay()
        except: delay()

def login_vs(email_alias, code, password):
    pass_md5 = hashlib.md5(password.encode()).hexdigest()
    payload = {"mobilePhone": email_alias, "loginType": 0, "verifyCode": code, "password": pass_md5, "channel": "vsagq956gu"}
    while True:
        try:
            r = requests.post("https://api.vsphone.com/vsphone/api/user/login", json=payload, headers=VSPHONE_HEADERS)
            if r.status_code == 200 and "data" in r.json():
                d = r.json()["data"]
                return d["userId"], d["token"]
            delay()
        except: delay()

# --- API ENDPOINTS ---

@app.route("/", methods=["GET"])
def create_account():
    global MAIL_TOKEN
    try:
        current_password = get_random_password()
        if MAIL_TOKEN is None:
            create_mail_account(current_password)

        alias = gen_email_alias()
        send_sms(alias)
        code = wait_for_code(alias)
        uid, user_token = login_vs(alias, code, current_password)

        return jsonify({"email": alias, "password": current_password, "userId": uid, "token": user_token})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/trial", methods=["GET"])
def buy_cloud_trial():
    email = request.args.get("mail")
    password = request.args.get("password")

    if not email or not password:
        return jsonify({"error": "Missing parameters: mail & password"}), 400

    try:
        # Bước 1: Login lấy token
        pass_md5 = hashlib.md5(password.encode()).hexdigest()
        login_payload = {"mobilePhone": email, "password": pass_md5, "loginType": 1, "channel": "vsagq956gu"}
        
        login_res = requests.post("https://api.vsphone.com/vsphone/api/user/login", 
                                  json=login_payload, headers=VSPHONE_HEADERS).json()
        
        if login_res.get("code") != 200:
            return jsonify({"success": False, "message": "Login failed"}), 401
        
        token = login_res["data"]["token"]
        userid = login_res["data"]["userId"]

        # Bước 2: Gọi API Mua Cloud Trial
        # goodId: 1 (ID mặc định cho gói Trial/Dùng thử Cloud)
        buy_headers = VSPHONE_HEADERS.copy()
        buy_headers.update({"token": token, "userid": str(userid)})
        buy_payload = {"goodId": 1, "payType": 5, "buyNum": 1}

        order_res = requests.post("https://api.vsphone.com/vsphone/api/order/createOrder", 
                                   json=buy_payload, headers=buy_headers).json()

        return jsonify({
            "success": True,
            "email": email,
            "cloud_status": order_res.get("message", "Request Processed"),
            "details": order_res
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5001)
