import hashlib
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _post_json(url, payload, access_token, timeout=20):
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + access_token,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise RuntimeError("Remote API returned HTTP " + str(error.code)) from None
    except (URLError, TimeoutError) as error:
        raise RuntimeError("Could not reach remote API: " + str(error)) from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise RuntimeError("Remote API returned an invalid response") from None


def _memory_settings():
    url = os.environ.get("UPSTASH_REDIS_REST_URL", "").rstrip("/")
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN", "")
    if not url or not token:
        raise RuntimeError(
            "UPSTASH_REDIS_REST_URL and UPSTASH_REDIS_REST_TOKEN are required for memory"
        )
    return url, token


def _memory_key(conversation_id):
    if not isinstance(conversation_id, str) or not conversation_id:
        raise RuntimeError("A conversation ID is required for memory")
    account_id = os.environ.get("INSTAGRAM_ACCOUNT_ID", "test")
    identifier = hashlib.sha256(conversation_id.encode("utf-8")).hexdigest()
    return "instagram-chat:{}:{}".format(account_id, identifier)


def _redis_pipeline(commands):
    url, token = _memory_settings()
    try:
        result = _post_json(url + "/pipeline", commands, token)
    except RuntimeError:
        raise RuntimeError("Conversation memory store request failed") from None

    if not isinstance(result, list) or len(result) != len(commands):
        raise RuntimeError("Conversation memory store returned an invalid response")
    values = []
    for item in result:
        if not isinstance(item, dict) or item.get("error"):
            raise RuntimeError("Conversation memory store returned an error")
        values.append(item.get("result"))
    return values


def _load_conversation(conversation_id):
    key = _memory_key(conversation_id)
    result = _redis_pipeline([["LRANGE", key, "-20", "-1"]])[0]
    if not isinstance(result, list):
        raise RuntimeError("Conversation memory store returned invalid history")

    history = []
    for item in result:
        try:
            message = json.loads(item)
        except (TypeError, json.JSONDecodeError):
            continue
        if (
            isinstance(message, dict)
            and message.get("role") in ("user", "assistant")
            and isinstance(message.get("content"), str)
        ):
            history.append(message)
    return history


def _save_turn(conversation_id, user_message, assistant_message):
    key = _memory_key(conversation_id)
    user_record = json.dumps({"role": "user", "content": user_message})
    assistant_record = json.dumps(
        {"role": "assistant", "content": assistant_message}
    )
    _redis_pipeline(
        [
            ["RPUSH", key, user_record, assistant_record],
            ["LTRIM", key, "-20", "-1"],
            ["EXPIRE", key, "2592000"],
        ]
    )


def generate_ai_reply(message, conversation_id):
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not configured")

    history = _load_conversation(conversation_id)
    payload = {
        "model": os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"),
        "messages": [
            {
                "role": "system",
                "content": os.environ.get(
                    "BOT_SYSTEM_PROMPT",
                    "You are a helpful, concise assistant replying in Instagram DMs.",
                ),
            },
            *history,
            {"role": "user", "content": message},
        ],
    }
    result = _post_json(
        "https://api.groq.com/openai/v1/chat/completions", payload, api_key
    )

    try:
        reply = result["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, AttributeError):
        raise RuntimeError("AI provider returned no message") from None

    if not reply:
        raise RuntimeError("AI provider returned an empty message")
    _save_turn(conversation_id, message, reply)
    return reply


def send_instagram_message(recipient_id, text):
    access_token = os.environ.get("INSTAGRAM_ACCESS_TOKEN", "")
    account_id = os.environ.get("INSTAGRAM_ACCOUNT_ID", "")
    if not access_token or not account_id:
        raise RuntimeError(
            "INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_ACCOUNT_ID must be configured"
        )

    version = os.environ.get("GRAPH_API_VERSION", "v26.0")
    if not version.startswith("v"):
        version = "v" + version
    url = "https://graph.facebook.com/{}/{}/messages".format(version, account_id)
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": text},
    }
    return _post_json(url, payload, access_token)