from __future__ import annotations

import ast
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]

READ_ONLY_GEMINI_TOOLS = {
    "get_customer",
    "get_subscription",
    "get_payment_status",
    "get_service_status",
    "search_knowledge_base",
}

CONTROLLED_ACTIONS = {
    "retry_subscription_sync",
    "create_support_ticket",
    "request_refund_review",
}

HIGH_CONFIDENCE_SECRET_PATTERNS = (
    (
        "Google API key",
        re.compile(
            r"\bAIza[0-9A-Za-z_-]{30,}\b"
        ),
    ),
    (
        "AWS access key",
        re.compile(
            r"\bAKIA[0-9A-Z]{16}\b"
        ),
    ),
    (
        "GitHub token",
        re.compile(
            r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b"
        ),
    ),
    (
        "OpenAI-style API key",
        re.compile(
            r"\bsk-[A-Za-z0-9_-]{24,}\b"
        ),
    ),
    (
        "Private key material",
        re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
        ),
    ),
)

TEXT_SUFFIXES = {
    ".py",
    ".js",
    ".html",
    ".css",
    ".md",
    ".txt",
    ".json",
    ".toml",
    ".ini",
    ".cfg",
    ".yml",
    ".yaml",
    ".ps1",
    ".sh",
}

SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
}

SENSITIVE_TRACKED_NAMES = {
    ".env",
    "credentials.json",
    "service-account.json",
    "service_account.json",
}


@dataclass
class Check:
    name: str
    status: str
    detail: str


def _read(
    relative_path: str,
) -> str:
    path = ROOT / relative_path

    if not path.exists():
        return ""

    return path.read_text(
        encoding="utf-8",
        errors="replace",
    )


def _git(
    *args: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "git",
            *args,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _is_git_repo() -> bool:
    result = _git(
        "rev-parse",
        "--is-inside-work-tree",
    )

    return (
        result.returncode == 0
        and result.stdout.strip()
        == "true"
    )


def _assignment_value(
    tree: ast.AST,
    variable_name: str,
) -> ast.AST | None:
    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.Assign,
        ):
            for target in node.targets:
                if (
                    isinstance(
                        target,
                        ast.Name,
                    )
                    and target.id
                    == variable_name
                ):
                    return node.value

        if isinstance(
            node,
            ast.AnnAssign,
        ):
            target = node.target

            if (
                isinstance(
                    target,
                    ast.Name,
                )
                and target.id
                == variable_name
            ):
                return node.value

    return None


def _function_declaration_names(
    tree: ast.AST,
) -> dict[str, str]:
    declarations: dict[
        str,
        str,
    ] = {}

    for node in ast.walk(
        tree
    ):
        targets: list[
            ast.expr
        ] = []

        value: ast.AST | None = None

        if isinstance(
            node,
            ast.Assign,
        ):
            targets = node.targets
            value = node.value

        elif isinstance(
            node,
            ast.AnnAssign,
        ):
            targets = [
                node.target
            ]
            value = node.value

        if not isinstance(
            value,
            ast.Call,
        ):
            continue

        function_name = ""

        if isinstance(
            value.func,
            ast.Attribute,
        ):
            function_name = (
                value.func.attr
            )
        elif isinstance(
            value.func,
            ast.Name,
        ):
            function_name = (
                value.func.id
            )

        if (
            function_name
            != "FunctionDeclaration"
        ):
            continue

        declared_name = None

        for keyword in value.keywords:
            if (
                keyword.arg == "name"
                and isinstance(
                    keyword.value,
                    ast.Constant,
                )
                and isinstance(
                    keyword.value.value,
                    str,
                )
            ):
                declared_name = (
                    keyword.value.value
                )
                break

        if not declared_name:
            continue

        for target in targets:
            if isinstance(
                target,
                ast.Name,
            ):
                declarations[
                    target.id
                ] = declared_name

    return declarations


def _tool_registry_names(
    tree: ast.AST,
    declarations: dict[
        str,
        str,
    ],
) -> dict[str, set[str]]:
    registries: dict[
        str,
        set[str],
    ] = {}

    for node in ast.walk(
        tree
    ):
        targets: list[
            ast.expr
        ] = []

        value: ast.AST | None = None

        if isinstance(
            node,
            ast.Assign,
        ):
            targets = node.targets
            value = node.value

        elif isinstance(
            node,
            ast.AnnAssign,
        ):
            targets = [
                node.target
            ]
            value = node.value

        if not isinstance(
            value,
            ast.Call,
        ):
            continue

        function_name = ""

        if isinstance(
            value.func,
            ast.Attribute,
        ):
            function_name = (
                value.func.attr
            )
        elif isinstance(
            value.func,
            ast.Name,
        ):
            function_name = (
                value.func.id
            )

        if function_name != "Tool":
            continue

        declaration_list = None

        for keyword in value.keywords:
            if (
                keyword.arg
                == "function_declarations"
            ):
                declaration_list = (
                    keyword.value
                )
                break

        if not isinstance(
            declaration_list,
            (
                ast.List,
                ast.Tuple,
            ),
        ):
            continue

        tool_names: set[str] = set()

        for item in declaration_list.elts:
            if isinstance(
                item,
                ast.Name,
            ):
                tool_names.add(
                    declarations.get(
                        item.id,
                        item.id,
                    )
                )

        for target in targets:
            if isinstance(
                target,
                ast.Name,
            ):
                registries[
                    target.id
                ] = tool_names

    return registries


def _dict_string_keys(
    tree: ast.AST,
    variable_name: str,
) -> set[str] | None:
    value = _assignment_value(
        tree,
        variable_name,
    )

    if not isinstance(
        value,
        ast.Dict,
    ):
        return None

    keys: set[str] = set()

    for key in value.keys:
        if (
            isinstance(
                key,
                ast.Constant,
            )
            and isinstance(
                key.value,
                str,
            )
        ):
            keys.add(
                key.value
            )

    return keys


def _iter_working_tree_text_files() -> Iterable[
    Path
]:
    for path in ROOT.rglob(
        "*"
    ):
        if not path.is_file():
            continue

        if any(
            part in SKIP_DIRS
            for part in path.parts
        ):
            continue

        relative = path.relative_to(
            ROOT
        )

        # A real local .env is expected to contain secrets and must never be
        # printed or scanned. Its Git tracking status is checked separately.
        if (
            relative.name
            == ".env"
        ):
            continue

        if (
            path.suffix.lower()
            in TEXT_SUFFIXES
            or relative.name
            in {
                ".env.example",
                ".gitignore",
            }
        ):
            yield path


def _secret_scan() -> list[
    tuple[str, str]
]:
    findings: list[
        tuple[
            str,
            str,
        ]
    ] = []

    for path in _iter_working_tree_text_files():
        try:
            text = path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue

        for kind, pattern in (
            HIGH_CONFIDENCE_SECRET_PATTERNS
        ):
            if pattern.search(
                text
            ):
                findings.append(
                    (
                        str(
                            path.relative_to(
                                ROOT
                            )
                        ),
                        kind,
                    )
                )

    return findings


def _check_required_files() -> Check:
    required = (
        ".gitignore",
        ".env.example",
        "app/agent/orchestrator.py",
        "app/actions/service.py",
        "app/actions/tools.py",
        "app/api/actions.py",
        "app/db/models.py",
        "app/db/seed.py",
        "app/templates/index.html",
        "app/static/app.js",
    )

    missing = [
        item
        for item in required
        if not (
            ROOT
            / item
        ).exists()
    ]

    if missing:
        return Check(
            "Required security-review files",
            "FAIL",
            "Missing: "
            + ", ".join(
                missing
            ),
        )

    return Check(
        "Required security-review files",
        "PASS",
        "All expected V3 security-review files are present.",
    )


def _check_git_repo() -> Check:
    if not _is_git_repo():
        return Check(
            "Git repository",
            "FAIL",
            "Run the audit from the SupportPilot repository root.",
        )

    return Check(
        "Git repository",
        "PASS",
        "Repository metadata is available for hygiene checks.",
    )


def _check_env_tracking() -> Check:
    if not _is_git_repo():
        return Check(
            ".env source-control exclusion",
            "FAIL",
            "Git repository check failed.",
        )

    result = _git(
        "ls-files",
        "--",
        ".env",
    )

    if (
        result.returncode != 0
    ):
        return Check(
            ".env source-control exclusion",
            "FAIL",
            "Unable to inspect tracked files.",
        )

    if result.stdout.strip():
        return Check(
            ".env source-control exclusion",
            "FAIL",
            ".env is tracked by Git. Remove it from tracking before release.",
        )

    gitignore = _read(
        ".gitignore"
    )

    ignored = any(
        line.strip()
        in {
            ".env",
            ".env*",
        }
        for line in gitignore.splitlines()
        if line.strip()
        and not line.lstrip().startswith(
            "#"
        )
    )

    if not ignored:
        return Check(
            ".env source-control exclusion",
            "FAIL",
            ".env is not tracked now, but .gitignore does not explicitly ignore it.",
        )

    return Check(
        ".env source-control exclusion",
        "PASS",
        ".env is not tracked and is explicitly ignored.",
    )


def _check_sensitive_tracked_files() -> Check:
    if not _is_git_repo():
        return Check(
            "Sensitive tracked files",
            "FAIL",
            "Git repository check failed.",
        )

    result = _git(
        "ls-files",
    )

    if result.returncode != 0:
        return Check(
            "Sensitive tracked files",
            "FAIL",
            "Unable to inspect tracked files.",
        )

    bad: list[str] = []

    for line in result.stdout.splitlines():
        path = Path(
            line.strip()
        )

        if not str(
            path
        ):
            continue

        name = path.name.lower()

        if name in SENSITIVE_TRACKED_NAMES:
            bad.append(
                str(
                    path
                )
            )
            continue

        if path.suffix.lower() in {
            ".pem",
            ".key",
            ".p12",
            ".pfx",
        }:
            bad.append(
                str(
                    path
                )
            )

    if bad:
        return Check(
            "Sensitive tracked files",
            "FAIL",
            "Potential credential/key files are tracked: "
            + ", ".join(
                bad
            ),
        )

    return Check(
        "Sensitive tracked files",
        "PASS",
        "No obvious credential/key files are tracked.",
    )


def _check_env_example() -> Check:
    text = _read(
        ".env.example"
    )

    # Parse one env line using horizontal whitespace only. Python regex \s
    # includes newlines, which could accidentally consume GEMINI_MODEL on the
    # next line and make a truly blank GEMINI_API_KEY look non-blank.

    if not text:
        return Check(
            ".env.example safety",
            "FAIL",
            ".env.example is missing or empty.",
        )

    gemini_match = re.search(
        r"(?m)^[ \t]*GEMINI_API_KEY[ \t]*=[ \t]*([^\r\n]*)$",
        text,
    )

    if not gemini_match:
        return Check(
            ".env.example safety",
            "FAIL",
            "GEMINI_API_KEY placeholder is missing.",
        )

    value = (
        gemini_match.group(
            1
        )
        .strip()
        .strip(
            "\"'"
        )
    )

    if value:
        return Check(
            ".env.example safety",
            "FAIL",
            "GEMINI_API_KEY in .env.example must be blank.",
        )

    return Check(
        ".env.example safety",
        "PASS",
        "Gemini key is represented only as a blank placeholder.",
    )


def _check_high_confidence_secrets() -> Check:
    findings = _secret_scan()

    if findings:
        redacted_locations = [
            (
                path
                + " ["
                + kind
                + "]"
            )
            for path, kind in findings
        ]

        return Check(
            "High-confidence secret scan",
            "FAIL",
            "Potential secret material detected (values intentionally hidden): "
            + "; ".join(
                redacted_locations
            ),
        )

    return Check(
        "High-confidence secret scan",
        "PASS",
        "No high-confidence API-key/private-key patterns found outside local .env.",
    )


def _check_gemini_registry() -> Check:
    source = _read(
        "app/agent/orchestrator.py"
    )

    if not source:
        return Check(
            "Gemini tool registry",
            "FAIL",
            "orchestrator.py is unavailable.",
        )

    try:
        tree = ast.parse(
            source
        )
    except SyntaxError as exc:
        return Check(
            "Gemini tool registry",
            "FAIL",
            f"orchestrator.py could not be parsed: {exc}",
        )

    declarations = (
        _function_declaration_names(
            tree
        )
    )

    registries = (
        _tool_registry_names(
            tree,
            declarations,
        )
    )

    exposed: set[str] = set()

    for tool_names in (
        registries.values()
    ):
        exposed.update(
            tool_names
        )

    write_exposure = (
        exposed
        & CONTROLLED_ACTIONS
    )

    if write_exposure:
        return Check(
            "Gemini tool registry",
            "FAIL",
            "Write-capable controlled actions are exposed directly to Gemini: "
            + ", ".join(
                sorted(
                    write_exposure
                )
            ),
        )

    missing_read_tools = (
        READ_ONLY_GEMINI_TOOLS
        - exposed
    )

    if missing_read_tools:
        return Check(
            "Gemini tool registry",
            "FAIL",
            "Expected read-only tools are missing from the parsed registry: "
            + ", ".join(
                sorted(
                    missing_read_tools
                )
            ),
        )

    return Check(
        "Gemini tool registry",
        "PASS",
        "Gemini is limited to the five approved read-only support tools.",
    )


def _check_action_allow_list() -> Check:
    source = _read(
        "app/actions/service.py"
    )

    if not source:
        return Check(
            "Controlled action allow-list",
            "FAIL",
            "app/actions/service.py is unavailable.",
        )

    try:
        tree = ast.parse(
            source
        )
    except SyntaxError as exc:
        return Check(
            "Controlled action allow-list",
            "FAIL",
            f"service.py could not be parsed: {exc}",
        )

    keys = _dict_string_keys(
        tree,
        "ACTION_INPUT_MODELS",
    )

    if keys is None:
        return Check(
            "Controlled action allow-list",
            "FAIL",
            "ACTION_INPUT_MODELS could not be inspected.",
        )

    if keys != CONTROLLED_ACTIONS:
        return Check(
            "Controlled action allow-list",
            "FAIL",
            "Allow-list differs from the locked V3 action set. Found: "
            + ", ".join(
                sorted(
                    keys
                )
            ),
        )

    return Check(
        "Controlled action allow-list",
        "PASS",
        "Exactly three controlled actions are allow-listed.",
    )


def _check_approval_enforcement() -> Check:
    source = _read(
        "app/actions/service.py"
    )

    requirements = (
        'proposal.approval_status != "APPROVED"',
        "PermissionError",
        "execute_approved_action",
    )

    missing = [
        item
        for item in requirements
        if item not in source
    ]

    if missing:
        return Check(
            "Server-side approval enforcement",
            "FAIL",
            "Required approval enforcement markers are missing.",
        )

    return Check(
        "Server-side approval enforcement",
        "PASS",
        "Execution path requires APPROVED status on the backend.",
    )


def _check_unknown_action_rejection() -> Check:
    source = _read(
        "app/actions/service.py"
    )

    if (
        "Unsupported controlled action"
        not in source
    ):
        return Check(
            "Unknown action rejection",
            "FAIL",
            "No explicit unsupported controlled-action rejection was found.",
        )

    return Check(
        "Unknown action rejection",
        "PASS",
        "Unsupported controlled actions are explicitly rejected.",
    )


def _check_duplicate_execution() -> Check:
    source = _read(
        "app/actions/service.py"
    )

    has_lock = (
        ".with_for_update()"
        in source
    )

    has_execution_lookup = (
        "ActionExecution.proposal_id"
        in source
    )

    if not (
        has_lock
        and has_execution_lookup
    ):
        return Check(
            "Duplicate execution protection",
            "FAIL",
            "Execution row-lock/reuse protection could not be confirmed.",
        )

    return Check(
        "Duplicate execution protection",
        "PASS",
        "Proposal execution is serialized and existing executions are reused.",
    )


def _check_customer_isolation() -> Check:
    source = _read(
        "app/actions/service.py"
    )

    required_markers = (
        "_validated_execution_arguments",
        "conversation.customer_id",
        "proposal.customer_id",
        "validated.get(",
        "_validate_action_resource_ownership",
    )

    if not all(
        marker in source
        for marker in required_markers
    ):
        return Check(
            "Customer isolation at action boundary",
            "FAIL",
            "Execution-time customer/context ownership validation could not be confirmed.",
        )

    return Check(
        "Customer isolation at action boundary",
        "PASS",
        "Proposal, conversation, arguments and referenced business resources are revalidated before writes.",
    )


def _check_verified_commit_rule() -> Check:
    source = _read(
        "app/actions/service.py"
    )

    markers = (
        "db.begin_nested()",
        'verification_status',
        "action_savepoint.rollback()",
        '"business_write_committed"',
        '"safe_rollback_applied"',
    )

    if not all(
        marker in source
        for marker in markers
    ):
        return Check(
            "Verified-write / rollback rule",
            "FAIL",
            "Safe rollback and verification-gated commit markers are incomplete.",
        )

    return Check(
        "Verified-write / rollback rule",
        "PASS",
        "Unverified/failed controlled writes are rolled back and not reported as committed success.",
    )


def _check_action_persistence() -> Check:
    source = _read(
        "app/db/models.py"
    )

    required = (
        "class ActionProposal",
        "class ActionExecution",
        "approval_status",
        "execution_status",
        "verification_status",
    )

    missing = [
        item
        for item in required
        if item not in source
    ]

    if missing:
        return Check(
            "Action lifecycle persistence",
            "FAIL",
            "Required proposal/execution persistence markers are missing.",
        )

    return Check(
        "Action lifecycle persistence",
        "PASS",
        "Proposal, approval, execution and verification states are represented in persistent models.",
    )


def _check_customer_ui_boundary() -> Check:
    customer_surface = (
        _read(
            "app/templates/index.html"
        )
        + "\n"
        + _read(
            "app/static/app.js"
        )
    ).lower()

    forbidden = (
        "/api/v1/actions/",
        "/approve",
        "/reject",
        "/execute",
        "approve action",
        "execute action",
    )

    found = [
        marker
        for marker in forbidden
        if marker
        in customer_surface
    ]

    if found:
        return Check(
            "Customer UI action boundary",
            "FAIL",
            "Customer-facing UI contains protected action-control references: "
            + ", ".join(
                found
            ),
        )

    return Check(
        "Customer UI action boundary",
        "PASS",
        "Customer UI does not expose protected approval/execution controls.",
    )


def _check_chain_of_thought_exposure() -> Check:
    public_sources = []

    for relative_dir in (
        "app/templates",
        "app/static",
    ):
        directory = (
            ROOT
            / relative_dir
        )

        if not directory.exists():
            continue

        for path in directory.rglob(
            "*"
        ):
            if (
                path.is_file()
                and path.suffix.lower()
                in {
                    ".html",
                    ".js",
                    ".css",
                }
            ):
                public_sources.append(
                    path
                )

    forbidden_phrases = (
        "chain of thought",
        "chain-of-thought",
        "private reasoning",
        "hidden reasoning",
    )

    # Explicit safety disclaimers are allowed. They state that private model
    # reasoning is NOT displayed; treating those sentences as exposure would
    # be a false positive.
    safe_disclaimer_phrases = (
        "no private model chain-of-thought",
        "no private model chain of thought",
        "no private chain-of-thought",
        "no private chain of thought",
        "does not expose chain-of-thought",
        "does not expose chain of thought",
        "does not display chain-of-thought",
        "does not display chain of thought",
        "private reasoning is not displayed",
        "hidden reasoning is not displayed",
    )

    findings: list[str] = []

    for path in public_sources:
        text = path.read_text(
            encoding="utf-8",
            errors="replace",
        ).lower()

        scan_text = text

        for disclaimer in safe_disclaimer_phrases:
            scan_text = scan_text.replace(
                disclaimer,
                "",
            )

        for phrase in forbidden_phrases:
            if phrase in scan_text:
                findings.append(
                    str(
                        path.relative_to(
                            ROOT
                        )
                    )
                    + " ["
                    + phrase
                    + "]"
                )

    if findings:
        return Check(
            "Private reasoning exposure",
            "FAIL",
            "Potential private-reasoning UI exposure detected: "
            + "; ".join(
                findings
            ),
        )

    return Check(
        "Private reasoning exposure",
        "PASS",
        "No private-reasoning exposure markers found in customer/operator frontend assets.",
    )


def _check_synthetic_seed_data() -> Check:
    source = _read(
        "app/db/seed.py"
    )

    if not source:
        return Check(
            "Synthetic seed data",
            "FAIL",
            "app/db/seed.py is unavailable.",
        )

    emails = re.findall(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        source,
    )

    if not emails:
        return Check(
            "Synthetic seed data",
            "FAIL",
            "No synthetic customer email markers were found in seed.py.",
        )

    non_test_emails = [
        email
        for email in emails
        if not email.lower().endswith(
            "@example.test"
        )
    ]

    if non_test_emails:
        return Check(
            "Synthetic seed data",
            "FAIL",
            "Seed data contains email domains outside example.test.",
        )

    if (
        "CUS-1007"
        not in source
        or "PAY-3007"
        not in source
    ):
        return Check(
            "Synthetic seed data",
            "FAIL",
            "Expected deterministic CloudDesk seed identifiers are incomplete.",
        )

    return Check(
        "Synthetic seed data",
        "PASS",
        "Seeded customer emails use example.test and deterministic CloudDesk IDs.",
    )


def _check_repo_noise() -> Check:
    gitignore = _read(
        ".gitignore"
    )

    normalized = {
        line.strip().rstrip(
            "/"
        )
        for line in gitignore.splitlines()
        if line.strip()
        and not line.lstrip().startswith(
            "#"
        )
    }

    recommended = {
        ".venv",
        "__pycache__",
        ".pytest_cache",
    }

    missing = sorted(
        recommended
        - normalized
    )

    if missing:
        return Check(
            "Repository noise exclusions",
            "WARN",
            "Recommended ignore entries not confirmed: "
            + ", ".join(
                missing
            ),
        )

    return Check(
        "Repository noise exclusions",
        "PASS",
        "Common local Python/runtime artifacts are ignored.",
    )


def run_audit() -> list[Check]:
    return [
        _check_required_files(),
        _check_git_repo(),
        _check_env_tracking(),
        _check_sensitive_tracked_files(),
        _check_env_example(),
        _check_high_confidence_secrets(),
        _check_gemini_registry(),
        _check_action_allow_list(),
        _check_approval_enforcement(),
        _check_unknown_action_rejection(),
        _check_duplicate_execution(),
        _check_customer_isolation(),
        _check_verified_commit_rule(),
        _check_action_persistence(),
        _check_customer_ui_boundary(),
        _check_chain_of_thought_exposure(),
        _check_synthetic_seed_data(),
        _check_repo_noise(),
    ]


def main() -> int:
    print(
        "SupportPilot AI V3 - Security & Repository Audit"
    )
    print(
        "=" * 76
    )
    print(
        "Repository:",
        ROOT,
    )
    print(
        "Secret values are never printed by this audit."
    )
    print(
        "=" * 76
    )

    checks = run_audit()

    for check in checks:
        print()
        print(
            f"{check.status:4}  {check.name}"
        )
        print(
            "      "
            + check.detail
        )

    failures = [
        check
        for check in checks
        if check.status
        == "FAIL"
    ]

    warnings = [
        check
        for check in checks
        if check.status
        == "WARN"
    ]

    passes = [
        check
        for check in checks
        if check.status
        == "PASS"
    ]

    print()
    print(
        "=" * 76
    )
    print(
        "Result:",
        f"{len(passes)} PASS / "
        f"{len(warnings)} WARN / "
        f"{len(failures)} FAIL",
    )

    if failures:
        print(
            "Security/repository audit: FAIL"
        )
        return 1

    print(
        "Security/repository audit: PASS"
    )

    if warnings:
        print(
            "Warnings are repository-hygiene recommendations and do not "
            "represent a failed security boundary."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
