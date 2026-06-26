#!/usr/bin/env python3
"""
WeChat ClawBot Message Sender via iLink API.

Usage:
    send_wechat.py send "消息内容"          # 发送文本消息
    send_wechat.py refresh                  # 刷新 context_token
    send_wechat.py status                   # 查看当前 token 状态

Configuration is read from WorkBuddy settings.json automatically.
context_token is cached to ~/.workbuddy/skills/wechat-clawbot-notify/.token_cache.json
"""

import json
import os
import sys
import time
import uuid
import base64
import hashlib
import urllib.request
import urllib.error

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding as crypto_padding

if sys.version_info < (3, 8):
    print("Error: Python 3.8 or newer is required.", file=sys.stderr)
    sys.exit(1)

# --- Paths ---
SKILL_DIR = os.environ.get("SKILL_DIR", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_FILE = os.path.join(SKILL_DIR, ".token_cache.json")
LOG_FILE = os.path.join(SKILL_DIR, "logs", "send_wechat.log")
CHANNEL_VERSION = "workbuddy-desktop-1.0.0"

def _workbuddy_settings_candidates():
    if sys.platform == "darwin":
        return [
            os.path.expanduser("~/.workbuddy/settings.json"),
            os.path.expanduser("~/Library/Application Support/WorkBuddy/User/settings.json"),
        ]
    if sys.platform == "win32":
        candidates = []
        userprofile = os.environ.get("USERPROFILE")
        if userprofile:
            candidates.append(os.path.join(userprofile, ".workbuddy", "settings.json"))
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(os.path.join(appdata, "WorkBuddy", "User", "settings.json"))
        if candidates:
            return candidates
        return [os.path.expanduser("~/AppData/Roaming/WorkBuddy/User/settings.json")]
    return [
        os.path.expanduser("~/.workbuddy/settings.json"),
        os.path.expanduser("~/.config/WorkBuddy/User/settings.json"),
    ]


def _extract_weixin_clawbot_config(settings):
    channels = settings.get("claw", {}).get("channels")
    if isinstance(channels, dict) and "weixinClawBot" in channels:
        return channels["weixinClawBot"]

    users = settings.get("claw", {}).get("users", {})
    if isinstance(users, dict):
        for uid, user_cfg in users.items():
            if not isinstance(user_cfg, dict):
                continue
            user_channels = user_cfg.get("channels", {})
            if isinstance(user_channels, dict) and "weixinClawBot" in user_channels:
                return user_channels["weixinClawBot"]

    return {}


WORKBUDDY_SETTINGS = _workbuddy_settings_candidates()[0]


def log(message):
    """Append-only action log."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{ts}\t{message}\n")


def load_config():
    """Load ClawBot config from WorkBuddy settings."""
    errors = []
    bot_cfg = {}
    settings_path = None

    for candidate in _workbuddy_settings_candidates():
        try:
            with open(candidate, "r", encoding="utf-8-sig") as f:
                settings = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            errors.append(f"{candidate}: {e}")
            continue

        candidate_cfg = _extract_weixin_clawbot_config(settings)
        if candidate_cfg.get("enabled"):
            bot_cfg = candidate_cfg
            settings_path = candidate
            break

    if not settings_path:
        detail = "; ".join(errors) if errors else "weixinClawBot channel is not enabled"
        print(f"Error: Cannot read WorkBuddy settings: {detail}", file=sys.stderr)
        sys.exit(1)

    if not bot_cfg.get("enabled"):
        print("Error: weixinClawBot channel is not enabled in WorkBuddy settings.", file=sys.stderr)
        sys.exit(1)

    required = ["botToken", "baseUrl", "userId"]
    for key in required:
        if not bot_cfg.get(key):
            print(f"Error: Missing '{key}' in weixinClawBot config.", file=sys.stderr)
            sys.exit(1)

    bot_cfg["_settings_path"] = settings_path
    return bot_cfg


def generate_wechat_uin():
    """Generate X-WECHAT-UIN header: random uint32 -> decimal string -> base64."""
    rand_uint32 = int.from_bytes(os.urandom(4), "little")
    decimal_str = str(rand_uint32)
    return base64.b64encode(decimal_str.encode("ascii")).decode("ascii")


def encrypt_aes_ecb(data: bytes, key: bytes) -> bytes:
    """Encrypt data with AES-128-ECB, PKCS7 padding."""
    padder = crypto_padding.PKCS7(128).padder()
    padded_data = padder.update(data) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    encryptor = cipher.encryptor()
    return encryptor.update(padded_data) + encryptor.finalize()


def make_headers(bot_token):
    """Build request headers for iLink API."""
    return {
        "Content-Type": "application/json",
        "AuthorizationType": "ilink_bot_token",
        "Authorization": f"Bearer {bot_token}",
        "X-WECHAT-UIN": generate_wechat_uin(),
    }


def api_request(base_url, path, bot_token, payload, timeout=15):
    """Make a POST request to the iLink API."""
    url = f"{base_url.rstrip('/')}{path}"
    headers = make_headers(bot_token)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"Error: HTTP {e.code} from {path}: {error_body}", file=sys.stderr)
        log(f"HTTP_ERROR\t{path}\t{e.code}\t{error_body[:200]}")
        return None
    except (urllib.error.URLError, OSError) as e:
        reason = getattr(e, "reason", str(e))
        print(f"Error: Network error calling {path}: {reason}", file=sys.stderr)
        log(f"NETWORK_ERROR\t{path}\t{reason}")
        return None


def load_cached_token(config):
    """Load cached context_token from disk."""
    cache = load_cache()
    if not cache or not cache_matches_config(cache, config):
        return None
    return cache.get("context_token")


def cache_matches_config(cache, config):
    """Return whether a cache entry belongs to the active ClawBot account."""
    cached_account_id = cache.get("account_id")
    if not cached_account_id:
        return True
    return cached_account_id == config.get("accountId")


def load_cache():
    """Load the cache file, tolerating legacy or malformed cache state."""
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_cached_token(token):
    """Save context_token to disk (convenience wrapper)."""
    save_cache(context_token=token)


def load_getupdates_buf(config):
    """Load the getupdates cursor from cache."""
    cache = load_cache()
    if not cache:
        return ""

    # Legacy caches did not record account_id. Keep legacy context_token usable,
    # but ignore legacy cursors because they can belong to a different bot and
    # iLink may reject them with ret=-14 after WorkBuddy reconnects/migrates.
    if not cache.get("account_id"):
        return ""

    if not cache_matches_config(cache, config):
        return ""
    return cache.get("get_updates_buf", "")


def save_cache(context_token=None, get_updates_buf=None, config=None):
    """Save context_token and/or get_updates_buf to disk."""
    cache = load_cache()

    if context_token is not None:
        cache["context_token"] = context_token
    if get_updates_buf is not None:
        cache["get_updates_buf"] = get_updates_buf
    if config is not None:
        cache["account_id"] = config.get("accountId")
        cache["settings_path"] = config.get("_settings_path")
    cache["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def refresh_token(config, retry_without_cursor=True):
    """Fetch latest messages via getupdates to extract a fresh context_token.

    getupdates is a long-polling endpoint (holds up to 35s).
    Uses get_updates_buf as cursor for pagination.
    """
    buf = load_getupdates_buf(config)
    payload = {
        "get_updates_buf": buf,
        "base_info": {"channel_version": CHANNEL_VERSION}
    }

    # getupdates holds connection up to 35s waiting for new messages
    print("Polling for messages (may take up to 35 seconds)...", file=sys.stderr)
    result = api_request(
        config["baseUrl"], "/ilink/bot/getupdates", config["botToken"],
        payload, timeout=45
    )

    if result is None:
        return None

    ret = result.get("ret", None)
    if ret is not None and ret != 0:
        print(f"Warning: getupdates returned ret={ret}", file=sys.stderr)
        log(f"TOKEN_REFRESH_FAILED\tret={ret}")
        if retry_without_cursor and buf:
            print("Retrying refresh without cached get_updates_buf...", file=sys.stderr)
            save_cache(get_updates_buf="", config=config)
            return refresh_token(config, retry_without_cursor=False)
        return None

    # Save the new cursor for next call
    new_buf = result.get("get_updates_buf", "")
    if new_buf:
        save_cache(get_updates_buf=new_buf, config=config)

    # Extract context_token from messages
    messages = result.get("msgs", [])

    if messages:
        for msg in reversed(messages):  # Most recent last
            token = msg.get("context_token", "")
            if token:
                save_cache(context_token=token, config=config)
                log(f"TOKEN_REFRESHED\t{token[:32]}...")
                print(f"Found {len(messages)} message(s).", file=sys.stderr)
                return token

    print("Warning: No messages with context_token found.", file=sys.stderr)
    print("Please send a message to your ClawBot in WeChat first, then run 'refresh' again.", file=sys.stderr)
    log("TOKEN_REFRESH_FAILED\tno messages found")
    return None


def send_message(config, text, context_token):
    """Send a text message to the user via ClawBot.

    All fields are required per the iLink protocol spec.
    Missing any field causes silent failure (HTTP 200 but no delivery).
    """
    client_id = f"workbuddy-notify-{uuid.uuid4().hex[:16]}"

    payload = {
        "msg": {
            "from_user_id": "",
            "to_user_id": config["userId"],
            "client_id": client_id,
            "message_type": 2,
            "message_state": 2,
            "context_token": context_token,
            "item_list": [
                {
                    "type": 1,
                    "text_item": {
                        "text": text
                    }
                }
            ]
        },
        "base_info": {
            "channel_version": CHANNEL_VERSION
        }
    }

    result = api_request(config["baseUrl"], "/ilink/bot/sendmessage", config["botToken"], payload)

    if result is None:
        return False

    # Check for errors - API may use "ret" or "errcode", or return empty {} on success
    ret = result.get("ret", result.get("errcode", None))
    if ret is not None and ret != 0:
        errmsg = result.get("errmsg", result.get("err_msg", json.dumps(result)))
        print(f"Error: API returned ret={ret}: {errmsg}", file=sys.stderr)
        log(f"SEND_FAILED\tret={ret}\t{errmsg}")
        return False

    log(f"SEND_OK\t{text[:50]}")
    return True


def get_upload_url(config, file_key, raw_size, raw_file_md5, encrypted_size, aes_key_hex):
    """Step 1: Get CDN upload URL from iLink API.

    Returns (cdn_upload_url, encrypted_query_param) on success, (None, None) on failure.

    Handles two response formats:
    - New format: {"upload_full_url": "https://...?encrypted_query_param=xxx"}
    - Old format: {"upload_url": "...", "upload_param": "..."}
    """
    payload = {
        "filekey": file_key,
        "media_type": 3,
        "to_user_id": config["userId"],
        "rawsize": raw_size,
        "rawfilemd5": raw_file_md5,
        "filesize": encrypted_size,
        "no_need_thumb": True,
        "aeskey": aes_key_hex,
    }
    result = api_request(config["baseUrl"], "/ilink/bot/getuploadurl", config["botToken"], payload)
    if result is None:
        return None, None

    ret = result.get("ret", 0)
    if ret != 0:
        errmsg = result.get("errmsg", json.dumps(result, ensure_ascii=False))
        print(f"Error: getuploadurl returned ret={ret}: {errmsg}", file=sys.stderr)
        log(f"GETUPLOADURL_FAILED\tret={ret}")
        return None, None

    # Try upload_param first (official API field)
    upload_param = result.get("upload_param", "")

    if upload_param:
        cdn_base = "https://novac2c.cdn.weixin.qq.com/c2c"
        cdn_url = f"{cdn_base}/upload?encrypted_query_param={upload_param}&filekey={file_key}"
        return cdn_url, upload_param

    # Fallback: use upload_full_url directly as the CDN upload URL
    # Extract encrypted_query_param from it for sendmessage later
    upload_full_url = result.get("upload_full_url", "")
    if upload_full_url:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(upload_full_url)
        qs = parse_qs(parsed.query)
        encrypted_param = qs.get("encrypted_query_param", [""])[0]
        if encrypted_param:
            # Use the full URL directly for CDN upload (server knows best)
            # Return the encrypted_param for sendmessage download reference
            return upload_full_url, encrypted_param

    print(f"Error: No upload_param or upload_full_url in response: {json.dumps(result, ensure_ascii=False)[:200]}", file=sys.stderr)
    return None, None


def upload_to_cdn(upload_url, upload_param, file_key, encrypted_data):
    """Step 2: Upload encrypted file to WeChat CDN.

    upload_url may already contain encrypted_query_param (new format),
    or may be a base URL needing query params appended (old format).
    """
    if not upload_url:
        upload_url = "https://novac2c.cdn.weixin.qq.com/c2c/upload"

    # If URL already has encrypted_query_param, use as-is; otherwise construct
    if "encrypted_query_param=" in upload_url:
        cdn_url = upload_url
    else:
        cdn_url = f"{upload_url}?encrypted_query_param={upload_param}&filekey={file_key}"

    req = urllib.request.Request(cdn_url, data=encrypted_data, method="POST")
    req.add_header("Content-Type", "application/octet-stream")

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            encrypted_param = resp.headers.get("x-encrypted-param", "")
            if not encrypted_param:
                # Try alternative header name
                encrypted_param = resp.headers.get("X-Encrypted-Param", "")
            if not encrypted_param:
                body = resp.read().decode("utf-8", errors="replace")[:200]
                print(f"Error: No x-encrypted-param in CDN upload response. Body: {body}", file=sys.stderr)
                log(f"CDN_UPLOAD_FAILED\tno_x_encrypted_param")
                return None
            return encrypted_param
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")[:200]
        print(f"Error: CDN upload HTTP {e.code}: {error_body}", file=sys.stderr)
        log(f"CDN_UPLOAD_FAILED\tHTTP {e.code}")
        return None
    except urllib.error.URLError as e:
        reason = getattr(e, "reason", str(e))
        print(f"Error: CDN upload network error: {reason}", file=sys.stderr)
        log(f"CDN_UPLOAD_FAILED\tnetwork_error")
        return None


def send_file_message(config, context_token, file_path, encrypted_param, aes_key, raw_size):
    """Step 3: Send file message via iLink API."""
    file_name = os.path.basename(file_path)
    # Official code: Buffer.from(uploaded.aeskey).toString("base64")
    # uploaded.aeskey is the hex string; base64-encode the ASCII bytes of the hex string
    aes_key_hex = aes_key.hex()
    aes_key_b64 = base64.b64encode(aes_key_hex.encode("ascii")).decode("ascii")

    payload = {
        "msg": {
            "from_user_id": "",
            "to_user_id": config["userId"],
            "client_id": f"workbuddy-notify-{uuid.uuid4().hex[:16]}",
            "message_type": 2,
            "message_state": 2,
            "context_token": context_token,
            "item_list": [
                {
                    "type": 4,
                    "file_item": {
                        "media": {
                            "encrypt_query_param": encrypted_param,
                            "aes_key": aes_key_b64,
                            "encrypt_type": 1,
                        },
                        "file_name": file_name,
                        "len": str(raw_size),
                    },
                }
            ],
        },
        "base_info": {
            "channel_version": CHANNEL_VERSION,
        },
    }

    result = api_request(config["baseUrl"], "/ilink/bot/sendmessage", config["botToken"], payload)

    if result is None:  # send_file_message
        return False

    ret = result.get("ret", None)
    if ret is not None and ret != 0:
        errmsg = result.get("errmsg", result.get("err_msg", json.dumps(result, ensure_ascii=False)))
        print(f"Error: Send file API returned ret={ret}: {errmsg}", file=sys.stderr)
        log(f"SEND_FILE_FAILED\tret={ret}")
        return False

    log(f"SEND_FILE_OK\t{file_name}\t{raw_size}")
    return True


def send_file(config, context_token, file_path):
    """Complete file send flow: encrypt → getuploadurl → upload CDN → sendmessage."""
    # Read original file
    with open(file_path, "rb") as f:
        original_data = f.read()

    raw_size = len(original_data)
    raw_file_md5 = hashlib.md5(original_data).hexdigest()

    # Generate random AES-128 key (16 bytes)
    aes_key = os.urandom(16)
    aes_key_hex = aes_key.hex()

    # Encrypt file with AES-128-ECB
    encrypted_data = encrypt_aes_ecb(original_data, aes_key)
    encrypted_size = len(encrypted_data)

    # Generate file key (32 hex chars = 16 bytes)
    file_key = uuid.uuid4().hex  # 32 hex chars

    # Step 1: Get upload URL
    upload_url, upload_param = get_upload_url(config, file_key, raw_size, raw_file_md5, encrypted_size, aes_key_hex)
    if not upload_param:
        return False

    # Step 2: Upload to CDN
    encrypted_param = upload_to_cdn(upload_url, upload_param, file_key, encrypted_data)
    if not encrypted_param:
        return False

    # Step 3: Send file message
    return send_file_message(config, context_token, file_path, encrypted_param, aes_key, raw_size)


def cmd_sendfile(args):
    """Handle 'sendfile' command: send a file to WeChat."""
    if not args:
        print("Error: No file path provided. Usage: send_wechat.py sendfile <file_path>", file=sys.stderr)
        sys.exit(1)

    file_path = args[0]
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    config = load_config()

    # Get context_token: try cache first, then refresh
    context_token = load_cached_token(config)
    if not context_token:
        print("No cached context_token. Attempting to refresh...", file=sys.stderr)
        context_token = refresh_token(config)
        if not context_token:
            print("Error: Cannot obtain context_token. Please send a message to your ClawBot in WeChat first.", file=sys.stderr)
            sys.exit(1)

    # Attempt to send file
    success = send_file(config, context_token, file_path)

    if not success:
        # Try refreshing token and retry once
        print("Retrying with refreshed token...", file=sys.stderr)
        context_token = refresh_token(config)
        if context_token:
            success = send_file(config, context_token, file_path)

    if success:
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)
        print(f"File sent successfully: {file_name} ({file_size:,} bytes)")
    else:
        print("Error: Failed to send file after retry.", file=sys.stderr)
        sys.exit(1)


def cmd_send(args):
    """Handle 'send' command."""
    if not args:
        print("Error: No message provided. Usage: send_wechat.py send \"消息内容\"", file=sys.stderr)
        sys.exit(1)

    text = " ".join(args)
    config = load_config()

    # Get context_token: try cache first, then refresh
    context_token = load_cached_token(config)
    if not context_token:
        print("No cached context_token. Attempting to refresh...", file=sys.stderr)
        context_token = refresh_token(config)
        if not context_token:
            print("Error: Cannot obtain context_token. Please send a message to your ClawBot in WeChat first.", file=sys.stderr)
            sys.exit(1)

    # Attempt to send
    success = send_message(config, text, context_token)

    if not success:
        # Try refreshing token and retry once
        print("Retrying with refreshed token...", file=sys.stderr)
        context_token = refresh_token(config)
        if context_token:
            success = send_message(config, text, context_token)

    if success:
        print(f"Message sent successfully: {text[:80]}")
    else:
        print("Error: Failed to send message after retry.", file=sys.stderr)
        sys.exit(1)


def cmd_refresh(_args):
    """Handle 'refresh' command."""
    config = load_config()
    token = refresh_token(config)
    if token:
        print(f"Token refreshed successfully: {token[:32]}...")
    else:
        print("Failed to refresh token. Send a message to ClawBot first.", file=sys.stderr)
        sys.exit(1)


def cmd_status(_args):
    """Handle 'status' command."""
    config = load_config()
    token = None
    updated_at = "N/A"
    cache_account_id = "N/A"
    if os.path.exists(CACHE_FILE):
        cache = load_cache()
        token = cache.get("context_token")
        updated_at = cache.get("updated_at", "N/A")
        cache_account_id = cache.get("account_id", "legacy")

    print(f"Settings:  {config.get('_settings_path', WORKBUDDY_SETTINGS)}")
    print(f"Bot ID:    {config.get('accountId', 'N/A')}")
    print(f"User ID:   {config['userId']}")
    print(f"Base URL:  {config['baseUrl']}")
    print(f"Enabled:   {config.get('enabled', False)}")
    print(f"Ready:     {bool(token)}")

    if os.path.exists(CACHE_FILE):
        print(f"Cache Bot: {cache_account_id}")
        if token:
            print(f"Token:     {token[:32]}...")
        else:
            print("Token:     Not cached (run 'refresh' first)")
        print(f"Updated:   {updated_at}")
    else:
        print("Token:     Not cached (run 'refresh' first)")


COMMANDS = {
    "send": cmd_send,
    "sendfile": cmd_sendfile,
    "refresh": cmd_refresh,
    "status": cmd_status,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print(__doc__.strip())
        print("\nCommands:")
        print("  send <message>       Send a text message to WeChat ClawBot")
        print("  sendfile <file_path>  Send a file (PDF/image/etc.) to WeChat ClawBot")
        print("  refresh              Refresh context_token from recent messages")
        print("  status               Show current configuration and token status")
        sys.exit(0)

    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(f"Error: Unknown command '{cmd}'. Use 'send', 'refresh', or 'status'.", file=sys.stderr)
        sys.exit(1)

    COMMANDS[cmd](sys.argv[2:])


if __name__ == "__main__":
    main()
