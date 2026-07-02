"""
fps-core/chain/manager.py — プロンプトチェーン管理
★ v2.9 新設

複数の処理ステップをチェーンとして定義・実行する。

ステップ種別:
  wildcard   — Wildcard 構文を展開する
  compile    — パイプラインでコンパイルする
  profile    — UserProfile を適用する
  translate  — 日本語→タグ変換する
  filter     — カテゴリフィルタを適用する
  export     — 指定形式にエクスポートする

使い方:
    cm = ChainManager()
    chain = cm.create("my_chain", steps=[
        {"type": "wildcard"},
        {"type": "translate"},
        {"type": "compile"},
        {"type": "profile"},
    ])
    result = cm.run(chain.id, "青い目の少女、__style__", context=ctx)
    print(result.final_pos)
"""
from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ChainStep:
    """チェーンの1ステップ定義"""
    type:    str                # wildcard / compile / profile / translate / filter / export
    params:  dict[str, Any]    = field(default_factory=dict)
    label:   str               = ""
    enabled: bool              = True

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "params": self.params,
                "label": self.label, "enabled": self.enabled}


@dataclass
class PromptChain:
    """プロンプトチェーン定義"""
    id:          str
    name:        str
    description: str             = ""
    steps:       list[ChainStep] = field(default_factory=list)
    created_at:  str             = ""
    updated_at:  str             = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class ChainStepResult:
    """各ステップの実行結果"""
    step_index: int
    step_type:  str
    input_pos:  str
    output_pos: str
    input_neg:  str   = ""
    output_neg: str   = ""
    elapsed_ms: float = 0.0
    error:      str   = ""
    success:    bool  = True


@dataclass
class ChainResult:
    """チェーン全体の実行結果"""
    chain_id:   str
    chain_name: str
    input:      str
    final_pos:  str
    final_neg:  str               = ""
    steps:      list[ChainStepResult] = field(default_factory=list)
    total_ms:   float             = 0.0
    success:    bool              = True
    error:      str               = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "chain_id":   self.chain_id,
            "chain_name": self.chain_name,
            "input":      self.input,
            "final_pos":  self.final_pos,
            "final_neg":  self.final_neg,
            "total_ms":   round(self.total_ms, 1),
            "success":    self.success,
            "error":      self.error,
            "steps": [{
                "step_index": s.step_index,
                "step_type":  s.step_type,
                "output_pos": s.output_pos,
                "elapsed_ms": round(s.elapsed_ms, 1),
                "success":    s.success,
                "error":      s.error,
            } for s in self.steps],
        }


class ChainManager:
    """プロンプトチェーン管理クラス"""

    def __init__(self, chains_dir: Path) -> None:
        self._dir = Path(chains_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    # ── CRUD ──────────────────────────────────────────────────────

    def create(
        self,
        name:        str,
        steps:       list[dict] | None = None,
        description: str = "",
    ) -> PromptChain:
        now = datetime.now().isoformat()
        cid = secrets.token_urlsafe(8)
        chain = PromptChain(
            id=cid, name=name, description=description,
            steps=[ChainStep(**s) for s in (steps or [])],
            created_at=now, updated_at=now,
        )
        self._save(chain)
        return chain

    def get(self, chain_id: str) -> PromptChain | None:
        path = self._dir / f"{chain_id}.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return self._dict_to_chain(data)
        except Exception:
            return None

    def list_all(self) -> list[PromptChain]:
        result = []
        for path in sorted(self._dir.glob("*.json")):
            try:
                result.append(self._dict_to_chain(
                    json.loads(path.read_text(encoding="utf-8"))
                ))
            except Exception:
                pass
        return result

    def update(
        self,
        chain_id:    str,
        name:        str | None = None,
        steps:       list[dict] | None = None,
        description: str | None = None,
    ) -> PromptChain | None:
        chain = self.get(chain_id)
        if chain is None:
            return None
        if name        is not None: chain.name        = name
        if description is not None: chain.description = description
        if steps       is not None:
            chain.steps = [ChainStep(**s) for s in steps]
        chain.updated_at = datetime.now().isoformat()
        self._save(chain)
        return chain

    def delete(self, chain_id: str) -> bool:
        path = self._dir / f"{chain_id}.json"
        if path.exists():
            path.unlink()
            return True
        return False

    # ── チェーン実行 ──────────────────────────────────────────────

    def run(
        self,
        chain_id: str,
        prompt:   str,
        neg:      str = "",
        context:  Any = None,   # CliContext
    ) -> ChainResult:
        """
        チェーンを実行する。

        Args:
            chain_id: チェーンID
            prompt:   入力プロンプト（pos）
            neg:      入力ネガティブ
            context:  CliContext インスタンス

        Returns:
            ChainResult
        """
        import time
        chain = self.get(chain_id)
        if chain is None:
            return ChainResult(
                chain_id=chain_id, chain_name="?",
                input=prompt, final_pos=prompt, final_neg=neg,
                success=False, error=f"Chain '{chain_id}' not found",
            )

        t_start = time.perf_counter()
        current_pos = prompt
        current_neg = neg
        step_results: list[ChainStepResult] = []

        for i, step in enumerate(chain.steps):
            if not step.enabled:
                continue
            t_step = time.perf_counter()
            input_pos = current_pos
            input_neg = current_neg
            error = ""
            try:
                current_pos, current_neg = self._run_step(
                    step, current_pos, current_neg, context
                )
            except Exception as e:
                error = str(e)
            elapsed = (time.perf_counter() - t_step) * 1000
            step_results.append(ChainStepResult(
                step_index=i, step_type=step.type,
                input_pos=input_pos, output_pos=current_pos,
                input_neg=input_neg, output_neg=current_neg,
                elapsed_ms=elapsed,
                error=error, success=not error,
            ))

        total_ms = (time.perf_counter() - t_start) * 1000
        return ChainResult(
            chain_id=chain.id, chain_name=chain.name,
            input=prompt,
            final_pos=current_pos,
            final_neg=current_neg,
            steps=step_results,
            total_ms=total_ms,
            success=not any(s.error for s in step_results),
        )

    def _run_step(
        self, step: ChainStep, pos: str, neg: str, ctx: Any
    ) -> tuple[str, str]:
        """1ステップを実行する"""
        if step.type == "wildcard":
            if ctx is None: return pos, neg
            from wildcard.engine import WildcardEngine  # type: ignore
            engine = WildcardEngine(wildcard_manager=ctx.wildcard_manager,
                                    seed=step.params.get("seed"))
            return engine.expand(pos, variables=step.params.get("variables", {})), neg

        if step.type == "translate":
            if ctx is None: return pos, neg
            from translate.engine import TranslateEngine  # type: ignore
            engine = TranslateEngine(
                dictionary_manager=ctx.dictionary_manager,
                api_url=step.params.get("api_url"),
                api_key=step.params.get("api_key"),
            )
            result = engine.translate(pos)
            return result.to_prompt(), neg

        if step.type == "compile":
            if ctx is None: return pos, neg
            result = ctx.pipeline_manager.compile(pos)
            return result.prompt, result.negative or neg

        if step.type == "profile":
            if ctx is None: return pos, neg
            upm = ctx.user_profile_manager
            tags = [t.strip() for t in pos.split(",") if t.strip()]
            return ", ".join(upm.apply_profile(tags)), neg

        if step.type == "filter":
            categories = step.params.get("categories", [])
            exclude    = step.params.get("exclude", False)
            if ctx is None or not categories: return pos, neg
            tags = [t.strip() for t in pos.split(",") if t.strip()]
            result_tags = []
            for tag in tags:
                r = ctx.dictionary_manager.lookup(tag)
                cat_match = r.found and r.category in categories
                if (cat_match and not exclude) or (not cat_match and exclude):
                    result_tags.append(tag)
            return ", ".join(result_tags), neg

        if step.type == "export":
            fmt = step.params.get("format", "a1111")
            from export.exporters import get_exporter  # type: ignore
            exporter = get_exporter(fmt)
            result = exporter.export(pos, neg)
            return result.content, neg

        raise ValueError(f"Unknown step type: {step.type!r}")

    # ── 内部処理 ──────────────────────────────────────────────────

    def _save(self, chain: PromptChain) -> None:
        (self._dir / f"{chain.id}.json").write_text(
            json.dumps(chain.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _dict_to_chain(data: dict) -> PromptChain:
        return PromptChain(
            id=data["id"], name=data["name"],
            description=data.get("description", ""),
            steps=[ChainStep(
                type=s["type"], params=s.get("params", {}),
                label=s.get("label", ""), enabled=s.get("enabled", True),
            ) for s in data.get("steps", [])],
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )
