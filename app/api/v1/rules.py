from fastapi import APIRouter, Depends, Response
from app.api.deps import get_services, require_api_key
from app.container import Services
from app.schemas.automation import RuleIn, RuleOut, RuleTestIn

router = APIRouter(prefix="/rules", tags=["rules"], dependencies=[Depends(require_api_key)])

@router.get("", response_model=list[RuleOut])
def list_rules(svc: Services = Depends(get_services)):
    return svc.rules.list()

@router.post("", response_model=RuleOut, status_code=201)
def create_rule(body: RuleIn, svc: Services = Depends(get_services)):
    return svc.rules.save(body)

@router.get("/{rule_id}", response_model=RuleOut)
def get_rule(rule_id: int, svc: Services = Depends(get_services)):
    return svc.rules.get(rule_id)

@router.put("/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: int, body: RuleIn, svc: Services = Depends(get_services)):
    return svc.rules.save(body, rule_id)

@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: int, svc: Services = Depends(get_services)):
    svc.rules.delete(rule_id)
    return Response(status_code=204)

@router.post("/{rule_id}/test")
def test_rule(rule_id: int, body: RuleTestIn, svc: Services = Depends(get_services)):
    return svc.rules.test(rule_id, body.message_id)
