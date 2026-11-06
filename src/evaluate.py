"""RAGAS-based evaluation of retrieval and generation."""

from src.logger import get_logger

logger = get_logger(__name__)


def run_evaluation(dataset_path: str = "tests/eval_dataset.json"):
    """Run RAGAS evaluation against a dataset."""
    logger.info("Evaluation placeholder: dataset %s", dataset_path)
    print("Evaluation not yet implemented.")
