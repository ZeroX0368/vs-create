from flask import Flask, jsonify, request
from flask_cors import CORS
import requests, time, json, random, string, hashlib

app = Flask(__name__)
CORS(app)

# Cấu hình Header mặc định cho VSPhone
VSPHONE_HEADERS = {
    "accept": "*/*",
    "appversion": "1009001",
    "clienttype": "web",
    "channel": "vsagq956gu",
    "content-type": "application/json",
    "user-agent": "Mozilla/5.0",
}

EMAIL_USERNAME = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
EMAIL_DOMAIN = None
MAIL_TOKEN = None

def delay(): time.sleep(1)

def get_random_password():
    return ''.join(random.choices(string.digits, k=6))

# --- CÁC HÀM HỖ TRỢ ĐÃ CÓ ---
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

# --- API CHÍNH ---

@app.route("/", methods=["GET"])
def create_account():
    global MAIL_TOKEN
    try:
        current_password = get_random_password()
        if MAIL_TOKEN is None:
            create_mail_account(current_password)

        alias = f"{EMAIL_USERNAME}+{''.join(random.choices(string.digits, k=4))}@{EMAIL_DOMAIN}"
        
        # Gửi SMS & Đợi code (Giả định các hàm send_sms, wait_for_code, login đã có logic như cũ)
        # Ở đây mình viết gọn lại để tập trung vào phần /buy
        send_sms(alias)
        code = wait_for_code(alias)
        uid, user_token = login(alias, code, current_password)

        return jsonify({
            "email": alias,
            "password": current_password,
            "userId": uid,
            "token": user_token
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/buy", methods=["GET"])
def buy_trial():
    email = request.args.get("email")
    password = request.args.get("password")

    if not email or not password:
        return jsonify({"error": "Missing email or password"}), 400

    try:
        # Bước 1: Login để lấy Token (Sử dụng mật khẩu đã hash MD5)
        pass_md5 = hashlib.md5(password.encode()).hexdigest()
        login_payload = {
            "mobilePhone": email,
            "password": pass_md5,
            "loginType": 1, # Thường login bằng pass là type 1
            "channel": "vsagq956gu"
        }
        
        login_res = requests.post("https://api.vsphone.com/vsphone/api/user/login", 
                                  json=login_payload, headers=VSPHONE_HEADERS).json()
        
        if login_res.get("code") != 200:
            return jsonify({"success": False, "message": "Login failed", "details": login_res}), 401
        
        user_token = login_res["data"]["token"]
        user_id = login_res["data"]["userId"]

        # Bước 2: Gọi API mua gói VIP Trial
        # Gói trial thường miễn phí (0đ) hoặc dùng point/coupon
        buy_headers = VSPHONE_HEADERS.copy()
        buy_headers["token"] = user_token
        buy_headers["userid"] = str(user_id)

        # Endpoint mua hàng (Đây là endpoint giả định dựa trên cấu trúc VSPhone)
        buy_payload = {
            "goodId": 1,      # ID của gói Trial VIP (Bạn cần check chính xác ID này)
            "payType": 5,     # 5 thường là hình thức thanh toán nội bộ/free
            "buyNum": 1
        }

        buy_res = requests.post("https://api.vsphone.com/vsphone/api/order/createOrder", 
                                 json=buy_payload, headers=buy_headers).json()

        return jsonify({
            "success": True,
            "email": email,
            "order_status": buy_res.get("message", "Processed"),
            "raw_response": buy_res
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# Giữ nguyên các hàm send_sms, wait_for_code, login từ code cũ của bạn...
# [Paste các hàm đó vào đây]

if __name__ == "__main__":
    app.run(debug=True, port=5001)
