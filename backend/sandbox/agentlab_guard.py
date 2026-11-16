"""AgentLab 샌드박스 보안 정책 (PEP 578 audit hook).

사용자 코드가 실행되는 파이썬 프로세스에서 다음을 막는다.
- 허용 목록 밖으로의 네트워크 연결 (키 유출, 클라우드 메타데이터 서버 접근 차단)
- 샌드박스 파이썬이 아닌 외부 프로그램 실행 (curl 등), os.system / exec / fork

audit hook 은 한 번 설치하면 파이썬 코드로 해제할 수 없다. 다만 ctypes 로 libc 를 직접
호출하면 우회할 수 있으므로, 공개 운영에서는 무권한 서비스 계정 + egress 방화벽 같은
인프라 격리를 함께 써야 한다 (docs/PRODUCTION_READINESS.md S1).

설정 (환경 변수)
- AGENTLAB_SANDBOX=1           이 값이 있을 때만 활성화된다 (서버 프로세스에는 없다)
- AGENTLAB_EGRESS_ALLOW=a,b    허용 호스트 (정확히 일치 또는 ".example.com" 접미사)
                               비어 있으면 모든 외부 연결을 막는다 (Mock 모드)
"""

from __future__ import annotations

import ipaddress
import os
import shutil
import sys
import threading
import time

_ENV_FLAG = "AGENTLAB_SANDBOX"


def _deny(what: str) -> None:
    msg = f"[AgentLab] 보안 정책: {what} 은(는) 샌드박스에서 허용되지 않습니다."
    try:
        sys.stderr.write(msg + "\n")
    except Exception:
        pass
    raise PermissionError(msg)


def install() -> None:
    if getattr(sys, "_agentlab_guard", False) or os.environ.get(_ENV_FLAG) != "1":
        return
    sys._agentlab_guard = True  # type: ignore[attr-defined]

    import socket

    allow = [h.strip().lower() for h in os.environ.get("AGENTLAB_EGRESS_ALLOW", "").split(",") if h.strip()]
    real_getaddrinfo = socket.getaddrinfo
    state = threading.local()
    cache: dict[str, tuple[float, set[str]]] = {}
    exe = os.path.realpath(sys.executable)
    env_path = os.environ.get("PATH", "")

    def host_allowed(host: str) -> bool:
        h = host.lower().rstrip(".")
        return any(h == a or (a.startswith(".") and h.endswith(a)) for a in allow)

    def allowed_ips() -> set[str]:
        """허용 호스트들이 지금 가리키는 IP (60초 캐시). hook 재진입을 막고 직접 해석한다."""
        out: set[str] = set()
        now = time.time()
        for a in allow:
            name = a.lstrip(".")
            hit = cache.get(name)
            if not hit or hit[0] < now:
                state.busy = True
                try:
                    ips = {ai[4][0] for ai in real_getaddrinfo(name, 443)}
                except OSError:
                    ips = set()
                finally:
                    state.busy = False
                cache[name] = (now + 60, ips)
                hit = cache[name]
            out |= hit[1]
        return out

    def check_ip(ip: str) -> None:
        try:
            addr = ipaddress.ip_address(ip.split("%")[0])
        except ValueError:
            _deny(f"주소 '{ip}' 로의 연결")
        if not addr.is_global:
            _deny(f"내부/메타데이터 주소 {ip} 로의 연결")
        if ip not in allowed_ips():
            cache.clear()  # CDN 이 IP 를 바꿨을 수 있으니 한 번 더 해석한다
        if ip not in allowed_ips():
            _deny(f"허용되지 않은 주소 {ip} 로의 연결 (허용: {', '.join(allow) or '없음'})")

    def is_sandbox_python(program: object, env: object) -> bool:
        if not isinstance(program, (str, bytes, os.PathLike)):
            return False
        prog = os.fsdecode(program)
        found = shutil.which(prog, path=env_path) if os.sep not in prog else prog
        if not found or os.path.realpath(found) != exe:
            return False
        if env is None:
            return True  # 현재 환경(활성화 플래그 포함)을 그대로 물려받는다
        if not isinstance(env, dict):
            return False
        # env={} 처럼 비밀값을 지우는 것은 좋은 습관이므로 허용하되, 자식에게도 이 정책이 걸리도록
        # 활성화 플래그와 허용 목록만 넣어 준다. Popen 은 audit 이후 이 dict 를 그대로 쓴다.
        as_bytes = any(isinstance(k, bytes) for k in env)
        for k, v in ((_ENV_FLAG, "1"), ("AGENTLAB_EGRESS_ALLOW", ",".join(allow))):
            env[k.encode() if as_bytes else k] = v.encode() if as_bytes else v
        return True

    def hook(event: str, args: tuple) -> None:
        if event == "socket.getaddrinfo":
            if getattr(state, "busy", False):
                return
            host = args[0]
            if isinstance(host, bytes):
                host = host.decode(errors="replace")
            if not host:
                return
            try:
                ipaddress.ip_address(str(host))
                return  # IP 리터럴은 connect 단계에서 검사한다
            except ValueError:
                pass
            if not host_allowed(str(host)):
                _deny(f"호스트 '{host}' 접속 (허용: {', '.join(allow) or '없음'})")
        elif event == "socket.connect" or event == "socket.sendto" or event == "socket.sendmsg":
            sock, address = args[0], args[1] if len(args) > 1 else None
            family = getattr(sock, "family", None)
            if family in (socket.AF_INET, socket.AF_INET6) and isinstance(address, tuple):
                check_ip(str(address[0]))
            elif address is not None:
                _deny(f"소켓 연결({family})")
        elif event == "subprocess.Popen":
            program, argv, _cwd, env = args[0], args[1], args[2], args[3]
            first = program if program is not None else (argv[0] if isinstance(argv, (list, tuple)) and argv else argv)
            if not is_sandbox_python(first, env):
                _deny(f"외부 프로그램 실행 ({first!r})")
            if isinstance(argv, (list, tuple)) and any(os.fsdecode(a) in ("-S",) for a in argv[1:] if isinstance(a, (str, bytes))):
                _deny("site 비활성화(-S) 파이썬 실행")
        elif event in ("os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty", "pty.spawn", "os.startfile"):
            _deny(event)

    sys.addaudithook(hook)


install()
