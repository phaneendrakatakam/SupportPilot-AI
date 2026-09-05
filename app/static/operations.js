const OPERATOR_STORAGE_KEY =
    "supportpilot.operatorName";

const QUEUE_REFRESH_MS = 8000;

const operatorNameInput =
    document.getElementById(
        "operator-name"
    );

const refreshQueueButton =
    document.getElementById(
        "refresh-queue-button"
    );

const queueStatus =
    document.getElementById(
        "queue-status"
    );

const reviewQueue =
    document.getElementById(
        "review-queue"
    );

const queueSearch =
    document.getElementById(
        "queue-search"
    );

const pendingCount =
    document.getElementById(
        "pending-count"
    );

const activeCount =
    document.getElementById(
        "active-count"
    );

const historyCount =
    document.getElementById(
        "history-count"
    );

const pendingCountBadge =
    document.getElementById(
        "pending-count-badge"
    );

const workspaceEmpty =
    document.getElementById(
        "workspace-empty"
    );

const workspaceContent =
    document.getElementById(
        "workspace-content"
    );

const caseTitle =
    document.getElementById(
        "case-title"
    );

const caseSubtitle =
    document.getElementById(
        "case-subtitle"
    );

const caseApprovalStatus =
    document.getElementById(
        "case-approval-status"
    );

const caseVerificationStatus =
    document.getElementById(
        "case-verification-status"
    );

const caseCustomer =
    document.getElementById(
        "case-customer"
    );

const caseIssueType =
    document.getElementById(
        "case-issue-type"
    );

const caseRunId =
    document.getElementById(
        "case-run-id"
    );

const caseConversationId =
    document.getElementById(
        "case-conversation-id"
    );

const customerRequest =
    document.getElementById(
        "customer-request"
    );

const evidenceList =
    document.getElementById(
        "evidence-list"
    );

const resolutionPanel =
    document.getElementById(
        "resolution-panel"
    );

const auditTrace =
    document.getElementById(
        "audit-trace"
    );

const actionRecommendation =
    document.getElementById(
        "action-recommendation"
    );

const approvalControls =
    document.getElementById(
        "approval-controls"
    );

const approveActionButton =
    document.getElementById(
        "approve-action-button"
    );

const rejectActionButton =
    document.getElementById(
        "reject-action-button"
    );


const rejectDialog = document.getElementById("reject-dialog");
const rejectForm = document.getElementById("reject-form");
const rejectDialogClose = document.getElementById("reject-dialog-close");
const rejectDialogCancel = document.getElementById("reject-dialog-cancel");
const rejectReasonSelect = document.getElementById("reject-reason-select");
const rejectReasonNote = document.getElementById("reject-reason-note");
const rejectDialogError = document.getElementById("reject-dialog-error");

const decisionSummary =
    document.getElementById(
        "decision-summary"
    );

const executionPanel =
    document.getElementById(
        "execution-panel"
    );

const executeActionButton =
    document.getElementById(
        "execute-action-button"
    );

const verificationPanel =
    document.getElementById(
        "verification-panel"
    );

const businessObjectCard =
    document.getElementById(
        "business-object-card"
    );

const businessObjectTitle =
    document.getElementById(
        "business-object-title"
    );

const businessObjectPanel =
    document.getElementById(
        "business-object-panel"
    );

let queueItems = [];
let activeFilter = "pending";
let selectedProposalId = null;
let selectedRunId = null;
let currentActionDetail = null;
let currentRunData = null;
let requestInFlight = false;


function element(
    tag,
    className = null,
    text = null
) {
    const node =
        document.createElement(
            tag
        );

    if (className) {
        node.className =
            className;
    }

    if (text !== null) {
        node.textContent =
            text;
    }

    return node;
}


function humanize(
    value
) {
    return String(
        value ?? ""
    )
        .replaceAll(
            "_",
            " "
        )
        .replace(
            /\b\w/g,
            (character) =>
                character.toUpperCase()
        );
}


function actionLabel(
    actionName
) {
    const labels = {
        retry_subscription_sync:
            "Retry subscription synchronization",

        create_support_ticket:
            "Create support ticket",

        request_refund_review:
            "Request refund review",
    };

    return labels[
        actionName
    ] || humanize(
        actionName
    );
}


function formatDateTime(
    value
) {
    if (!value) {
        return "—";
    }

    const parsed =
        new Date(
            value
        );

    if (
        Number.isNaN(
            parsed.getTime()
        )
    ) {
        return String(
            value
        );
    }

    const day = String(
        parsed.getDate()
    ).padStart(
        2,
        "0"
    );

    const month = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ][
        parsed.getMonth()
    ];

    const year =
        parsed.getFullYear();

    const time =
        parsed.toLocaleTimeString(
            undefined,
            {
                hour: "numeric",
                minute: "2-digit",
            }
        );

    return (
        `${day} ${month} ${year}`
        + ` · ${time}`
    );
}


function relativeTime(
    value
) {
    if (!value) {
        return "";
    }

    const time =
        new Date(
            value
        ).getTime();

    if (
        Number.isNaN(
            time
        )
    ) {
        return "";
    }

    const diffMs =
        Date.now()
        - time;

    const minutes =
        Math.floor(
            diffMs / 60000
        );

    if (minutes < 1) {
        return "just now";
    }

    if (minutes < 60) {
        return `${minutes}m ago`;
    }

    const hours =
        Math.floor(
            minutes / 60
        );

    if (hours < 24) {
        return `${hours}h ago`;
    }

    const days =
        Math.floor(
            hours / 24
        );

    return `${days}d ago`;
}


function safeJson(
    value
) {
    return JSON.stringify(
        value ?? null,
        null,
        2
    );
}


function setQueueStatus(
    text,
    isError = false
) {
    queueStatus.textContent =
        text;

    queueStatus.className =
        isError
            ? "queue-status error"
            : "queue-status";
}


async function fetchJson(
    url,
    options = undefined
) {
    const response =
        await fetch(
            url,
            options
        );

    let data = null;

    try {
        data =
            await response.json();
    } catch (_error) {
        data = null;
    }

    if (!response.ok) {
        const detail =
            data?.detail
            || `Request failed (${response.status}).`;

        throw new Error(
            detail
        );
    }

    return data;
}


function queueBucket(
    detail
) {
    const proposal =
        detail.proposal;

    const execution =
        detail.execution;

    if (
        proposal.approval_status
        === "PENDING_APPROVAL"
    ) {
        return "pending";
    }

    if (
        proposal.approval_status
        === "REJECTED"
    ) {
        return "history";
    }

    if (!execution) {
        return "active";
    }

    if (
        execution.verification_status
        === "VERIFIED"
    ) {
        return "history";
    }

    if (
        execution.execution_status
        === "FAILED"
        || execution.verification_status
        === "FAILED"
    ) {
        return "active";
    }

    if (
        execution.execution_status
        === "SKIPPED"
    ) {
        return "history";
    }

    return "active";
}


function queueStatusInfo(
    detail
) {
    const proposal =
        detail.proposal;

    const execution =
        detail.execution;

    if (
        proposal.approval_status
        === "PENDING_APPROVAL"
    ) {
        return {
            text: "PENDING APPROVAL",
            className: "status-pending",
        };
    }

    if (
        proposal.approval_status
        === "REJECTED"
    ) {
        return {
            text: "REJECTED",
            className: "status-error",
        };
    }

    if (!execution) {
        return {
            text: "APPROVED · READY",
            className: "status-success",
        };
    }

    if (
        execution.verification_status
        === "VERIFIED"
    ) {
        return {
            text: "VERIFIED",
            className: "status-success",
        };
    }

    if (
        execution.execution_status
        === "FAILED"
        || execution.verification_status
        === "FAILED"
    ) {
        return {
            text: "NEEDS ATTENTION",
            className: "status-error",
        };
    }

    if (
        execution.execution_status
        === "EXECUTING"
    ) {
        return {
            text: "EXECUTING",
            className: "status-pending",
        };
    }

    if (
        execution.execution_status
        === "SKIPPED"
    ) {
        return {
            text: "SKIPPED",
            className: "status-neutral",
        };
    }

    return {
        text: proposal.approval_status,
        className: "status-neutral",
    };
}


function updateQueueCounts() {
    const pending =
        queueItems.filter(
            (item) =>
                queueBucket(
                    item
                ) === "pending"
        ).length;

    const active =
        queueItems.filter(
            (item) =>
                queueBucket(
                    item
                ) === "active"
        ).length;

    const history =
        queueItems.filter(
            (item) =>
                queueBucket(
                    item
                ) === "history"
        ).length;

    pendingCount.textContent =
        String(
            pending
        );

    activeCount.textContent =
        String(
            active
        );

    historyCount.textContent =
        String(
            history
        );

    pendingCountBadge.textContent =
        `${pending} pending`;
}


function queueItemMatchesSearch(
    detail,
    query
) {
    if (!query) {
        return true;
    }

    const proposal =
        detail.proposal;

    const searchable = [
        proposal.customer_id,
        proposal.issue_type,
        proposal.action_name,
        actionLabel(
            proposal.action_name
        ),
        proposal.reason,
        proposal.proposal_id,
        proposal.run_id,
    ]
        .join(
            " "
        )
        .toLowerCase();

    return searchable.includes(
        query.toLowerCase()
    );
}


function renderQueue() {
    reviewQueue.replaceChildren();

    updateQueueCounts();

    const query =
        queueSearch.value.trim();

    const visible =
        queueItems.filter(
            (detail) => {
                const bucket =
                    queueBucket(
                        detail
                    );

                const filterMatch =
                    activeFilter
                    === "all"
                    || bucket
                    === activeFilter;

                return (
                    filterMatch
                    && queueItemMatchesSearch(
                        detail,
                        query
                    )
                );
            }
        );

    if (
        visible.length === 0
    ) {
        const empty =
            element(
                "div",
                "queue-empty",
                (
                    activeFilter
                    === "pending"
                        ? "No pending human reviews right now. New AI recommendations will appear here automatically."
                        : "No review cases match this filter."
                )
            );

        reviewQueue.appendChild(
            empty
        );

        return;
    }

    visible.forEach(
        (detail) => {
            const proposal =
                detail.proposal;

            const status =
                queueStatusInfo(
                    detail
                );

            const button =
                element(
                    "button",
                    (
                        "review-item"
                        + (
                            proposal.proposal_id
                            === selectedProposalId
                                ? " active"
                                : ""
                        )
                    )
                );

            button.type =
                "button";

            const top =
                element(
                    "div",
                    "review-item-top"
                );

            top.appendChild(
                element(
                    "span",
                    "review-customer",
                    proposal.customer_id
                )
            );

            top.appendChild(
                element(
                    "span",
                    "review-time",
                    relativeTime(
                        proposal.proposed_at
                    )
                )
            );

            button.appendChild(
                top
            );

            button.appendChild(
                element(
                    "div",
                    "review-issue",
                    humanize(
                        proposal.issue_type
                    )
                )
            );

            button.appendChild(
                element(
                    "div",
                    "review-action",
                    actionLabel(
                        proposal.action_name
                    )
                )
            );

            const bottom =
                element(
                    "div",
                    "review-item-bottom"
                );

            bottom.appendChild(
                element(
                    "span",
                    (
                        "mini-status "
                        + status.className
                    ),
                    status.text
                )
            );

            bottom.appendChild(
                element(
                    "span",
                    "review-time",
                    formatDateTime(
                        proposal.proposed_at
                    )
                )
            );

            button.appendChild(
                bottom
            );

            button.addEventListener(
                "click",
                () => {
                    selectReview(
                        proposal.proposal_id,
                        proposal.run_id
                    );
                }
            );

            reviewQueue.appendChild(
                button
            );
        }
    );
}


async function loadQueue(
    silent = false
) {
    if (!silent) {
        setQueueStatus(
            "Loading review queue..."
        );
    }

    refreshQueueButton.disabled =
        true;

    try {
        const data =
            await fetchJson(
                "/api/v1/actions?limit=100"
            );

        queueItems =
            Array.isArray(
                data
            )
                ? data
                : [];

        renderQueue();

        setQueueStatus(
            (
                queueItems.length > 0
                    ? `${queueItems.length} review record(s) loaded.`
                    : "Queue is empty."
            )
        );

    } catch (error) {
        setQueueStatus(
            error.message
            || "Could not load the human review queue.",
            true
        );

    } finally {
        refreshQueueButton.disabled =
            false;
    }
}


function statusClassForApproval(
    value
) {
    if (
        value === "APPROVED"
    ) {
        return "status-pill status-success";
    }

    if (
        value === "REJECTED"
    ) {
        return "status-pill status-error";
    }

    return "status-pill status-pending";
}


function statusClassForVerification(
    value
) {
    if (
        value === "VERIFIED"
    ) {
        return "status-pill status-success";
    }

    if (
        value === "FAILED"
    ) {
        return "status-pill status-error";
    }

    if (
        value === "PENDING"
    ) {
        return "status-pill status-pending";
    }

    return "status-pill status-neutral";
}


function addMetaPair(
    container,
    label,
    value
) {
    container.appendChild(
        element(
            "span",
            null,
            label
        )
    );

    container.appendChild(
        element(
            "strong",
            null,
            String(
                value ?? "—"
            )
        )
    );
}


function flattenPrimitiveEntries(
    value,
    prefix = "",
    output = []
) {
    if (
        output.length >= 8
    ) {
        return output;
    }

    if (
        value === null
        || value === undefined
    ) {
        return output;
    }

    if (
        typeof value !== "object"
    ) {
        output.push([
            prefix || "value",
            String(
                value
            ),
        ]);

        return output;
    }

    if (
        Array.isArray(
            value
        )
    ) {
        if (
            value.length === 0
        ) {
            return output;
        }

        value.slice(
            0,
            3
        ).forEach(
            (item, index) => {
                flattenPrimitiveEntries(
                    item,
                    `${prefix}[${index}]`,
                    output
                );
            }
        );

        return output;
    }

    Object.entries(
        value
    ).forEach(
        ([key, item]) => {
            if (
                output.length >= 8
            ) {
                return;
            }

            const nextPrefix =
                prefix
                    ? `${prefix}.${key}`
                    : key;

            flattenPrimitiveEntries(
                item,
                nextPrefix,
                output
            );
        }
    );

    return output;
}


function evidenceSummary(
    execution
) {
    const result =
        execution.result;

    if (!result) {
        return execution.error
            || "No structured result was returned.";
    }

    const preferredKeys = {
        get_customer: [
            "customer_id",
            "name",
            "status",
            "account_status",
        ],
        get_subscription: [
            "plan",
            "requested_plan",
            "subscription_status",
            "last_sync_status",
        ],
        get_payment_status: [
            "payment_id",
            "plan",
            "status",
            "amount",
            "currency",
        ],
        get_service_status: [
            "service",
            "region",
            "status",
            "incident_status",
        ],
    };

    const keys =
        preferredKeys[
            execution.tool_name
        ] || [];

    const values = [];

    keys.forEach(
        (key) => {
            if (
                result
                && typeof result === "object"
                && !Array.isArray(
                    result
                )
                && result[key]
                !== undefined
                && result[key]
                !== null
            ) {
                values.push(
                    `${humanize(key)}: ${result[key]}`
                );
            }
        }
    );

    if (
        values.length > 0
    ) {
        return values.join(
            " · "
        );
    }

    const flattened =
        flattenPrimitiveEntries(
            result
        );

    if (
        flattened.length === 0
    ) {
        return "Structured evidence was returned.";
    }

    return flattened
        .slice(
            0,
            5
        )
        .map(
            ([key, value]) =>
                `${humanize(key)}: ${value}`
        )
        .join(
            " · "
        );
}


function renderEvidence(
    runData
) {
    evidenceList.replaceChildren();

    const executions =
        Array.isArray(
            runData.tool_executions
        )
            ? runData.tool_executions
            : [];

    if (
        executions.length === 0
    ) {
        evidenceList.appendChild(
            element(
                "div",
                "inline-error",
                "No persisted read-only tool evidence is available for this run."
            )
        );

        return;
    }

    executions.forEach(
        (execution, index) => {
            const isError =
                execution.result_status
                === "ERROR";

            const card =
                element(
                    "article",
                    (
                        "evidence-card"
                        + (
                            isError
                                ? " error"
                                : ""
                        )
                    )
                );

            const header =
                element(
                    "div",
                    "evidence-header"
                );

            header.appendChild(
                element(
                    "span",
                    "evidence-name",
                    `${index + 1}. ${execution.tool_name}`
                )
            );

            header.appendChild(
                element(
                    "span",
                    (
                        "evidence-status "
                        + (
                            isError
                                ? "error"
                                : "success"
                        )
                    ),
                    execution.result_status
                )
            );

            card.appendChild(
                header
            );

            card.appendChild(
                element(
                    "div",
                    "evidence-summary",
                    evidenceSummary(
                        execution
                    )
                )
            );

            const details =
                element(
                    "details",
                    "evidence-details"
                );

            details.appendChild(
                element(
                    "summary",
                    null,
                    "View structured payload"
                )
            );

            const payload =
                element(
                    "pre",
                    "evidence-json"
                );

            payload.textContent =
                safeJson({
                    arguments:
                        execution.arguments,
                    result:
                        execution.result,
                    latency_ms:
                        execution.latency_ms,
                    error:
                        execution.error,
                });

            details.appendChild(
                payload
            );

            card.appendChild(
                details
            );

            evidenceList.appendChild(
                card
            );
        }
    );
}


function renderResolution(
    runData
) {
    resolutionPanel.replaceChildren();

    const wrapper =
        element(
            "div",
            "resolution-panel-inner"
        );

    let resolutionClass =
        "resolution-status";

    if (
        runData.resolution_status
        === "RESOLVED"
    ) {
        resolutionClass +=
            " resolved";
    }

    if (
        runData.error
    ) {
        resolutionClass +=
            " error";
    }

    wrapper.appendChild(
        element(
            "span",
            resolutionClass,
            runData.resolution_status
            || "NO STRUCTURED RESOLUTION"
        )
    );

    const meta =
        element(
            "div",
            "resolution-meta"
        );

    addMetaPair(
        meta,
        "Issue type",
        runData.issue_type
        || "—"
    );

    addMetaPair(
        meta,
        "Intent",
        runData.intent
        || "—"
    );

    wrapper.appendChild(
        meta
    );

    wrapper.appendChild(
        element(
            "div",
            "resolution-copy",
            runData.resolution_summary
            || "No structured resolution summary was persisted."
        )
    );

    resolutionPanel.appendChild(
        wrapper
    );
}


function renderAuditTrace(
    runData
) {
    auditTrace.replaceChildren();

    const trace =
        Array.isArray(
            runData.trace
        )
            ? runData.trace
            : [];

    if (
        trace.length === 0
    ) {
        auditTrace.appendChild(
            element(
                "div",
                "inline-error",
                "No persisted structured trace is available."
            )
        );

        return;
    }

    trace.forEach(
        (event, index) => {
            const row =
                element(
                    "div",
                    "audit-event"
                );

            row.appendChild(
                element(
                    "div",
                    "audit-event-title",
                    `${index + 1}. ${event.type || "event"}`
                )
            );

            row.appendChild(
                element(
                    "div",
                    "audit-event-copy",
                    (
                        event.step !== undefined
                            ? `Step ${event.step}`
                            : "Structured application event"
                    )
                )
            );

            const raw =
                element(
                    "pre",
                    "audit-json"
                );

            raw.textContent =
                safeJson(
                    event
                );

            row.appendChild(
                raw
            );

            auditTrace.appendChild(
                row
            );
        }
    );
}


function overallCaseStatus(
    detail
) {
    const proposal =
        detail.proposal;

    const execution =
        detail.execution;

    if (
        execution?.verification_status
        === "VERIFIED"
    ) {
        if (
            proposal.action_name
            === "request_refund_review"
        ) {
            return {
                text:
                    "Refund review submitted",
                className:
                    "overall-case-value success",
            };
        }

        if (
            proposal.action_name
            === "create_support_ticket"
        ) {
            return {
                text:
                    "Support case open",
                className:
                    "overall-case-value success",
            };
        }

        return {
            text:
                "Resolved",
            className:
                "overall-case-value success",
        };
    }

    if (
        execution?.execution_status
        === "FAILED"
        || execution?.verification_status
        === "FAILED"
        || proposal.approval_status
        === "REJECTED"
    ) {
        return {
            text:
                "Needs support",
            className:
                "overall-case-value error",
        };
    }

    if (
        execution?.execution_status
        === "EXECUTING"
    ) {
        return {
            text:
                "Action in progress",
            className:
                "overall-case-value pending",
        };
    }

    if (
        proposal.approval_status
        === "APPROVED"
    ) {
        return {
            text:
                "Approved · awaiting execution",
            className:
                "overall-case-value pending",
        };
    }

    return {
        text:
            "Awaiting human approval",
        className:
            "overall-case-value pending",
    };
}


function isTechnicalArgumentKey(
    key
) {
    return (
        key.endsWith("_id")
        || key === "issue_type"
    );
}


function appendActionArgument(
    container,
    key,
    value
) {
    const row =
        element(
            "div",
            (
                "action-argument-row"
                + (
                    isTechnicalArgumentKey(
                        key
                    )
                        ? " technical"
                        : ""
                )
                + (
                    key === "evidence"
                    || key === "summary"
                    || key === "reason"
                        ? " full-width"
                        : ""
                )
            )
        );

    row.appendChild(
        element(
            "span",
            "action-argument-label",
            humanize(
                key
            )
        )
    );

    const valueWrap =
        element(
            "div",
            "action-argument-value"
        );

    if (
        Array.isArray(
            value
        )
    ) {
        if (
            value.length === 0
        ) {
            valueWrap.appendChild(
                element(
                    "span",
                    "argument-empty",
                    "No items"
                )
            );

        } else {
            const list =
                element(
                    "ul",
                    "argument-list"
                );

            value.forEach(
                (item) => {
                    const itemText =
                        typeof item === "object"
                            ? safeJson(
                                item
                            )
                            : String(
                                item
                            );

                    list.appendChild(
                        element(
                            "li",
                            null,
                            itemText
                        )
                    );
                }
            );

            valueWrap.appendChild(
                list
            );
        }

    } else if (
        value
        && typeof value === "object"
    ) {
        const nested =
            element(
                "div",
                "argument-object"
            );

        flattenPrimitiveEntries(
            value
        )
            .slice(
                0,
                8
            )
            .forEach(
                ([nestedKey, nestedValue]) => {
                    const nestedRow =
                        element(
                            "div",
                            "argument-object-row"
                        );

                    nestedRow.appendChild(
                        element(
                            "span",
                            null,
                            humanize(
                                nestedKey
                            )
                        )
                    );

                    nestedRow.appendChild(
                        element(
                            "strong",
                            null,
                            nestedValue
                        )
                    );

                    nested.appendChild(
                        nestedRow
                    );
                }
            );

        valueWrap.appendChild(
            nested
        );

    } else {
        valueWrap.appendChild(
            element(
                "strong",
                null,
                String(
                    value ?? "—"
                )
            )
        );
    }

    row.appendChild(
        valueWrap
    );

    container.appendChild(
        row
    );
}


function stateEntries(
    state
) {
    if (
        !state
        || typeof state !== "object"
    ) {
        return [];
    }

    return flattenPrimitiveEntries(
        state
    ).slice(
        0,
        8
    );
}


function stateEntryMap(
    state
) {
    return new Map(
        stateEntries(
            state
        )
    );
}


function renderActionRecommendation(
    detail
) {
    actionRecommendation.replaceChildren();

    const proposal =
        detail.proposal;

    const statusRow =
        element(
            "div",
            "action-status-row"
        );

    statusRow.appendChild(
        element(
            "span",
            statusClassForApproval(
                proposal.approval_status
            ),
            proposal.approval_status
        )
    );

    statusRow.appendChild(
        element(
            "span",
            "review-time",
            formatDateTime(
                proposal.proposed_at
            )
        )
    );

    actionRecommendation.appendChild(
        statusRow
    );

    const overallCase =
        overallCaseStatus(
            detail
        );

    const overallCaseRow =
        element(
            "div",
            "overall-case-row"
        );

    overallCaseRow.appendChild(
        element(
            "span",
            "overall-case-label",
            "Overall case"
        )
    );

    overallCaseRow.appendChild(
        element(
            "strong",
            overallCase.className,
            overallCase.text
        )
    );

    actionRecommendation.appendChild(
        overallCaseRow
    );

    actionRecommendation.appendChild(
        element(
            "div",
            "action-name",
            actionLabel(
                proposal.action_name
            )
        )
    );

    actionRecommendation.appendChild(
        element(
            "div",
            "action-reason",
            proposal.reason
        )
    );

    const argumentsGrid =
        element(
            "div",
            "action-arguments"
        );

    const argumentsObject =
        proposal.arguments
        && typeof proposal.arguments
        === "object"
            ? proposal.arguments
            : {};

    const preferredOrder = [
        "customer_id",
        "payment_id",
        "requested_plan",
        "issue_type",
        "priority",
        "summary",
        "reason",
        "evidence",
    ];

    const entries =
        Object.entries(
            argumentsObject
        ).sort(
            ([firstKey], [secondKey]) => {
                const firstIndex =
                    preferredOrder.indexOf(
                        firstKey
                    );

                const secondIndex =
                    preferredOrder.indexOf(
                        secondKey
                    );

                const normalizedFirst =
                    firstIndex === -1
                        ? preferredOrder.length
                        : firstIndex;

                const normalizedSecond =
                    secondIndex === -1
                        ? preferredOrder.length
                        : secondIndex;

                return (
                    normalizedFirst
                    - normalizedSecond
                );
            }
        );

    if (
        entries.length === 0
    ) {
        appendActionArgument(
            argumentsGrid,
            "arguments",
            "None"
        );

    } else {
        entries.forEach(
            ([key, value]) => {
                appendActionArgument(
                    argumentsGrid,
                    key,
                    value
                );
            }
        );
    }

    actionRecommendation.appendChild(
        argumentsGrid
    );

    approvalControls.hidden =
        proposal.approval_status
        !== "PENDING_APPROVAL";

    if (
        proposal.approval_status
        === "PENDING_APPROVAL"
    ) {
        decisionSummary.hidden =
            true;
        decisionSummary.textContent =
            "";

    } else {
        decisionSummary.hidden =
            false;

        decisionSummary.textContent =
            (
                proposal.approval_status
                === "APPROVED"
                    ? "Approved"
                    : "Rejected"
            )
            + (
                proposal.decided_by
                    ? ` by ${proposal.decided_by}`
                    : ""
            )
            + (
                proposal.decided_at
                    ? ` · ${formatDateTime(proposal.decided_at)}`
                    : ""
            );
    }
}


function executionClass(
    executionStatus
) {
    if (
        executionStatus
        === "SUCCEEDED"
    ) {
        return "execution-state success";
    }

    if (
        executionStatus
        === "FAILED"
    ) {
        return "execution-state error";
    }

    if (
        executionStatus
        === "EXECUTING"
    ) {
        return "execution-state pending";
    }

    return "execution-state neutral";
}


function renderExecution(
    detail
) {
    executionPanel.replaceChildren();

    const proposal =
        detail.proposal;

    const execution =
        detail.execution;

    executeActionButton.hidden =
        true;

    if (
        proposal.approval_status
        === "PENDING_APPROVAL"
    ) {
        executionPanel.appendChild(
            element(
                "span",
                "execution-state neutral",
                "NOT STARTED"
            )
        );

        executionPanel.appendChild(
            element(
                "div",
                "execution-copy",
                "Execution is blocked until a human operator approves the recommendation."
            )
        );

        return;
    }

    if (
        proposal.approval_status
        === "REJECTED"
    ) {
        executionPanel.appendChild(
            element(
                "span",
                "execution-state error",
                "BLOCKED"
            )
        );

        executionPanel.appendChild(
            element(
                "div",
                "execution-copy",
                "The human operator rejected this action. No controlled action can execute from this proposal."
            )
        );

        return;
    }

    if (!execution) {
        executionPanel.appendChild(
            element(
                "span",
                "execution-state pending",
                "READY TO EXECUTE"
            )
        );

        executionPanel.appendChild(
            element(
                "div",
                "execution-copy",
                "Human approval is recorded. Execution remains a separate deliberate operator step."
            )
        );

        executeActionButton.hidden =
            false;

        return;
    }

    executionPanel.appendChild(
        element(
            "span",
            executionClass(
                execution.execution_status
            ),
            execution.execution_status
        )
    );

    const copyParts = [];

    if (
        execution.completed_at
    ) {
        copyParts.push(
            `Completed ${formatDateTime(execution.completed_at)}`
        );
    }

    if (
        execution.error
    ) {
        copyParts.push(
            `Error: ${execution.error}`
        );
    }

    if (
        copyParts.length === 0
    ) {
        copyParts.push(
            "Controlled execution record is persisted."
        );
    }

    executionPanel.appendChild(
        element(
            "div",
            "execution-copy",
            copyParts.join(
                " · "
            )
        )
    );
}


function appendStateValues(
    container,
    state,
    comparisonState = null,
    emptyText = "No state snapshot"
) {
    const entries =
        stateEntries(
            state
        );

    if (
        entries.length === 0
    ) {
        container.appendChild(
            element(
                "div",
                "state-empty",
                emptyText
            )
        );

        return;
    }

    const comparison =
        stateEntryMap(
            comparisonState
        );

    entries.forEach(
        ([key, value]) => {
            const previousValue =
                comparison.has(
                    key
                )
                    ? comparison.get(
                        key
                    )
                    : undefined;

            const changed =
                comparisonState
                && (
                    previousValue === undefined
                    || previousValue !== value
                );

            const row =
                element(
                    "div",
                    (
                        "state-value"
                        + (
                            changed
                                ? " changed"
                                : ""
                        )
                        + (
                            isTechnicalArgumentKey(
                                key.split(".").at(-1)
                            )
                                ? " technical"
                                : ""
                        )
                    )
                );

            row.appendChild(
                element(
                    "span",
                    null,
                    humanize(
                        key
                    )
                )
            );

            const valueWrap =
                element(
                    "strong",
                    null,
                    value
                );

            row.appendChild(
                valueWrap
            );

            container.appendChild(
                row
            );
        }
    );
}


function renderVerification(
    detail
) {
    verificationPanel.replaceChildren();

    const execution =
        detail.execution;

    if (!execution) {
        verificationPanel.appendChild(
            element(
                "span",
                "verification-state neutral",
                "NOT RUN"
            )
        );

        verificationPanel.appendChild(
            element(
                "div",
                "verification-copy",
                "Verification starts only after an approved controlled action is executed."
            )
        );

        return;
    }

    let verificationClass =
        "verification-state neutral";

    if (
        execution.verification_status
        === "VERIFIED"
    ) {
        verificationClass =
            "verification-state success";
    } else if (
        execution.verification_status
        === "FAILED"
    ) {
        verificationClass =
            "verification-state error";
    } else if (
        execution.verification_status
        === "PENDING"
    ) {
        verificationClass =
            "verification-state pending";
    }

    verificationPanel.appendChild(
        element(
            "span",
            verificationClass,
            execution.verification_status
        )
    );

    if (
        execution.before_state
        || execution.after_state
    ) {
        const comparison =
            element(
                "div",
                "state-comparison"
            );

        const before =
            element(
                "div",
                "state-box"
            );

        before.appendChild(
            element(
                "div",
                "state-box-title",
                "Before action"
            )
        );

        const beforeValues =
            element(
                "div",
                "state-values"
            );

        appendStateValues(
            beforeValues,
            execution.before_state,
            null,
            (
                detail.proposal.action_name
                === "create_support_ticket"
                    ? "No support ticket existed before this action."
                    : (
                        detail.proposal.action_name
                        === "request_refund_review"
                            ? "No refund review existed before this action."
                            : "No prior state snapshot was recorded."
                    )
            )
        );

        before.appendChild(
            beforeValues
        );

        const after =
            element(
                "div",
                "state-box"
            );

        after.appendChild(
            element(
                "div",
                "state-box-title",
                "After action"
            )
        );

        const afterValues =
            element(
                "div",
                "state-values"
            );

        appendStateValues(
            afterValues,
            execution.after_state,
            execution.before_state,
            "No post-action state snapshot was recorded."
        );

        after.appendChild(
            afterValues
        );

        comparison.appendChild(
            before
        );

        comparison.appendChild(
            element(
                "div",
                "state-arrow",
                "→"
            )
        );

        comparison.appendChild(
            after
        );

        verificationPanel.appendChild(
            comparison
        );
    }

    if (
        execution.verification_result
    ) {
        const result =
            element(
                "div",
                (
                    "verification-result"
                    + (
                        execution.verification_status
                        === "FAILED"
                            ? " failed"
                            : ""
                    )
                )
            );

        result.textContent =
            (
                execution.verification_status
                === "VERIFIED"
                    ? "✓ Verification succeeded. "
                    : "Verification result: "
            )
            + flattenPrimitiveEntries(
                execution.verification_result
            )
                .slice(
                    0,
                    6
                )
                .map(
                    ([key, value]) =>
                        `${humanize(key)}: ${value}`
                )
                .join(
                    " · "
                );

        verificationPanel.appendChild(
            result
        );
    }

    if (
        execution.error
    ) {
        verificationPanel.appendChild(
            element(
                "div",
                "inline-error",
                execution.error
            )
        );
    }
}


function findInspectorProposal(
    runData,
    proposalId
) {
    const proposals =
        Array.isArray(
            runData.action_proposals
        )
            ? runData.action_proposals
            : [];

    return proposals.find(
        (proposal) =>
            proposal.proposal_id
            === proposalId
    ) || null;
}


function renderBusinessObject(
    inspectorProposal
) {
    businessObjectCard.hidden =
        true;

    businessObjectPanel.replaceChildren();

    if (
        !inspectorProposal
        || !inspectorProposal.business_object
    ) {
        return;
    }

    const businessObject =
        inspectorProposal.business_object;

    businessObjectCard.hidden =
        false;

    const highlight =
        element(
            "div",
            "business-object-highlight"
        );

    if (
        businessObject.type
        === "support_ticket"
    ) {
        businessObjectTitle.textContent =
            "Specialist support handoff";

        const heading =
            element(
                "div",
                "handoff-heading"
            );

        const headingCopy =
            element(
                "div",
                "handoff-heading-copy"
            );

        headingCopy.appendChild(
            element(
                "span",
                "handoff-kicker",
                "SUPPORT CASE"
            )
        );

        headingCopy.appendChild(
            element(
                "div",
                "business-object-number",
                businessObject.ticket_number
                || "Ticket created"
            )
        );

        heading.appendChild(
            headingCopy
        );

        heading.appendChild(
            element(
                "span",
                "handoff-status-chip",
                businessObject.status
                || "OPEN"
            )
        );

        highlight.appendChild(
            heading
        );

        highlight.appendChild(
            element(
                "div",
                "handoff-explainer",
                "The unresolved customer issue is now owned by the specialist support workflow."
            )
        );

        const meta =
            element(
                "div",
                "business-object-meta"
            );

        addMetaPair(
            meta,
            "Priority",
            businessObject.priority
        );

        addMetaPair(
            meta,
            "Issue type",
            humanize(
                businessObject.issue_type
            )
        );

        highlight.appendChild(
            meta
        );

        if (
            businessObject.summary
        ) {
            const summary =
                element(
                    "div",
                    "handoff-summary"
                );

            summary.appendChild(
                element(
                    "span",
                    "handoff-summary-label",
                    "Handoff summary"
                )
            );

            summary.appendChild(
                element(
                    "div",
                    "business-object-copy",
                    businessObject.summary
                )
            );

            highlight.appendChild(
                summary
            );
        }

    } else if (
        businessObject.type
        === "refund_review"
    ) {
        businessObjectTitle.textContent =
            "Billing review handoff";

        const heading =
            element(
                "div",
                "handoff-heading"
            );

        const headingCopy =
            element(
                "div",
                "handoff-heading-copy"
            );

        headingCopy.appendChild(
            element(
                "span",
                "handoff-kicker",
                "REFUND REVIEW"
            )
        );

        headingCopy.appendChild(
            element(
                "div",
                "business-object-number",
                businessObject.review_number
                || "Refund review created"
            )
        );

        heading.appendChild(
            headingCopy
        );

        heading.appendChild(
            element(
                "span",
                "handoff-status-chip",
                businessObject.status
                || "PENDING REVIEW"
            )
        );

        highlight.appendChild(
            heading
        );

        highlight.appendChild(
            element(
                "div",
                "handoff-explainer",
                "The refund was not issued automatically. This record is waiting for a human billing decision."
            )
        );

        const meta =
            element(
                "div",
                "business-object-meta"
            );

        addMetaPair(
            meta,
            "Payment",
            businessObject.payment_id
        );

        highlight.appendChild(
            meta
        );

        if (
            businessObject.reason
        ) {
            const summary =
                element(
                    "div",
                    "handoff-summary"
                );

            summary.appendChild(
                element(
                    "span",
                    "handoff-summary-label",
                    "Review reason"
                )
            );

            summary.appendChild(
                element(
                    "div",
                    "business-object-copy",
                    businessObject.reason
                )
            );

            highlight.appendChild(
                summary
            );
        }

    } else {
        businessObjectTitle.textContent =
            "Created record";

        const raw =
            element(
                "pre",
                "evidence-json"
            );

        raw.textContent =
            safeJson(
                businessObject
            );

        highlight.appendChild(
            raw
        );
    }

    businessObjectPanel.appendChild(
        highlight
    );
}


function renderSelectedCase() {
    if (
        !currentActionDetail
        || !currentRunData
    ) {
        return;
    }

    const proposal =
        currentActionDetail.proposal;

    const execution =
        currentActionDetail.execution;

    const inspectorProposal =
        findInspectorProposal(
            currentRunData,
            proposal.proposal_id
        );

    workspaceEmpty.hidden =
        true;

    workspaceContent.hidden =
        false;

    caseTitle.textContent =
        actionLabel(
            proposal.action_name
        );

    caseSubtitle.textContent =
        (
            `${proposal.customer_id} · `
            + `${humanize(proposal.issue_type)} · `
            + `Proposed ${formatDateTime(proposal.proposed_at)}`
        );

    caseApprovalStatus.className =
        statusClassForApproval(
            proposal.approval_status
        );

    caseApprovalStatus.textContent =
        proposal.approval_status;

    if (execution) {
        caseVerificationStatus.hidden =
            false;

        caseVerificationStatus.className =
            statusClassForVerification(
                execution.verification_status
            );

        caseVerificationStatus.textContent =
            execution.verification_status;

    } else {
        caseVerificationStatus.hidden =
            true;
        caseVerificationStatus.textContent =
            "";
    }

    caseCustomer.textContent =
        proposal.customer_id;

    caseIssueType.textContent =
        proposal.issue_type;

    caseRunId.textContent =
        proposal.run_id;

    caseConversationId.textContent =
        proposal.conversation_id;

    customerRequest.textContent =
        currentRunData.request_message
        || "No persisted customer request is available.";

    renderEvidence(
        currentRunData
    );

    renderResolution(
        currentRunData
    );

    renderAuditTrace(
        currentRunData
    );

    renderActionRecommendation(
        currentActionDetail
    );

    renderExecution(
        currentActionDetail
    );

    renderVerification(
        currentActionDetail
    );

    renderBusinessObject(
        inspectorProposal
    );

    renderQueue();
}


async function selectReview(
    proposalId,
    runId
) {
    selectedProposalId =
        proposalId;

    selectedRunId =
        runId;

    renderQueue();

    workspaceEmpty.hidden =
        false;

    workspaceContent.hidden =
        true;

    workspaceEmpty.querySelector(
        "h2"
    ).textContent =
        "Loading review...";

    workspaceEmpty.querySelector(
        "p"
    ).textContent =
        "Loading persisted evidence and action state.";

    try {
        const [
            actionDetail,
            runData,
        ] = await Promise.all([
            fetchJson(
                (
                    "/api/v1/actions/"
                    + encodeURIComponent(
                        proposalId
                    )
                )
            ),
            fetchJson(
                (
                    "/api/v1/debug/runs/"
                    + encodeURIComponent(
                        runId
                    )
                )
            ),
        ]);

        currentActionDetail =
            actionDetail;

        currentRunData =
            runData;

        renderSelectedCase();

    } catch (error) {
        workspaceEmpty.hidden =
            false;

        workspaceContent.hidden =
            true;

        workspaceEmpty.querySelector(
            "h2"
        ).textContent =
            "Could not load review";

        workspaceEmpty.querySelector(
            "p"
        ).textContent =
            error.message
            || "The selected review could not be loaded.";
    }
}


function operatorName() {
    return operatorNameInput.value.trim();
}


function showDecisionError(
    message
) {
    decisionSummary.hidden =
        false;

    decisionSummary.textContent =
        message;

    decisionSummary.classList.add(
        "inline-error"
    );
}


function clearDecisionError() {
    decisionSummary.classList.remove(
        "inline-error"
    );
}


function closeRejectDialog() {
    if (rejectDialog.open) {
        rejectDialog.close();
    }

    rejectDialogError.hidden = true;
    rejectDialogError.textContent = "";
}


function openRejectDialog() {
    rejectReasonSelect.value = "";
    rejectReasonNote.value = "";
    rejectDialogError.hidden = true;
    rejectDialogError.textContent = "";
    rejectDialog.showModal();
    rejectReasonSelect.focus();
}


function rejectionReason() {
    const selected = rejectReasonSelect.value.trim();
    const note = rejectReasonNote.value.trim();

    if (!selected) {
        return null;
    }

    if (
        selected === "Other"
        && !note
    ) {
        return null;
    }

    return note
        ? `${selected}: ${note}`
        : selected;
}


async function decideAction(
    decision,
    decisionReason = null
) {
    if (
        requestInFlight
        || !selectedProposalId
    ) {
        return;
    }

    const operator =
        operatorName();

    if (!operator) {
        showDecisionError(
            "Enter the operator name before approving or rejecting an action."
        );

        operatorNameInput.focus();
        return;
    }

    localStorage.setItem(
        OPERATOR_STORAGE_KEY,
        operator
    );

    clearDecisionError();

    requestInFlight =
        true;

    approveActionButton.disabled =
        true;

    rejectActionButton.disabled =
        true;

    decisionSummary.hidden =
        false;

    decisionSummary.textContent =
        (
            decision === "approve"
                ? "Recording human approval..."
                : "Recording human rejection..."
        );

    try {
        await fetchJson(
            (
                "/api/v1/actions/"
                + encodeURIComponent(
                    selectedProposalId
                )
                + `/` + decision
            ),
            {
                method: "POST",
                headers: {
                    "Content-Type":
                        "application/json",
                },
                body: JSON.stringify({
                    decided_by:
                        operator,
                    ...(
                        decision === "reject"
                        && decisionReason
                            ? {
                                reason:
                                    decisionReason,
                            }
                            : {}
                    ),
                }),
            }
        );

        const originalProposalId =
            selectedProposalId;
        const originalRunId =
            selectedRunId;
        const originalConversationId =
            currentActionDetail?.proposal?.conversation_id
            || null;

        await loadQueue(
            true
        );

        if (
            decision === "reject"
            && originalConversationId
        ) {
            const fallback =
                queueItems.find(
                    (item) => (
                        item.proposal.conversation_id
                        === originalConversationId
                        && item.proposal.approval_status
                        === "PENDING_APPROVAL"
                        && item.proposal.action_name
                        === "create_support_ticket"
                    )
                );

            if (fallback) {
                await selectReview(
                    fallback.proposal.proposal_id,
                    fallback.proposal.run_id
                );
                return;
            }
        }

        await selectReview(
            originalProposalId,
            originalRunId
        );

    } catch (error) {
        showDecisionError(
            error.message
            || "The human decision could not be recorded."
        );

    } finally {
        requestInFlight =
            false;

        approveActionButton.disabled =
            false;

        rejectActionButton.disabled =
            false;
    }
}


async function executeSelectedAction() {
    if (
        requestInFlight
        || !selectedProposalId
        || !selectedRunId
    ) {
        return;
    }

    requestInFlight =
        true;

    executeActionButton.disabled =
        true;

    executeActionButton.textContent =
        "Executing...";

    try {
        await fetchJson(
            (
                "/api/v1/actions/"
                + encodeURIComponent(
                    selectedProposalId
                )
                + "/execute"
            ),
            {
                method: "POST",
            }
        );

        await Promise.all([
            loadQueue(
                true
            ),
            selectReview(
                selectedProposalId,
                selectedRunId
            ),
        ]);

    } catch (error) {
        executionPanel.appendChild(
            element(
                "div",
                "inline-error",
                error.message
                || "The approved action could not be executed."
            )
        );

    } finally {
        requestInFlight =
            false;

        executeActionButton.disabled =
            false;

        executeActionButton.textContent =
            "Execute approved action";
    }
}


function restoreEmptyWorkspaceCopy() {
    workspaceEmpty.querySelector(
        "h2"
    ).textContent =
        "Select a review case";

    workspaceEmpty.querySelector(
        "p"
    ).textContent =
        (
            "Choose an item from the Human Review Queue to inspect "
            + "the customer request, evidence, recommendation and "
            + "action lifecycle."
        );
}


function chooseFirstPendingReview() {
    if (
        selectedProposalId
        || queueItems.length === 0
    ) {
        return;
    }

    const pending =
        queueItems.find(
            (item) =>
                queueBucket(
                    item
                ) === "pending"
        );

    if (pending) {
        selectReview(
            pending.proposal.proposal_id,
            pending.proposal.run_id
        );
    }
}


refreshQueueButton.addEventListener(
    "click",
    async () => {
        await loadQueue();
        chooseFirstPendingReview();
    }
);


queueSearch.addEventListener(
    "input",
    renderQueue
);


document
    .querySelectorAll(
        ".queue-tab"
    )
    .forEach(
        (button) => {
            button.addEventListener(
                "click",
                () => {
                    activeFilter =
                        button.dataset.filter
                        || "pending";

                    document
                        .querySelectorAll(
                            ".queue-tab"
                        )
                        .forEach(
                            (tab) => {
                                tab.classList.toggle(
                                    "active",
                                    tab === button
                                );
                            }
                        );

                    renderQueue();
                }
            );
        }
    );


operatorNameInput.addEventListener(
    "change",
    () => {
        const value =
            operatorName();

        if (value) {
            localStorage.setItem(
                OPERATOR_STORAGE_KEY,
                value
            );
        }
    }
);


approveActionButton.addEventListener(
    "click",
    () => {
        decideAction(
            "approve"
        );
    }
);


rejectActionButton.addEventListener(
    "click",
    openRejectDialog
);

rejectDialogClose.addEventListener(
    "click",
    closeRejectDialog
);

rejectDialogCancel.addEventListener(
    "click",
    closeRejectDialog
);

rejectForm.addEventListener(
    "submit",
    async (event) => {
        event.preventDefault();

        const reason = rejectionReason();

        if (!reason) {
            rejectDialogError.hidden = false;
            rejectDialogError.textContent = (
                rejectReasonSelect.value === "Other"
                    ? "Add a short note for the Other reason."
                    : "Choose a rejection reason before continuing."
            );
            return;
        }

        closeRejectDialog();

        await decideAction(
            "reject",
            reason
        );
    }
);


executeActionButton.addEventListener(
    "click",
    executeSelectedAction
);


const storedOperator =
    localStorage.getItem(
        OPERATOR_STORAGE_KEY
    );

if (storedOperator) {
    operatorNameInput.value =
        storedOperator;
}


restoreEmptyWorkspaceCopy();

loadQueue()
    .then(
        chooseFirstPendingReview
    );

setInterval(
    () => {
        loadQueue(
            true
        );
    },
    QUEUE_REFRESH_MS
);
