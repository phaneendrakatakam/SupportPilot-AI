const workspace =
    document.getElementById(
        "workspace"
    );

const developerViewButton =
    document.getElementById(
        "developer-view-button"
    );

const agentTracePanel =
    document.getElementById(
        "agent-trace-panel"
    );

const chatForm =
    document.getElementById(
        "chat-form"
    );

const messageInput =
    document.getElementById(
        "message-input"
    );

const sendButton =
    document.getElementById(
        "send-button"
    );

const customerIdInput =
    document.getElementById(
        "customer-id"
    );

const chatMessages =
    document.getElementById(
        "chat-messages"
    );

const traceEvents =
    document.getElementById(
        "trace-events"
    );

const runStatus =
    document.getElementById(
        "run-status"
    );

const intentDisplay =
    document.getElementById(
        "intent-display"
    );

const runIdDisplay =
    document.getElementById(
        "run-id-display"
    );

const conversationIdDisplay =
    document.getElementById(
        "conversation-id-display"
    );

const modelDisplay =
    document.getElementById(
        "model-display"
    );

const systemStatus =
    document.getElementById(
        "system-status"
    );

const newConversationButton =
    document.getElementById(
        "new-conversation-button"
    );


let conversationId = null;

let isSending = false;

let developerViewOpen = false;


function setDeveloperView(
    open
) {
    developerViewOpen =
        open;

    workspace.classList.toggle(
        "developer-view-open",
        open
    );

    developerViewButton.classList.toggle(
        "active",
        open
    );

    developerViewButton.setAttribute(
        "aria-expanded",
        String(open)
    );

    agentTracePanel.setAttribute(
        "aria-hidden",
        String(!open)
    );

    developerViewButton.textContent =
        open
            ? "Hide Developer View"
            : "Developer View";
}


function scrollChatToBottom() {
    chatMessages.scrollTop =
        chatMessages.scrollHeight;
}


function createElement(
    tag,
    className = null,
    text = null
) {
    const element =
        document.createElement(tag);

    if (className) {
        element.className =
            className;
    }

    if (text !== null) {
        element.textContent =
            text;
    }

    return element;
}


function addMessage(
    role,
    message
) {
    const row =
        createElement(
            "div",
            `message-row ${role}`
        );

    const avatar =
        createElement(
            "div",
            "avatar",
            role === "user"
                ? "YOU"
                : "AI"
        );

    const content =
        createElement(
            "div",
            "message-content"
        );

    const label =
        createElement(
            "div",
            "message-label",
            role === "user"
                ? "Customer"
                : "SupportPilot"
        );

    const bubble =
        createElement(
            "div",
            "message-bubble",
            message
        );

    content.appendChild(
        label
    );

    content.appendChild(
        bubble
    );

    row.appendChild(
        avatar
    );

    row.appendChild(
        content
    );

    chatMessages.appendChild(
        row
    );

    scrollChatToBottom();

    return row;
}


function addLoadingMessage() {
    const row =
        createElement(
            "div",
            "message-row assistant loading"
        );

    row.id =
        "loading-message";

    const avatar =
        createElement(
            "div",
            "avatar",
            "AI"
        );

    const content =
        createElement(
            "div",
            "message-content"
        );

    const label =
        createElement(
            "div",
            "message-label",
            "SupportPilot"
        );

    const bubble =
        createElement(
            "div",
            "message-bubble"
        );

    const dots =
        createElement(
            "span",
            "loading-dots"
        );

    for (
        let index = 0;
        index < 3;
        index += 1
    ) {
        dots.appendChild(
            document.createElement(
                "span"
            )
        );
    }

    bubble.appendChild(
        dots
    );

    content.appendChild(
        label
    );

    content.appendChild(
        bubble
    );

    row.appendChild(
        avatar
    );

    row.appendChild(
        content
    );

    chatMessages.appendChild(
        row
    );

    scrollChatToBottom();
}


function removeLoadingMessage() {
    const loadingMessage =
        document.getElementById(
            "loading-message"
        );

    if (loadingMessage) {
        loadingMessage.remove();
    }
}


function setRunStatus(
    status,
    cssClass
) {
    runStatus.textContent =
        status;

    runStatus.className =
        `run-status ${cssClass}`;
}


function clearTrace() {
    traceEvents.replaceChildren();

    intentDisplay.textContent =
        "—";

    runIdDisplay.textContent =
        "—";
}


function showEmptyTrace() {
    traceEvents.replaceChildren();

    const empty =
        createElement(
            "div",
            "trace-empty"
        );

    const icon =
        createElement(
            "div",
            "trace-empty-icon",
            "◌"
        );

    const title =
        createElement(
            "h3",
            null,
            "No agent run yet"
        );

    const description =
        createElement(
            "p",
            null,
            (
                "Send a customer message "
                + "to inspect SupportPilot's "
                + "structured execution trace."
            )
        );

    empty.appendChild(
        icon
    );

    empty.appendChild(
        title
    );

    empty.appendChild(
        description
    );

    traceEvents.appendChild(
        empty
    );
}


function addTraceText(
    container,
    label,
    value,
    className = ""
) {
    const labelElement =
        createElement(
            "div",
            "trace-label",
            label
        );

    const valueElement =
        createElement(
            "div",
            `trace-value ${className}`,
            value
        );

    container.appendChild(
        labelElement
    );

    container.appendChild(
        valueElement
    );
}


function addTraceJson(
    container,
    label,
    value
) {
    const labelElement =
        createElement(
            "div",
            "trace-label",
            label
        );

    const pre =
        createElement(
            "pre",
            "trace-code"
        );

    pre.textContent =
        JSON.stringify(
            value,
            null,
            2
        );

    container.appendChild(
        labelElement
    );

    container.appendChild(
        pre
    );
}


function renderTrace(
    trace
) {
    traceEvents.replaceChildren();

    if (
        !Array.isArray(trace)
        || trace.length === 0
    ) {
        showEmptyTrace();
        return;
    }


    trace.forEach(
        (event) => {
            const card =
                createElement(
                    "div",
                    "trace-event"
                );

            const header =
                createElement(
                    "div",
                    "trace-event-header"
                );

            const eventType =
                createElement(
                    "span",
                    "trace-event-type",
                    event.type
                        || "event"
                );

            const step =
                createElement(
                    "span",
                    "trace-step",
                    `STEP ${
                        event.step
                        ?? "—"
                    }`
                );

            header.appendChild(
                eventType
            );

            header.appendChild(
                step
            );

            card.appendChild(
                header
            );


            if (
                event.type ===
                "request"
            ) {
                addTraceText(
                    card,
                    "Customer ID",
                    event.customer_id
                        || "Not provided"
                );

                addTraceText(
                    card,
                    "Message",
                    event.message
                        || "—"
                );
            }


            if (
                event.type ===
                "tool_call"
            ) {
                addTraceText(
                    card,
                    "Tool",
                    event.tool
                        || "—"
                );

                addTraceJson(
                    card,
                    "Arguments",
                    event.arguments
                        || {}
                );

                addTraceText(
                    card,
                    "Status",
                    event.result_status
                        || "—",
                    event.result_status
                        === "SUCCESS"
                        ? "trace-success"
                        : "trace-error"
                );

                if (
                    event.latency_ms
                    !== undefined
                ) {
                    addTraceText(
                        card,
                        "Tool Latency",
                        `${event.latency_ms} ms`
                    );
                }

                addTraceJson(
                    card,
                    "Result",
                    event.result
                        || {}
                );
            }


            if (
                event.type ===
                "final_response"
            ) {
                addTraceText(
                    card,
                    "Intent",
                    event.intent
                        || "general"
                );

                addTraceText(
                    card,
                    "Response",
                    event.response
                        || "—"
                );
            }


            traceEvents.appendChild(
                card
            );
        }
    );
}


async function checkHealth() {
    try {
        const response =
            await fetch(
                "/health"
            );

        const data =
            await response.json();

        modelDisplay.textContent =
            data.model
            || "Unknown";


        if (
            response.ok
            && data.database
            === "up"
            && data.agent
            === "configured"
        ) {
            systemStatus.className =
                "status-badge online";

            systemStatus.innerHTML =
                '<span class="status-dot"></span>System Online';

            return;
        }


        systemStatus.className =
            "status-badge offline";

        systemStatus.innerHTML =
            '<span class="status-dot"></span>System Degraded';

    } catch (error) {
        modelDisplay.textContent =
            "Unavailable";

        systemStatus.className =
            "status-badge offline";

        systemStatus.innerHTML =
            '<span class="status-dot"></span>System Offline';
    }
}


function setSendingState(
    sending
) {
    isSending =
        sending;

    sendButton.disabled =
        sending;

    messageInput.disabled =
        sending;

    customerIdInput.disabled =
        sending;

    sendButton.textContent =
        sending
            ? "Working..."
            : "Send";
}


async function sendMessage(
    message
) {
    if (isSending) {
        return;
    }

    const cleanMessage =
        message.trim();

    if (!cleanMessage) {
        return;
    }


    const customerId =
        customerIdInput
            .value
            .trim();


    addMessage(
        "user",
        cleanMessage
    );

    addLoadingMessage();

    clearTrace();

    setRunStatus(
        "Running",
        "running"
    );

    setSendingState(
        true
    );


    const requestBody = {
        message:
            cleanMessage,

        customer_id:
            customerId
            || null,

        conversation_id:
            conversationId
            || null
    };


    try {
        const response =
            await fetch(
                "/api/v1/support/chat",
                {
                    method:
                        "POST",

                    headers: {
                        "Content-Type":
                            "application/json"
                    },

                    body:
                        JSON.stringify(
                            requestBody
                        )
                }
            );


        const data =
            await response.json();


        removeLoadingMessage();


        if (!response.ok) {
            const detail =
                data.detail
                || (
                    "SupportPilot could "
                    + "not process the request."
                );

            addMessage(
                "assistant",
                `Error: ${detail}`
            );

            setRunStatus(
                "Failed",
                "failed"
            );

            return;
        }


        conversationId =
            data.conversation_id;


        conversationIdDisplay.textContent =
            conversationId;


        intentDisplay.textContent =
            data.intent
            || "general";


        runIdDisplay.textContent =
            data.run_id
            || "—";


        addMessage(
            "assistant",
            data.response
        );


        renderTrace(
            data.trace
        );


        setRunStatus(
            "Complete",
            "complete"
        );

    } catch (error) {
        removeLoadingMessage();

        addMessage(
            "assistant",
            (
                "SupportPilot could not "
                + "reach the local API. "
                + "Please make sure the "
                + "FastAPI server is running."
            )
        );

        setRunStatus(
            "Failed",
            "failed"
        );

    } finally {
        setSendingState(
            false
        );

        messageInput.focus();
    }
}


developerViewButton.addEventListener(
    "click",
    () => {
        setDeveloperView(
            !developerViewOpen
        );
    }
);


chatForm.addEventListener(
    "submit",
    async (event) => {
        event.preventDefault();

        const message =
            messageInput.value;

        messageInput.value =
            "";

        messageInput.style.height =
            "auto";

        await sendMessage(
            message
        );
    }
);


messageInput.addEventListener(
    "keydown",
    (event) => {
        if (
            event.key === "Enter"
            && !event.shiftKey
        ) {
            event.preventDefault();

            chatForm.requestSubmit();
        }
    }
);


messageInput.addEventListener(
    "input",
    () => {
        messageInput.style.height =
            "auto";

        messageInput.style.height =
            `${Math.min(
                messageInput.scrollHeight,
                110
            )}px`;
    }
);


document
    .querySelectorAll(
        ".quick-action"
    )
    .forEach(
        (button) => {
            button.addEventListener(
                "click",
                () => {
                    const message =
                        button.dataset.message;

                    if (message) {
                        sendMessage(
                            message
                        );
                    }
                }
            );
        }
    );


newConversationButton.addEventListener(
    "click",
    () => {
        conversationId =
            null;

        conversationIdDisplay.textContent =
            "New";

        clearTrace();

        showEmptyTrace();

        setRunStatus(
            "Idle",
            "idle"
        );


        const existingMessages =
            Array.from(
                chatMessages.children
            );


        existingMessages.forEach(
            (
                element,
                index
            ) => {
                if (index > 0) {
                    element.remove();
                }
            }
        );


        messageInput.value =
            "";

        messageInput.focus();
    }
);


setDeveloperView(
    false
);

checkHealth();