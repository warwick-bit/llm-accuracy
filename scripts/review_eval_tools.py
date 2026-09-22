#!/usr/bin/env python3
"""Synthetic-only MCP evidence tools; no credentials, network or answer keys."""

from __future__ import annotations

import ast
import json
import operator
import sqlite3
import sys
from decimal import Decimal, localcontext
from pathlib import Path


def calculate(expression: str) -> str:
    """Evaluate bounded decimal arithmetic, without eval or Python execution."""
    if not isinstance(expression, str) or len(expression) > 500:
        raise ValueError("expression_limit")
    tree = ast.parse(expression, mode="eval")
    if len(list(ast.walk(tree))) > 100:
        raise ValueError("expression_limit")
    operations = {ast.Add: operator.add, ast.Sub: operator.sub,
                  ast.Mult: operator.mul, ast.Div: operator.truediv}

    def visit(node: ast.AST) -> Decimal:
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return Decimal(ast.get_source_segment(expression, node))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        if isinstance(node, ast.BinOp) and type(node.op) in operations:
            return operations[type(node.op)](visit(node.left), visit(node.right))
        raise ValueError("arithmetic_only")

    with localcontext() as context:
        context.prec = 40
        result = visit(tree.body)
    if not result.is_finite() or abs(result.adjusted()) > 100:
        raise ValueError("result_limit")
    return str(result)


def query(fixture: dict, sql: str) -> dict:
    """Execute a read-only statement against trusted synthetic in-memory data."""
    if not isinstance(sql, str) or len(sql) > 8000:
        raise ValueError("query_limit")
    connection = sqlite3.connect(":memory:")
    try:
        connection.executescript(fixture.get("setup_sql", ""))
        allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ,
                   sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
        functions = {"sum", "count", "avg", "total", "min", "max", "abs", "round",
                     "coalesce", "ifnull", "nullif", "length", "lower", "upper", "substr",
                     "date", "datetime", "julianday", "strftime", "row_number", "rank",
                     "dense_rank", "lag", "lead", "first_value", "last_value", "nth_value"}

        def authorize(action, first, second, database, trigger):
            if action == sqlite3.SQLITE_FUNCTION and second not in functions:
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY

        connection.set_authorizer(authorize)
        if hasattr(connection, "setlimit"):
            connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 1_000_000)
        ticks = 0

        def limit() -> int:
            nonlocal ticks
            ticks += 1
            return int(ticks > 1000)

        connection.set_progress_handler(limit, 1000)
        cursor = connection.execute(sql)
        rows = cursor.fetchmany(101)
        return {"columns": [item[0] for item in cursor.description or []],
                "rows": rows[:100], "partial": len(rows) > 100}
    finally:
        connection.close()


TOOLS = [
    {"name": "evidence", "description": "Read the complete synthetic review artifact, definitions and tables.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "query", "description": "Execute a read-only SQLite query against the evidence tables.",
     "inputSchema": {"type": "object", "properties": {"sql": {"type": "string"}},
                     "required": ["sql"], "additionalProperties": False}},
    {"name": "calculate", "description": "Compute decimal arithmetic with +, -, *, / and parentheses.",
     "inputSchema": {"type": "object", "properties": {"expression": {"type": "string"}},
                     "required": ["expression"], "additionalProperties": False}},
]


def tool_result(fixture: dict, name: str, arguments: dict) -> dict:
    try:
        if name == "evidence":
            result = fixture
        elif name == "query":
            result = query(fixture, arguments["sql"])
        elif name == "calculate":
            result = {"value": calculate(arguments["expression"])}
        else:
            raise ValueError("unknown_tool")
        return {"content": [{"type": "text", "text": json.dumps(result)}]}
    except Exception:
        # Never echo arbitrary request text or exception/provider detail.
        return {"isError": True, "content": [{"type": "text", "text": "invalid_or_disallowed_operation"}]}


def serve(fixture_path: Path, trace_path: Path) -> None:
    fixture = json.loads(fixture_path.read_text())
    for line in sys.stdin:
        try:
            message = json.loads(line)
            if "id" not in message:
                continue
            method = message.get("method")
            if method == "initialize":
                result = {"protocolVersion": message["params"]["protocolVersion"],
                          "capabilities": {"tools": {}},
                          "serverInfo": {"name": "synthetic-review", "version": "1.0.0"}}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                params = message["params"]
                name = params.get("name", "unknown")
                result = tool_result(fixture, name, params.get("arguments", {}))
                with trace_path.open("a") as trace:
                    trace.write(json.dumps({"tool": name if name in {"evidence", "query", "calculate"}
                                            else "unknown", "ok": not result.get("isError", False)}) + "\n")
            elif method == "ping":
                result = {}
            else:
                print(json.dumps({"jsonrpc": "2.0", "id": message["id"],
                                  "error": {"code": -32601, "message": "method_not_found"}}), flush=True)
                continue
            print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}), flush=True)
        except Exception:
            # Malformed transport has no trustworthy request id to echo.
            continue


if __name__ == "__main__":
    serve(Path(sys.argv[1]), Path(sys.argv[2]))
