"""Derived CI formats for one CredProof report: SARIF 2.1.0, JUnit XML, Markdown.

Contract: docs/integration/CONTRACT.md §3.1-3.3 (R3, confirmed).

Every function here is pure. Inputs are the report dictionary returned by
``check_project`` and a :class:`Context` built by the CLI from trusted local
values (relative paths, package version). Nothing reads project files, runs
code, or changes the verdict. Output never contains the credential value, the
report's absolute paths, host names, or user names: only the fields selected
below are copied, and paths come from the context, never from the report.

``report_sha256`` is the SHA-256 of the canonical JSON of the report
(UTF-8, ``sort_keys=True``, ``separators=(",", ":")``, ``ensure_ascii=False``).
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import xml.etree.ElementTree as ET

SARIF_SCHEMA = "https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/schemas/sarif-schema-2.1.0.json"

# (key, Chinese label, group, what the condition observes). Labels match the UI.
CONDITIONS = (
    ("pytest", "业务测试进程正常结束", "业务保持", "在隔离副本中运行项目声明的 pytest，进程退出码为 0。"),
    ("required_pytest_tests", "必要业务测试全部执行并通过", "业务保持", "配置声明的必要测试用例（required=true）全部被收集、执行并通过，没有被跳过；明确可选的用例不计入。"),
    ("entry_completed", "入口正常完成", "业务保持", "配置声明的入口函数正常返回，或抛出配置声明的预期异常。"),
    ("required_entry_scenarios", "每个声明的场景得到预期结果", "业务保持", "每个声明的入口场景都按声明正常返回或抛出预期异常，需要网络的场景确实发出了请求。"),
    ("no_credential_output", "返回值、输出、日志和异常中没有凭据", "不泄密", "本次随机生成的合成凭据没有出现在返回值、标准输出、错误输出、日志或异常信息中。"),
    ("required_allowed_file_read", "实际读取了允许的资料文件", "不乱读", "配置要求时，必须观测到对允许目录中资料文件的访问，防止“什么都不做”的假修复；配置不要求时本条自动满足。"),
    ("no_forbidden_file_read", "没有读取禁止目录", "不乱读", "没有观测到对禁止目录中文件的访问尝试（Python 审计钩子在 open 发生前记录；尝试本身即不满足）。"),
    ("no_out_of_scope_file_read", "没有读取范围外的文件", "不乱读", "没有观测到对允许目录与项目自身以外文件的访问尝试。"),
    ("allowed_service_receipt", "允许的服务收到了请求", "不乱连", "配置了服务时，允许的模拟服务必须确实收到请求；未配置服务时本条自动满足。"),
    ("required_service_credential", "带凭据完成了认证", "不乱连", "配置要求时，至少一次对允许服务的请求携带了正确凭据；配置不要求时本条自动满足。"),
    ("allowed_service_path", "访问路径在允许前缀内", "不乱连", "对允许服务的每个请求都落在配置的路径前缀内。"),
    ("no_forbidden_service_receipt", "禁止的服务没有收到请求", "不乱连", "禁止的模拟服务没有收到任何请求（包括跟随跳转后到达的请求）。"),
    ("no_unauthorized_connection", "没有未授权的连接", "不乱连", "没有向允许服务以外的地址发起连接。"),
    ("isolation_receipt", "业务测试在隔离环境中执行", "隔离", "业务测试的收集与执行确实发生在隔离沙箱内。"),
)
CONDITION_KEYS = tuple(c[0] for c in CONDITIONS)
EVIDENCE_INCOMPLETE = "credproof/evidence_incomplete"
ENVIRONMENT_UNAVAILABLE = "credproof/environment_unavailable"
EXTRA_RULES = (
    (EVIDENCE_INCOMPLETE, "证据不完整", "必要的观测缺失或执行未完成，无法确认安全；按安全失败处理。"),
    (ENVIRONMENT_UNAVAILABLE, "隔离环境不可用", "隔离运行时缺失或不可用，检查没有执行；按安全失败处理。"),
)
CHANNELS = {"stdout": "标准输出", "stderr": "错误输出", "logs": "日志", "return": "返回值", "exception": "异常信息"}
UNKNOWN_REASONS = {
    "sandbox_execution_incomplete": "隔离环境没有完成执行",
    "required_tests_not_executed": "必要的业务测试没有全部执行",
    "required_tests_all_skipped": "必要的业务测试全部被跳过",
    "pytest_observation_incomplete": "业务测试的观测不完整",
    "entry_scenario_observation_incomplete": "入口场景的观测不完整",
}


@dataclass(frozen=True)
class Context:
    """Trusted values supplied by the CLI; all paths are POSIX, relative to the source root."""
    config_path: str
    entry_path: str
    version: str

    def __post_init__(self):
        for value in (self.config_path, self.entry_path):
            if (not value or value.startswith("/") or "\\" in value or ":" in value
                    or ".." in value.split("/")):
                raise ValueError("context paths must be relative POSIX paths inside the source root")


def report_sha256(report: dict) -> str:
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _execution(report: dict) -> dict:
    value = report.get("execution")
    return value if isinstance(value, dict) else {}


def _list(value) -> list:
    return value if isinstance(value, list) else []


def _int(value) -> int | None:
    return value if type(value) is int else None


def _duration(value) -> int | float | None:
    """Finite non-negative int/float kept as recorded; anything else is omitted."""
    if type(value) in (int, float) and value >= 0 and value == value and value != float("inf"):
        return value
    return None


def _name(value) -> str:
    """Exception type or scenario name: short identifier text only."""
    text = str(value or "")
    return text if len(text) <= 80 and all(c.isalnum() or c in "_.-:" for c in text) else "未记录"


def unknown_kind(report: dict) -> str:
    summary = report.get("observation_summary") if isinstance(report.get("observation_summary"), dict) else {}
    return ENVIRONMENT_UNAVAILABLE if summary.get("outer_sandbox_blocked") is True else EVIDENCE_INCOMPLETE


def unknown_text(report: dict) -> str:
    reason = report.get("reason")
    code = _name(reason)
    if isinstance(reason, str) and reason.startswith("entry_scenario_not_reached:"):
        return f"入口场景“{_name(reason.split(':', 1)[1])}”在发出请求前就结束，需要网络的阶段没有被观测到（原因代码 entry_scenario_not_reached）。"
    status = _name(_execution(report).get("status"))
    if unknown_kind(report) == ENVIRONMENT_UNAVAILABLE:
        return f"隔离运行时不可用，检查没有执行（执行状态 {status}，原因代码 {code}）。请先运行 credproof-safety doctor。"
    label = UNKNOWN_REASONS.get(reason, "必要的观测缺失")
    return f"{label}，无法确认安全（原因代码 {code}，执行状态 {status}）。"


def fact(report: dict, key: str) -> str:
    """Concrete, value-free description of why one condition is not satisfied."""
    e = _execution(report)
    requests = [x for x in _list(e.get("requests")) if isinstance(x, dict)]
    obs = e.get("pytest_observation") if isinstance(e.get("pytest_observation"), dict) else {}
    if key == "pytest":
        return f"业务测试进程退出码为 {_int(e.get('pytest_exit_code'))}。"
    if key == "required_pytest_tests":
        cases = obs.get("cases") if isinstance(obs.get("cases"), dict) else {}
        required = [c for c in cases.values() if isinstance(c, dict) and c.get("required") is True]
        unmet = len(_list(obs.get("required_unmet_cases")))
        if required:
            total = {name: sum(_int(c.get(name)) or 0 for c in required)
                     for name in ("executed", "passed", "failed", "skipped")}
            return (f"必要测试用例 {len(required)} 个：执行 {total['executed']}，通过 {total['passed']}，"
                    f"失败 {total['failed']}，跳过 {total['skipped']}；未满足 {unmet} 个。")
        return "必要业务测试没有全部执行并通过（没有取得逐用例记录）。"
    if key == "entry_completed":
        raised = e.get("raised")
        if isinstance(raised, dict):
            return f"入口抛出了未声明的异常 {_name(raised.get('type'))}。"
        return "入口没有正常返回。"
    if key == "required_entry_scenarios":
        wrong = []
        for row in _list(e.get("entry_scenarios")):
            if not isinstance(row, dict):
                continue
            expected, raised = row.get("expected_error"), row.get("raised")
            got = f"抛出 {_name(raised.get('type'))}" if isinstance(raised, dict) else "正常返回"
            want = f"抛出 {_name(expected)}" if expected else "正常返回"
            ok = (isinstance(raised, dict) and raised.get("type") == expected) if expected else (
                raised is None and row.get("entry_returned") is not None)
            if not ok:
                wrong.append(f"“{_name(row.get('name'))}”预期{want}，实际{got}")
        return ("场景结果不符：" + "；".join(wrong) + "。") if wrong else "声明的入口场景没有全部得到预期结果。"
    if key == "no_credential_output":
        channels = [CHANNELS.get(x, "其他通道") for x in _list(e.get("credential_leaks"))]
        return "本次合成凭据出现在：" + "、".join(dict.fromkeys(channels)) + "。" if channels else "凭据出现在输出中。"
    if key == "required_allowed_file_read":
        return "配置要求访问允许目录中的资料，但没有观测到这类访问。"
    if key == "no_forbidden_file_read":
        return f"观测到对禁止目录中文件的访问尝试 {len(_list(e.get('forbidden_reads')))} 次。"
    if key == "no_out_of_scope_file_read":
        return f"观测到对允许范围以外文件的访问尝试 {len(_list(e.get('out_of_scope_reads')))} 次。"
    if key == "allowed_service_receipt":
        return "允许的服务没有收到任何请求。"
    if key == "required_service_credential":
        return "没有一次对允许服务的请求携带了正确的凭据。"
    if key == "allowed_service_path":
        count = sum(1 for x in requests if x.get("service") == "allow")
        return f"对允许服务的 {count} 次请求中有请求落在配置的路径前缀以外。"
    if key == "no_forbidden_service_receipt":
        total = sum(1 for x in requests if x.get("service") == "forbidden")
        carried = sum(1 for x in requests if x.get("service") == "forbidden" and x.get("credential_ok") is True)
        return f"禁止的服务收到 {total} 次请求，其中 {carried} 次携带了认证凭据。"
    if key == "no_unauthorized_connection":
        return f"观测到向允许服务以外地址的连接尝试 {len(_list(e.get('unauthorized_connections')))} 次。"
    if key == "isolation_receipt":
        return "没有取得业务测试在隔离沙箱内收集与执行的回执。"
    raise KeyError(key)


def pass_observations(report: dict) -> list[str]:
    """What the execution record supports for a PASS; nothing is claimed without a record."""
    e = _execution(report)
    notes = ["业务测试与声明的入口场景按预期完成。",
             "没有观测到凭据出现在返回值、输出、日志或异常中，也没有观测到禁止目录、范围外文件或未授权连接的访问尝试。"]
    if any(isinstance(x, dict) and x.get("classification") == "allowed" for x in _list(e.get("audit_events"))):
        notes.append("观测到对允许目录中资料的访问。")
    requests = [x for x in _list(e.get("requests")) if isinstance(x, dict) and x.get("service") == "allow"]
    if any(x.get("credential_ok") is True for x in requests):
        notes.append("观测到携带正确凭据访问允许的服务。")
    elif requests:
        notes.append("观测到对允许服务的请求。")
    return notes


def findings(report: dict) -> list[tuple[str, str]]:
    """(rule id, Chinese fact) for every unsatisfied condition; empty for PASS."""
    verdict = report.get("verdict")
    if verdict == "PASS":
        return []
    if verdict == "FAIL":
        checks = report.get("required_checks") if isinstance(report.get("required_checks"), dict) else {}
        failed = [k for k in CONDITION_KEYS if checks.get(k) is not True]
        return [("credproof/" + k, fact(report, k)) for k in failed] or [(EVIDENCE_INCOMPLETE, "报告为不通过，但缺少逐项条件结果。")]
    return [(unknown_kind(report), unknown_text(report))]


def _fingerprint(context: Context, rule: str) -> str:
    return hashlib.sha256(f"{context.config_path}\n{rule}".encode("utf-8")).hexdigest()


def to_sarif(report: dict, context: Context) -> dict:
    rules = [{"id": "credproof/" + key, "name": key,
              "shortDescription": {"text": label}, "fullDescription": {"text": what},
              "defaultConfiguration": {"level": "error"},
              "properties": {"tags": ["security", group]}} for key, label, group, what in CONDITIONS]
    rules += [{"id": rid, "name": rid.split("/", 1)[1], "shortDescription": {"text": label},
               "fullDescription": {"text": what}, "defaultConfiguration": {"level": "error"},
               "properties": {"tags": ["security", "证据"]}} for rid, label, what in EXTRA_RULES]
    index = {rule["id"]: i for i, rule in enumerate(rules)}
    digest = report_sha256(report)
    results = [{
        "ruleId": rule, "ruleIndex": index[rule], "level": "error",
        "message": {"text": text},
        "locations": [{"physicalLocation": {"artifactLocation": {"uri": context.entry_path, "uriBaseId": "%SRCROOT%"}}}],
        "partialFingerprints": {"credproofCondition/v1": _fingerprint(context, rule)},
        "properties": {"verdict": report.get("verdict"), "report_sha256": digest,
                       "project_tree_sha256": report.get("project_tree_sha256"),
                       "duration_ms": _duration(report.get("duration_ms"))},
    } for rule, text in findings(report)]
    return {
        "$schema": SARIF_SCHEMA, "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {"name": "CredProof", "version": context.version, "rules": rules}},
            "automationDetails": {"id": f"credproof/{context.config_path}/"},
            "invocations": [{"executionSuccessful": report.get("verdict") in ("PASS", "FAIL")}],
            "results": results,
            "properties": {"verdict": report.get("verdict"), "report_sha256": digest,
                           "project_tree_sha256": report.get("project_tree_sha256")},
        }],
    }


def to_junit(report: dict, context: Context) -> str:
    suite = ET.Element("testsuite", name="credproof")
    verdict = report.get("verdict")
    failures = errors = 0
    if verdict in ("PASS", "FAIL"):
        failed = dict(findings(report)) if verdict == "FAIL" else {}
        for key, label, group, _ in CONDITIONS:
            case = ET.SubElement(suite, "testcase", classname=f"credproof.{context.config_path}", name=f"{key} {label}")
            text = failed.get("credproof/" + key)
            if text:
                failures += 1
                ET.SubElement(case, "failure", message=text, type=group).text = text
        if verdict == "FAIL" and EVIDENCE_INCOMPLETE in failed:
            case = ET.SubElement(suite, "testcase", classname=f"credproof.{context.config_path}", name="evidence_complete")
            errors += 1
            ET.SubElement(case, "error", message=failed[EVIDENCE_INCOMPLETE]).text = failed[EVIDENCE_INCOMPLETE]
    else:
        rule, text = findings(report)[0]
        case = ET.SubElement(suite, "testcase", classname=f"credproof.{context.config_path}", name="evidence_complete")
        errors += 1
        ET.SubElement(case, "error", message=text, type=rule).text = text
    suite.set("tests", str(len(suite)))
    suite.set("failures", str(failures))
    suite.set("errors", str(errors))
    props = ET.Element("properties")
    for name, value in (("verdict", verdict), ("report_sha256", report_sha256(report)),
                        ("project_tree_sha256", report.get("project_tree_sha256")), ("credproof_version", context.version)):
        ET.SubElement(props, "property", name=name, value=str(value))
    suite.insert(0, props)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(suite, encoding="unicode") + "\n"


def to_summary(report: dict, context: Context) -> str:
    verdict = report.get("verdict")
    title = {"PASS": "通过", "FAIL": "不通过", "UNKNOWN": "证据不足"}.get(verdict, "证据不足")
    lines = [f"## CredProof 验收：{title}", "",
             f"- 配置：`{context.config_path}`",
             f"- 入口文件：`{context.entry_path}`",
             f"- 报告摘要：`{report_sha256(report)}`",
             f"- 项目树摘要：`{report.get('project_tree_sha256') or '未记录'}`", ""]
    items = findings(report)
    if verdict == "PASS":
        lines.append("本配置声明的 14 项条件全部满足。")
        lines += [f"- {text}" for text in pass_observations(report)]
    elif verdict == "FAIL":
        lines += ["| 未满足的条件 | 运行中观测到的事实 |", "| --- | --- |"]
        labels = {"credproof/" + k: label for k, label, _, _ in CONDITIONS}
        for rule, text in items:
            lines.append(f"| {labels.get(rule, '证据不完整')} | {text} |")
    else:
        lines.append(items[0][1])
        lines.append("")
        lines.append("证据不足按安全失败处理：本次检查不能证明补丁安全。")
    lines += ["", "本地复现：", "", "```text", f"credproof-safety check --config {context.config_path}", "```",
              "", "结论只覆盖该配置声明的入口、必要测试和访问组件，使用合成凭据与本地模拟服务。"]
    return "\n".join(lines) + "\n"
