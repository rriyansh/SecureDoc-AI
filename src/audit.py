"""Structured audit trail for compliance and debugging."""

import os
import json
import uuid
import threading
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path

from src.config import config
from src.logger import get_logger
from src.security import sanitize_dict

logger = get_logger(__name__)


class AuditEventType(Enum):
    """Types of audit events."""
    QUERY = "query"
    INGESTION = "ingestion"
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    PII_DETECTED = "pii_detected"
    INPUT_SANITIZED = "input_sanitized"
    CONFIG_CHANGE = "config_change"
    SECRET_ROTATION = "secret_rotation"
    EVALUATION = "evaluation"
    ADMIN_ACTION = "admin_action"
    ERROR = "error"


class AuditLevel(Enum):
    """Audit event severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Structured audit event."""
    event_id: str
    timestamp: str
    event_type: str
    level: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_id: Optional[str] = None
    resource: Optional[str] = None
    action: Optional[str] = None
    outcome: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return asdict(self)

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class AuditLogger:
    """Structured audit logger with file rotation."""

    def __init__(
        self,
        log_dir: str = "./audit",
        max_file_size: int = 100 * 1024 * 1024,  # 100MB
        max_files: int = 10,
        buffer_size: int = 100,
    ):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_file_size = max_file_size
        self.max_files = max_files
        self.buffer_size = buffer_size
        self._buffer: List[AuditEvent] = []
        self._buffer_lock = threading.Lock()
        self._current_file: Optional[Path] = None
        self._file_handle = None
        self._rotate_file()

    def _rotate_file(self) -> None:
        """Rotate to a new log file."""
        if self._file_handle:
            self._file_handle.close()
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        self._current_file = self.log_dir / f"audit_{timestamp}.jsonl"
        self._file_handle = open(self._current_file, "a", encoding="utf-8")
        self._cleanup_old_files()

    def _cleanup_old_files(self) -> None:
        """Remove old log files beyond max_files."""
        files = sorted(self.log_dir.glob("audit_*.jsonl"))
        while len(files) >= self.max_files:
            oldest = files.pop(0)
            try:
                oldest.unlink()
            except OSError:
                pass

    def _should_rotate(self) -> bool:
        """Check if current file should be rotated."""
        if not self._current_file:
            return True
        try:
            return self._current_file.stat().st_size >= self.max_file_size
        except OSError:
            return True

    def _flush_buffer(self) -> None:
        """Flush buffer to file."""
        with self._buffer_lock:
            if not self._buffer:
                return
            if self._should_rotate():
                self._rotate_file()
            for event in self._buffer:
                self._file_handle.write(event.to_json() + "\n")
            self._file_handle.flush()
            self._buffer.clear()

    def log(
        self,
        event_type: AuditEventType,
        level: AuditLevel = AuditLevel.INFO,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        outcome: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log an audit event."""
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.utcnow().isoformat() + "Z",
            event_type=event_type.value,
            level=level.value,
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            resource=resource,
            action=action,
            outcome=outcome,
            details=sanitize_dict(details or {}),
            metadata=metadata or {},
        )
        with self._buffer_lock:
            self._buffer.append(event)
            if len(self._buffer) >= self.buffer_size:
                self._flush_buffer()
        return event.event_id

    def log_query(
        self,
        user_id: str,
        question: str,
        answer: str,
        num_results: int,
        duration_ms: float,
        request_id: str,
        ip_address: Optional[str] = None,
        pii_detected: bool = False,
    ) -> str:
        """Log a query event."""
        return self.log(
            event_type=AuditEventType.QUERY,
            level=AuditLevel.INFO,
            user_id=user_id,
            request_id=request_id,
            ip_address=ip_address,
            resource="rag_query",
            action="query",
            outcome="success",
            details={
                "question": question[:200],
                "answer_length": len(answer),
                "num_results": num_results,
                "duration_ms": duration_ms,
                "pii_detected": pii_detected,
            },
        )

    def log_ingestion(
        self,
        user_id: str,
        num_documents: int,
        num_chunks: int,
        duration_ms: float,
        request_id: str,
        outcome: str = "success",
        error: Optional[str] = None,
    ) -> str:
        """Log an ingestion event."""
        return self.log(
            event_type=AuditEventType.INGESTION,
            level=AuditLevel.INFO if outcome == "success" else AuditLevel.ERROR,
            user_id=user_id,
            request_id=request_id,
            resource="document_ingestion",
            action="ingest",
            outcome=outcome,
            details={
                "num_documents": num_documents,
                "num_chunks": num_chunks,
                "duration_ms": duration_ms,
                "error": error,
            },
        )

    def log_auth(
        self,
        event_type: AuditEventType,
        user_id: Optional[str],
        method: str,
        outcome: str,
        request_id: str,
        ip_address: Optional[str] = None,
        error: Optional[str] = None,
    ) -> str:
        """Log an authentication event."""
        return self.log(
            event_type=event_type,
            level=AuditLevel.INFO if outcome == "success" else AuditLevel.WARNING,
            user_id=user_id,
            request_id=request_id,
            ip_address=ip_address,
            resource="authentication",
            action=method,
            outcome=outcome,
            details={
                "method": method,
                "error": error,
            },
        )

    def log_rate_limit(
        self,
        user_id: Optional[str],
        scope: str,
        key: str,
        request_id: str,
        ip_address: Optional[str] = None,
    ) -> str:
        """Log a rate limit event."""
        return self.log(
            event_type=AuditEventType.RATE_LIMIT_EXCEEDED,
            level=AuditLevel.WARNING,
            user_id=user_id,
            request_id=request_id,
            ip_address=ip_address,
            resource="rate_limiter",
            action="limit_exceeded",
            outcome="blocked",
            details={
                "scope": scope,
                "key": key[:8] + "...",
            },
        )

    def log_pii(
        self,
        user_id: Optional[str],
        pii_types: List[str],
        request_id: str,
        ip_address: Optional[str] = None,
        action_taken: str = "redacted",
    ) -> str:
        """Log a PII detection event."""
        return self.log(
            event_type=AuditEventType.PII_DETECTED,
            level=AuditLevel.WARNING,
            user_id=user_id,
            request_id=request_id,
            ip_address=ip_address,
            resource="security",
            action="pii_detection",
            outcome=action_taken,
            details={
                "pii_types": pii_types,
                "action_taken": action_taken,
            },
        )

    def log_admin_action(
        self,
        user_id: str,
        action: str,
        resource: str,
        request_id: str,
        ip_address: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Log an admin action."""
        return self.log(
            event_type=AuditEventType.ADMIN_ACTION,
            level=AuditLevel.INFO,
            user_id=user_id,
            request_id=request_id,
            ip_address=ip_address,
            resource=resource,
            action=action,
            outcome="success",
            details=details or {},
        )

    def log_error(
        self,
        error: Exception,
        user_id: Optional[str] = None,
        request_id: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> str:
        """Log an error event."""
        return self.log(
            event_type=AuditEventType.ERROR,
            level=AuditLevel.ERROR,
            user_id=user_id,
            request_id=request_id,
            ip_address=ip_address,
            resource=resource,
            action=action,
            outcome="error",
            details={
                "error_type": type(error).__name__,
                "error_message": str(error),
            },
        )

    def flush(self) -> None:
        """Flush any buffered events."""
        self._flush_buffer()

    def close(self) -> None:
        """Close the audit logger."""
        self._flush_buffer()
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None


audit_logger = AuditLogger()


def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance."""
    return audit_logger