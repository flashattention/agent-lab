"""비동기 동시성: 한 프로세스가 여러 요청을 동시에 처리하는 모습을 측정한다.

httpx.AsyncClient + ASGITransport 로 앱을 프로세스 안에서 '동시에' 호출한다.
(ASGITransport 는 lifespan 을 실행하지 않으므로 app.router.lifespan_context 로 직접 감싼다)

1) 서로 다른 thread 10개 동시 요청 → 도구 I/O(0.2s)가 겹쳐서 처리된다
2) 같은 thread 에 동시 요청(double-texting) → 409
3) 동시 실행 슬롯 초과 → 503 + Retry-After (빠르게 실패해서 과부하 전파를 막는다)
4) 실행 시간 초과 → 504
"""

from __future__ import annotations

import asyncio
import time
from collections import Counter

import agent_service
import httpx
from agent_service import app

HEADERS = {"X-API-Key": "key-alice"}


async def call(client: httpx.AsyncClient, thread: str, msg: str = "order A-1 상태?") -> int:
    r = await client.post(f"/threads/{thread}/runs", json={"message": msg}, headers=HEADERS)
    return r.status_code


async def main() -> None:
    async with app.router.lifespan_context(app):  # startup → 에이전트 생성
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://agent") as client:
            print("=" * 70 + "\n1) 순차 vs 동시 — 요청 5개\n" + "=" * 70)
            t0 = time.perf_counter()
            for i in range(5):
                await call(client, f"seq-{i}")
            seq = time.perf_counter() - t0
            t0 = time.perf_counter()
            codes = await asyncio.gather(*(call(client, f"par-{i}") for i in range(5)))
            par = time.perf_counter() - t0
            print(f"  순차: {seq:.2f}s   동시: {par:.2f}s   (상태코드 {Counter(codes)})")
            print("  → async 도구가 I/O 를 기다리는 동안 이벤트 루프가 다른 요청을 처리한다")
            assert par < seq

            print("\n" + "=" * 70 + "\n2) 같은 thread 로 동시에 두 번 (double-texting)\n" + "=" * 70)
            codes = await asyncio.gather(call(client, "dup"), call(client, "dup", "하나 더!"))
            print("  상태코드:", codes, "→ 하나는 409 Conflict")
            assert sorted(codes) == [200, 409]

            print("\n" + "=" * 70 + "\n3) 동시 실행 슬롯을 2개로 줄이고 6개 요청\n" + "=" * 70)
            app.state.run_slots = asyncio.Semaphore(2)
            codes = await asyncio.gather(*(call(client, f"burst-{i}") for i in range(6)))
            print("  상태코드 분포:", Counter(codes), "→ 초과분은 즉시 503 (클라이언트는 Retry-After 후 재시도)")
            assert 503 in codes
            app.state.run_slots = asyncio.Semaphore(agent_service.MAX_CONCURRENT_RUNS)

            print("\n" + "=" * 70 + "\n4) 실행 타임아웃을 0.05초로 줄이면\n" + "=" * 70)
            agent_service.RUN_TIMEOUT_S = 0.05
            code = await call(client, "slow")
            print("  상태코드:", code, "→ 504 Gateway Timeout")
            assert code == 504
            agent_service.RUN_TIMEOUT_S = 30


asyncio.run(main())
