"""
fps-core/user/manager.py — UserProfileManager
★ v2.0 新設

パーソナライゼーション基盤の中核。

Public API:
  - load()              プロファイルをファイルから読み込む
  - save()              プロファイルをファイルに保存する
  - learn(history_entries)  History データからタグ頻度を学習する
  - recommend(n)        頻出タグから推奨リストを返す
  - apply_profile(tags) プロファイルをタグリストに適用する
  - set_tag_weight(tag, weight)  タグの重みを手動設定する
  - add_style_rule(rule)         スタイルルールを追加する
  - remove_style_rule(rule_id)   スタイルルールを削除する
  - score_trends(days)           スコア傾向（時系列）を返す
  - reset()             プロファイルをリセットする
"""
from __future__ import annotations

import json
import logging
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .exceptions import ProfileNotFoundError, ProfileSaveError
from .models import (
    ScoreTrendEntry, StyleRule, TagFrequencyEntry, TagWeight, UserProfile
)

logger = logging.getLogger(__name__)

_PROFILE_FILENAME = "profile.json"
_MIN_FREQUENCY_THRESHOLD = 2    # 推奨に含める最低出現回数
_MAX_RECOMMENDATIONS = 30       # 推奨タグの最大件数


class UserProfileManager:
    """
    ユーザープロファイル管理クラス。

    使い方:
        upm = UserProfileManager(profile_dir=Path("fps-data/user"))
        upm.load()
        upm.learn(history_entries)
        recs = upm.recommend(10)
    """

    def __init__(self, profile_dir: Path) -> None:
        self._dir = Path(profile_dir)
        self._path = self._dir / _PROFILE_FILENAME
        self._profile = UserProfile()
        self._lock = threading.RLock()
        self._loaded = False

    # ── 読み書き ──────────────────────────────────────────────

    def load(self) -> "UserProfileManager":
        """プロファイルを JSON からロードする。ファイルがなければ新規作成。"""
        self._dir.mkdir(parents=True, exist_ok=True)
        with self._lock:
            if not self._path.exists():
                self._profile = UserProfile()
                self._loaded = True
                logger.info("UserProfile: 新規プロファイルを作成しました")
                return self
            try:
                data = json.loads(self._path.read_text(encoding="utf-8"))
                self._profile = self._dict_to_profile(data)
                self._loaded = True
                logger.info("UserProfile: ロード完了 (タグ頻度=%d件, ルール=%d件)",
                            len(self._profile.tag_frequencies),
                            len(self._profile.style_rules))
            except Exception as e:
                logger.warning("UserProfile: ロード失敗 → 新規作成: %s", e)
                self._profile = UserProfile()
                self._loaded = True
        return self

    def save(self) -> None:
        """プロファイルを JSON に保存する。"""
        self._dir.mkdir(parents=True, exist_ok=True)
        with self._lock:
            try:
                self._path.write_text(
                    json.dumps(self._profile.to_dict(), ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                logger.debug("UserProfile: 保存完了")
            except Exception as e:
                raise ProfileSaveError(f"プロファイル保存失敗: {e}") from e

    # ── 学習 ──────────────────────────────────────────────────

    def learn(self, history_entries: list[Any]) -> dict[str, int]:
        """
        History エントリからタグ使用頻度を学習する。

        Args:
            history_entries: HistoryEntry オブジェクトのリスト

        Returns:
            {"learned": 学習タグ数, "updated": 更新タグ数, "total": 総タグ種類数}
        """
        learned = 0
        updated = 0
        tag_counts: dict[str, list[float]] = defaultdict(list)

        for entry in history_entries:
            output = getattr(entry, "output_prompt", "") or ""
            for raw_tag in output.split(","):
                tag = raw_tag.strip().lower()
                if not tag:
                    continue
                # 重みは overall_score から推定（スコアが高いほど良いタグ）
                weight = max(0.5, min(2.0, getattr(entry, "overall_score", 50.0) / 50.0))
                tag_counts[tag].append(weight)

        with self._lock:
            for tag, weights in tag_counts.items():
                if tag in self._profile.tag_frequencies:
                    entry = self._profile.tag_frequencies[tag]
                    entry.count += len(weights)
                    entry.total_weight += sum(weights)
                    entry.last_used = datetime.now()
                    updated += 1
                else:
                    self._profile.tag_frequencies[tag] = TagFrequencyEntry(
                        tag=tag,
                        count=len(weights),
                        total_weight=sum(weights),
                        last_used=datetime.now(),
                    )
                    learned += 1

            self._profile.last_learned = datetime.now()

        self.save()
        logger.info("UserProfile: 学習完了 新規=%d 更新=%d 総計=%d",
                    learned, updated, len(self._profile.tag_frequencies))
        return {
            "learned": learned,
            "updated": updated,
            "total": len(self._profile.tag_frequencies),
        }

    # ── 推奨 ──────────────────────────────────────────────────

    def recommend(self, n: int = 20) -> list[TagFrequencyEntry]:
        """
        頻出タグから推奨タグリストを返す。

        閾値（_MIN_FREQUENCY_THRESHOLD）以上の出現回数かつ
        重み > 0（除外設定されていない）タグを頻度順で返す。
        """
        with self._lock:
            excluded = set(self._profile.excluded_tags())
            candidates = [
                e for e in self._profile.tag_frequencies.values()
                if e.count >= _MIN_FREQUENCY_THRESHOLD and e.tag not in excluded
            ]
            # 頻度 × 平均重み でスコアリング
            candidates.sort(key=lambda e: e.count * e.avg_weight, reverse=True)
            return candidates[:min(n, _MAX_RECOMMENDATIONS)]

    # ── プロファイル適用 ──────────────────────────────────────

    def apply_profile(self, tags: list[str]) -> list[str]:
        """
        タグリストにユーザープロファイルを適用する。

        処理順:
          1. always_exclude タグを除去（有効なスタイルルール全て）
          2. 重み = 0.0 のタグを除去
          3. always_include タグを先頭に追加（重複なし）
        """
        with self._lock:
            # スタイルルールから除外タグ収集
            exclude_set: set[str] = set()
            include_list: list[str] = []
            for rule in self._profile.style_rules:
                if not rule.enabled:
                    continue
                exclude_set.update(rule.always_exclude)
                include_list.extend(rule.always_include)

            # 重み 0 のタグも除外
            exclude_set.update(self._profile.excluded_tags())

            result = [t for t in tags if t.strip().lower() not in exclude_set]
            # include を先頭に（重複なし）
            existing = set(result)
            prefix = [t for t in include_list if t not in existing]
            return list(dict.fromkeys(prefix + result))

    # ── タグ重み操作 ───────────────────────────────────────────

    def set_tag_weight(self, tag: str, weight: float,
                       reason: str = "manual") -> TagWeight:
        """タグの重みを手動設定する（0.0 = 除外）。"""
        if not 0.0 <= weight <= 3.0:
            raise ValueError(f"weight は 0.0〜3.0 の範囲で指定してください: {weight}")
        with self._lock:
            tw = TagWeight(tag=tag.lower(), weight=weight, reason=reason)
            self._profile.tag_weights[tag.lower()] = tw
        self.save()
        return tw

    def remove_tag_weight(self, tag: str) -> bool:
        with self._lock:
            existed = tag.lower() in self._profile.tag_weights
            self._profile.tag_weights.pop(tag.lower(), None)
        if existed:
            self.save()
        return existed

    # ── スタイルルール操作 ─────────────────────────────────────

    def add_style_rule(self, rule: StyleRule) -> StyleRule:
        """スタイルルールを追加する。同 ID が存在すれば上書き。"""
        with self._lock:
            self._profile.style_rules = [
                r for r in self._profile.style_rules if r.id != rule.id
            ]
            self._profile.style_rules.append(rule)
        self.save()
        return rule

    def remove_style_rule(self, rule_id: str) -> bool:
        with self._lock:
            before = len(self._profile.style_rules)
            self._profile.style_rules = [
                r for r in self._profile.style_rules if r.id != rule_id
            ]
            removed = len(self._profile.style_rules) < before
        if removed:
            self.save()
        return removed

    # ── スコアトレンド ─────────────────────────────────────────

    def build_score_trends(self, history_entries: list[Any],
                           days: int = 30) -> list[ScoreTrendEntry]:
        """
        History エントリからスコア傾向（日別集計）を構築して保存する。

        Args:
            history_entries: HistoryEntry のリスト
            days:            集計日数

        Returns:
            ScoreTrendEntry のリスト（日付昇順）
        """
        cutoff = datetime.now() - timedelta(days=days)
        daily: dict[str, list[float]] = defaultdict(list)
        daily_tags: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for entry in history_entries:
            created = getattr(entry, "created_at", None)
            if created is None:
                continue
            if isinstance(created, str):
                try:
                    created = datetime.fromisoformat(created)
                except Exception:
                    continue
            if created < cutoff:
                continue
            date_key = created.strftime("%Y-%m-%d")
            daily[date_key].append(entry.overall_score)
            for tag in entry.output_prompt.split(","):
                t = tag.strip().lower()
                if t:
                    daily_tags[date_key][t] += 1

        trends = []
        for date_key in sorted(daily.keys()):
            scores = daily[date_key]
            top_tag = max(daily_tags[date_key], key=daily_tags[date_key].get,
                          default="") if daily_tags[date_key] else ""
            trends.append(ScoreTrendEntry(
                date=date_key,
                avg_score=sum(scores) / len(scores),
                entry_count=len(scores),
                top_tag=top_tag,
            ))

        with self._lock:
            self._profile.score_trends = trends
        self.save()
        return trends

    # ── ゲッター ───────────────────────────────────────────────

    def get_profile(self) -> UserProfile:
        with self._lock:
            return self._profile

    def reset(self) -> None:
        """プロファイルを完全リセットする。"""
        with self._lock:
            self._profile = UserProfile()
        self.save()
        logger.info("UserProfile: リセットしました")

    def statistics(self) -> dict[str, Any]:
        with self._lock:
            p = self._profile
            return {
                "tag_frequency_count": len(p.tag_frequencies),
                "tag_weight_count": len(p.tag_weights),
                "excluded_tag_count": len(p.excluded_tags()),
                "style_rule_count": len(p.style_rules),
                "score_trend_count": len(p.score_trends),
                "last_learned": p.last_learned.isoformat() if p.last_learned else None,
            }

    # ── 内部ヘルパー ──────────────────────────────────────────

    @staticmethod
    def _dict_to_profile(data: dict) -> UserProfile:
        p = UserProfile()
        for tag, w in data.get("tag_weights", {}).items():
            p.tag_weights[tag] = TagWeight(
                tag=w["tag"], weight=w["weight"], reason=w.get("reason", "manual"),
                last_updated=datetime.fromisoformat(w.get("last_updated",
                                                          datetime.now().isoformat())),
            )
        for r in data.get("style_rules", []):
            p.style_rules.append(StyleRule(
                id=r["id"], name=r["name"],
                always_include=r.get("always_include", []),
                always_exclude=r.get("always_exclude", []),
                enabled=r.get("enabled", True),
            ))
        for tag, e in data.get("tag_frequencies", {}).items():
            p.tag_frequencies[tag] = TagFrequencyEntry(
                tag=e["tag"], count=e["count"],
                total_weight=e.get("avg_weight", 1.0) * e["count"],
                last_used=datetime.fromisoformat(e.get("last_used",
                                                       datetime.now().isoformat())),
            )
        for s in data.get("score_trends", []):
            p.score_trends.append(ScoreTrendEntry(
                date=s["date"], avg_score=s["avg_score"],
                entry_count=s["entry_count"], top_tag=s.get("top_tag", ""),
            ))
        if data.get("last_learned"):
            p.last_learned = datetime.fromisoformat(data["last_learned"])
        if data.get("created_at"):
            p.created_at = datetime.fromisoformat(data["created_at"])
        return p


    # ══════════════════════════════════════════════════════════════
    # ★ v2.1 — 設定管理（自動学習モードなど）
    # ══════════════════════════════════════════════════════════════

    _DEFAULT_SETTINGS: "dict[str, Any]" = {
        "auto_learn": False,          # compile 後に自動学習するか
        "auto_learn_interval": 10,    # 何件 compile ごとに学習するか
        "apply_profile_default": False,  # compile 時にデフォルトで適用するか
        "recommendation_threshold": 2,   # 推奨タグの最低出現回数
    }

    def load_settings(self) -> "dict[str, Any]":
        """設定ファイル（settings.json）を読み込む。"""
        settings_path = self._dir / "settings.json"
        if not settings_path.exists():
            return dict(self._DEFAULT_SETTINGS)
        try:
            return {**self._DEFAULT_SETTINGS,
                    **json.loads(settings_path.read_text(encoding="utf-8"))}
        except Exception:
            return dict(self._DEFAULT_SETTINGS)

    def save_settings(self, settings: "dict[str, Any]") -> "dict[str, Any]":
        """設定ファイルを保存する。不明なキーは無視する。"""
        self._dir.mkdir(parents=True, exist_ok=True)
        merged = {**self._DEFAULT_SETTINGS}
        for k, v in settings.items():
            if k in self._DEFAULT_SETTINGS:
                merged[k] = v
        path = self._dir / "settings.json"
        path.write_text(json.dumps(merged, ensure_ascii=False, indent=2),
                        encoding="utf-8")
        return merged

    def get_settings(self) -> "dict[str, Any]":
        """現在の設定を返す（ファイルから読み込み）。"""
        return self.load_settings()

    def should_auto_learn(self, compile_count: int) -> bool:
        """
        現在の compile_count で自動学習を実行すべきか判定する。

        auto_learn=True かつ compile_count が interval の倍数のとき True。
        """
        s = self.load_settings()
        if not s.get("auto_learn", False):
            return False
        interval = max(1, int(s.get("auto_learn_interval", 10)))
        return compile_count > 0 and compile_count % interval == 0

    def __repr__(self) -> str:
        return (f"UserProfileManager(tags={len(self._profile.tag_frequencies)}, "
                f"rules={len(self._profile.style_rules)}, loaded={self._loaded})")
