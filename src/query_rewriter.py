"""Query rewriting and expansion for improved retrieval."""

import re
from typing import List, Dict, Set, Optional
from dataclasses import dataclass

from src.config import config
from src.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RewrittenQuery:
    """Result of query rewriting."""
    original: str
    rewritten: str
    expansions: List[str]
    intent: Optional[str] = None
    entities: List[str] = field(default_factory=list)


class QueryRewriter:
    """Rewrite and expand queries for better retrieval."""

    def __init__(self):
        self.synonyms = self._load_synonyms()
        self.abbreviations = self._load_abbreviations()
        self.stop_words = self._load_stop_words()

    def _load_synonyms(self) -> Dict[str, List[str]]:
        """Load domain-specific synonyms."""
        return {
            "policy": ["guideline", "rule", "regulation", "procedure", "standard"],
            "document": ["file", "record", "report", "paper", "text"],
            "security": ["protection", "safety", "defense", "safeguard"],
            "access": ["permission", "authorization", "entry", "admission"],
            "data": ["information", "records", "details", "facts"],
            "user": ["person", "individual", "account", "member"],
            "system": ["platform", "application", "software", "service"],
            "requirement": ["need", "necessity", "prerequisite", "condition"],
            "compliance": ["adherence", "conformity", "observance"],
            "incident": ["event", "occurrence", "breach", "issue"],
            "encryption": ["encoding", "cipher", "scrambling"],
            "authentication": ["verification", "validation", "confirmation"],
            "retention": ["storage", "keeping", "preservation"],
            "sharing": ["distribution", "disclosure", "transmission"],
            "approval": ["authorization", "consent", "permission"],
        }

    def _load_abbreviations(self) -> Dict[str, str]:
        """Load common abbreviations."""
        return {
            "mfa": "multi-factor authentication",
            "2fa": "two-factor authentication",
            "pii": "personally identifiable information",
            "gdpr": "general data protection regulation",
            "hipaa": "health insurance portability and accountability act",
            "soc": "service organization control",
            "iso": "international organization for standardization",
            "pci": "payment card industry",
            "dpo": "data protection officer",
            "ciso": "chief information security officer",
            "api": "application programming interface",
            "sdk": "software development kit",
            "ui": "user interface",
            "ux": "user experience",
            "db": "database",
            "ssl": "secure sockets layer",
            "tls": "transport layer security",
            "vpn": "virtual private network",
            "ssh": "secure shell",
            "jwt": "json web token",
            "oauth": "open authorization",
            "saml": "security assertion markup language",
            "rbac": "role-based access control",
            "abac": "attribute-based access control",
        }

    def _load_stop_words(self) -> Set[str]:
        """Load stop words to filter."""
        return {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
            "be", "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "can", "this", "that",
            "these", "those", "i", "you", "he", "she", "it", "we", "they",
            "me", "him", "her", "us", "them", "my", "your", "his", "its",
            "our", "their", "what", "which", "who", "whom", "whose", "where",
            "when", "why", "how", "all", "each", "few", "more", "most",
            "other", "some", "such", "no", "nor", "not", "only", "own",
            "same", "so", "than", "too", "very", "just", "now",
        }

    def expand_abbreviations(self, query: str) -> str:
        """Expand known abbreviations in query."""
        words = query.split()
        expanded = []
        for word in words:
            lower = word.lower().strip(".,!?;:")
            if lower in self.abbreviations:
                expanded.append(self.abbreviations[lower])
            else:
                expanded.append(word)
        return " ".join(expanded)

    def add_synonyms(self, query: str) -> List[str]:
        """Generate query variations with synonyms."""
        words = query.lower().split()
        variations = [query]

        for i, word in enumerate(words):
            if word in self.synonyms:
                for synonym in self.synonyms[word]:
                    new_words = words.copy()
                    new_words[i] = synonym
                    variations.append(" ".join(new_words))

        return variations[:5]  # Limit variations

    def extract_entities(self, query: str) -> List[str]:
        """Extract potential entities from query."""
        entities = []

        # Extract quoted phrases
        quoted = re.findall(r'"([^"]*)"', query)
        entities.extend(quoted)

        # Extract capitalized words (potential proper nouns)
        capitalized = re.findall(r'\b[A-Z][a-z]+\b', query)
        entities.extend(capitalized)

        # Extract technical terms (camelCase, snake_case, UPPER_CASE)
        technical = re.findall(r'\b[a-z]+(?:[A-Z][a-z]+)+\b|\b[A-Z_]{2,}\b', query)
        entities.extend(technical)

        return list(set(entities))

    def detect_intent(self, query: str) -> Optional[str]:
        """Detect query intent."""
        query_lower = query.lower()

        intent_patterns = {
            "definition": ["what is", "define", "definition of", "meaning of"],
            "procedure": ["how to", "steps to", "procedure for", "process for"],
            "policy": ["policy on", "policy for", "rule about", "guideline for"],
            "requirement": ["requirement for", "required to", "must i", "do i need to"],
            "permission": ["can i", "allowed to", "permission to", "authorized to"],
            "incident": ["incident", "breach", "violation", "report"],
            "retention": ["retention", "keep", "store", "how long"],
            "sharing": ["share", "send", "disclose", "external"],
            "encryption": ["encrypt", "encryption", "encrypted"],
            "access": ["access", "login", "permission", "credential"],
        }

        for intent, patterns in intent_patterns.items():
            for pattern in patterns:
                if pattern in query_lower:
                    return intent

        return None

    def rewrite(self, query: str) -> RewrittenQuery:
        """Rewrite query with expansions."""
        original = query.strip()

        # Expand abbreviations
        expanded = self.expand_abbreviations(original)

        # Generate synonym variations
        variations = self.add_synonyms(expanded)

        # Extract entities
        entities = self.extract_entities(original)

        # Detect intent
        intent = self.detect_intent(original)

        # Combine into rewritten query (use first variation with most terms)
        rewritten = max(variations, key=lambda v: len(v.split()))

        return RewrittenQuery(
            original=original,
            rewritten=rewritten,
            expansions=variations[1:],
            intent=intent,
            entities=entities,
        )

    def rewrite_for_retrieval(self, query: str) -> List[str]:
        """Generate multiple queries for retrieval."""
        result = self.rewrite(query)
        queries = [result.rewritten] + result.expansions

        # Add entity-focused queries
        for entity in result.entities:
            queries.append(f"{entity} {result.rewritten}")

        # Add intent-focused query if detected
        if result.intent:
            queries.append(f"{result.intent}: {result.rewritten}")

        # Deduplicate while preserving order
        seen = set()
        unique_queries = []
        for q in queries:
            if q not in seen:
                seen.add(q)
                unique_queries.append(q)

        return unique_queries[:5]


query_rewriter = QueryRewriter()