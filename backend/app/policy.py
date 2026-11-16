"""LLM 이 고도화한 코드의 정적 보안 정책.

고도화 결과는 구조 해시로 모든 사용자에게 공유되므로, 프롬프트 주입으로 만들어진 악성 코드가
캐시에 들어가면 다른 사용자의 API 키로 실행될 수 있다. 캐시에 넣기 전에 AST 를 검사해
에이전트 코드에 필요 없는 위험한 기능(네트워크, 파일, 프로세스, 동적 실행, 비밀 환경 변수)을 거부한다.

이 검사는 '허용 목록' 방식이다. 새 라이브러리가 필요하면 ALLOWED_IMPORTS 에 명시적으로 추가한다.
"""

from __future__ import annotations

import ast

POLICY_VERSION = "1"

ALLOWED_IMPORTS = {
    # 생성 프로젝트 자신
    "agent",
    "main",
    # 프레임워크
    "langgraph",
    "langchain",
    "langchain_core",
    "langchain_openai",
    "langchain_text_splitters",
    "pydantic",
    "typing_extensions",
    "dotenv",
    # 안전한 표준 라이브러리
    "__future__",
    "abc",
    "asyncio",
    "collections",
    "contextlib",
    "dataclasses",
    "datetime",
    "decimal",
    "enum",
    "functools",
    "itertools",
    "json",
    "logging",
    "math",
    "operator",
    "random",
    "re",
    "sqlite3",
    "statistics",
    "string",
    "textwrap",
    "time",
    "typing",
    "uuid",
    "ast",  # 계산기 도구의 안전한 수식 파서
    "os",  # 아래에서 os.getenv/os.environ.get(리터럴) 만 허용
}

FORBIDDEN_CALLS = {
    "eval",
    "exec",
    "compile",
    "__import__",
    "open",
    "globals",
    "vars",
    "locals",
    "breakpoint",
    "input",
    "memoryview",
    "setattr",
    "delattr",
}
SAFE_DUNDERS = {"__name__", "__doc__", "__init__", "__all__", "__file__", "__class__", "__future__", "__main__"}
SECRET_WORDS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL")
OS_ALLOWED = {"getenv", "environ"}


def _root(mod: str | None) -> str:
    return (mod or "").split(".")[0]


TEST_ONLY_IMPORTS = {"pytest"}  # tests/ 아래 파일에서만 허용


def check_source(path: str, source: str) -> list[dict]:
    """한 파일의 위반 목록. [{file, line, rule, message}]"""
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as e:
        return [{"file": path, "line": e.lineno or 1, "rule": "syntax", "message": str(e.msg)}]
    out: list[dict] = []
    allowed = ALLOWED_IMPORTS | (TEST_ONLY_IMPORTS if path.replace("\\", "/").startswith("tests/") else set())
    # os.environ 은 .get("<리터럴>") 이나 ["<리터럴>"] 로만 쓸 수 있다 (items()/copy()/dict(os.environ) 등 전체 덤프 차단)
    parents: dict[int, ast.AST] = {}
    for p in ast.walk(tree):
        for ch in ast.iter_child_nodes(p):
            parents[id(ch)] = p

    def bad(node: ast.AST, rule: str, message: str) -> None:
        out.append({"file": path, "line": getattr(node, "lineno", 1), "rule": rule, "message": message})

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if _root(a.name) not in allowed:
                    bad(node, "import", f"허용되지 않은 모듈 import: {a.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and _root(node.module) not in allowed:
                bad(node, "import", f"허용되지 않은 모듈 import: {node.module}")
            if _root(node.module) == "os":
                bad(node, "os", "os 에서 직접 import 할 수 없습니다 (os.getenv 만 허용)")
        elif isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in FORBIDDEN_CALLS:
                bad(node, "call", f"금지된 호출: {fn.id}()")
            if isinstance(fn, ast.Name) and fn.id == "getattr" and len(node.args) >= 2 and not isinstance(node.args[1], ast.Constant):
                bad(node, "call", "동적 getattr(…, <변수>) 는 허용되지 않습니다")
            # os.getenv("X") / os.environ.get("X")
            target = None
            if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name) and fn.value.id == "os" and fn.attr == "getenv":
                target = node
            if (
                isinstance(fn, ast.Attribute)
                and fn.attr == "get"
                and isinstance(fn.value, ast.Attribute)
                and isinstance(fn.value.value, ast.Name)
                and fn.value.value.id == "os"
                and fn.value.attr == "environ"
            ):
                target = node
            if target is not None:
                arg = target.args[0] if target.args else None
                if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
                    bad(node, "env", "환경 변수 이름은 문자열 리터럴이어야 합니다")
                elif any(w in arg.value.upper() for w in SECRET_WORDS):
                    bad(node, "env", f"비밀 값 환경 변수 접근: {arg.value}")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("__") and node.attr.endswith("__") and node.attr not in SAFE_DUNDERS:
                bad(node, "dunder", f"허용되지 않은 속성 접근: {node.attr}")
            if isinstance(node.value, ast.Name) and node.value.id == "os" and node.attr not in OS_ALLOWED:
                bad(node, "os", f"os.{node.attr} 는 허용되지 않습니다")
            if isinstance(node.value, ast.Name) and node.value.id == "os" and node.attr == "environ":
                par = parents.get(id(node))
                via_get = isinstance(par, ast.Attribute) and par.attr == "get" and isinstance(parents.get(id(par)), ast.Call)
                via_sub = isinstance(par, ast.Subscript) and par.value is node
                if not (via_get or via_sub):
                    bad(node, "env", 'os.environ 은 .get("이름") 또는 ["이름"] 로만 사용할 수 있습니다')
        elif isinstance(node, ast.Subscript):
            # os.environ["X"] (읽기/쓰기 모두) 는 리터럴 + 비밀 아님만
            v = node.value
            if isinstance(v, ast.Attribute) and isinstance(v.value, ast.Name) and v.value.id == "os" and v.attr == "environ":
                key = node.slice
                if not (isinstance(key, ast.Constant) and isinstance(key.value, str)) or any(w in key.value.upper() for w in SECRET_WORDS):
                    bad(node, "env", "os.environ 의 비밀 값/동적 키 접근은 허용되지 않습니다")
        elif isinstance(node, ast.Name) and node.id in ("__builtins__", "__loader__", "__spec__"):
            bad(node, "dunder", f"허용되지 않은 이름: {node.id}")
    return out


def check_files(files: dict[str, str]) -> list[dict]:
    issues: list[dict] = []
    for path, src in files.items():
        if path.endswith(".py"):
            issues += check_source(path, src)
    return issues
