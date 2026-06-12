import asyncio
from cogu.skills import (
    IMAdapterManager, SkillIntegrationHub,
    IMPlatform, IntegrationDomain,
    IMMessage, IMResponse,
    MatrixAdapter, FeishuAdapter, HTTPAdapter, WebSocketAdapter,
)

def test_im_platform_enum():
    assert IMPlatform.MATRIX.value == "matrix"
    assert IMPlatform.FEISHU.value == "feishu"
    assert IMPlatform.HTTP.value == "http"
    assert IMPlatform.WEBSOCKET.value == "ws"
    assert len(list(IMPlatform)) == 8
    print("  PASS: IMPlatform enum (8 platforms)")

def test_im_message():
    msg = IMMessage(content="hello", sender="user1", platform=IMPlatform.MATRIX)
    assert msg.content == "hello"
    assert msg.sender == "user1"
    assert msg.thread_id == ""
    assert msg.attachments == []

    msg2 = IMMessage.from_text("test", sender="u2", platform=IMPlatform.WECHAT)
    assert msg2.platform == IMPlatform.WECHAT
    print("  PASS: IMMessage + from_text factory")

def test_im_response():
    resp = IMResponse(content="ok")
    assert resp.success
    assert resp.error == ""
    resp2 = IMResponse(content="", success=False, error="timeout")
    assert not resp2.success
    assert resp2.error == "timeout"
    print("  PASS: IMResponse")

def test_adapters():
    ma = MatrixAdapter(homeserver="https://matrix.org", access_token="tok", user_id="@a:b")
    assert ma.platform() == IMPlatform.MATRIX

    fa = FeishuAdapter(app_id="app", app_secret="sec")
    assert fa.platform() == IMPlatform.FEISHU

    ha = HTTPAdapter()
    assert ha.platform() == IMPlatform.HTTP

    wa = WebSocketAdapter(url="ws://localhost:8080")
    assert wa.platform() == IMPlatform.WEBSOCKET
    print("  PASS: 4 adapter constructors")

async def test_adapter_manager():
    manager = IMAdapterManager()
    http = HTTPAdapter()
    ws = WebSocketAdapter()

    manager.register(http)
    manager.register(ws)

    assert manager.get(IMPlatform.HTTP) is http
    assert manager.get(IMPlatform.WEBSOCKET) is ws
    assert manager.get(IMPlatform.MATRIX) is None

    platforms = manager.list_platforms()
    assert len(platforms) == 2
    assert IMPlatform.HTTP in platforms

    await manager.broadcast(IMResponse(content="broadcast"))
    await manager.close_all()
    print("  PASS: IMAdapterManager register/get/broadcast/close_all")

async def test_http_adapter_receive():
    http = HTTPAdapter()
    http.enqueue(IMMessage(content="msg1"))
    http.enqueue(IMMessage(content="msg2"))

    received = []
    async for msg in http.receive():
        received.append(msg)
    assert len(received) == 2
    assert received[0].content == "msg1"
    assert received[1].content == "msg2"
    print("  PASS: HTTPAdapter enqueue/receive async iterator")

async def test_integration_hub_route():
    hub = SkillIntegrationHub()

    @hub.route("summarize", IntegrationDomain.REASONING)
    async def summarize_handler(data, ctx):
        return f"summary: {data.get('text', '')[:20]}..."

    result = await hub.dispatch("summarize", IntegrationDomain.REASONING,
                                {"text": "long text here"}, "")
    assert result.success
    assert "summary:" in result.content
    print("  PASS: IntegrationHub route decorator + dispatch")

async def test_integration_hub_reasoner():
    hub = SkillIntegrationHub()

    async def mock_reasoner(task, input, context):
        return {"content": f"reasoned: {task}"}

    hub.register_reasoner(mock_reasoner)
    result = await hub.dispatch("unknown-task", IntegrationDomain.REASONING,
                                {"data": "x"}, "")
    assert result.success
    assert "reasoned:" in result.content
    print("  PASS: IntegrationHub fallback reasoner")

async def test_integration_hub_gui_handler():
    hub = SkillIntegrationHub()

    async def mock_gui(action, params, context):
        return f"gui: {action} done"

    hub.register_gui_handler(mock_gui)
    result = await hub.dispatch("click", IntegrationDomain.GUI,
                                {"x": 10, "y": 20}, "")
    assert result.success
    assert "gui:" in result.content and "click" in result.content
    print("  PASS: IntegrationHub fallback gui_handler")

async def test_integration_hub_office_handler():
    hub = SkillIntegrationHub()

    async def mock_office(skill, data, context):
        return f"office: {skill} processed"

    hub.register_office_handler(mock_office)
    result = await hub.dispatch("convert", IntegrationDomain.OFFICE,
                                {"format": "pdf"}, "")
    assert result.success
    assert "office:" in result.content
    print("  PASS: IntegrationHub fallback office_handler")

async def test_integration_hub_no_handler():
    hub = SkillIntegrationHub()
    result = await hub.dispatch("unknown", IntegrationDomain.GENERAL,
                                {}, "")
    assert not result.success
    assert "no handler" in result.error
    print("  PASS: IntegrationHub no-handler error")

async def test_integration_hub_error_handling():
    hub = SkillIntegrationHub()

    @hub.route("fail", IntegrationDomain.REASONING)
    def fail_handler(data, ctx):
        raise RuntimeError("simulated failure")

    result = await hub.dispatch("fail", IntegrationDomain.REASONING, {}, "")
    assert not result.success
    assert "simulated failure" in result.error
    print("  PASS: IntegrationHub error handling")

def test_integration_domain_enum():
    assert IntegrationDomain.REASONING.value == "reasoning"
    assert IntegrationDomain.GUI.value == "gui"
    assert IntegrationDomain.OFFICE.value == "office"
    assert IntegrationDomain.GENERAL.value == "general"
    print("  PASS: IntegrationDomain enum (4 domains)")

async def test_ws_adapter_receive():
    ws = WebSocketAdapter()
    ws.enqueue(IMMessage(content="ws1"))
    ws.enqueue(IMMessage(content="ws2"))

    received = []
    async for msg in ws.receive():
        received.append(msg)
    assert len(received) == 2
    print("  PASS: WebSocketAdapter receive")

async def test_matrix_feishu_receive_empty():
    ma = MatrixAdapter()
    msgs = []
    async for m in ma.receive():
        msgs.append(m)
    assert len(msgs) == 0

    fa = FeishuAdapter()
    msgs = []
    async for m in fa.receive():
        msgs.append(m)
    assert len(msgs) == 0
    print("  PASS: Matrix/Feishu empty receive (stub)")

async def test_e2e_orchestrator():
    from cogu.orchestrator import ConductorOrchestrator, Musician, MusicianRole

    musician = Musician(name="analyst-1", role=MusicianRole.ANALYST)
    result = await musician.perform(task="analyze data", context="sample")
    assert result.role == MusicianRole.ANALYST
    assert result.success
    print("  PASS: Musician perform (simulate)")

    orchestrator = ConductorOrchestrator()
    assert orchestrator is not None
    print("  PASS: ConductorOrchestrator construction")

async def main():
    print("\n=== COGU SkillsSystem + Integration E2E ===\n")

    tests = [
        ("IMPlatform enum", test_im_platform_enum),
        ("IMMessage", test_im_message),
        ("IMResponse", test_im_response),
        ("Adapters constructors", test_adapters),
        ("IMAdapterManager", lambda: test_adapter_manager()),
        ("HTTPAdapter receive", lambda: test_http_adapter_receive()),
        ("WebSocket receive", lambda: test_ws_adapter_receive()),
        ("Matrix/Feishu stubs", test_matrix_feishu_receive_empty),
        ("IntegrationDomain", test_integration_domain_enum),
        ("Hub route dispatch", lambda: test_integration_hub_route()),
        ("Hub reasoner fallback", lambda: test_integration_hub_reasoner()),
        ("Hub gui fallback", lambda: test_integration_hub_gui_handler()),
        ("Hub office fallback", lambda: test_integration_hub_office_handler()),
        ("Hub no-handler error", lambda: test_integration_hub_no_handler()),
        ("Hub error handling", lambda: test_integration_hub_error_handling()),
        ("Orchestrator E2E", test_e2e_orchestrator),
    ]

    passed = 0
    failed = 0
    for name, fn in tests:
        try:
            result = fn()
            if hasattr(result, "__await__"):
                await result
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  FAIL: {name} - {e}")

    print(f"\n=== Results: {passed}/{passed+failed} passed ===\n")
    return failed == 0

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
