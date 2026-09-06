const app =
    document.getElementById(
        "app"
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

const systemStatus =
    document.getElementById(
        "system-status"
    );

const newConversationButton =
    document.getElementById(
        "new-conversation-button"
    );

const statusCard =
    document.getElementById(
        "status-card"
    );

const statusIcon =
    document.getElementById(
        "status-icon"
    );

const statusTitle =
    document.getElementById(
        "status-title"
    );

const statusCopy =
    document.getElementById(
        "status-copy"
    );

const statusBadge =
    document.getElementById(
        "status-badge"
    );

const caseCard =
    document.getElementById(
        "case-card"
    );

const sideCaseTitle =
    document.getElementById(
        "side-case-title"
    );

const sideCaseCopy =
    document.getElementById(
        "side-case-copy"
    );

const progress1 =
    document.getElementById(
        "progress1"
    );

const progress2 =
    document.getElementById(
        "progress2"
    );

const progress3 =
    document.getElementById(
        "progress3"
    );


let conversationId = null;
let isSending = false;
let casePollTimer = null;
let lastRenderedCaseFingerprint = null;
let renderedAssistantMessages = new Set();


const CONVERSATION_STORAGE_KEY =
    "supportpilot.activeConversationId";

const CUSTOMER_STORAGE_KEY =
    "supportpilot.activeCustomerId";

const LAST_RUN_STORAGE_KEY =
    "supportpilot.lastRunId";

function saveSessionState(
    activeConversationId,
    activeCustomerId
) {
    if (activeConversationId) {
        localStorage.setItem(
            CONVERSATION_STORAGE_KEY,
            activeConversationId
        );
    }

    if (activeCustomerId) {
        localStorage.setItem(
            CUSTOMER_STORAGE_KEY,
            activeCustomerId
        );
    }
}


function clearSessionState() {
    localStorage.removeItem(
        CONVERSATION_STORAGE_KEY
    );

    localStorage.removeItem(
        CUSTOMER_STORAGE_KEY
    );

    localStorage.removeItem(
        LAST_RUN_STORAGE_KEY
    );

    conversationId = null;
    lastRenderedCaseFingerprint = null;

    stopCasePolling();
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


function escapeHtml(
    value
) {
    return String(
        value ?? ""
    )
        .replaceAll(
            "&",
            "&amp;"
        )
        .replaceAll(
            "<",
            "&lt;"
        )
        .replaceAll(
            ">",
            "&gt;"
        )
        .replaceAll(
            '"',
            "&quot;"
        )
        .replaceAll(
            "'",
            "&#039;"
        );
}


function renderInlineMarkdown(
    value
) {
    let rendered =
        escapeHtml(
            value
        );

    const inlineCode = [];

    rendered = rendered.replace(
        /`([^`\n]+)`/g,
        (
            _match,
            code
        ) => {
            const token =
                (
                    "@@SUPPORTPILOT_INLINE_CODE_"
                    + inlineCode.length
                    + "@@"
                );

            inlineCode.push(
                `<code>${code}</code>`
            );

            return token;
        }
    );

    rendered = rendered.replace(
        /\*\*(.+?)\*\*/g,
        "<strong>$1</strong>"
    );

    rendered = rendered.replace(
        /__(.+?)__/g,
        "<strong>$1</strong>"
    );

    rendered = rendered.replace(
        /(^|[^*])\*([^*\n]+)\*(?!\*)/g,
        "$1<em>$2</em>"
    );

    rendered = rendered.replace(
        /~~(.+?)~~/g,
        "<del>$1</del>"
    );

    inlineCode.forEach(
        (
            code,
            index
        ) => {
            rendered = rendered.replace(
                (
                    "@@SUPPORTPILOT_INLINE_CODE_"
                    + index
                    + "@@"
                ),
                code
            );
        }
    );

    return rendered;
}


function renderSafeMarkdown(
    value
) {
    const lines = String(
        value ?? ""
    )
        .replace(
            /\r\n?/g,
            "\n"
        )
        .split(
            "\n"
        );

    const blocks = [];
    let paragraphLines = [];
    let listType = null;
    let listItems = [];

    function flushParagraph() {
        if (
            paragraphLines.length
            === 0
        ) {
            return;
        }

        blocks.push(
            (
                "<p>"
                + paragraphLines.join(
                    "<br>"
                )
                + "</p>"
            )
        );

        paragraphLines = [];
    }

    function flushList() {
        if (
            !listType
            || listItems.length === 0
        ) {
            listType = null;
            listItems = [];
            return;
        }

        const items =
            listItems
                .map(
                    (item) =>
                        `<li>${item}</li>`
                )
                .join("");

        blocks.push(
            (
                `<${listType}>`
                + items
                + `</${listType}>`
            )
        );

        listType = null;
        listItems = [];
    }

    lines.forEach(
        (line) => {
            if (
                line.trim() === ""
            ) {
                flushParagraph();
                flushList();
                return;
            }

            const unorderedMatch =
                line.match(
                    /^\s*[-+*]\s+(.+)$/
                );

            const orderedMatch =
                line.match(
                    /^\s*\d+\.\s+(.+)$/
                );

            if (
                unorderedMatch
                || orderedMatch
            ) {
                flushParagraph();

                const nextListType =
                    unorderedMatch
                        ? "ul"
                        : "ol";

                if (
                    listType
                    && listType
                    !== nextListType
                ) {
                    flushList();
                }

                listType =
                    nextListType;

                listItems.push(
                    renderInlineMarkdown(
                        unorderedMatch
                            ? unorderedMatch[1]
                            : orderedMatch[1]
                    )
                );

                return;
            }

            flushList();

            paragraphLines.push(
                renderInlineMarkdown(
                    line
                )
            );
        }
    );

    flushParagraph();
    flushList();

    return blocks.join("");
}


function scrollChatToBottom() {
    requestAnimationFrame(
        () => {
            chatMessages.scrollTop =
                chatMessages.scrollHeight;
        }
    );
}


function copyButton(
    message
) {
    const button =
        createElement(
            "button",
            "copy-response",
            "Copy response"
        );

    button.type =
        "button";

    button.addEventListener(
        "click",
        async () => {
            try {
                await navigator.clipboard.writeText(
                    message
                );
                button.textContent =
                    "Copied";
            } catch (_error) {
                button.textContent =
                    "Copy unavailable";
            }

            window.setTimeout(
                () => {
                    button.textContent =
                        "Copy response";
                },
                1200
            );
        }
    );

    return button;
}


function assistantAvatar() {
    return createElement(
        "div",
        "ai-avatar",
        "SP"
    );
}


function addSummaryItem(
    container,
    label,
    value,
    tone = ""
) {
    const item =
        createElement(
            "div",
            (
                "summary-item "
                + tone
            ).trim()
        );

    item.appendChild(
        createElement(
            "span",
            null,
            label
        )
    );

    item.appendChild(
        createElement(
            "strong",
            null,
            value
        )
    );

    container.appendChild(
        item
    );
}


function summaryForAction(
    actionName,
    phase = "pending",
    detail = null
) {
    if (
        actionName
        === "retry_subscription_sync"
    ) {
        if (phase === "resolved") {
            return [
                ["Payment", "Confirmed", "good"],
                ["Current plan", "Pro", "good"],
                ["Case status", "Resolved", "good"],
            ];
        }

        if (phase === "problem") {
            return [
                ["Payment", "Confirmed", "good"],
                ["Plan update", "Not completed", "problem"],
                ["Case status", "Needs support", "problem"],
            ];
        }

        return [
            ["Payment", "Confirmed", "good"],
            ["Current plan", "Basic", "warn"],
            ["Case status", "Under review", "warn"],
        ];
    }

    if (
        actionName
        === "create_support_ticket"
    ) {
        if (phase === "ticket-created") {
            return [
                ["Investigation", "Complete", "good"],
                ["Case reference", detail || "Created", "good"],
                ["Case status", "With support", "warn"],
            ];
        }

        return [
            ["Investigation", "Complete", "good"],
            ["Support case", "Awaiting review", "warn"],
            ["Case status", "Under review", "warn"],
        ];
    }

    if (
        actionName
        === "request_refund_review"
    ) {
        if (phase === "refund-created") {
            return [
                ["Payment", "Verified", "good"],
                ["Review reference", detail || "Created", "good"],
                ["Status", "Under review", "warn"],
            ];
        }

        return [
            ["Payment", "Verified", "good"],
            ["Refund review", "Awaiting approval", "warn"],
            ["Status", "Under review", "warn"],
        ];
    }

    return [
        ["Investigation", "Complete", "good"],
        ["Case status", "Under review", "warn"],
        ["Next step", "Support review", "warn"],
    ];
}


function detailsForAction(
    actionName,
    phase = "pending"
) {
    if (
        actionName
        === "retry_subscription_sync"
    ) {
        if (phase === "resolved") {
            return [
                "Your Pro payment is confirmed.",
                "Your subscription is now on Pro.",
                "The subscription update completed successfully.",
                "The updated subscription state was checked again after the correction.",
            ];
        }

        return [
            "Your Pro payment is confirmed.",
            "Your account is currently still on Basic.",
            "The plan update did not complete successfully.",
            "No additional payment is required.",
        ];
    }

    if (
        actionName
        === "create_support_ticket"
    ) {
        return [
            "SupportPilot checked the available CloudDesk evidence for this issue.",
            "The issue needs a human support case rather than an automatic account change.",
            "No unsupported account change has been made.",
        ];
    }

    if (
        actionName
        === "request_refund_review"
    ) {
        return [
            "The relevant payment was verified before requesting review.",
            "SupportPilot does not issue an automatic refund.",
            "A refund review must be handled through the controlled support process.",
        ];
    }

    return [
        "SupportPilot completed the available evidence checks.",
        "The issue needs additional support review.",
        "No unsupported account change has been made.",
    ];
}


function addCustomerSummary(
    messageContent,
    actionName,
    phase = "pending",
    detail = null
) {
    const summary =
        createElement(
            "div",
            "customer-summary"
        );

    summaryForAction(
        actionName,
        phase,
        detail
    ).forEach(
        ([label, value, tone]) => {
            addSummaryItem(
                summary,
                label,
                value,
                tone
            );
        }
    );

    messageContent.appendChild(
        summary
    );

    const toggle =
        createElement(
            "button",
            "details-toggle",
            "View what we checked"
        );

    toggle.type =
        "button";

    const details =
        createElement(
            "div",
            "details"
        );

    const list =
        createElement(
            "ul"
        );

    detailsForAction(
        actionName,
        phase
    ).forEach(
        (itemText) => {
            list.appendChild(
                createElement(
                    "li",
                    null,
                    itemText
                )
            );
        }
    );

    details.appendChild(
        list
    );

    toggle.addEventListener(
        "click",
        () => {
            details.classList.toggle(
                "open"
            );

            toggle.textContent =
                details.classList.contains(
                    "open"
                )
                    ? "Hide details"
                    : "View what we checked";
        }
    );

    messageContent.appendChild(
        toggle
    );

    messageContent.appendChild(
        details
    );
}


function addMessage(
    role,
    message,
    options = {}
) {
    const row =
        createElement(
            "div",
            `row ${role}`
        );

    if (role === "user") {
        row.appendChild(
            createElement(
                "div",
                "bubble",
                message
            )
        );

        chatMessages.appendChild(
            row
        );

        scrollChatToBottom();
        return row;
    }

    const wrap =
        createElement(
            "div",
            "ai-wrap"
        );

    wrap.appendChild(
        assistantAvatar()
    );

    const content =
        createElement(
            "div",
            "message-content"
        );

    const meta =
        createElement(
            "div",
            "meta"
        );

    meta.innerHTML =
        "<strong>SupportPilot</strong> AI support assistant";

    content.appendChild(
        meta
    );

    const bubble =
        createElement(
            "div",
            "bubble markdown-content"
        );

    bubble.innerHTML =
        renderSafeMarkdown(
            message
        );

    content.appendChild(
        bubble
    );

    if (
        options.actionName
    ) {
        addCustomerSummary(
            content,
            options.actionName,
            options.phase || "pending",
            options.detail || null
        );
    }

    if (
        options.copy !== false
    ) {
        content.appendChild(
            copyButton(
                message
            )
        );
    }

    wrap.appendChild(
        content
    );

    row.appendChild(
        wrap
    );

    chatMessages.appendChild(
        row
    );

    renderedAssistantMessages.add(
        message
    );

    scrollChatToBottom();

    return row;
}


function resetChatToWelcome() {
    renderedAssistantMessages.clear();
    chatMessages.replaceChildren();

    const row =
        createElement(
            "div",
            "row assistant welcome-message"
        );

    const wrap =
        createElement(
            "div",
            "ai-wrap"
        );

    wrap.appendChild(
        assistantAvatar()
    );

    const content =
        createElement(
            "div",
            "message-content"
        );

    const meta =
        createElement(
            "div",
            "meta"
        );

    meta.innerHTML =
        "<strong>SupportPilot</strong> AI support assistant";

    content.appendChild(
        meta
    );

    const bubble =
        createElement(
            "div",
            "bubble markdown-content"
        );

    bubble.innerHTML =
        (
            "<p>Hi! Tell me what happened and I’ll "
            + "check the relevant CloudDesk systems before answering.</p>"
        );

    content.appendChild(
        bubble
    );

    wrap.appendChild(
        content
    );

    row.appendChild(
        wrap
    );

    chatMessages.appendChild(
        row
    );
}


function addLoadingMessage() {
    const row =
        createElement(
            "div",
            "row assistant loading-message"
        );

    const wrap =
        createElement(
            "div",
            "ai-wrap"
        );

    wrap.appendChild(
        assistantAvatar()
    );

    const content =
        createElement(
            "div",
            "message-content"
        );

    const meta =
        createElement(
            "div",
            "meta"
        );

    meta.innerHTML =
        "<strong>SupportPilot</strong> Checking CloudDesk";

    content.appendChild(
        meta
    );

    const bubble =
        createElement(
            "div",
            "bubble"
        );

    const dots =
        createElement(
            "span",
            "loading-dots"
        );

    dots.innerHTML =
        "<span></span><span></span><span></span>";

    bubble.appendChild(
        dots
    );

    content.appendChild(
        bubble
    );

    wrap.appendChild(
        content
    );

    row.appendChild(
        wrap
    );

    chatMessages.appendChild(
        row
    );

    scrollChatToBottom();
}


function removeLoadingMessage() {
    const loading =
        chatMessages.querySelector(
            ".loading-message"
        );

    if (loading) {
        loading.remove();
    }
}


function setSendingState(
    sending
) {
    isSending =
        sending;

    messageInput.disabled =
        sending;

    sendButton.disabled =
        sending;

    newConversationButton.disabled =
        sending;

    document
        .querySelectorAll(
            ".quick"
        )
        .forEach(
            (button) => {
                button.disabled =
                    sending;
            }
        );

    sendButton.textContent =
        sending
            ? "Checking..."
            : "Send";
}


function setCaseProgress(
    stage
) {
    [
        progress1,
        progress2,
        progress3,
    ].forEach(
        (
            item,
            index
        ) => {
            item.classList.toggle(
                "done",
                index < stage
            );
        }
    );
}


function setCaseMode(
    mode,
    {
        title,
        copy,
        badge,
        sideTitle,
        sideCopy,
        progress,
        icon,
    }
) {
    app.classList.remove(
        "case-mode-neutral",
        "case-mode-review",
        "case-mode-resolved",
        "case-mode-problem"
    );

    app.classList.add(
        `case-mode-${mode}`
    );

    caseCard.className =
        `case-card ${mode === "neutral" ? "neutral" : mode}`;

    if (mode === "neutral") {
        statusCard.hidden =
            true;
    } else {
        statusCard.hidden =
            false;

        statusIcon.textContent =
            icon || "!";

        statusTitle.textContent =
            title;

        statusCopy.textContent =
            copy;

        statusBadge.textContent =
            badge;
    }

    sideCaseTitle.textContent =
        sideTitle;

    sideCaseCopy.textContent =
        sideCopy;

    setCaseProgress(
        progress
    );
}


function showNoActiveCase() {
    setCaseMode(
        "neutral",
        {
            title: "",
            copy: "",
            badge: "",
            sideTitle: "No active case",
            sideCopy: "Ask a support question to get started.",
            progress: 0,
            icon: "",
        }
    );
}


function showUnderReview(
    caseType
) {
    let copy =
        (
            "We found the issue and it needs a safe support review. "
            + "You do not need to take any additional action right now."
        );

    if (
        caseType
        === "SUBSCRIPTION_UPDATE"
    ) {
        copy =
            (
                "Your Pro payment went through, but the plan update "
                + "has not been applied yet. You do not need to pay again."
            );
    }

    if (
        caseType
        === "SUPPORT_CASE"
    ) {
        copy =
            (
                "We found that this issue needs a human support case. "
                + "Your case is being prepared for review."
            );
    }

    if (
        caseType
        === "REFUND_REVIEW"
    ) {
        copy =
            (
                "Your payment was verified and the refund request "
                + "needs human review. No refund has been issued automatically."
            );
    }

    setCaseMode(
        "review",
        {
            title: "We found the issue",
            copy,
            badge: "UNDER REVIEW",
            sideTitle: "Under review",
            sideCopy: (
                "We found the issue and your case is being safely reviewed."
            ),
            progress: 2,
            icon: "!",
        }
    );
}


function showGenericEscalation() {
    setCaseMode(
        "review",
        {
            title: "Additional support review needed",
            copy: (
                "SupportPilot completed the available checks, but this issue "
                + "needs additional support review before any change is made."
            ),
            badge: "UNDER REVIEW",
            sideTitle: "Under review",
            sideCopy: (
                "The investigation is complete and additional support review is needed."
            ),
            progress: 2,
            icon: "!",
        }
    );
}


function showRetryResolved() {
    setCaseMode(
        "resolved",
        {
            title: "Your issue is resolved",
            copy: (
                "Your account is now on Pro and the subscription update "
                + "was verified successfully."
            ),
            badge: "RESOLVED",
            sideTitle: "Resolved",
            sideCopy: (
                "Your Pro subscription has been applied and verified."
            ),
            progress: 3,
            icon: "✓",
        }
    );
}


function showTicketCreated(
    ticketNumber
) {
    const reference =
        ticketNumber || "your new support case";

    setCaseMode(
        "review",
        {
            title: "Your case has been escalated",
            copy: (
                "A support case was created for human follow-up. "
                + `Your case reference is ${reference}.`
            ),
            badge: "CASE OPEN",
            sideTitle: "With support team",
            sideCopy: (
                `Case ${reference} is open for human follow-up.`
            ),
            progress: 3,
            icon: "✓",
        }
    );
}


function showRefundReviewCreated(
    reviewNumber
) {
    const reference =
        reviewNumber || "your refund review";

    setCaseMode(
        "review",
        {
            title: "Your refund review was submitted",
            copy: (
                "Your refund request is now waiting for human review. "
                + `Your review reference is ${reference}. No refund was issued automatically.`
            ),
            badge: "UNDER REVIEW",
            sideTitle: "Refund review open",
            sideCopy: (
                `Review ${reference} is waiting for a human decision.`
            ),
            progress: 3,
            icon: "✓",
        }
    );
}


function showActionProblem(
    caseType
) {
    let copy =
        (
            "We couldn't complete the recommended support action safely. "
            + "No unsupported account change was made, and the issue still needs support review."
        );

    if (
        caseType
        === "REFUND_REVIEW"
    ) {
        copy =
            (
                "We couldn't safely create the refund review request. "
                + "No refund was issued, and the case still needs support review."
            );
    }

    setCaseMode(
        "problem",
        {
            title: "We still need to review this",
            copy,
            badge: "NEEDS SUPPORT",
            sideTitle: "Needs support",
            sideCopy: (
                "The issue remains open and no unsupported change was made."
            ),
            progress: 2,
            icon: "!",
        }
    );
}


function showActionRejected(
    caseType
) {
    let copy =
        (
            "No account change was made. Your issue still needs support review."
        );

    if (
        caseType
        === "REFUND_REVIEW"
    ) {
        copy =
            (
                "No refund review was submitted and no refund was issued. "
                + "Your request still needs support review."
            );
    }

    setCaseMode(
        "problem",
        {
            title: "Your case still needs support",
            copy,
            badge: "NEEDS SUPPORT",
            sideTitle: "Needs support",
            sideCopy: (
                "The proposed support step was not completed. No account change was made."
            ),
            progress: 2,
            icon: "!",
        }
    );
}


function caseFingerprint(
    snapshot
) {
    return JSON.stringify({
        status:
            snapshot?.case_status
            ?? null,
        type:
            snapshot?.case_type
            ?? null,
        plan:
            snapshot?.current_plan
            ?? null,
        reference:
            snapshot?.reference
            ?? null,
        updated:
            snapshot?.updated_at
            ?? null,
    });
}


function appendCustomerCaseOutcomeMessage(
    snapshot
) {
    const message =
        snapshot?.customer_message;

    if (
        !message
        || renderedAssistantMessages.has(
            message
        )
    ) {
        return;
    }

    addMessage(
        "assistant",
        message
    );
}


function handleCustomerCaseStatus(
    snapshot,
    {
        appendOutcome = true,
    } = {}
) {
    if (!snapshot) {
        return;
    }

    const fingerprint =
        caseFingerprint(
            snapshot
        );

    const changed =
        fingerprint
        !== lastRenderedCaseFingerprint;

    lastRenderedCaseFingerprint =
        fingerprint;

    if (
        snapshot.case_status
        === "RESOLVED"
    ) {
        showRetryResolved();

        if (
            appendOutcome
            && changed
        ) {
            appendCustomerCaseOutcomeMessage(
                snapshot
            );
        }

        stopCasePolling();
        return;
    }

    if (
        snapshot.case_status
        === "CASE_OPEN"
    ) {
        showTicketCreated(
            snapshot.reference
        );

        if (
            appendOutcome
            && changed
        ) {
            appendCustomerCaseOutcomeMessage(
                snapshot
            );
        }

        stopCasePolling();
        return;
    }

    if (
        snapshot.case_status
        === "REFUND_REVIEW_OPEN"
    ) {
        showRefundReviewCreated(
            snapshot.reference
        );

        if (
            appendOutcome
            && changed
        ) {
            appendCustomerCaseOutcomeMessage(
                snapshot
            );
        }

        stopCasePolling();
        return;
    }

    if (
        snapshot.case_status
        === "NEEDS_SUPPORT"
    ) {
        if (
            snapshot.case_type
            === "GENERAL_REVIEW"
        ) {
            setCaseMode(
                "problem",
                {
                    title:
                        snapshot.title
                        || "We still need to review this",
                    copy:
                        snapshot.message
                        || (
                            "The issue is still open and needs "
                            + "additional support review."
                        ),
                    badge:
                        "NEEDS SUPPORT",
                    sideTitle:
                        "Needs support",
                    sideCopy:
                        (
                            "The issue remains open and no unsupported "
                            + "account change was made."
                        ),
                    progress:
                        2,
                    icon:
                        "!",
                }
            );
        } else {
            showActionProblem(
                snapshot.case_type
            );
        }

        if (
            appendOutcome
            && changed
        ) {
            appendCustomerCaseOutcomeMessage(
                snapshot
            );
        }

        stopCasePolling();
        return;
    }

    if (
        snapshot.case_status
        === "NEEDS_INFORMATION"
    ) {
        setCaseMode(
            "review",
            {
                title:
                    snapshot.title
                    || "We need a little more information",
                copy:
                    snapshot.message
                    || (
                        "Continue the conversation so SupportPilot "
                        + "can complete the review."
                    ),
                badge:
                    "MORE INFO NEEDED",
                sideTitle:
                    "Conversation open",
                sideCopy:
                    "Continue the conversation to complete the review.",
                progress:
                    1,
                icon:
                    "?",
            }
        );

        stopCasePolling();
        return;
    }

    if (
        snapshot.case_status
        === "UNDER_REVIEW"
    ) {
        if (
            snapshot.customer_message
        ) {
            setCaseMode(
                "review",
                {
                    title:
                        snapshot.title
                        || "Additional support review needed",
                    copy:
                        snapshot.message
                        || (
                            "Your case is being prepared for "
                            + "additional support review."
                        ),
                    badge:
                        "UNDER REVIEW",
                    sideTitle:
                        "Under review",
                    sideCopy:
                        (
                            "Your case is moving to the next "
                            + "human-reviewed support step."
                        ),
                    progress:
                        2,
                    icon:
                        "!",
                }
            );

            if (
                appendOutcome
                && changed
            ) {
                appendCustomerCaseOutcomeMessage(
                    snapshot
                );
            }

        } else if (
            snapshot.case_type
            === "GENERAL_REVIEW"
        ) {
            showGenericEscalation();
        } else {
            showUnderReview(
                snapshot.case_type
            );
        }

        return;
    }

    showNoActiveCase();
    stopCasePolling();
}


async function refreshCaseStatus(
    {
        appendOutcome = true,
    } = {}
) {
    if (!conversationId) {
        return null;
    }

    const customerId =
        customerIdInput.value.trim();

    const queryString =
        customerId
            ? (
                "?customer_id="
                + encodeURIComponent(
                    customerId
                )
            )
            : "";

    try {
        const response =
            await fetch(
                (
                    "/api/v1/support/conversations/"
                    + encodeURIComponent(
                        conversationId
                    )
                    + "/case-status"
                    + queryString
                ),
                {
                    cache:
                        "no-store",
                }
            );

        if (!response.ok) {
            if (
                response.status
                === 403
                || response.status
                === 404
            ) {
                stopCasePolling();
            }
            return null;
        }

        const snapshot =
            await response.json();

        handleCustomerCaseStatus(
            snapshot,
            {
                appendOutcome,
            }
        );

        return snapshot;

    } catch (_error) {
        // Background status refresh must never block the support chat.
        return null;
    }
}


function startCasePolling() {
    stopCasePolling();

    if (!conversationId) {
        return;
    }

    refreshCaseStatus({
        appendOutcome:
            false,
    });

    casePollTimer =
        window.setInterval(
            () => {
                refreshCaseStatus();
            },
            3000
        );
}


function stopCasePolling() {
    if (casePollTimer) {
        window.clearInterval(
            casePollTimer
        );

        casePollTimer = null;
    }
}


function customerSafeActionName(
    proposal
) {
    return proposal?.action_name
        || null;
}



function customerSafeCaseTypeFromProposal(
    proposal
) {
    const actionName =
        customerSafeActionName(
            proposal
        );

    if (
        actionName
        === "retry_subscription_sync"
    ) {
        return "SUBSCRIPTION_UPDATE";
    }

    if (
        actionName
        === "create_support_ticket"
    ) {
        return "SUPPORT_CASE";
    }

    if (
        actionName
        === "request_refund_review"
    ) {
        return "REFUND_REVIEW";
    }

    return "GENERAL_REVIEW";
}


function renderResultState(
    resolution,
    actionProposal
) {
    if (actionProposal) {
        showUnderReview(
            customerSafeCaseTypeFromProposal(
                actionProposal
            )
        );

        startCasePolling();
        return;
    }

    if (
        resolution?.resolution_status
        === "ESCALATION_REQUIRED"
    ) {
        showGenericEscalation();
        startCasePolling();
        return;
    }

    if (
        resolution?.resolution_status
        === "UNRESOLVED"
        || resolution?.resolution_status
        === "NEEDS_INFORMATION"
    ) {
        setCaseMode(
            "review",
            {
                title: (
                    resolution.resolution_status
                    === "NEEDS_INFORMATION"
                        ? "We need a little more information"
                        : "We couldn't fully verify this yet"
                ),
                copy: (
                    resolution.summary
                    || (
                        "SupportPilot needs more verified information "
                        + "before reaching a conclusion."
                    )
                ),
                badge: (
                    resolution.resolution_status
                    === "NEEDS_INFORMATION"
                        ? "MORE INFO NEEDED"
                        : "NOT YET RESOLVED"
                ),
                sideTitle:
                    "Conversation open",
                sideCopy: (
                    "Continue the conversation so SupportPilot "
                    + "can complete the review."
                ),
                progress:
                    1,
                icon:
                    "?",
            }
        );
        return;
    }

    showNoActiveCase();
}


async function restoreConversation() {
    const storedConversationId =
        localStorage.getItem(
            CONVERSATION_STORAGE_KEY
        );

    const storedCustomerId =
        localStorage.getItem(
            CUSTOMER_STORAGE_KEY
        );

    if (storedCustomerId) {
        customerIdInput.value =
            storedCustomerId;
    }

    if (!storedConversationId) {
        showNoActiveCase();
        return;
    }

    try {
        const queryString =
            storedCustomerId
                ? (
                    "?customer_id="
                    + encodeURIComponent(
                        storedCustomerId
                    )
                )
                : "";

        const response =
            await fetch(
                (
                    "/api/v1/support/conversations/"
                    + encodeURIComponent(
                        storedConversationId
                    )
                    + queryString
                ),
                {
                    cache:
                        "no-store",
                }
            );

        if (!response.ok) {
            if (
                response.status
                === 403
                || response.status
                === 404
            ) {
                clearSessionState();
                resetChatToWelcome();
                showNoActiveCase();
            }
            return;
        }

        const data =
            await response.json();

        conversationId =
            data.conversation_id;

        if (data.customer_id) {
            customerIdInput.value =
                data.customer_id;
        }

        renderedAssistantMessages.clear();
        chatMessages.replaceChildren();

        if (
            Array.isArray(
                data.messages
            )
            && data.messages.length > 0
        ) {
            data.messages.forEach(
                (storedMessage) => {
                    if (
                        storedMessage.role
                        === "user"
                        || storedMessage.role
                        === "assistant"
                    ) {
                        addMessage(
                            storedMessage.role,
                            storedMessage.content,
                            {
                                copy: (
                                    storedMessage.role
                                    === "assistant"
                                ),
                            }
                        );
                    }
                }
            );
        } else {
            resetChatToWelcome();
        }

        const caseSnapshot =
            await refreshCaseStatus({
                appendOutcome:
                    true,
            });

        if (
            caseSnapshot?.case_status
            === "UNDER_REVIEW"
        ) {
            startCasePolling();
        }

    } catch (_error) {
        // Restoration failure should not block starting a new support request.
    }
}


async function checkHealth() {
    const statusText =
        systemStatus.querySelector(
            ".status-text"
        );

    try {
        const response =
            await fetch(
                "/health"
            );

        const data =
            await response.json();

        if (
            response.ok
            && data.database === "up"
            && data.agent === "configured"
        ) {
            systemStatus.className =
                "online online-state";

            statusText.textContent =
                "Support online";

            return;
        }

        systemStatus.className =
            "online offline-state";

        statusText.textContent =
            "Support degraded";
    } catch (_error) {
        systemStatus.className =
            "online offline-state";

        statusText.textContent =
            "Support offline";
    }
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
            || null,
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
                            "application/json",
                    },

                    body:
                        JSON.stringify(
                            requestBody
                        ),
                }
            );

        const data =
            await response.json();

        removeLoadingMessage();

        if (!response.ok) {
            const detail =
                data.detail
                || (
                    "SupportPilot could not "
                    + "process the request."
                );

            addMessage(
                "assistant",
                `**Request error:** ${detail}`
            );

            return;
        }

        conversationId =
            data.conversation_id;

        saveSessionState(
            conversationId,
            customerId
        );

        if (data.run_id) {
            localStorage.setItem(
                LAST_RUN_STORAGE_KEY,
                data.run_id
            );
        }

        const actionProposal =
            data.action_proposal
            || null;

        const actionName =
            customerSafeActionName(
                actionProposal
            );

        addMessage(
            "assistant",
            data.response,
            {
                actionName,
                phase: "pending",
            }
        );

        renderResultState(
            data.resolution,
            actionProposal
        );
    } catch (_error) {
        removeLoadingMessage();

        addMessage(
            "assistant",
            (
                "I couldn't reach the local SupportPilot API. "
                + "Please make sure the FastAPI server is running."
            )
        );
    } finally {
        setSendingState(
            false
        );

        messageInput.focus();
    }
}


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
            (
                Math.min(
                    messageInput.scrollHeight,
                    100
                )
                + "px"
            );
    }
);


document
    .querySelectorAll(
        ".quick"
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
        clearSessionState();
        resetChatToWelcome();
        showNoActiveCase();

        messageInput.value =
            "";

        messageInput.style.height =
            "auto";

        messageInput.focus();
    }
);


customerIdInput.addEventListener(
    "change",
    () => {
        const storedCustomerId =
            localStorage.getItem(
                CUSTOMER_STORAGE_KEY
            );

        const nextCustomerId =
            customerIdInput.value.trim();

        if (
            conversationId
            && storedCustomerId
            && nextCustomerId
            && nextCustomerId
                !== storedCustomerId
        ) {
            clearSessionState();
            resetChatToWelcome();
            showNoActiveCase();
        }
    }
);


window.addEventListener(
    "focus",
    () => {
        if (conversationId) {
            refreshCaseStatus();
        }
    }
);


window.addEventListener(
    "beforeunload",
    stopCasePolling
);


checkHealth();
restoreConversation();
