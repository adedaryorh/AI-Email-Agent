"""Bounded read-only tool orchestration; sending is deliberately not a tool."""
import hashlib
import json
import time
from app.core.exceptions import ConflictError
from app.models.agent import AgentRun
from app.repositories.agent_repo import AgentRepository
from app.schemas.agent import Decision, GroundedReply, Verification
from app.services.knowledge_service import KnowledgeService


def body_hash(body):
    return hashlib.sha256(body.encode()).hexdigest()


class AgentService:
    def __init__(self, db, assistant, settings):
        self.db, self.assistant, self.settings = db, assistant, settings
        self.repo = AgentRepository(db)
        self.knowledge = KnowledgeService(db)

    def generate(self, message, read_thread):
        self.repo.abandon_previous(message.id)
        run = self.repo.add(AgentRun(message_id=message.id))
        self.db.commit()
        started = time.monotonic()
        used = 0
        estimated_cost = 0.0
        sources = self.knowledge.search(message.subject + " " + message.body_text[:2000])
        preferences = self.knowledge.preferences()
        data = {"subject": message.subject, "body": message.body_text[:self.settings.max_body_chars],
                "sources": sources, "thread": [], "preferences": preferences["instructions"],
                "template": self.settings.draft_template, "clarification": "", "completed_tools": []}

        def event(tool, summary, usage=None, cost=None):
            run.events = [*run.events, {"tool": tool, "summary": summary,
                "elapsed_ms": int((time.monotonic() - started) * 1000), "usage": usage, "estimated_cost_usd": cost}]
            self.db.commit()

        def call(method, schema):
            nonlocal used, estimated_cost
            size = len(json.dumps(data))
            if time.monotonic() - started >= self.settings.agent_timeout_seconds or used + size > self.settings.agent_max_input_chars:
                raise ConflictError("Agent budget exceeded; shorten the message or knowledge context")
            # UTF-8 bytes plus a conservative allowance for prompts, schemas and
            # provider framing. This is a local estimate, not a billing guarantee.
            ceiling = self.cost(len(json.dumps(data).encode()) + 8192, self.settings.agent_max_output_tokens)
            limit = self.settings.agent_max_cost_usd
            if limit is not None and estimated_cost + ceiling > limit:
                raise ConflictError("Estimated agent cost budget exceeded")
            used += size
            self.assistant.call_timeout_seconds = max(1, min(45, self.settings.agent_timeout_seconds - (time.monotonic() - started)))
            result = schema.model_validate(getattr(self.assistant, method)(data))
            usage = getattr(self.assistant, "last_usage", None)
            cost = self.cost(usage.get("input_tokens", 0), usage.get("output_tokens", 0)) if usage else None
            event(method, "Structured response validated", usage, cost)
            if limit is not None and (not usage or "input_tokens" not in usage or "output_tokens" not in usage):
                raise ConflictError("Provider usage is unavailable; cost-budgeted run stopped")
            estimated_cost += cost or 0
            if limit is not None and estimated_cost > limit:
                raise ConflictError("Reported usage exceeded the estimated cost budget")
            if time.monotonic() - started >= self.settings.agent_timeout_seconds:
                raise ConflictError("Agent time budget exceeded")
            return result

        try:
            event("search_knowledge", f"Retrieved {len(sources)} source excerpts")
            seen = set()
            for _ in range(self.settings.agent_max_steps):
                decision = call("plan", Decision)
                if decision.tool == "finish":
                    break
                signature = (decision.tool, decision.query if decision.tool == "search_knowledge" else "")
                if signature in seen:
                    raise ConflictError("Agent repeated a tool call; stopped safely")
                seen.add(signature)
                data["completed_tools"].append({"tool": decision.tool, "query": decision.query})
                if decision.tool == "search_knowledge":
                    found = self.knowledge.search(decision.query)
                    sources = list({s["id"]: s for s in [*sources, *found]}.values())[:10]
                    data["sources"] = sources
                    event(decision.tool, f"Retrieved {len(found)} source excerpts")
                elif decision.tool == "read_thread":
                    # Bound even a provider returning excessive history.
                    data["thread"] = str(read_thread())[:self.settings.max_body_chars]
                    event(decision.tool, "Loaded bounded Gmail thread context")
                else:
                    data["clarification"] = decision.query
                    event(decision.tool, "Draft will request missing information; no message sent")
                    break
            else:
                raise ConflictError("Agent step budget exceeded")
            reply = call("compose", GroundedReply)
            available = {s["id"] for s in sources}
            if not set(reply.citations) <= available:
                raise ConflictError("Draft cites an unknown source")
            data["draft"] = reply.body
            data["citations"] = reply.citations
            verification = call("verify", Verification).model_dump()
            verification.update(body_hash=body_hash(reply.body), preferences_version=preferences["version"], citations=reply.citations)
            run.status = "completed" if verification["passed"] else "needs_revision"
            return reply.body, sources, verification, run.id
        except Exception as exc:
            run.status = "failed"
            event("stopped", type(exc).__name__)
            raise
        finally:
            run.elapsed_ms = int((time.monotonic() - started) * 1000)
            run.input_chars = used
            self.db.commit()

    def cost(self, input_tokens, output_tokens):
        price_in, price_out = self.settings.llm_input_usd_per_million, self.settings.llm_output_usd_per_million
        if price_in is None or price_out is None:
            return None
        return (input_tokens * price_in + output_tokens * price_out) / 1_000_000

    def verify_edit(self, message, body, sources):
        preferences = self.knowledge.preferences()
        self.assistant.call_timeout_seconds = min(45, self.settings.agent_timeout_seconds)
        data = {"body": message.body_text[:self.settings.max_body_chars], "draft": body,
                "sources": sources, "preferences": preferences["instructions"]}
        self.repo.abandon_previous(message.id)
        run = self.repo.add(AgentRun(message_id=message.id))
        self.db.commit()
        started = time.monotonic()
        try:
            size = len(json.dumps(data))
            if size > self.settings.agent_max_input_chars:
                raise ConflictError("Verification input budget exceeded")
            limit = self.settings.agent_max_cost_usd
            if limit is not None:
                ceiling = self.cost(len(json.dumps(data).encode()) + 8192, self.settings.agent_max_output_tokens)
                if ceiling > limit:
                    raise ConflictError("Estimated verification cost budget exceeded")
            run.input_chars = size
            result = Verification.model_validate(self.assistant.verify(data)).model_dump()
            usage = getattr(self.assistant, "last_usage", None)
            cost = self.cost(usage.get("input_tokens", 0), usage.get("output_tokens", 0)) if usage else None
            run.events = [{"tool": "verify_edit", "summary": "Human-edited reply verified",
                           "elapsed_ms": int((time.monotonic() - started) * 1000),
                           "usage": usage, "estimated_cost_usd": cost}]
            if limit is not None and (not usage or "input_tokens" not in usage or "output_tokens" not in usage):
                raise ConflictError("Provider usage is unavailable; verification stopped")
            if limit is not None and cost > limit:
                raise ConflictError("Reported usage exceeded the estimated cost budget")
            if time.monotonic() - started >= self.settings.agent_timeout_seconds:
                raise ConflictError("Verification time budget exceeded")
            result.update(body_hash=body_hash(body), preferences_version=preferences["version"])
            run.status = "completed" if result["passed"] else "needs_revision"
            return result, run.id
        except Exception as exc:
            run.status = "failed"
            run.events = [*run.events, {"tool": "stopped", "summary": type(exc).__name__,
                          "elapsed_ms": int((time.monotonic() - started) * 1000), "usage": None}]
            raise
        finally:
            run.elapsed_ms = int((time.monotonic() - started) * 1000)
            self.db.commit()

    def require_verified(self, draft):
        report = draft.verification or {}
        if not report.get("passed") or report.get("body_hash") != body_hash(draft.body):
            raise ConflictError("Draft must pass verification before approval or sending")
        if not self.knowledge.sources_current(draft.sources or []):
            raise ConflictError("Knowledge sources changed; regenerate this draft")
        if report.get("preferences_version") != self.knowledge.preferences()["version"]:
            raise ConflictError("Preferences changed; edit or regenerate this draft")
