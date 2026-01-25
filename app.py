from flask import Flask, jsonify, request
from flask_cors import CORS
import requests, time, json, random, string, hashlib

app = Flask(__name__)
CORS(app)

# Cấu hình CyberTemp
CYBERTEMP_KEY = 'tk_326e94871669e567d91dd844987e6b94bb8a89684d40c5a4d1e3020c7beeb421'
CYBER_HEADERS = {"x-api-key": CYBERTEMP_KEY, "Content-Type": "application/json"}

VSPHONE_HEADERS = {
    "accept": "*/*",
    "appversion": "1009001",
    "clienttype": "web",
    "channel": "vsagq956gu",
    "content-type": "application/json",
    "user-agent": "Mozilla/5.0",
}

def delay(): time.sleep(1)

def get_random_password():
    return ''.join(random.choices(string.digits, k=6))

# --- HÀM HỖ TRỢ CYBERTEMP ---

def get_cyber_domain():
    """Lấy danh sách domain từ CyberTemp và chọn ngẫu nhiên"""
    while True:
        try:
            r = requests.get("https://www.cybertemp.xyz/api/v1/domains", headers=CYBER_HEADERS)
            if r.status_code == 200:
                domains = r.json().get("domains", [])
                return random.choice(domains)
            delay()
        except: delay()

def create_cyber_account():
    """Tạo một địa chỉ email mới trên CyberTemp"""
    username = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    domain = get_cyber_domain()
    address = f"{username}@{domain}"
    
    payload = {"address": address}
    while True:
        try:
            r = requests.post("https://www.cybertemp.xyz/api/v1/emails", json=payload, headers=CYBER_HEADERS)
            if r.status_code == 201:
                return address
            delay()
        except: delay()

def wait_for_cyber_code(email_address):
    """Đợi và lấy mã OTP từ hộp thư CyberTemp"""
    while True:
        try:
            r = requests.get(f"https://www.cybertemp.xyz/api/v1/emails/{email_address}/messages", headers=CYBER_HEADERS)
            if r.status_code == 200:
                messages = r.json().get("messages", [])
                for m in messages:
                    # Kiểm tra tiêu đề hoặc nội dung có chứa VSPhone
                    subject = m.get("subject", "")
                    content = m.get("body", "") # Hoặc m.get("text", "") tùy API trả về
                    
                    if "VSPhone" in subject or "VSPhone" in content:
                        # Tìm chuỗi 6 số liên tiếp
                        import re
                        otp = re.findall(r'\b\d{6}\b', content)
                        if otp:
                            return otp[0]
            delay()
        except: delay()

# --- HÀM HỖ TRỢ VSPHONE ---

def send_vsphone_sms(email):
    data = {
        "smsType": 2,
        "mobilePhone": email,
        "captchaVerifyParam": json.dumps({"data": ""})
    }
    while True:
        try:
            r = requests.post("https://api.vsphone.com/vsphone/api/sms/smsSend", json=data, headers=VSPHONE_HEADERS)
            if r.status_code == 200: return
            delay()
        except: delay()

def login_vsphone(email, code, password):
    pass_md5 = hashlib.md5(password.encode()).hexdigest()
    payload = {
        "mobilePhone": email,
        "loginType": 0,
        "verifyCode": code,
        "password": pass_md5, 
        "channel": "vsagq956gu"
    }
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
    try:
        current_password = get_random_password()
        
        # 1. Tạo Email từ CyberTemp
        email = create_cyber_account()
        
        # 2. Gửi SMS yêu cầu mã từ VSPhone
        send_vsphone_sms(email)
        
        # 3. Đợi lấy mã OTP 6 số
        code = wait_for_cyber_code(email)
        
        # 4. Đăng nhập lấy UserId và Token
        uid, user_token = login_vsphone(email, code, current_password)

        return jsonify({
            "email": email,
            "password": current_password,
            "userId": uid,
            "token": user_token,
            "provider": "CyberTemp"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5001)
