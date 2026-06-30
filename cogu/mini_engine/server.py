
import argparse
import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from .pangu_engine import PanguEngine, PanguEngineConfig

engine: PanguEngine = None


class PanguAPIHandler(BaseHTTPRequestHandler):
    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_sse(self, data: dict):
        chunk = f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
        self.wfile.write(chunk.encode("utf-8"))
        self.wfile.flush()

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/v1/models":
            models_data = [
                {
                    "id": "openPangu-Embedded-1B",
                    "object": "model",
                    "owned_by": "huawei-pangu",
                }
            ]
            if engine and engine.backend_type == "qwen-gguf":
                models_data.insert(0, {
                    "id": "Qwen3.5-0.8B",
                    "object": "model",
                    "owned_by": "qwen-community",
                })
            self._send_json({
                "object": "list",
                "data": models_data,
            })
        elif path == "/healthz":
            self._send_json({"status": "ok", "backend": engine.backend_type if engine else "not_loaded"})
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path

        if path == "/v1/chat/completions":
            self._handle_chat_completions()
        else:
            self._send_json({"error": "not found"}, 404)

    def _handle_chat_completions(self):
        global engine

        body = self._read_body()
        messages = body.get("messages", [])
        stream = body.get("stream", False)
        temperature = body.get("temperature", 0.7)
        max_tokens = body.get("max_tokens", 2048)
        top_p = body.get("top_p", 0.9)

        system = ""
        prompt = ""
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            elif msg["role"] == "user":
                prompt = msg["content"]

        if not prompt:
            self._send_json({"error": "empty prompt"}, 400)
            return

        if stream:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()

            try:
                for chunk in engine.generate_stream(
                    prompt, system=system,
                    temperature=temperature, max_new_tokens=max_tokens, top_p=top_p
                ):
                    self._send_sse({
                        "id": f"pangu-{int(time.time())}",
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": "openPangu-Embedded-1B",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": chunk},
                                "finish_reason": None,
                            }
                        ],
                    })
                self._send_sse({
                    "id": f"pangu-{int(time.time())}",
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": "openPangu-Embedded-1B",
                    "choices": [
                        {
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop",
                        }
                    ],
                })
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            except BrokenPipeError:
                pass
        else:
            result = engine.to_openai_format(
                prompt, system=system,
                temperature=temperature, max_new_tokens=max_tokens, top_p=top_p
            )
            self._send_json(result)

    def log_message(self, format, *args):
        pass


def main():
    global engine

    parser = argparse.ArgumentParser(description="COGU Local Model OpenAI-Compatible API Server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8199)
    parser.add_argument("--backend", default="auto", choices=["auto", "transformers", "gguf"])
    parser.add_argument("--local-model", default="auto", choices=["auto", "qwen", "pangu"])
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()

    config = PanguEngineConfig(backend=args.backend, device=args.device, local_model=args.local_model)
    engine = PanguEngine(config)
    engine.load()

    server = HTTPServer((args.host, args.port), PanguAPIHandler)
    print(f"[PanguEngine] OpenAI-compatible API server running at http://{args.host}:{args.port}")
    print(f"[PanguEngine] Backend: {engine.backend_type}")
    print(f"[PanguEngine] Endpoints:")
    print(f"  POST /v1/chat/completions  — Chat completion (supports streaming)")
    print(f"  GET  /v1/models            — List models")
    print(f"  GET  /healthz              — Health check")
    print()
    print(f"  2026.6.12 — COGU 诞生日，也是华为发布 OpenPangu 2.0 的日子。")
    print(f"  中国最早的大模型即将满血归来。")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[PanguEngine] Shutting down...")
        engine.unload()
        server.server_close()


if __name__ == "__main__":
    main()
