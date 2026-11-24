"""evalcore — framework-agnostic evaluation core (no web framework dependency)."""

from .assertions import ASSERTION_TYPES, evaluate_all, evaluate_assertion
from .calibration import (
    AdmissionPolicy,
    admit,
    calibration_metrics,
    cohens_kappa,
    find_disagreements,
    judge_identity,
    mean_pairwise_kappa,
)
from .compare import Comparison, compare_runs, gate
from .dataset import dataset_hash, load_and_validate, load_dataset, validate_dataset
from .manifest import RunManifest, validate_pair
from .models import (
    AgentResult,
    AssertionResult,
    AssertionSpec,
    Case,
    Dataset,
    Layer,
    SampleResult,
    SampleStatus,
    ToolCall,
)
from .runner import AgentAdapter, CallableAdapter, RunContext, execute_run, execute_sample, score_result
from .stats import (
    BootstrapPolicy,
    Decision,
    paired_cluster_bootstrap,
    repeated_run_stats,
    wilson_interval,
)
from .summary import summarize

__all__ = [
    "ASSERTION_TYPES", "AdmissionPolicy", "AgentAdapter", "AgentResult", "AssertionResult", "AssertionSpec",
    "BootstrapPolicy", "CallableAdapter", "Case", "Comparison", "Dataset", "Decision", "Layer", "RunContext",
    "RunManifest", "SampleResult", "SampleStatus", "ToolCall", "admit", "calibration_metrics", "cohens_kappa",
    "compare_runs", "dataset_hash", "evaluate_all", "evaluate_assertion", "execute_run", "execute_sample",
    "find_disagreements", "gate", "judge_identity", "load_and_validate", "load_dataset", "mean_pairwise_kappa",
    "paired_cluster_bootstrap", "repeated_run_stats", "score_result", "summarize", "validate_dataset",
    "validate_pair", "wilson_interval",
]
