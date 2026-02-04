"""
Collaborative Ontology Review System.

Provides workflow for team review and approval of ontologies:
- Comments on entities, properties, relationships, rules
- Approval workflow: draft → review → approved → published
- Review history and audit trail
- Export/import review data

Use case: Team reviews ontology before deploying to production.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from powerbi_ontology.ontology_generator import Ontology

logger = logging.getLogger(__name__)


class ReviewStatus(Enum):
    """Status of ontology review."""
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"


class CommentType(Enum):
    """Type of review comment."""
    COMMENT = "comment"
    SUGGESTION = "suggestion"
    ISSUE = "issue"
    APPROVAL = "approval"
    REJECTION = "rejection"


class TargetType(Enum):
    """Type of element being commented on."""
    ONTOLOGY = "ontology"
    ENTITY = "entity"
    PROPERTY = "property"
    RELATIONSHIP = "relationship"
    RULE = "rule"


@dataclass
class ReviewComment:
    """A comment on an ontology element."""
    id: str
    author: str
    content: str
    comment_type: CommentType
    target_type: TargetType
    target_path: str  # e.g., "Customer.Email" or "rule:HighValue"
    created_at: datetime
    resolved: bool = False
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    replies: List["ReviewComment"] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "author": self.author,
            "content": self.content,
            "comment_type": self.comment_type.value,
            "target_type": self.target_type.value,
            "target_path": self.target_path,
            "created_at": self.created_at.isoformat(),
            "resolved": self.resolved,
            "resolved_by": self.resolved_by,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "replies": [r.to_dict() for r in self.replies],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReviewComment":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            author=data["author"],
            content=data["content"],
            comment_type=CommentType(data["comment_type"]),
            target_type=TargetType(data["target_type"]),
            target_path=data["target_path"],
            created_at=datetime.fromisoformat(data["created_at"]),
            resolved=data.get("resolved", False),
            resolved_by=data.get("resolved_by"),
            resolved_at=datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None,
            replies=[cls.from_dict(r) for r in data.get("replies", [])],
        )


@dataclass
class ReviewAction:
    """An action in the review workflow."""
    id: str
    actor: str
    action: str  # "submit", "approve", "reject", "request_changes", "publish"
    from_status: ReviewStatus
    to_status: ReviewStatus
    timestamp: datetime
    comment: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "actor": self.actor,
            "action": self.action,
            "from_status": self.from_status.value,
            "to_status": self.to_status.value,
            "timestamp": self.timestamp.isoformat(),
            "comment": self.comment,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReviewAction":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            actor=data["actor"],
            action=data["action"],
            from_status=ReviewStatus(data["from_status"]),
            to_status=ReviewStatus(data["to_status"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            comment=data.get("comment", ""),
        )


@dataclass
class OntologyReview:
    """
    Review state for an ontology.

    Tracks comments, approval status, and review history.
    """
    ontology_name: str
    ontology_version: str
    status: ReviewStatus = ReviewStatus.DRAFT
    comments: List[ReviewComment] = field(default_factory=list)
    history: List[ReviewAction] = field(default_factory=list)
    reviewers: List[str] = field(default_factory=list)
    approvers: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_comment(
        self,
        author: str,
        content: str,
        target_type: TargetType,
        target_path: str,
        comment_type: CommentType = CommentType.COMMENT,
    ) -> ReviewComment:
        """Add a comment to the review."""
        comment = ReviewComment(
            id=str(uuid4())[:8],
            author=author,
            content=content,
            comment_type=comment_type,
            target_type=target_type,
            target_path=target_path,
            created_at=datetime.now(),
        )
        self.comments.append(comment)
        self.updated_at = datetime.now()
        logger.info(f"Comment added by {author} on {target_path}")
        return comment

    def reply_to_comment(
        self,
        comment_id: str,
        author: str,
        content: str,
    ) -> Optional[ReviewComment]:
        """Reply to an existing comment."""
        parent = self._find_comment(comment_id)
        if not parent:
            logger.warning(f"Comment {comment_id} not found")
            return None

        reply = ReviewComment(
            id=str(uuid4())[:8],
            author=author,
            content=content,
            comment_type=CommentType.COMMENT,
            target_type=parent.target_type,
            target_path=parent.target_path,
            created_at=datetime.now(),
        )
        parent.replies.append(reply)
        self.updated_at = datetime.now()
        return reply

    def resolve_comment(self, comment_id: str, resolved_by: str) -> bool:
        """Mark a comment as resolved."""
        comment = self._find_comment(comment_id)
        if not comment:
            return False

        comment.resolved = True
        comment.resolved_by = resolved_by
        comment.resolved_at = datetime.now()
        self.updated_at = datetime.now()
        logger.info(f"Comment {comment_id} resolved by {resolved_by}")
        return True

    def _find_comment(self, comment_id: str) -> Optional[ReviewComment]:
        """Find a comment by ID."""
        for comment in self.comments:
            if comment.id == comment_id:
                return comment
            for reply in comment.replies:
                if reply.id == comment_id:
                    return reply
        return None

    def get_comments_for(self, target_path: str) -> List[ReviewComment]:
        """Get all comments for a specific element."""
        return [c for c in self.comments if c.target_path == target_path]

    def get_unresolved_comments(self) -> List[ReviewComment]:
        """Get all unresolved comments."""
        return [c for c in self.comments if not c.resolved]

    def get_issues(self) -> List[ReviewComment]:
        """Get all issue-type comments."""
        return [c for c in self.comments if c.comment_type == CommentType.ISSUE]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "ontology_name": self.ontology_name,
            "ontology_version": self.ontology_version,
            "status": self.status.value,
            "comments": [c.to_dict() for c in self.comments],
            "history": [h.to_dict() for h in self.history],
            "reviewers": self.reviewers,
            "approvers": self.approvers,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "OntologyReview":
        """Create from dictionary."""
        review = cls(
            ontology_name=data["ontology_name"],
            ontology_version=data["ontology_version"],
            status=ReviewStatus(data["status"]),
            comments=[ReviewComment.from_dict(c) for c in data.get("comments", [])],
            history=[ReviewAction.from_dict(h) for h in data.get("history", [])],
            reviewers=data.get("reviewers", []),
            approvers=data.get("approvers", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            metadata=data.get("metadata", {}),
        )
        return review

    def save(self, path: str):
        """Save review to file."""
        Path(path).write_text(json.dumps(self.to_dict(), indent=2))
        logger.info(f"Review saved to {path}")

    @classmethod
    def load(cls, path: str) -> "OntologyReview":
        """Load review from file."""
        data = json.loads(Path(path).read_text())
        return cls.from_dict(data)


class ReviewWorkflow:
    """
    Manages the review workflow for ontologies.

    State transitions:
        draft → in_review → approved → published
                         ↘ changes_requested → in_review
                         ↘ rejected
    """

    # Valid state transitions
    TRANSITIONS = {
        ReviewStatus.DRAFT: [ReviewStatus.IN_REVIEW],
        ReviewStatus.IN_REVIEW: [
            ReviewStatus.APPROVED,
            ReviewStatus.CHANGES_REQUESTED,
            ReviewStatus.REJECTED,
        ],
        ReviewStatus.CHANGES_REQUESTED: [ReviewStatus.IN_REVIEW],
        ReviewStatus.APPROVED: [ReviewStatus.PUBLISHED, ReviewStatus.IN_REVIEW],
        ReviewStatus.REJECTED: [ReviewStatus.DRAFT],
        ReviewStatus.PUBLISHED: [],  # Terminal state
    }

    def __init__(self, review: OntologyReview):
        """Initialize workflow with review."""
        self.review = review

    def can_transition(self, to_status: ReviewStatus) -> bool:
        """Check if transition is valid."""
        valid_transitions = self.TRANSITIONS.get(self.review.status, [])
        return to_status in valid_transitions

    def submit_for_review(self, actor: str, reviewers: List[str], comment: str = "") -> bool:
        """Submit ontology for review."""
        if not self.can_transition(ReviewStatus.IN_REVIEW):
            logger.warning(f"Cannot submit from {self.review.status}")
            return False

        self._record_action(actor, "submit", ReviewStatus.IN_REVIEW, comment)
        self.review.reviewers = reviewers
        self.review.status = ReviewStatus.IN_REVIEW
        logger.info(f"Ontology submitted for review by {actor}")
        return True

    def approve(self, actor: str, comment: str = "") -> bool:
        """Approve the ontology."""
        if not self.can_transition(ReviewStatus.APPROVED):
            logger.warning(f"Cannot approve from {self.review.status}")
            return False

        if actor not in self.review.reviewers:
            logger.warning(f"{actor} is not a reviewer")
            return False

        self._record_action(actor, "approve", ReviewStatus.APPROVED, comment)
        self.review.approvers.append(actor)
        self.review.status = ReviewStatus.APPROVED

        # Add approval comment
        self.review.add_comment(
            author=actor,
            content=comment or "Approved",
            target_type=TargetType.ONTOLOGY,
            target_path="",
            comment_type=CommentType.APPROVAL,
        )

        logger.info(f"Ontology approved by {actor}")
        return True

    def request_changes(self, actor: str, comment: str) -> bool:
        """Request changes to the ontology."""
        if not self.can_transition(ReviewStatus.CHANGES_REQUESTED):
            logger.warning(f"Cannot request changes from {self.review.status}")
            return False

        if actor not in self.review.reviewers:
            logger.warning(f"{actor} is not a reviewer")
            return False

        self._record_action(actor, "request_changes", ReviewStatus.CHANGES_REQUESTED, comment)
        self.review.status = ReviewStatus.CHANGES_REQUESTED

        # Add comment with requested changes
        self.review.add_comment(
            author=actor,
            content=comment,
            target_type=TargetType.ONTOLOGY,
            target_path="",
            comment_type=CommentType.ISSUE,
        )

        logger.info(f"Changes requested by {actor}")
        return True

    def reject(self, actor: str, comment: str) -> bool:
        """Reject the ontology."""
        if not self.can_transition(ReviewStatus.REJECTED):
            logger.warning(f"Cannot reject from {self.review.status}")
            return False

        if actor not in self.review.reviewers:
            logger.warning(f"{actor} is not a reviewer")
            return False

        self._record_action(actor, "reject", ReviewStatus.REJECTED, comment)
        self.review.status = ReviewStatus.REJECTED

        # Add rejection comment
        self.review.add_comment(
            author=actor,
            content=comment,
            target_type=TargetType.ONTOLOGY,
            target_path="",
            comment_type=CommentType.REJECTION,
        )

        logger.info(f"Ontology rejected by {actor}")
        return True

    def resubmit(self, actor: str, comment: str = "") -> bool:
        """Resubmit after changes requested."""
        if not self.can_transition(ReviewStatus.IN_REVIEW):
            logger.warning(f"Cannot resubmit from {self.review.status}")
            return False

        self._record_action(actor, "resubmit", ReviewStatus.IN_REVIEW, comment)
        self.review.status = ReviewStatus.IN_REVIEW
        logger.info(f"Ontology resubmitted by {actor}")
        return True

    def publish(self, actor: str, comment: str = "") -> bool:
        """Publish the approved ontology."""
        if not self.can_transition(ReviewStatus.PUBLISHED):
            logger.warning(f"Cannot publish from {self.review.status}")
            return False

        self._record_action(actor, "publish", ReviewStatus.PUBLISHED, comment)
        self.review.status = ReviewStatus.PUBLISHED
        logger.info(f"Ontology published by {actor}")
        return True

    def reset_to_draft(self, actor: str, comment: str = "") -> bool:
        """Reset rejected ontology to draft."""
        if self.review.status != ReviewStatus.REJECTED:
            logger.warning("Can only reset from rejected state")
            return False

        self._record_action(actor, "reset", ReviewStatus.DRAFT, comment)
        self.review.status = ReviewStatus.DRAFT
        self.review.reviewers = []
        self.review.approvers = []
        logger.info(f"Ontology reset to draft by {actor}")
        return True

    def _record_action(self, actor: str, action: str, to_status: ReviewStatus, comment: str):
        """Record an action in the history."""
        review_action = ReviewAction(
            id=str(uuid4())[:8],
            actor=actor,
            action=action,
            from_status=self.review.status,
            to_status=to_status,
            timestamp=datetime.now(),
            comment=comment,
        )
        self.review.history.append(review_action)
        self.review.updated_at = datetime.now()


class ReviewReport:
    """Generate reports from review data."""

    def __init__(self, review: OntologyReview):
        """Initialize with review."""
        self.review = review

    def to_markdown(self) -> str:
        """Generate markdown report."""
        lines = [
            f"# Review Report: {self.review.ontology_name}",
            "",
            f"**Version:** {self.review.ontology_version}",
            f"**Status:** {self.review.status.value.upper()}",
            f"**Created:** {self.review.created_at.strftime('%Y-%m-%d %H:%M')}",
            f"**Updated:** {self.review.updated_at.strftime('%Y-%m-%d %H:%M')}",
            "",
        ]

        # Reviewers
        if self.review.reviewers:
            lines.append("## Reviewers")
            lines.append("")
            for reviewer in self.review.reviewers:
                status = "✅" if reviewer in self.review.approvers else "⏳"
                lines.append(f"- {status} {reviewer}")
            lines.append("")

        # Summary
        unresolved = self.review.get_unresolved_comments()
        issues = self.review.get_issues()

        lines.append("## Summary")
        lines.append("")
        lines.append(f"- Total comments: {len(self.review.comments)}")
        lines.append(f"- Unresolved: {len(unresolved)}")
        lines.append(f"- Issues: {len([i for i in issues if not i.resolved])}")
        lines.append("")

        # Comments by target
        if self.review.comments:
            lines.append("## Comments")
            lines.append("")

            # Group by target
            by_target: Dict[str, List[ReviewComment]] = {}
            for c in self.review.comments:
                key = c.target_path or "(ontology)"
                if key not in by_target:
                    by_target[key] = []
                by_target[key].append(c)

            for target, comments in by_target.items():
                lines.append(f"### {target}")
                lines.append("")
                for c in comments:
                    status = "✅" if c.resolved else "⬜"
                    icon = self._comment_icon(c.comment_type)
                    lines.append(f"{status} {icon} **{c.author}**: {c.content}")
                    if c.replies:
                        for r in c.replies:
                            lines.append(f"  - **{r.author}**: {r.content}")
                lines.append("")

        # History
        if self.review.history:
            lines.append("## History")
            lines.append("")
            lines.append("| Time | Actor | Action | Status |")
            lines.append("|------|-------|--------|--------|")
            for h in self.review.history:
                time = h.timestamp.strftime("%Y-%m-%d %H:%M")
                lines.append(f"| {time} | {h.actor} | {h.action} | {h.to_status.value} |")
            lines.append("")

        return "\n".join(lines)

    def _comment_icon(self, comment_type: CommentType) -> str:
        """Get icon for comment type."""
        icons = {
            CommentType.COMMENT: "💬",
            CommentType.SUGGESTION: "💡",
            CommentType.ISSUE: "⚠️",
            CommentType.APPROVAL: "✅",
            CommentType.REJECTION: "❌",
        }
        return icons.get(comment_type, "💬")


def create_review(ontology: Ontology) -> OntologyReview:
    """Create a new review for an ontology."""
    return OntologyReview(
        ontology_name=ontology.name,
        ontology_version=ontology.version,
    )


def load_review(path: str) -> OntologyReview:
    """Load review from file."""
    return OntologyReview.load(path)
