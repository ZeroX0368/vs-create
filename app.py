from flask import Flask, jsonify, request
from flask_cors import CORS
import requests, time, json, random, string, hashlib, re

app = Flask(__name__)
CORS(app)

CYBERTEMP_API_KEY = 'tk_888edc4ffa2a7b4e0235d026c7546f24ec998dc59537de317386ff7cb0126593'

def delay(seconds=3):
    time.sleep(seconds)

def get_random_password():
    return str(random.randint(100000, 999999))

def generate_email_username():
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choices(chars, k=10))

def get_domains(api_key, options=None):
    if options is None:
        options = {}
    
    params = {}
    if options.get('tld_include'):
        params['tld_include'] = options['tld_include']
    if options.get('tld_exclude'):
        params['tld_exclude'] = options['tld_exclude']
    if options.get('type'):
        params['type'] = options['type']
    if options.get('limit'):
        params['limit'] = str(options['limit'])
    if options.get('offset'):
        params['offset'] = str(options['offset'])
    
    url = "https://api.cybertemp.xyz/getDomains"
    headers = {'X-API-KEY': api_key}
    
    response = requests.get(url, params=params, headers=headers)
    if response.status_code != 200:
        raise Exception(f"CyberTemp getDomains failed: {response.status_code}")
    
    return response.json()

def get_emails(email, api_key=None, limit=25, offset=0):
    headers = {'X-API-KEY': api_key} if api_key else {}
    params = {'email': email}
    if limit != 25:
        params['limit'] = str(limit)
    if offset > 0:
        params['offset'] = str(offset)
    
    url = "https://api.cybertemp.xyz/getMail"
    response = requests.get(url, params=params, headers=headers)
    
    if response.status_code != 200:
        raise Exception(f"CyberTemp getMail failed: {response.status_code}")
    
    return response.json()

def create_cybertemp_email():
    try:
        domains_data = get_domains(CYBERTEMP_API_KEY, {
            'tld_include': 'com,net',
            'tld_exclude': 'xyz',
            'type': 'discord'
        })
        
        if isinstance(domains_data, list):
            domains = domains_data
        elif isinstance(domains_data, dict):
            domains = domains_data.get('domains', [])
        else:
            domains = []
        
        if not domains or len(domains) == 0:
            raise Exception("No domains available from CyberTemp")
        
        first_domain = domains[0]
        if isinstance(first_domain, dict):
            domain = first_domain.get('domain', str(first_domain))
        else:
            domain = str(first_domain)
        
        username = generate_email_username()
        email = f"{username}@{domain}"
        
        return {'email': email, 'domain': domain}
    except Exception as e:
        print(f"CyberTemp error: {e}")
        raise

def check_cybertemp_inbox(email):
    try:
        data = get_emails(email, CYBERTEMP_API_KEY, 50, 0)
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return data.get('mails') or data.get('messages') or []
        return []
    except Exception as e:
        print(f"CyberTemp inbox error: {e}")
        raise

def extract_otp(messages):
    if not isinstance(messages, list):
        return None
    
    for m in messages:
        if isinstance(m, dict):
            subject = str(m.get('subject', ''))
            body = str(m.get('text') or m.get('body') or m.get('snippet') or m.get('html') or m.get('content') or '')
            combined = f"{subject} {body}"
        else:
            combined = str(m)
        
        match = re.search(r'\b\d{6}\b', combined)
        if match:
            return match.group(0)
    
    return None

def send_sms(email_alias):
    data = {
        "smsType": 2,
        "mobilePhone": email_alias,
        "captchaVerifyParam": json.dumps({"data": ""})
    }
    headers = {"Content-Type": "application/json"}
    
    response = requests.post("https://api.vsphone.com/vsphone/api/sms/smsSend", json=data, headers=headers)
    if response.status_code != 200:
        raise Exception(f"VSPhone SMS request failed: {response.status_code}")
    
    return response.json()

def login_vsphone(email_alias, code, password):
    pass_md5 = hashlib.md5(password.encode()).hexdigest()
    
    payload = {
        "mobilePhone": email_alias,
        "loginType": 0,
        "verifyCode": code,
        "password": pass_md5,
        "channel": "vsagq956gu"
    }
    headers = {
        "accept": "*/*",
        "appversion": "1009001",
        "clienttype": "web",
        "channel": "vsagq956gu",
        "content-type": "application/json",
        "user-agent": "Mozilla/5.0",
        "userid": "0"
    }
    
    response = requests.post("https://api.vsphone.com/vsphone/api/user/login", json=payload, headers=headers)
    data = response.json()
    
    if response.status_code == 200 and data.get('data'):
        return data['data']['userId'], data['data']['token']
    else:
        raise Exception(f"Login failed: {data.get('message', json.dumps(data))}")

@app.route("/reg", methods=["GET"])
def create_account():
    try:
        password = get_random_password()
        
        email_data = create_cybertemp_email()
        email = email_data['email']
        
        send_sms(email)
        
        code = None
        attempts = 0
        max_attempts = 40
        
        while attempts < max_attempts:
            delay(3)
            
            try:
                messages = check_cybertemp_inbox(email)
                code = extract_otp(messages)
                
                if code:
                    break
            except Exception as e:
                print(f"Polling error: {e}")
            
            attempts += 1
        
        if not code:
            raise Exception("Timeout: 6-digit OTP not received after 2 minutes.")
        
        user_id, user_token = login_vsphone(email, code, password)
        
        return jsonify({
            "email": email,
            "password": password,
            "userId": user_id,
            "token": user_token
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
