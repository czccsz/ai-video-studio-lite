"""Chat Completions compatible storyboard provider. No credentials are saved."""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from .storyboard import validate


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def plan(topic, *, base_url=None, api_key=None, model=None):
    topic = topic.strip()
    if not topic or len(topic) > 2000:
        raise ValueError("请输入 1–2000 字的视频主题")
    base_url = (base_url or os.getenv("AI_BASE_URL", "https://api.deepseek.com")).rstrip("/")
    api_key = api_key or os.getenv("AI_API_KEY", "")
    model = model or os.getenv("AI_MODEL", "")
    url = urlsplit(base_url)
    local = url.hostname in {"localhost", "127.0.0.1", "::1"}
    if not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError("接口地址格式不正确，请填写服务商提供的基础地址")
    if url.scheme != "https" and not (local and url.scheme == "http"):
        raise ValueError("远程接口必须使用 HTTPS；本机接口可以使用 HTTP")
    if not model.strip():
        raise ValueError("请填写服务商提供的模型名称（AI_MODEL）")
    if not api_key and not local:
        raise ValueError("请填写模型接口密钥（AI_API_KEY）")
    schema = '{"title":"视频总标题","scenes":[{"heading":"分镜标题","narration":"旁白","duration":6}]}'
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "你是中文短视频编导。只输出 JSON，不要代码围栏。格式：" + schema +
             "。写 4–6 个分镜，总标题不超过 60 字，分镜标题不超过 32 字，旁白每段 25–60 字，"
             "每段 duration 为 6–15 秒。内容具体，不编造事实或来源，不包含图片路径。"},
            {"role": "user", "content": topic},
        ],
        "stream": False,
    }
    headers = {"Content-Type": "application/json", "User-Agent": "ai-video-studio-lite/0.1"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    request = Request(base_url + "/chat/completions", data=json.dumps(payload).encode(), headers=headers)
    try:
        handlers = [_NoRedirect()]
        if local:
            handlers.append(ProxyHandler({}))
        with build_opener(*handlers).open(request, timeout=120) as response:
            raw = response.read(256_001)
        if len(raw) > 256_000:
            raise ValueError("模型响应过大，请缩短主题或减少分镜")
        content = json.loads(raw)["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise ValueError("模型没有返回文字内容")
        content = content.strip()
        if content.startswith("```") and content.endswith("```"):
            content = content.split("\n", 1)[1].rsplit("```", 1)[0]
        return validate(json.loads(content), allow_images=False)
    except HTTPError as exc:
        code = exc.code
        exc.close()
        hints = {401: "请检查接口密钥", 403: "请检查账号权限", 429: "请检查额度或稍后重试"}
        raise RuntimeError(f"模型接口返回 HTTP {code}：{hints.get(code, '请检查地址、模型名称和服务状态')}") from None
    except (URLError, TimeoutError):
        raise RuntimeError("模型接口连接失败或超时，请检查网络和基础地址") from None
    except (KeyError, IndexError, TypeError, json.JSONDecodeError):
        raise ValueError("模型返回格式不正确，请重试或手动编辑分镜 JSON") from None
