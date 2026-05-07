"""
Tests de integración para el Recolector de Inventarios.
Apuntan al servidor corriendo en http://127.0.0.1:8000

Uso:
    uv run python tests/test_recolector.py
    uv run python tests/test_recolector.py -v   # verbose
"""
import sys
import json
import urllib.request
import urllib.error
from typing import Any

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL = "http://127.0.0.1:8000/api/recolector"

BUSINESSES = {
    "nexora":   "11111111-1111-1111-1111-111111111111",
    "veridian": "22222222-2222-2222-2222-222222222222",
    "arcturus": "33333333-3333-3333-3333-333333333333",
    "luminary": "44444444-4444-4444-4444-444444444444",
}

VERBOSE = "-v" in sys.argv

# ---------------------------------------------------------------------------
# Mini test runner
# ---------------------------------------------------------------------------

passed = 0
failed = 0
errors = []


def get(path: str) -> tuple[int, Any]:
    url = f"{BASE_URL}{path}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"error": f"Non-JSON response (HTTP {e.code}) — probable 500, revisa el servidor"}
    except Exception as e:
        return 0, {"error": str(e)}


def check(name: str, condition: bool, detail: str = ""):
    global passed, failed
    if condition:
        passed += 1
        if VERBOSE:
            print(f"  ✅  {name}")
    else:
        failed += 1
        msg = f"  ❌  {name}" + (f" — {detail}" if detail else "")
        errors.append(msg)
        print(msg)


def section(title: str):
    print(f"\n{'─'*55}")
    print(f"  {title}")
    print(f"{'─'*55}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

section("USDConsumption — respuestas 200 por empresa")
for name, uid in BUSINESSES.items():
    code, body = get(f"/businesses/{uid}/USDConsumption")
    check(f"{name}: HTTP 200", code == 200, f"got {code} — {body.get('error','')}")
    if code == 200:
        check(f"{name}: tiene 'consumption'", "consumption" in body,
              f"keys: {list(body.keys())}")
        check(f"{name}: consumption es lista", isinstance(body.get("consumption"), list))
        if body.get("consumption"):
            record = body["consumption"][0]
            for field in ("month_year", "total_usd_spent"):
                check(f"{name}: campo '{field}' presente", field in record,
                      f"keys: {list(record.keys())}")
            check(f"{name}: total_usd_spent es número",
                  isinstance(record["total_usd_spent"], (int, float)),
                  f"type: {type(record['total_usd_spent'])}")

section("USDConsumption — filtro por mes")
uid = BUSINESSES["nexora"]
code, body = get(f"/businesses/{uid}/USDConsumption?month=2026-05")
check("filtro month=2026-05: HTTP 200 o 404", code in (200, 404), f"got {code}")
if code == 200 and body.get("consumption"):
    for r in body["consumption"]:
        check("todos los registros son del mes filtrado",
              r["month_year"] == "2026-05", f"got {r['month_year']}")
    check("filtro retorna exactamente 1 registro", len(body["consumption"]) == 1,
          f"got {len(body['consumption'])}")

section("CloudGovernance — respuestas 200 por empresa")
for name, uid in BUSINESSES.items():
    code, body = get(f"/businesses/{uid}/CloudGovernance")
    check(f"{name}: HTTP 200", code == 200, f"got {code} — {body.get('error','')}")
    if code == 200:
        gov = body.get("governance", {})
        for field in ("mandatory_tags", "responsible_area", "spend_limits_by_project"):
            check(f"{name}: campo '{field}' presente", field in gov,
                  f"keys: {list(gov.keys())}")
        check(f"{name}: mandatory_tags es dict",
              isinstance(gov.get("mandatory_tags"), dict))
        check(f"{name}: spend_limits es dict",
              isinstance(gov.get("spend_limits_by_project"), dict))
        check(f"{name}: responsible_area no vacío",
              bool(gov.get("responsible_area")),
              f"got: '{gov.get('responsible_area')}'")

section("S3Usage — respuestas 200 por empresa")
for name, uid in BUSINESSES.items():
    code, body = get(f"/businesses/{uid}/S3Usage")
    check(f"{name}: HTTP 200", code == 200, f"got {code} — {body.get('error','')}")
    if code == 200:
        check(f"{name}: service == 'S3'", body.get("service") == "S3",
              f"got {body.get('service')}")
        check(f"{name}: 'buckets' es lista", isinstance(body.get("buckets"), list))
        check(f"{name}: 'total_waste_gb' presente", "total_waste_gb" in body)
        for bucket in body.get("buckets", []):
            check(f"{name}: bucket tiene 'name'", "name" in bucket)
            check(f"{name}: waste_percentage 0-100",
                  0 <= bucket.get("waste_percentage", -1) <= 100,
                  f"got {bucket.get('waste_percentage')}")

section("EC2Usage — respuestas 200 por empresa")
for name, uid in BUSINESSES.items():
    code, body = get(f"/businesses/{uid}/EC2Usage")
    check(f"{name}: HTTP 200", code == 200, f"got {code} — {body.get('error','')}")
    if code == 200:
        check(f"{name}: service == 'EC2'", body.get("service") == "EC2",
              f"got {body.get('service')}")
        check(f"{name}: 'instances' es lista", isinstance(body.get("instances"), list))
        for inst in body.get("instances", []):
            check(f"{name}: instance tiene 'instance_id'", "instance_id" in inst)
            check(f"{name}: 'is_underutilized' es bool",
                  isinstance(inst.get("is_underutilized"), bool))
            check(f"{name}: 'optimization_suggestions' es lista",
                  isinstance(inst.get("optimization_suggestions"), list))

section("Manejo de errores — UUID inválido")
for endpoint in ("USDConsumption", "CloudGovernance", "S3Usage", "EC2Usage"):
    code, body = get(f"/businesses/not-a-uuid/{endpoint}")
    check(f"{endpoint}: UUID inválido → 400", code == 400, f"got {code}")

section("Manejo de errores — UUID válido pero inexistente")
ghost = "99999999-9999-9999-9999-999999999999"
for endpoint in ("USDConsumption", "CloudGovernance", "S3Usage", "EC2Usage"):
    code, body = get(f"/businesses/{ghost}/{endpoint}")
    check(f"{endpoint}: business inexistente → 404", code == 404, f"got {code}")

# ---------------------------------------------------------------------------
# Resumen
# ---------------------------------------------------------------------------

total = passed + failed
print(f"\n{'═'*55}")
print(f"  Resultado: {passed}/{total} tests pasaron  {'✅' if failed == 0 else '❌'}")
if errors:
    print(f"\n  Fallidos ({failed}):")
    for e in errors:
        print(f"  {e}")
print(f"{'═'*55}\n")

sys.exit(0 if failed == 0 else 1)