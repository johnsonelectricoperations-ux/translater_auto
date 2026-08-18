"""로컬 웹 UI 서버: 자막/답변을 브라우저에 실시간 전송(WebSocket)한다."""
import json
import os

from aiohttp import web, WSMsgType

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


class UIServer:
    """브라우저 화면과의 연결 담당.

    - broadcast(event): 연결된 모든 브라우저에 JSON 이벤트 전송
    - 브라우저에서 오는 메시지({"type": "ask"} 등)는 on_message 콜백으로 전달
    """

    def __init__(self, port: int, on_message):
        self.port = port
        self.on_message = on_message
        self._clients: set[web.WebSocketResponse] = set()
        self._runner = None

    async def start(self):
        app = web.Application()
        app.router.add_get("/", self._index)
        app.router.add_get("/ws", self._ws_handler)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", self.port)
        await site.start()
        print(f"[화면] 브라우저에서 열기: http://localhost:{self.port}")

    async def stop(self):
        for ws in list(self._clients):
            await ws.close()
        if self._runner:
            await self._runner.cleanup()

    async def _index(self, request):
        return web.FileResponse(os.path.join(STATIC_DIR, "index.html"))

    async def _ws_handler(self, request):
        ws = web.WebSocketResponse(heartbeat=30)
        await ws.prepare(request)
        self._clients.add(ws)
        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                    except json.JSONDecodeError:
                        continue
                    await self.on_message(data)
        finally:
            self._clients.discard(ws)
        return ws

    async def broadcast(self, event: dict):
        dead = []
        payload = json.dumps(event, ensure_ascii=False)
        for ws in self._clients:
            try:
                await ws.send_str(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)
