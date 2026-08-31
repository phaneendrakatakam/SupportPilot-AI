const RUN_STORAGE_KEY =
    "supportpilot.lastRunId";

const runInput =
    document.getElementById(
        "run-id-input"
    );

const loadButton =
    document.getElementById(
        "load-run-button"
    );

const statusElement =
    document.getElementById(
        "inspector-status"
    );

const summary =
    document.getElementById(
        "run-summary"
    );

const requestSection =
    document.getElementById(
        "request-section"
    );

const requestMessage =
    document.getElementById(
        "request-message"
    );

const resolutionSection =
    document.getElementById(
        "resolution-section"
    );

const resolutionContent =
    document.getElementById(
        "resolution-content"
    );

const toolSection =
    document.getElementById(
        "tool-section"
    );

const toolExecutions =
    document.getElementById(
        "tool-executions"
    );

const traceSection =
    document.getElementById(
        "trace-section"
    );

const traceEvents =
    document.getElementById(
        "trace-events"
    );

const responseSection =
    document.getElementById(
        "response-section"
    );

const finalResponse =
    document.getElementById(
        "final-response"
    );


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


function setStatus(
    text,
    className = ""
) {
    statusElement.textContent =
        text;

    statusElement.className =
        (
            "inspector-status "
            + className
        ).trim();
}


function jsonBlock(
    value
) {
    const pre =
        element(
            "pre",
            "json-block"
        );

    pre.textContent =
        JSON.stringify(
            value,
            null,
            2
        );

    return pre;
}


function addSummaryItem(
    label,
    value
) {
    const item =
        element(
            "div",
            "summary-item"
        );

    item.appendChild(
        element(
            "span",
            "summary-label",
            label
        )
    );

    item.appendChild(
        element(
            "div",
            "summary-value",
            value ?? "—"
        )
    );

    summary.appendChild(
        item
    );
}


function renderRun(
    data
) {
    summary.replaceChildren();

    addSummaryItem(
        "Run ID",
        data.run_id
    );

    addSummaryItem(
        "Conversation ID",
        data.conversation_id
    );

    addSummaryItem(
        "Customer",
        data.customer_id
    );

    addSummaryItem(
        "Intent",
        data.intent
    );

    addSummaryItem(
        "Prompt",
        data.prompt_version
    );

    addSummaryItem(
        "Resolution",
        data.resolution_status
    );

    addSummaryItem(
        "Latency",
        data.latency_ms !== null
            ? (
                data.latency_ms
                + " ms"
            )
            : "—"
    );

    addSummaryItem(
        "Error",
        data.error || "None"
    );

    summary.hidden =
        false;

    requestMessage.textContent =
        data.request_message
        || "No persisted request message.";

    requestSection.hidden =
        false;

    resolutionContent.replaceChildren();

    const resolutionStatus =
        element(
            "div",
            "resolution-status",
            data.resolution_status
            || "NO STRUCTURED RESOLUTION"
        );

    resolutionContent.appendChild(
        resolutionStatus
    );

    const issue =
        element(
            "div",
            "field"
        );

    issue.appendChild(
        element(
            "div",
            "field-label",
            "Issue type"
        )
    );

    issue.appendChild(
        element(
            "div",
            null,
            data.issue_type || "—"
        )
    );

    resolutionContent.appendChild(
        issue
    );

    const resolutionSummary =
        element(
            "div",
            "field"
        );

    resolutionSummary.appendChild(
        element(
            "div",
            "field-label",
            "Resolution summary"
        )
    );

    resolutionSummary.appendChild(
        element(
            "div",
            null,
            data.resolution_summary
            || "—"
        )
    );

    resolutionContent.appendChild(
        resolutionSummary
    );

    resolutionSection.hidden =
        false;

    toolExecutions.replaceChildren();

    if (
        Array.isArray(
            data.tool_executions
        )
        && data.tool_executions.length > 0
    ) {
        data.tool_executions.forEach(
            (
                execution,
                index
            ) => {
                const card =
                    element(
                        "article",
                        "tool-card"
                    );

                const header =
                    element(
                        "div",
                        "tool-header"
                    );

                header.appendChild(
                    element(
                        "span",
                        "tool-name",
                        (
                            (index + 1)
                            + ". "
                            + execution.tool_name
                        )
                    )
                );

                const statusClass =
                    execution.result_status
                    === "SUCCESS"
                        ? "status-success"
                        : (
                            execution.result_status
                            === "ERROR"
                                ? "status-error"
                                : "status-warning"
                        );

                header.appendChild(
                    element(
                        "span",
                        statusClass,
                        execution.result_status
                    )
                );

                card.appendChild(
                    header
                );

                const latency =
                    element(
                        "div",
                        "field"
                    );

                latency.appendChild(
                    element(
                        "div",
                        "field-label",
                        "Latency"
                    )
                );

                latency.appendChild(
                    element(
                        "div",
                        null,
                        execution.latency_ms !== null
                            ? (
                                execution.latency_ms
                                + " ms"
                            )
                            : "—"
                    )
                );

                card.appendChild(
                    latency
                );

                const args =
                    element(
                        "div",
                        "field"
                    );

                args.appendChild(
                    element(
                        "div",
                        "field-label",
                        "Arguments"
                    )
                );

                args.appendChild(
                    jsonBlock(
                        execution.arguments
                    )
                );

                card.appendChild(
                    args
                );

                const result =
                    element(
                        "div",
                        "field"
                    );

                result.appendChild(
                    element(
                        "div",
                        "field-label",
                        "Result"
                    )
                );

                result.appendChild(
                    jsonBlock(
                        execution.result
                    )
                );

                card.appendChild(
                    result
                );

                if (execution.error) {
                    const error =
                        element(
                            "div",
                            "field"
                        );

                    error.appendChild(
                        element(
                            "div",
                            "field-label",
                            "Error"
                        )
                    );

                    error.appendChild(
                        element(
                            "div",
                            "status-error",
                            execution.error
                        )
                    );

                    card.appendChild(
                        error
                    );
                }

                toolExecutions.appendChild(
                    card
                );
            }
        );

    } else {
        toolExecutions.appendChild(
            element(
                "p",
                "status-warning",
                (
                    "No tool executions were "
                    + "persisted for this run."
                )
            )
        );
    }

    toolSection.hidden =
        false;

    traceEvents.replaceChildren();

    if (
        Array.isArray(
            data.trace
        )
        && data.trace.length > 0
    ) {
        data.trace.forEach(
            (
                event,
                index
            ) => {
                const card =
                    element(
                        "article",
                        "trace-card"
                    );

                const header =
                    element(
                        "div",
                        "trace-header"
                    );

                header.appendChild(
                    element(
                        "span",
                        "trace-type",
                        (
                            (index + 1)
                            + ". "
                            + (
                                event.type
                                || "event"
                            )
                        )
                    )
                );

                header.appendChild(
                    element(
                        "span",
                        null,
                        (
                            "Step "
                            + (
                                event.step
                                ?? "—"
                            )
                        )
                    )
                );

                card.appendChild(
                    header
                );

                card.appendChild(
                    jsonBlock(
                        event
                    )
                );

                traceEvents.appendChild(
                    card
                );
            }
        );

    } else {
        traceEvents.appendChild(
            element(
                "p",
                "status-warning",
                (
                    "No persisted structured "
                    + "trace is available."
                )
            )
        );
    }

    traceSection.hidden =
        false;

    finalResponse.textContent =
        data.final_response
        || "No final response was persisted.";

    responseSection.hidden =
        false;
}


async function loadRun() {
    const runId =
        runInput.value.trim();

    if (!runId) {
        setStatus(
            "Enter a run ID.",
            "error"
        );

        return;
    }

    setStatus(
        "Loading run..."
    );

    loadButton.disabled =
        true;

    try {
        const response =
            await fetch(
                (
                    "/api/v1/debug/runs/"
                    + encodeURIComponent(
                        runId
                    )
                )
            );

        const data =
            await response.json();

        if (!response.ok) {
            throw new Error(
                data.detail
                || "Run lookup failed."
            );
        }

        renderRun(
            data
        );

        setStatus(
            "Run loaded successfully.",
            "success"
        );

    } catch (error) {
        setStatus(
            error.message
            || "Run lookup failed.",
            "error"
        );

    } finally {
        loadButton.disabled =
            false;
    }
}


loadButton.addEventListener(
    "click",
    loadRun
);


runInput.addEventListener(
    "keydown",
    (event) => {
        if (
            event.key === "Enter"
        ) {
            event.preventDefault();
            loadRun();
        }
    }
);


const queryRunId =
    new URLSearchParams(
        window.location.search
    ).get(
        "run_id"
    );

const storedRunId =
    localStorage.getItem(
        RUN_STORAGE_KEY
    );

if (
    queryRunId
    || storedRunId
) {
    runInput.value =
        queryRunId
        || storedRunId;

    loadRun();
}
