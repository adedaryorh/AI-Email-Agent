from langgraph.graph import END, START, StateGraph
from app.graph.nodes import GraphDeps, make_nodes
from app.graph.state import SortingState


def route_after_classify(state):
    return "human_review" if state.get("needs_review") else "extract"


def build_sorting_graph(deps: GraphDeps, checkpointer):
    graph = StateGraph(SortingState)
    for name, node in make_nodes(deps).items():
        graph.add_node(name, node)
    graph.add_edge(START, "classify")
    graph.add_conditional_edges("classify", route_after_classify, {"human_review": "human_review", "extract": "extract"})
    graph.add_edge("human_review", "extract")
    graph.add_edge("extract", "rules")
    graph.add_edge("rules", "apply_actions")
    graph.add_edge("apply_actions", "draft")
    graph.add_edge("draft", END)
    return graph.compile(checkpointer=checkpointer)
