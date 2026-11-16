from app.runner import stream_run


async def collect(files: dict[str, str], entry: str = "main.py", **kw) -> dict:
    """stream_run 결과를 종류별로 모은다."""
    out = {"events": [], "stdout": "", "stderr": "", "trace": [], "start": None, "exit": None}
    async for ev in stream_run(files, entry, **kw):
        out["events"].append(ev)
        t = ev["type"]
        if t in ("stdout", "stderr"):
            out[t] += ev["data"]
        elif t == "trace":
            out["trace"].append(ev["event"])
        else:
            out[t] = ev
    return out


REACT_AGENT = '''
from typing import Annotated, TypedDict
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

@tool
def get_weather(city: str) -> str:
    """도시 날씨"""
    return f"{city}: 맑음 21도"

llm = ChatOpenAI(model="gpt-5-mini").bind_tools([get_weather])

class S(TypedDict):
    messages: Annotated[list, add_messages]

def agent(s: S):
    return {"messages": [llm.invoke(s["messages"])]}

g = StateGraph(S)
g.add_node("agent", agent)
g.add_node("tools", ToolNode([get_weather]))
g.add_edge(START, "agent")
g.add_conditional_edges("agent", tools_condition)
g.add_edge("tools", "agent")
app = g.compile()
for chunk in app.stream({"messages": [HumanMessage("서울 날씨?")]}, stream_mode="updates"):
    print(list(chunk))
'''
