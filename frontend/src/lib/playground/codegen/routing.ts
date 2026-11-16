// 라우팅 함수 모음 (routing.py).
import type { Ctx } from "./context.ts";
import { llmExpr, pascal, py, targetKey } from "./context.ts";

export function routingFile(c: Ctx): string | null {
  const routers = c.g.nodes.filter((n) => n.kind === "router");
  const maps = c.g.nodes.filter((n) => n.kind === "map");
  const evals = c.g.nodes.filter((n) => n.kind === "evaluator");
  const humans = c.g.nodes.filter((n) => n.kind === "human" && (c.out.get(n.id) ?? []).some((e) => e.sourceHandle === "reject"));
  if (!routers.length && !maps.length && !evals.length && !humans.length) return null;

  const imports = new Set<string>(["from typing import Literal", "", `from ${c.pkg}.state import State`]);
  const blocks: string[] = [];

  for (const r of routers) {
    const keys = (c.out.get(r.id) ?? []).map((e) => targetKey(c, e.target));
    const lit = `Literal[${keys.map(py).join(", ")}]`;
    const strategy = r.data.strategy ?? "llm";
    if (strategy === "tools_condition") {
      const toolsEdge = (c.out.get(r.id) ?? []).find((e) => c.byId.get(e.target)?.kind === "tools");
      const other = (c.out.get(r.id) ?? []).find((e) => e !== toolsEdge);
      blocks.push(`def ${r.data.name}(state: State) -> ${lit}:
    """tools_condition: 마지막 AIMessage 에 tool_calls 가 있으면 도구 노드로, 없으면 다음 단계로."""
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return ${py(toolsEdge ? targetKey(c, toolsEdge.target) : "__end__")}
    return ${py(other ? targetKey(c, other.target) : "__end__")}`);
    } else if (strategy === "state_key") {
      blocks.push(`def ${r.data.name}(state: State) -> ${lit}:
    """state[${py(r.data.stateKey ?? "route")}] 값과 같은 이름의 경로로 보낸다. 일치하지 않으면 첫 경로."""
    value = str(state.get(${py(r.data.stateKey ?? "route")}, ""))
    return value if value in ${JSON.stringify(keys)} else ${py(keys[0] ?? "__end__")}`);
    } else {
      imports.add("from langchain.messages import SystemMessage");
      imports.add("from pydantic import BaseModel, Field");
      imports.add("from agent.config import get_llm");
      if (r.data.model?.trim()) imports.add("import os");
      const cls = `${pascal(r.data.name)}Decision`;
      const desc = (c.out.get(r.id) ?? [])
        .map((e) => {
          const t = c.byId.get(e.target);
          return `- ${targetKey(c, e.target)}: ${t?.kind === "end" ? "더 할 일이 없으면 종료" : (t?.data.description || t?.data.prompt || "").slice(0, 80)}`;
        })
        .join("\\n");
      blocks.push(`class ${cls}(BaseModel):
    """라우팅 결정."""

    destination: ${lit} = Field(description="요청을 처리할 경로")


_${r.data.name}_llm = ${llmExpr(c, r)}.with_structured_output(${cls})


def ${r.data.name}(state: State) -> ${lit}:
    """LLM 이 구조화 출력으로 경로를 고른다 (Routing 패턴)."""
    decision = _${r.data.name}_llm.invoke(
        [SystemMessage(${py(r.data.prompt ?? "가장 적절한 경로를 고르세요.")} + "\\n\\n[경로]\\n${desc}"), *state["messages"]]
    )
    print(f"  🔀 ${r.data.name} → {decision.destination}")
    return decision.destination`);
    }
  }

  for (const m of maps) {
    imports.add("from langgraph.types import Send");
    const worker = (c.out.get(m.id) ?? [])[0];
    const wname = worker ? targetKey(c, worker.target) : "__end__";
    blocks.push(`MAX_ITEMS_${m.data.name.toUpperCase()} = ${m.data.maxItems ?? 4}


def ${m.data.name}(state: State) -> list[Send]:
    """직전 메시지를 줄/불릿 단위 항목으로 나눠 각각 '${wname}' 워커로 병렬 전송한다 (map 단계).

    Send(node, payload) 는 같은 노드를 서로 다른 입력으로 여러 번 동시에 실행한다.
    """
    text = state["messages"][-1].text
    items = [line.strip(" -*•0123456789.)\\t") for line in text.splitlines()]
    items = [i for i in items if len(i) > 1][:MAX_ITEMS_${m.data.name.toUpperCase()}] or [text[:200]]
    print(f"  🔱 {len(items)}개 항목으로 분기")
    return [Send(${py(wname)}, {"item": item}) for item in items]`);
  }

  for (const e of evals) {
    const pass = (c.out.get(e.id) ?? []).find((x) => x.sourceHandle === "pass");
    const retry = (c.out.get(e.id) ?? []).find((x) => x.sourceHandle === "retry");
    blocks.push(`def route_${e.data.name}(state: State) -> Literal["pass", "retry"]:
    """평가 결과 또는 반복 상한에 따라 분기한다. (pass → ${pass ? targetKey(c, pass.target) : "?"}, retry → ${retry ? targetKey(c, retry.target) : "?"})"""
    from ${c.pkg}.nodes.${e.data.name} import MAX_ITERATIONS

    if state.get(${py(`${e.data.name}_verdict`)}) == "pass" or state.get(${py(`${e.data.name}_count`)}, 0) >= MAX_ITERATIONS:
        return "pass"
    return "retry"`);
  }

  for (const h of humans) {
    blocks.push(`def route_${h.data.name}(state: State) -> Literal["approve", "reject"]:
    """사람의 결정에 따라 분기한다."""
    return "reject" if state.get(${py(`${h.data.name}_decision`)}) == "reject" else "approve"`);
  }

  const imp = [...imports];
  const std = imp.filter((x) => x.startsWith("from typing") || x === "import os").sort((a, b) => (a.startsWith("import") ? -1 : 0) - (b.startsWith("import") ? -1 : 0));
  const third = imp.filter((x) => x.startsWith("from langchain") || x.startsWith("from langgraph") || x.startsWith("from pydantic")).sort();
  const local = imp.filter((x) => x.startsWith("from agent")).sort();
  return `"""라우팅 함수 모음: add_conditional_edges 에 전달된다.

라우팅 함수는 노드가 아니다. 상태를 읽고 '다음에 갈 곳'만 반환한다.
반환 타입의 Literal 은 그래프 시각화와 정적 검증에 사용된다.
"""

${std.join("\n")}

${third.join("\n")}

${local.join("\n")}


${blocks.join("\n\n\n")}
`;
}
