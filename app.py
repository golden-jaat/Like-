from flask import Flask, request, jsonify
import asyncio
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToJson
import binascii
import aiohttp
import requests
import json
import like_pb2
import like_count_pb2
import uid_generator_pb2
from google.protobuf.message import DecodeError

app = Flask(__name__)

def load_tokens(server_name):
    try:
        if server_name == "IND":
            with open("token_ind.json", "r") as f:
                tokens = json.load(f)
        elif server_name in {"BR", "US", "SAC", "NA"}:
            with open("token_br.json", "r") as f:
                tokens = json.load(f)
        else:
            with open("token_bd.json", "r") as f:
                tokens = json.load(f)
        return tokens
    except Exception as e:
        app.logger.error(f"Error loading tokens for server {server_name}: {e}")
        return None

def encrypt_message(plaintext):
    try:
        key = b'Yg&tc%DEuh6%Zc^8'
        iv = b'6oyZDr22E3ychjM%'
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded_message = pad(plaintext, AES.block_size)
        encrypted_message = cipher.encrypt(padded_message)
        return binascii.hexlify(encrypted_message).decode('utf-8')
    except Exception as e:
        app.logger.error(f"Error encrypting message: {e}")
        return None

def create_protobuf_message(user_id, region):
    try:
        message = like_pb2.like()
        message.uid = int(user_id)
        message.region = region
        return message.SerializeToString()
    except Exception as e:
        app.logger.error(f"Error creating protobuf message: {e}")
        return None

async def send_request(encrypted_uid, token, url):
    try:
        edata = bytes.fromhex(encrypted_uid)
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'Expect': "100-continue",
            'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB53"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=edata, headers=headers) as response:
                if response.status != 200:
                    app.logger.error(f"Request failed with status code: {response.status}")
                    return response.status
                return await response.text()
    except Exception as e:
        app.logger.error(f"Exception in send_request: {e}")
        return None

async def send_multiple_requests(uid, server_name, url):
    try:
        region = server_name
        protobuf_message = create_protobuf_message(uid, region)
        if protobuf_message is None:
            app.logger.error("Failed to create protobuf message.")
            return None
        encrypted_uid = encrypt_message(protobuf_message)
        if encrypted_uid is None:
            app.logger.error("Encryption failed.")
            return None
        tasks = []
        tokens = load_tokens(server_name)
        if tokens is None:
            app.logger.error("Failed to load tokens.")
            return None
        for i in range(100):
            token = tokens[i % len(tokens)]["token"]
            tasks.append(send_request(encrypted_uid, token, url))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return results
    except Exception as e:
        app.logger.error(f"Exception in send_multiple_requests: {e}")
        return None

def create_protobuf(uid):
    try:
        message = uid_generator_pb2.uid_generator()
        message.saturn_ = int(uid)
        message.garena = 1
        return message.SerializeToString()
    except Exception as e:
        app.logger.error(f"Error creating uid protobuf: {e}")
        return None

def enc(uid):
    protobuf_data = create_protobuf(uid)
    if protobuf_data is None:
        return None
    encrypted_uid = encrypt_message(protobuf_data)
    return encrypted_uid

def make_request(encrypt, server_name, token):
    try:
        if server_name == "IND":
            url = "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
        elif server_name in {"BR", "US", "SAC", "NA"}:
            url = "https://client.us.freefiremobile.com/GetPlayerPersonalShow"
        else:
            url = "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow"
        edata = bytes.fromhex(encrypt)
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'Expect': "100-continue",
            'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB53"
        }
        response = requests.post(url, data=edata, headers=headers, verify=False, timeout=30)
        hex_data = response.content.hex()
        binary = bytes.fromhex(hex_data)
        decode = decode_protobuf(binary)
        if decode is None:
            app.logger.error("Protobuf decoding returned None.")
        return decode
    except Exception as e:
        app.logger.error(f"Error in make_request: {e}")
        return None

def decode_protobuf(binary):
    try:
        items = like_count_pb2.Info()
        items.ParseFromString(binary)
        return items
    except DecodeError as e:
        app.logger.error(f"Error decoding Protobuf data: {e}")
        return None
    except Exception as e:
        app.logger.error(f"Unexpected error during protobuf decoding: {e}")
        return None

def fetch_player_info(uid):
    try:
        url = f"https://starhosterpanel.qzz.io/accinfo?uid={uid}"
        app.logger.info(f"Fetching player info from: {url}")
        response = requests.get(url, timeout=10)
        app.logger.info(f"API Response Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            app.logger.info(f"API Response Data Keys: {data.keys() if data else 'No data'}")
            
            # Try to get basicInfo
            basic_info = data.get("basicInfo", {})
            if basic_info:
                app.logger.info(f"Basic Info found - Region: {basic_info.get('region', 'NA')}, Level: {basic_info.get('level', 'NA')}")
            else:
                app.logger.warning("No basicInfo in API response")
                # Try alternate paths
                basic_info = data.get("accountInfo", {})
            
            region = basic_info.get("region", "NA")
            # If region is NA but we have data, something is wrong
            if region == "NA" and basic_info:
                app.logger.warning(f"Region is NA but basic_info exists: {basic_info}")
                
            return {
                "Level": basic_info.get("level", "NA"),
                "Region": region,
                "ReleaseVersion": basic_info.get("releaseVersion", "NA"),
                "Nickname": basic_info.get("nickname", "NA"),
                "Liked": basic_info.get("liked", 0),
                "Rank": basic_info.get("rank", 0),
                "Exp": basic_info.get("exp", 0),
                "BadgeCnt": basic_info.get("badgeCnt", 0),
                "HasElitePass": basic_info.get("hasElitePass", False),
                "PrimeLevel": basic_info.get("primeInfo", {}).get("primeLevel", 0),
                "CreditScore": data.get("creditScoreInfo", {}).get("creditScore", 0)
            }
        else:
            app.logger.error(f"Player info API failed with status code: {response.status_code}")
            return {
                "Level": "NA", 
                "Region": "NA", 
                "ReleaseVersion": "NA",
                "Nickname": "NA",
                "Liked": 0,
                "Rank": 0,
                "Exp": 0,
                "BadgeCnt": 0,
                "HasElitePass": False,
                "PrimeLevel": 0,
                "CreditScore": 0
            }
    except requests.exceptions.Timeout:
        app.logger.error(f"Timeout fetching player info for UID: {uid}")
        return {
            "Level": "NA", 
            "Region": "NA", 
            "ReleaseVersion": "NA",
            "Nickname": "NA",
            "Liked": 0,
            "Rank": 0,
            "Exp": 0,
            "BadgeCnt": 0,
            "HasElitePass": False,
            "PrimeLevel": 0,
            "CreditScore": 0
        }
    except requests.exceptions.ConnectionError as e:
        app.logger.error(f"Connection error fetching player info: {e}")
        return {
            "Level": "NA", 
            "Region": "NA", 
            "ReleaseVersion": "NA",
            "Nickname": "NA",
            "Liked": 0,
            "Rank": 0,
            "Exp": 0,
            "BadgeCnt": 0,
            "HasElitePass": False,
            "PrimeLevel": 0,
            "CreditScore": 0
        }
    except Exception as e:
        app.logger.error(f"Error fetching player info from API: {e}")
        return {
            "Level": "NA", 
            "Region": "NA", 
            "ReleaseVersion": "NA",
            "Nickname": "NA",
            "Liked": 0,
            "Rank": 0,
            "Exp": 0,
            "BadgeCnt": 0,
            "HasElitePass": False,
            "PrimeLevel": 0,
            "CreditScore": 0
        }

@app.route('/like', methods=['GET'])
def handle_requests():
    uid = request.args.get("uid")
    server_name = request.args.get("server_name", "").upper()
    
    app.logger.info(f"Received request - UID: {uid}, Server: {server_name}")
    
    if not uid or not server_name:
        return jsonify({"error": "UID and server_name are required"}), 400

    try:
        def process_request():
            # Fetch player info from the API
            player_info = fetch_player_info(uid)
            region = player_info["Region"]
            level = player_info["Level"]
            release_version = player_info["ReleaseVersion"]
            nickname = player_info["Nickname"]
            current_likes = player_info["Liked"]
            rank = player_info["Rank"]
            exp = player_info["Exp"]
            badge_cnt = player_info["BadgeCnt"]
            has_elite_pass = player_info["HasElitePass"]
            prime_level = player_info["PrimeLevel"]
            credit_score = player_info["CreditScore"]
            
            app.logger.info(f"Player info from API - Region: {region}, Level: {level}, ReleaseVersion: {release_version}")
            
            # If API returned NA for region, use the server_name provided
            if region == "NA" or region == "":
                app.logger.warning(f"API returned region as NA, using server_name: {server_name}")
                server_name_used = server_name
            # Validate server_name against region from API
            elif region != "NA" and server_name != region:
                app.logger.warning(f"Server name {server_name} does not match API region {region}. Using API region.")
                server_name_used = region
            else:
                server_name_used = server_name
            
            app.logger.info(f"Using server: {server_name_used}")
            
            tokens = load_tokens(server_name_used)
            if tokens is None:
                raise Exception("Failed to load tokens.")
            token = tokens[0]['token']
            encrypted_uid = enc(uid)
            if encrypted_uid is None:
                raise Exception("Encryption of UID failed.")

            before = make_request(encrypted_uid, server_name_used, token)
            if before is None:
                raise Exception("Failed to retrieve initial player info.")
            try:
                jsone = MessageToJson(before)
            except Exception as e:
                raise Exception(f"Error converting 'before' protobuf to JSON: {e}")
            data_before = json.loads(jsone)
            before_like = data_before.get('AccountInfo', {}).get('Likes', 0)
            try:
                before_like = int(before_like)
            except Exception:
                before_like = 0
            app.logger.info(f"Likes before command: {before_like}")

            if server_name_used == "IND":
                url = "https://client.ind.freefiremobile.com/LikeProfile"
            elif server_name_used in {"BR", "US", "SAC", "NA"}:
                url = "https://client.us.freefiremobile.com/LikeProfile"
            else:
                url = "https://clientbp.ggpolarbear.com/LikeProfile"

            asyncio.run(send_multiple_requests(uid, server_name_used, url))

            after = make_request(encrypted_uid, server_name_used, token)
            if after is None:
                raise Exception("Failed to retrieve player info after like requests.")
            try:
                jsone_after = MessageToJson(after)
            except Exception as e:
                raise Exception(f"Error converting 'after' protobuf to JSON: {e}")
            data_after = json.loads(jsone_after)
            after_like = int(data_after.get('AccountInfo', {}).get('Likes', 0))
            player_uid = int(data_after.get('AccountInfo', {}).get('UID', 0))
            player_name = str(data_after.get('AccountInfo', {}).get('PlayerNickname', ''))
            like_given = after_like - before_like
            status = 1 if like_given != 0 else 2
            
            result = {
                "LikesGivenByAPI": like_given,
                "LikesAfterCommand": after_like,
                "LikesBeforeCommand": before_like,
                "PlayerNickname": player_name if player_name != '' else nickname,
                "Region": region if region != "NA" else server_name_used,
                "UID": player_uid,
                "ReleaseVersion": release_version if release_version != "NA" else "OB53",
                "status": status
            }
            return result

        result = process_request()
        return jsonify(result)
    except Exception as e:
        app.logger.error(f"Error processing request: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Enable debug logging
    import logging
    logging.basicConfig(level=logging.INFO)
    app.run(debug=True, use_reloader=False)