# -*- coding: utf-8 -*-
"""
A/B 测试服务

管理 A/B 实验的流量抽取、路由回复记录、投票统计与后台 CRUD。
"""

import logging
import random
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.future import select

from src.database.models import ABExperiment, ABArm, ABRoutedReply, ABVote, ABFeedback
from src.database.database import AsyncSessionLocal
from src.chat.utils.database import chat_db_manager

log = logging.getLogger(__name__)

AI_RELOAD_PENDING_KEY = "ai_reload_pending"


class ABTestService:
    """
    A/B 实验的流量抽取与数据 CRUD 服务。
    """

    @staticmethod
    def _experiment_to_dict(experiment: ABExperiment) -> Dict[str, Any]:
        return {
            "id": experiment.id,
            "name": experiment.name,
            "note": experiment.note,
            "enabled": experiment.enabled,
            "created_at": experiment.created_at,
            "updated_at": experiment.updated_at,
        }

    @staticmethod
    def _arm_to_dict(arm: ABArm) -> Dict[str, Any]:
        return {
            "id": arm.id,
            "experiment_id": arm.experiment_id,
            "label": arm.label,
            "model_full_id": arm.model_full_id,
            "traffic_percent": arm.traffic_percent,
            "enabled": arm.enabled,
            "created_at": arm.created_at,
        }

    @staticmethod
    def _reply_to_dict(reply: ABRoutedReply) -> Dict[str, Any]:
        return {
            "id": reply.id,
            "experiment_id": reply.experiment_id,
            "arm_id": reply.arm_id,
            "message_id": reply.message_id,
            "channel_id": reply.channel_id,
            "guild_id": reply.guild_id,
            "trigger_user_id": reply.trigger_user_id,
            "question_text": reply.question_text,
            "reply_text": reply.reply_text,
            "model_full_id": reply.model_full_id,
            "created_at": reply.created_at,
        }

    @staticmethod
    async def get_active_experiment() -> Optional[Dict[str, Any]]:
        stmt = (
            select(ABExperiment)
            .where(ABExperiment.enabled == 1)
            .order_by(ABExperiment.id)
            .limit(1)
        )
        async with AsyncSessionLocal() as session:
            result = await session.execute(stmt)
            experiment = result.scalars().first()
        if not experiment:
            return None
        return {
            "id": experiment.id,
            "name": experiment.name,
            "note": experiment.note,
            "enabled": experiment.enabled,
        }

    @staticmethod
    async def draw_arm() -> Optional[Dict[str, Any]]:
        try:
            experiment = await ABTestService.get_active_experiment()
            if not experiment:
                return None
            stmt = (
                select(ABArm)
                .where(ABArm.experiment_id == experiment["id"], ABArm.enabled == 1)
                .order_by(ABArm.id)
            )
            async with AsyncSessionLocal() as session:
                result = await session.execute(stmt)
                arms = list(result.scalars().all())
            if not arms:
                return None
            roll = random.uniform(0, 100)
            cumulative = 0.0
            chosen = None
            for arm in arms:
                cumulative += max(int(arm.traffic_percent or 0), 0)
                if roll < cumulative:
                    chosen = arm
                    break
            if chosen is None:
                return None
            return {
                "experiment_id": experiment["id"],
                "arm_id": chosen.id,
                "model_full_id": chosen.model_full_id,
                "label": chosen.label,
            }
        except Exception as e:
            log.error(f"[A/B] 抽取实验分组失败，本次回复走默认模型: {e}", exc_info=True)
            return None

    @staticmethod
    async def record_routed_reply(
        *,
        experiment_id: int,
        arm_id: int,
        model_full_id: str,
        guild_id: Optional[int],
        channel_id: int,
        message_id: int,
        trigger_user_id: int,
        question_text: str,
        reply_text: str,
    ) -> int:
        reply = ABRoutedReply(
            experiment_id=experiment_id,
            arm_id=arm_id,
            model_full_id=model_full_id,
            guild_id=guild_id,
            channel_id=channel_id,
            message_id=message_id,
            trigger_user_id=trigger_user_id,
            question_text=question_text,
            reply_text=reply_text,
        )
        async with AsyncSessionLocal() as session:
            session.add(reply)
            await session.commit()
            await session.refresh(reply)
        return reply.id

    @staticmethod
    async def get_reply_by_message_id(message_id: int) -> Optional[Dict[str, Any]]:
        stmt = select(ABRoutedReply).where(ABRoutedReply.message_id == message_id)
        async with AsyncSessionLocal() as session:
            result = await session.execute(stmt)
            reply = result.scalars().first()
        if not reply:
            return None
        return ABTestService._reply_to_dict(reply)

    @staticmethod
    async def record_vote(reply_id: int, voter_id: int, vote: int) -> None:
        stmt = pg_insert(ABVote).values(
            reply_id=reply_id, voter_id=voter_id, vote=vote
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["reply_id", "voter_id"],
            set_={"vote": stmt.excluded.vote, "updated_at": func.now()},
        )
        async with AsyncSessionLocal() as session:
            await session.execute(stmt)
            await session.commit()

    @staticmethod
    async def record_feedback(
        reply_id: int, user_id: int, reasons: List[str], free_text: Optional[str]
    ) -> None:
        feedback = ABFeedback(
            reply_id=reply_id,
            user_id=user_id,
            reasons=list(reasons or []),
            free_text=free_text,
        )
        async with AsyncSessionLocal() as session:
            session.add(feedback)
            await session.commit()

    @staticmethod
    async def set_ai_reload_pending() -> None:
        await chat_db_manager.set_global_setting(AI_RELOAD_PENDING_KEY, "1")

    @staticmethod
    async def consume_ai_reload_pending() -> bool:
        value = await chat_db_manager.get_global_setting(AI_RELOAD_PENDING_KEY)
        if value == "1":
            await chat_db_manager.delete_global_setting(AI_RELOAD_PENDING_KEY)
            return True
        return False

    @staticmethod
    async def list_experiments() -> List[Dict[str, Any]]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(ABExperiment).order_by(ABExperiment.id))
            experiments = list(result.scalars().all())
            result = await session.execute(select(ABArm).order_by(ABArm.experiment_id, ABArm.id))
            arms = list(result.scalars().all())
        arms_by_experiment: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for arm in arms:
            arms_by_experiment[arm.experiment_id].append(ABTestService._arm_to_dict(arm))
        return [
            {**ABTestService._experiment_to_dict(experiment), "arms": arms_by_experiment.get(experiment.id, [])}
            for experiment in experiments
        ]

    @staticmethod
    async def create_experiment(
        name: str, note: Optional[str], arms: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        experiment = ABExperiment(name=name, note=note, enabled=0)
        async with AsyncSessionLocal() as session:
            session.add(experiment)
            await session.flush()
            arm_rows = ABTestService._build_arms(experiment.id, arms)
            session.add_all(arm_rows)
            await session.commit()
            await session.refresh(experiment)
            for arm in arm_rows:
                await session.refresh(arm)
        return {
            **ABTestService._experiment_to_dict(experiment),
            "arms": [ABTestService._arm_to_dict(arm) for arm in arm_rows],
        }

    @staticmethod
    def _build_arms(experiment_id: int, arms: List[Dict[str, Any]]) -> List[ABArm]:
        arm_rows = []
        for arm_data in arms or []:
            arm_rows.append(
                ABArm(
                    experiment_id=experiment_id,
                    label=str(arm_data.get("label", "")),
                    model_full_id=str(arm_data.get("model_full_id", "")),
                    traffic_percent=min(
                        100, max(0, int(arm_data.get("traffic_percent", 10) or 0))
                    ),
                    enabled=1 if arm_data.get("enabled", 1) else 0,
                )
            )
        return arm_rows

    @staticmethod
    async def update_experiment(
        experiment_id: int, *, name: Optional[str] = None, note: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ABExperiment).where(ABExperiment.id == experiment_id)
            )
            experiment = result.scalars().first()
            if not experiment:
                return None
            if name is not None:
                experiment.name = name
            if note is not None:
                experiment.note = note
            await session.commit()
            await session.refresh(experiment)
        return ABTestService._experiment_to_dict(experiment)

    @staticmethod
    async def delete_experiment(experiment_id: int) -> None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ABExperiment).where(ABExperiment.id == experiment_id)
            )
            experiment = result.scalars().first()
            if not experiment:
                return
            await session.delete(experiment)
            await session.commit()

    @staticmethod
    async def set_experiment_enabled(experiment_id: int, enabled: bool) -> None:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ABExperiment).where(ABExperiment.id == experiment_id)
            )
            experiment = result.scalars().first()
            if not experiment:
                return
            if enabled:
                await session.execute(
                    ABExperiment.__table__.update()
                    .where(ABExperiment.enabled == 1)
                    .values(enabled=0)
                )
            experiment.enabled = 1 if enabled else 0
            await session.commit()

    @staticmethod
    async def replace_arms(
        experiment_id: int, arms: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ABArm)
                .where(ABArm.experiment_id == experiment_id)
                .order_by(ABArm.id)
            )
            existing = {arm.id: arm for arm in result.scalars().all()}
            kept_ids = set()
            final_arms = []
            for arm_data in arms or []:
                arm_id = arm_data.get("id")
                if arm_id is not None and arm_id in existing:
                    arm = existing[arm_id]
                    if "label" in arm_data:
                        arm.label = str(arm_data["label"])
                    if "model_full_id" in arm_data:
                        arm.model_full_id = str(arm_data["model_full_id"])
                    if "traffic_percent" in arm_data:
                        arm.traffic_percent = min(
                            100, max(0, int(arm_data["traffic_percent"] or 0))
                        )
                    if "enabled" in arm_data:
                        arm.enabled = 1 if arm_data["enabled"] else 0
                    kept_ids.add(arm.id)
                    final_arms.append(arm)
                else:
                    arm = ABArm(
                        experiment_id=experiment_id,
                        label=str(arm_data.get("label", "")),
                        model_full_id=str(arm_data.get("model_full_id", "")),
                        traffic_percent=min(
                            100, max(0, int(arm_data.get("traffic_percent", 10) or 0))
                        ),
                        enabled=1 if arm_data.get("enabled", 1) else 0,
                    )
                    session.add(arm)
                    final_arms.append(arm)
            for arm_id, arm in existing.items():
                if arm_id not in kept_ids:
                    await session.delete(arm)
            await session.commit()
            for arm in final_arms:
                await session.refresh(arm)
        return [ABTestService._arm_to_dict(arm) for arm in final_arms]

    @staticmethod
    async def _load_stats_rows(
        experiment_id: int, days: int
    ):
        cutoff = datetime.now() - timedelta(days=days)
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ABExperiment).where(ABExperiment.id == experiment_id)
            )
            experiment = result.scalars().first()
            if not experiment:
                return None, [], [], [], []
            result = await session.execute(
                select(ABArm)
                .where(ABArm.experiment_id == experiment_id)
                .order_by(ABArm.id)
            )
            arms = list(result.scalars().all())
            result = await session.execute(
                select(ABRoutedReply)
                .where(
                    ABRoutedReply.experiment_id == experiment_id,
                    ABRoutedReply.created_at >= cutoff,
                )
                .order_by(ABRoutedReply.id)
            )
            replies = list(result.scalars().all())
            reply_ids = [reply.id for reply in replies]
            votes: List[ABVote] = []
            feedback: List[ABFeedback] = []
            if reply_ids:
                result = await session.execute(
                    select(ABVote).where(ABVote.reply_id.in_(reply_ids))
                )
                votes = list(result.scalars().all())
                result = await session.execute(
                    select(ABFeedback)
                    .where(ABFeedback.reply_id.in_(reply_ids))
                    .order_by(ABFeedback.id)
                )
                feedback = list(result.scalars().all())
        return experiment, arms, replies, votes, feedback

    @staticmethod
    async def get_stats(experiment_id: int, days: int = 30) -> Dict[str, Any]:
        loaded = await ABTestService._load_stats_rows(experiment_id, days)
        experiment, arms, replies, votes, feedback = loaded
        if experiment is None:
            return {}

        arm_by_id = {arm.id: arm for arm in arms}
        reply_arm: Dict[int, int] = {reply.id: reply.arm_id for reply in replies}
        reply_date: Dict[int, str] = {}
        for reply in replies:
            created_at = reply.created_at
            reply_date[reply.id] = (
                created_at.date().isoformat() if created_at else ""
            )

        per_arm: Dict[int, Dict[str, Any]] = {
            arm.id: {
                "arm_id": arm.id,
                "label": arm.label,
                "model_full_id": arm.model_full_id,
                "traffic_percent": arm.traffic_percent,
                "routed_count": 0,
                "votes": {"better": 0, "worse": 0, "same": 0, "total": 0},
                "better_rate": None,
                "worse_rate": None,
                "net_score": None,
            }
            for arm in arms
        }
        daily: Dict[tuple, Dict[str, Any]] = {}

        for reply in replies:
            arm_stats = per_arm.get(reply.arm_id)
            if arm_stats is not None:
                arm_stats["routed_count"] += 1
            date_str = reply_date.get(reply.id, "")
            key = (date_str, reply.arm_id)
            bucket = daily.setdefault(
                key,
                {"date": date_str, "arm_id": reply.arm_id, "routed": 0, "better": 0, "worse": 0, "same": 0},
            )
            bucket["routed"] += 1

        vote_key_map = {1: "better", 2: "worse", 3: "same"}
        for vote in votes:
            arm_id = reply_arm.get(vote.reply_id)
            if arm_id is None:
                continue
            arm_stats = per_arm.get(arm_id)
            vote_key = vote_key_map.get(vote.vote)
            if arm_stats is not None and vote_key:
                arm_stats["votes"][vote_key] += 1
                arm_stats["votes"]["total"] += 1
            date_str = reply_date.get(vote.reply_id, "")
            bucket = daily.get((date_str, arm_id))
            if bucket is not None and vote_key:
                bucket[vote_key] += 1

        totals = {"routed": 0, "better": 0, "worse": 0, "same": 0, "votes_total": 0}
        for arm_stats in per_arm.values():
            v = arm_stats["votes"]
            arm_stats["better_rate"] = v["better"] / v["total"] if v["total"] else None
            arm_stats["worse_rate"] = v["worse"] / v["total"] if v["total"] else None
            arm_stats["net_score"] = (
                (v["better"] - v["worse"]) / v["total"] if v["total"] else None
            )
            totals["routed"] += arm_stats["routed_count"]
            totals["better"] += v["better"]
            totals["worse"] += v["worse"]
            totals["same"] += v["same"]
            totals["votes_total"] += v["total"]

        reason_counter: Counter = Counter()
        free_text_count = 0
        for item in feedback:
            for reason in item.reasons or []:
                reason_counter[reason] += 1
            if item.free_text:
                free_text_count += 1
        reason_ranking = [
            {"reason": reason, "count": count}
            for reason, count in reason_counter.most_common()
        ]

        daily_series = [daily[key] for key in sorted(daily.keys(), key=lambda k: (k[0], k[1]))]

        return {
            "experiment": ABTestService._experiment_to_dict(experiment),
            "days": days,
            "arms": list(per_arm.values()),
            "totals": totals,
            "daily": daily_series,
            "reason_ranking": reason_ranking,
            "feedback_count": len(feedback),
            "feedback_free_text_count": free_text_count,
        }

    @staticmethod
    async def list_feedback(
        experiment_id: int, limit: int = 200
    ) -> List[Dict[str, Any]]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ABFeedback, ABRoutedReply)
                .join(ABRoutedReply, ABFeedback.reply_id == ABRoutedReply.id)
                .where(ABRoutedReply.experiment_id == experiment_id)
                .order_by(ABFeedback.id.desc())
                .limit(limit)
            )
            rows = list(result.all())
        return [
            {
                "id": feedback.id,
                "reply_id": feedback.reply_id,
                "user_id": feedback.user_id,
                "reasons": feedback.reasons,
                "free_text": feedback.free_text,
                "created_at": feedback.created_at,
                "message_id": reply.message_id,
                "channel_id": reply.channel_id,
                "arm_id": reply.arm_id,
                "model_full_id": reply.model_full_id,
                "question_text": reply.question_text,
                "reply_text": reply.reply_text,
            }
            for feedback, reply in rows
        ]

    @staticmethod
    async def export_rows(experiment_id: int, days: int = 30) -> List[Dict[str, Any]]:
        loaded = await ABTestService._load_stats_rows(experiment_id, days)
        _, arms, replies, votes, feedback = loaded
        arm_label = {arm.id: arm.label for arm in arms}

        votes_by_reply: Dict[int, Dict[str, int]] = defaultdict(
            lambda: {"better": 0, "worse": 0, "same": 0}
        )
        vote_key_map = {1: "better", 2: "worse", 3: "same"}
        for vote in votes:
            vote_key = vote_key_map.get(vote.vote)
            if vote_key:
                votes_by_reply[vote.reply_id][vote_key] += 1

        feedback_by_reply: Dict[int, List[ABFeedback]] = defaultdict(list)
        for item in feedback:
            feedback_by_reply[item.reply_id].append(item)

        rows = []
        for reply in replies:
            vote_counts = votes_by_reply.get(reply.id, {"better": 0, "worse": 0, "same": 0})
            feedback_items = feedback_by_reply.get(reply.id, [])
            rows.append(
                {
                    "id": reply.id,
                    "message_id": reply.message_id,
                    "channel_id": reply.channel_id,
                    "guild_id": reply.guild_id,
                    "trigger_user_id": reply.trigger_user_id,
                    "arm_id": reply.arm_id,
                    "arm_label": arm_label.get(reply.arm_id, ""),
                    "model_full_id": reply.model_full_id,
                    "question_text": reply.question_text,
                    "reply_text": reply.reply_text,
                    "created_at": reply.created_at.isoformat() if reply.created_at else None,
                    "better": vote_counts["better"],
                    "worse": vote_counts["worse"],
                    "same": vote_counts["same"],
                    "feedback_reasons": ";".join(
                        reason
                        for item in feedback_items
                        for reason in item.reasons or []
                    ),
                    "feedback_texts": " | ".join(
                        item.free_text for item in feedback_items if item.free_text
                    ),
                }
            )
        return rows


ab_test_service = ABTestService()
