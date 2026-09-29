"""Fixed AST repair heuristic; no fixture IDs, labels or candidate execution.

The public contract supplies the provider-error text. A flow-insensitive local
taint approximation handles direct credential reads and container assignments.
This is deliberately a useful baseline, not a claim of a general Python repairer.
"""
from __future__ import annotations

import ast

HELPER = '''def _cp_redact(value):
    secret = os.environ.get("CP_TEST_CREDENTIAL", "")
    if isinstance(value, str):
        return value.replace(secret, "[REDACTED]") if secret else value
    if isinstance(value, dict):
        return {_cp_redact(key): _cp_redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_cp_redact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_cp_redact(item) for item in value)
    return value
'''


def _root_name(node):
    while isinstance(node, (ast.Subscript, ast.Attribute)):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _credential_read(node):
    if isinstance(node, ast.Subscript):
        return (isinstance(node.value, ast.Attribute) and isinstance(node.value.value, ast.Name)
                and node.value.value.id == "os" and node.value.attr == "environ"
                and isinstance(node.slice, ast.Constant) and node.slice.value == "CP_TEST_CREDENTIAL")
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.args:
        return (ast.unparse(node.func) in {"os.getenv", "os.environ.get"}
                and isinstance(node.args[0], ast.Constant) and node.args[0].value == "CP_TEST_CREDENTIAL")
    return False


def repair(source: str) -> dict:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return {"status": "UNSUPPORTED", "code": source, "actions": ["syntax_unavailable"]}
    if any(isinstance(x, (ast.FunctionDef, ast.Name)) and (getattr(x, "name", None) == "_cp_redact"
            or getattr(x, "id", None) == "_cp_redact") for x in ast.walk(tree)):
        return {"status": "UNSUPPORTED", "code": source, "actions": ["reserved_helper_present"]}
    # Names are deliberately global across functions: conservative overtainting is
    # possible. The same full hidden behavior matrix judges every repaired output.
    tainted = set()
    loggers = {"logging"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            if ast.unparse(node.value.func) == "logging.getLogger":
                loggers.update(filter(None, (_root_name(x) for x in node.targets)))

    def is_tainted(node):
        if node is None:
            return False
        if _credential_read(node) or isinstance(node, ast.Name) and node.id in tainted:
            return True
        # The authentication response itself is public; this is the specified
        # declassification boundary, not a blanket exclusion for all calls.
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "authenticate":
            return False
        return any(is_tainted(child) for child in ast.iter_child_nodes(node))

    changed = True
    while changed:
        size = len(tainted)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and is_tainted(node.value):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                tainted.update(filter(None, (_root_name(x) for x in targets)))
        changed = len(tainted) != size

    actions, need_helper = [], False

    class Transform(ast.NodeTransformer):
        exception_names = []

        def visit_ExceptHandler(self, node):
            self.exception_names.append(node.name)
            node = self.generic_visit(node)
            self.exception_names.pop()
            return node

        def visit_Call(self, node):
            nonlocal need_helper
            # Trusted requirements say provider details must be replaced by this
            # public message. This generic exception-text rule does not use IDs.
            if (self.exception_names and isinstance(node.func, ast.Name) and node.func.id == "str"
                    and len(node.args) == 1 and isinstance(node.args[0], ast.Name)
                    and node.args[0].id in self.exception_names):
                actions.append("replace_exception_detail_with_contract_message")
                return ast.copy_location(ast.Constant("Authentication service unavailable"), node)
            node = self.generic_visit(node)
            sink = isinstance(node.func, ast.Name) and node.func.id == "print"
            sink = sink or (isinstance(node.func, ast.Attribute) and _root_name(node.func.value) in loggers
                            and node.func.attr in {"debug", "info", "warning", "error", "critical", "exception", "log"})
            if sink:
                for i, argument in enumerate(node.args):
                    if is_tainted(argument):
                        node.args[i] = ast.Call(func=ast.Name(id="_cp_redact", ctx=ast.Load()), args=[argument], keywords=[])
                        need_helper = True
                        actions.append("redact_tainted_diagnostic_argument")
            return node

        def visit_Return(self, node):
            nonlocal need_helper
            node = self.generic_visit(node)
            if is_tainted(node.value):
                node.value = ast.Call(func=ast.Name(id="_cp_redact", ctx=ast.Load()), args=[node.value], keywords=[])
                need_helper = True
                actions.append("redact_tainted_return")
            return node

    tree = Transform().visit(tree)
    if not actions:
        return {"status": "UNCHANGED", "code": source, "actions": []}
    if need_helper:
        if not any(isinstance(x, ast.Import) and any(n.name == "os" and n.asname is None for n in x.names) for x in tree.body):
            tree.body.insert(0, ast.Import(names=[ast.alias(name="os")]))
        tree.body.extend(ast.parse(HELPER).body)
    ast.fix_missing_locations(tree)
    return {"status": "PATCHED", "code": ast.unparse(tree) + "\n", "actions": sorted(set(actions))}


def fixed(source: str) -> str:
    return repair(source)["code"]
