from app.core.exceptions import NotFoundError
from app.models.automation import Rule
from app.schemas.automation import RuleDefinition


def matches(definition, message, classification):
    for condition in definition.conditions:
        if condition.field.startswith("entities."):
            actual = (message.entities or {}).get(condition.field.split(".", 1)[1])
        elif condition.field in ("category", "priority"):
            actual = getattr(classification, condition.field)
        else:
            actual = getattr(message, condition.field)
        if condition.op == "exists":
            ok = bool(actual)
        elif condition.op == "eq":
            ok = str(actual).casefold() == condition.value.casefold()
        else:
            items = actual if isinstance(actual, list) else [actual or ""]
            ok = any(condition.value.casefold() in str(item).casefold() for item in items)
        if not ok:
            return False
    return True

class RuleService:
    def __init__(self, db, repository, messages, classification, audit):
        self.db, self.repository = db, repository
        self.messages, self.classification, self.audit = messages, classification, audit

    def list(self):
        return self.repository.rules()

    def get(self, rule_id):
        row = self.repository.rule(rule_id)
        if not row:
            raise NotFoundError("Rule not found")
        return row

    def save(self, data, rule_id=None):
        values = data.model_dump(mode="json")
        row = self.get(rule_id) if rule_id is not None else self.repository.add(Rule(**values))
        for key, value in values.items():
            setattr(row, key, value)
        self.db.commit()
        return row

    def delete(self, rule_id):
        self.repository.delete(self.get(rule_id))
        self.db.commit()

    def test(self, rule_id, message_id):
        message = self.messages.get(message_id)
        classification = self.classification.latest(message_id)
        if not classification:
            raise NotFoundError("Message has not been classified")
        definition = RuleDefinition.model_validate(self.get(rule_id).definition)
        matched = matches(definition, message, classification)
        return {"matched": matched, "actions": [a.model_dump() for a in definition.actions] if matched else []}

    def evaluate(self, message, classification):
        if message.action_plan is not None:
            return message.action_plan
        plan = {"labels": [], "archive": False, "priority": classification.priority, "draft": False, "matched_rules": []}
        for rule in self.repository.rules(enabled_only=True):
            definition = RuleDefinition.model_validate(rule.definition)
            if not matches(definition, message, classification):
                continue
            plan["matched_rules"].append(rule.id)
            for action in definition.actions:
                if action.type == "label":
                    plan["labels"].append(action.value)
                elif action.type == "set_priority":
                    plan["priority"] = action.value
                else:
                    plan[action.type] = True
        message.action_plan = plan
        self.audit.add(message.id, "rules_evaluated", plan)
        self.db.commit()
        return plan
