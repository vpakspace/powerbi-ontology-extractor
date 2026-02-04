"""
Tests for Collaborative Ontology Review module.

Tests review workflow and commenting functionality:
- Comment creation and management
- Review workflow state transitions
- Report generation
- Serialization/deserialization
"""

import json
import pytest
from datetime import datetime
from pathlib import Path

from powerbi_ontology.review import (
    OntologyReview,
    ReviewWorkflow,
    ReviewReport,
    ReviewComment,
    ReviewAction,
    ReviewStatus,
    CommentType,
    TargetType,
    create_review,
    load_review,
)
from powerbi_ontology.ontology_generator import (
    Ontology,
    OntologyEntity,
    OntologyProperty,
)


@pytest.fixture
def sample_ontology():
    """Create sample ontology for testing."""
    return Ontology(
        name="Test_Ontology",
        version="1.0",
        source="test.pbix",
        entities=[
            OntologyEntity(
                name="Customer",
                description="Customer entity",
                entity_type="dimension",
                properties=[
                    OntologyProperty(name="Id", data_type="Integer", required=True),
                    OntologyProperty(name="Name", data_type="String"),
                ],
                constraints=[],
            ),
        ],
        relationships=[],
        business_rules=[],
    )


@pytest.fixture
def review(sample_ontology):
    """Create sample review."""
    return create_review(sample_ontology)


@pytest.fixture
def review_with_comments(review):
    """Create review with some comments."""
    review.add_comment(
        author="alice",
        content="Customer entity looks good",
        target_type=TargetType.ENTITY,
        target_path="Customer",
        comment_type=CommentType.COMMENT,
    )
    review.add_comment(
        author="bob",
        content="Should Id be required?",
        target_type=TargetType.PROPERTY,
        target_path="Customer.Id",
        comment_type=CommentType.ISSUE,
    )
    return review


class TestOntologyReview:
    """Tests for OntologyReview class."""

    def test_create_review(self, sample_ontology):
        """Test creating a new review."""
        review = create_review(sample_ontology)

        assert review.ontology_name == "Test_Ontology"
        assert review.ontology_version == "1.0"
        assert review.status == ReviewStatus.DRAFT
        assert len(review.comments) == 0

    def test_add_comment(self, review):
        """Test adding a comment."""
        comment = review.add_comment(
            author="alice",
            content="Looks good",
            target_type=TargetType.ENTITY,
            target_path="Customer",
        )

        assert comment.author == "alice"
        assert comment.content == "Looks good"
        assert len(review.comments) == 1

    def test_add_comment_with_type(self, review):
        """Test adding a typed comment."""
        comment = review.add_comment(
            author="bob",
            content="This is an issue",
            target_type=TargetType.PROPERTY,
            target_path="Customer.Id",
            comment_type=CommentType.ISSUE,
        )

        assert comment.comment_type == CommentType.ISSUE

    def test_reply_to_comment(self, review):
        """Test replying to a comment."""
        comment = review.add_comment(
            author="alice",
            content="Original comment",
            target_type=TargetType.ENTITY,
            target_path="Customer",
        )

        reply = review.reply_to_comment(comment.id, "bob", "Reply to comment")

        assert reply is not None
        assert reply.author == "bob"
        assert len(comment.replies) == 1

    def test_reply_to_nonexistent_comment(self, review):
        """Test replying to nonexistent comment."""
        reply = review.reply_to_comment("nonexistent", "bob", "Reply")
        assert reply is None

    def test_resolve_comment(self, review):
        """Test resolving a comment."""
        comment = review.add_comment(
            author="alice",
            content="Issue to resolve",
            target_type=TargetType.ENTITY,
            target_path="Customer",
            comment_type=CommentType.ISSUE,
        )

        result = review.resolve_comment(comment.id, "bob")

        assert result is True
        assert comment.resolved is True
        assert comment.resolved_by == "bob"

    def test_resolve_nonexistent_comment(self, review):
        """Test resolving nonexistent comment."""
        result = review.resolve_comment("nonexistent", "bob")
        assert result is False

    def test_get_comments_for(self, review_with_comments):
        """Test getting comments for specific element."""
        comments = review_with_comments.get_comments_for("Customer")
        assert len(comments) == 1
        assert comments[0].author == "alice"

    def test_get_unresolved_comments(self, review_with_comments):
        """Test getting unresolved comments."""
        unresolved = review_with_comments.get_unresolved_comments()
        assert len(unresolved) == 2

        # Resolve one
        review_with_comments.resolve_comment(unresolved[0].id, "admin")
        unresolved = review_with_comments.get_unresolved_comments()
        assert len(unresolved) == 1

    def test_get_issues(self, review_with_comments):
        """Test getting issue comments."""
        issues = review_with_comments.get_issues()
        assert len(issues) == 1
        assert issues[0].comment_type == CommentType.ISSUE


class TestReviewSerialization:
    """Tests for review serialization."""

    def test_to_dict(self, review_with_comments):
        """Test converting review to dict."""
        data = review_with_comments.to_dict()

        assert data["ontology_name"] == "Test_Ontology"
        assert data["status"] == "draft"
        assert len(data["comments"]) == 2

    def test_from_dict(self, review_with_comments):
        """Test creating review from dict."""
        data = review_with_comments.to_dict()
        restored = OntologyReview.from_dict(data)

        assert restored.ontology_name == review_with_comments.ontology_name
        assert restored.status == review_with_comments.status
        assert len(restored.comments) == len(review_with_comments.comments)

    def test_save_and_load(self, review_with_comments, tmp_path):
        """Test saving and loading review."""
        path = tmp_path / "review.json"
        review_with_comments.save(str(path))

        loaded = load_review(str(path))

        assert loaded.ontology_name == review_with_comments.ontology_name
        assert len(loaded.comments) == len(review_with_comments.comments)

    def test_comment_to_dict(self, review):
        """Test comment serialization."""
        comment = review.add_comment(
            author="alice",
            content="Test",
            target_type=TargetType.ENTITY,
            target_path="Customer",
        )

        data = comment.to_dict()

        assert data["author"] == "alice"
        assert data["content"] == "Test"
        assert data["target_type"] == "entity"

    def test_comment_from_dict(self, review):
        """Test comment deserialization."""
        comment = review.add_comment(
            author="alice",
            content="Test",
            target_type=TargetType.ENTITY,
            target_path="Customer",
        )

        data = comment.to_dict()
        restored = ReviewComment.from_dict(data)

        assert restored.author == comment.author
        assert restored.content == comment.content


class TestReviewWorkflow:
    """Tests for ReviewWorkflow class."""

    def test_submit_for_review(self, review):
        """Test submitting for review."""
        workflow = ReviewWorkflow(review)
        result = workflow.submit_for_review("alice", ["bob", "carol"])

        assert result is True
        assert review.status == ReviewStatus.IN_REVIEW
        assert review.reviewers == ["bob", "carol"]

    def test_cannot_submit_from_in_review(self, review):
        """Test cannot submit when already in review."""
        workflow = ReviewWorkflow(review)
        workflow.submit_for_review("alice", ["bob"])

        result = workflow.submit_for_review("alice", ["carol"])
        assert result is False

    def test_approve(self, review):
        """Test approving review."""
        workflow = ReviewWorkflow(review)
        workflow.submit_for_review("alice", ["bob"])

        result = workflow.approve("bob", "Looks good")

        assert result is True
        assert review.status == ReviewStatus.APPROVED
        assert "bob" in review.approvers

    def test_approve_requires_reviewer(self, review):
        """Test only reviewer can approve."""
        workflow = ReviewWorkflow(review)
        workflow.submit_for_review("alice", ["bob"])

        result = workflow.approve("carol", "Approve")  # carol is not reviewer

        assert result is False
        assert review.status == ReviewStatus.IN_REVIEW

    def test_request_changes(self, review):
        """Test requesting changes."""
        workflow = ReviewWorkflow(review)
        workflow.submit_for_review("alice", ["bob"])

        result = workflow.request_changes("bob", "Please fix the Id type")

        assert result is True
        assert review.status == ReviewStatus.CHANGES_REQUESTED

    def test_resubmit_after_changes(self, review):
        """Test resubmitting after changes requested."""
        workflow = ReviewWorkflow(review)
        workflow.submit_for_review("alice", ["bob"])
        workflow.request_changes("bob", "Fix issues")

        result = workflow.resubmit("alice", "Fixed the issues")

        assert result is True
        assert review.status == ReviewStatus.IN_REVIEW

    def test_reject(self, review):
        """Test rejecting review."""
        workflow = ReviewWorkflow(review)
        workflow.submit_for_review("alice", ["bob"])

        result = workflow.reject("bob", "Does not meet requirements")

        assert result is True
        assert review.status == ReviewStatus.REJECTED

    def test_publish(self, review):
        """Test publishing approved review."""
        workflow = ReviewWorkflow(review)
        workflow.submit_for_review("alice", ["bob"])
        workflow.approve("bob")

        result = workflow.publish("admin")

        assert result is True
        assert review.status == ReviewStatus.PUBLISHED

    def test_cannot_publish_unapproved(self, review):
        """Test cannot publish unapproved review."""
        workflow = ReviewWorkflow(review)
        workflow.submit_for_review("alice", ["bob"])

        result = workflow.publish("admin")

        assert result is False
        assert review.status == ReviewStatus.IN_REVIEW

    def test_reset_to_draft(self, review):
        """Test resetting rejected review to draft."""
        workflow = ReviewWorkflow(review)
        workflow.submit_for_review("alice", ["bob"])
        workflow.reject("bob", "Rejected")

        result = workflow.reset_to_draft("alice")

        assert result is True
        assert review.status == ReviewStatus.DRAFT
        assert review.reviewers == []

    def test_history_recorded(self, review):
        """Test that actions are recorded in history."""
        workflow = ReviewWorkflow(review)
        workflow.submit_for_review("alice", ["bob"])
        workflow.approve("bob")

        assert len(review.history) == 2
        assert review.history[0].action == "submit"
        assert review.history[1].action == "approve"

    def test_can_transition(self, review):
        """Test can_transition method."""
        workflow = ReviewWorkflow(review)

        assert workflow.can_transition(ReviewStatus.IN_REVIEW) is True
        assert workflow.can_transition(ReviewStatus.APPROVED) is False


class TestReviewReport:
    """Tests for ReviewReport class."""

    def test_to_markdown(self, review_with_comments):
        """Test generating markdown report."""
        report = ReviewReport(review_with_comments)
        markdown = report.to_markdown()

        assert "# Review Report:" in markdown
        assert "Test_Ontology" in markdown
        assert "DRAFT" in markdown

    def test_report_includes_comments(self, review_with_comments):
        """Test report includes comments."""
        report = ReviewReport(review_with_comments)
        markdown = report.to_markdown()

        assert "alice" in markdown
        assert "bob" in markdown
        assert "Customer" in markdown

    def test_report_with_reviewers(self, review):
        """Test report shows reviewers."""
        workflow = ReviewWorkflow(review)
        workflow.submit_for_review("alice", ["bob", "carol"])

        report = ReviewReport(review)
        markdown = report.to_markdown()

        assert "## Reviewers" in markdown
        assert "bob" in markdown
        assert "carol" in markdown

    def test_report_with_history(self, review):
        """Test report shows history."""
        workflow = ReviewWorkflow(review)
        workflow.submit_for_review("alice", ["bob"])
        workflow.approve("bob")

        report = ReviewReport(review)
        markdown = report.to_markdown()

        assert "## History" in markdown
        assert "submit" in markdown
        assert "approve" in markdown


class TestReviewAction:
    """Tests for ReviewAction class."""

    def test_to_dict(self):
        """Test action serialization."""
        action = ReviewAction(
            id="test123",
            actor="alice",
            action="approve",
            from_status=ReviewStatus.IN_REVIEW,
            to_status=ReviewStatus.APPROVED,
            timestamp=datetime.now(),
            comment="Looks good",
        )

        data = action.to_dict()

        assert data["actor"] == "alice"
        assert data["action"] == "approve"
        assert data["from_status"] == "in_review"
        assert data["to_status"] == "approved"

    def test_from_dict(self):
        """Test action deserialization."""
        data = {
            "id": "test123",
            "actor": "alice",
            "action": "approve",
            "from_status": "in_review",
            "to_status": "approved",
            "timestamp": datetime.now().isoformat(),
            "comment": "Looks good",
        }

        action = ReviewAction.from_dict(data)

        assert action.actor == "alice"
        assert action.from_status == ReviewStatus.IN_REVIEW
