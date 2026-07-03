from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from src.physicalop import auto_parse_op


@dataclass
class OperatorTreeNode:
    op: str
    node_id: str
    children: Dict[str, "OperatorTreeNode"] = field(default_factory=dict)
    is_solution_node: bool = False

    # Turn/round that first created this node (1-based). Used for UI coloring.
    created_turn: Optional[int] = None

    # Display / details
    op_name: Optional[str] = None
    tables: List[str] = field(default_factory=list)
    label: Optional[str] = None
    op_full: Optional[str] = None
    out_table: Optional[str] = None
    out_preview: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "id": self.node_id,
            "op": self.op,
            "label": self.label or self.op,
            "opName": self.op_name,
            "tables": self.tables,
            "opFull": self.op_full,
            "outTable": self.out_table,
            "outPreview": self.out_preview,
            "isSolution": self.is_solution_node,
            "createdTurn": self.created_turn,
            "children": [child.to_dict() for child in self.children.values()],
        }


class OperatorTree:
    """A trie-like operator tree.

    Matching is string-level equality (after strip), as required.
    """

    def __init__(self):
        self.root = OperatorTreeNode(op="ROOT", node_id=self._make_node_id(["ROOT"]), label="ROOT")

    @staticmethod
    def _extract_table_names(op_obj: Any) -> List[str]:
        """Best-effort extraction of table names from an operator object.

        Many ops use `table_name` or `table_names`, but some reference multiple
        tables. We scan common attribute patterns and filter to names starting
        with 'table_'.
        """
        candidates: List[str] = []
        try:
            for k, v in vars(op_obj).items():
                lk = str(k).lower()
                if "table" not in lk:
                    continue
                if isinstance(v, str):
                    candidates.append(v)
                elif isinstance(v, list):
                    for x in v:
                        if isinstance(x, str):
                            candidates.append(x)
        except Exception:
            return []

        seen = set()
        out: List[str] = []
        for t in candidates:
            t2 = (t or "").strip()
            if not t2:
                continue
            if not t2.startswith("table_"):
                continue
            if t2 in seen:
                continue
            seen.add(t2)
            out.append(t2)
        return out

    @classmethod
    def _op_metadata(cls, op_str: str) -> dict:
        op_str2 = " ".join((op_str or "").strip().split())
        meta = {
            "op_full": op_str2,
            "op_name": None,
            "tables": [],
            "label": op_str2,
        }
        try:
            op_obj = auto_parse_op(op_str2)
            meta["op_name"] = op_obj.__class__.__name__
            meta["tables"] = cls._extract_table_names(op_obj)
            if meta["tables"]:
                meta["label"] = f"{meta['op_name']} ({', '.join(meta['tables'])})"
            else:
                meta["label"] = str(meta["op_name"] or op_str2)
        except Exception:
            # Parsing failed: keep raw string
            meta["label"] = op_str2
        return meta

    @staticmethod
    def _normalize_op(op: str) -> str:
        return " ".join(op.strip().split())

    @staticmethod
    def _make_node_id(path_ops: List[str]) -> str:
        # Stable, deterministic id based on path
        return "path::" + "||".join(path_ops)

    def add_chain(self, ops: List[str] | List[dict], is_solution: bool = False) -> List[str]:
        """Add an operator chain into the tree.

        `ops` can be:
        - List[str]: operator strings
        - List[dict]: each dict may contain: op, out_table, out_preview

        Returns the path node ids from root to leaf (excluding ROOT) for highlighting.
        """
        steps: List[dict] = []
        if not ops:
            return []
        if isinstance(ops[0], str):
            for s in ops:  # type: ignore[index]
                if s and str(s).strip():
                    steps.append({"op": str(s)})
        else:
            steps = [x for x in ops if isinstance(x, dict) and x.get("op")]  # type: ignore[assignment]

        cur = self.root
        path_ops = ["ROOT"]
        path_node_ids: List[str] = []

        for step in steps:
            raw_op = str(step.get("op", ""))
            op_norm = self._normalize_op(raw_op)
            if not op_norm:
                continue

            turn = step.get("turn")
            try:
                turn_int = int(turn) if turn is not None else None
            except Exception:
                turn_int = None

            meta = self._op_metadata(op_norm)
            path_ops_next = path_ops + [op_norm]
            node_id = self._make_node_id(path_ops_next)

            if op_norm not in cur.children:
                cur.children[op_norm] = OperatorTreeNode(
                    op=op_norm,
                    node_id=node_id,
                    op_name=meta.get("op_name"),
                    tables=list(meta.get("tables") or []),
                    label=meta.get("label"),
                    op_full=meta.get("op_full"),
                    created_turn=turn_int,
                )
            cur = cur.children[op_norm]

            # If node pre-exists (seen in earlier tree), don't overwrite created_turn.
            if cur.created_turn is None and turn_int is not None:
                cur.created_turn = turn_int

            # Update details if we have more info now (best-effort)
            if not cur.op_name and meta.get("op_name"):
                cur.op_name = meta.get("op_name")
            if (not cur.tables) and meta.get("tables"):
                cur.tables = list(meta.get("tables") or [])
            if meta.get("label"):
                cur.label = meta.get("label")
            if meta.get("op_full"):
                cur.op_full = meta.get("op_full")

            if step.get("out_table"):
                cur.out_table = step.get("out_table")
            if step.get("out_preview"):
                cur.out_preview = step.get("out_preview")

            path_ops = path_ops_next
            path_node_ids.append(cur.node_id)

        if is_solution:
            cur.is_solution_node = True

        return path_node_ids

    def to_dict(self) -> dict:
        return self.root.to_dict()
