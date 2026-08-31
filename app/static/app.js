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

const conversationIdDisplay =
    document.getElementById(
        "conversation-id-display"
    );

const sessionStateLabel =
    document.getElementById(
        "session-state-label"
    );

const systemStatus =
    document.getElementById(
        "system-status"
    );

const newConversationButton =
    document.getElementById(
        "new-conversation-button"
    );

const resolutionBanner =
    document.getElementById(
        "resolution-banner"
    );

const resolutionBannerLabel =
    document.getElementById(
        "resolution-banner-label"
    );

const resolutionBannerText =
    document.getElementById(
        "resolution-banner-text"
    );


let conversationId = null;
let isSending = false;


const CONVERSATION_STORAGE_KEY =
    "supportpilot.activeConversationId";

const CUSTOMER_STORAGE_KEY =
    "supportpilot.activeCustomerId";

const LAST_RUN_STORAGE_KEY =
    "supportpilot.lastRunId";


function saveActiveConversation(
    activeConversationId,
    activeCustomerId
) {
    localStorage.setItem(
        CONVERSATION_STORAGE_KEY,
        activeConversationId
    );

    if (activeCustomerId) {
        localStorage.setItem(
            CUSTOMER_STORAGE_KEY,
            activeCustomerId
        );
    } else {
        localStorage.removeItem(
            CUSTOMER_STORAGE_KEY
        );
    }
}


function clearActiveConversation() {
    localStorage.removeItem(
        CONVERSATION_STORAGE_KEY
    );

    localStorage.removeItem(
        CUSTOMER_STORAGE_KEY
    );

    localStorage.removeItem(
        LAST_RUN_STORAGE_KEY
    );
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
        /(^|[^\w])_([^_\n]+)_(?!\w)/g,
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
    let inCodeBlock = false;
    let codeLines = [];


    function flushParagraph() {
        if (
            paragraphLines.length === 0
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


    function flushCodeBlock() {
        blocks.push(
            (
                "<pre><code>"
                + escapeHtml(
                    codeLines.join(
                        "\n"
                    )
                )
                + "</code></pre>"
            )
        );

        codeLines = [];
    }


    lines.forEach(
        (line) => {
            if (
                /^\s*```/.test(
                    line
                )
            ) {
                if (inCodeBlock) {
                    flushCodeBlock();
                    inCodeBlock = false;
                } else {
                    flushParagraph();
                    flushList();
                    inCodeBlock = true;
                    codeLines = [];
                }

                return;
            }

            if (inCodeBlock) {
                codeLines.push(
                    line
                );
                return;
            }

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

                const itemText =
                    unorderedMatch
                        ? unorderedMatch[1]
                        : orderedMatch[1];

                listItems.push(
                    renderInlineMarkdown(
                        itemText
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

    if (inCodeBlock) {
        flushCodeBlock();
    }

    flushParagraph();
    flushList();

    return blocks.join("");
}


function assistantAvatar() {
    const avatar =
        createElement(
            "div",
            "assistant-avatar"
        );

    avatar.innerHTML = `
        <svg viewBox="0 0 24 24" aria-hidden="true">
            <path
                d="M6.5 5.5h11A2.5 2.5 0 0 1 20 8v6.8a2.5 2.5 0 0 1-2.5 2.5H13l-3.3 2.4v-2.4H6.5A2.5 2.5 0 0 1 4 14.8V8a2.5 2.5 0 0 1 2.5-2.5Z"
                fill="currentColor"
            />
            <circle cx="8.5" cy="11.2" r="1" fill="white" />
            <circle cx="12" cy="11.2" r="1" fill="white" />
            <circle cx="15.5" cy="11.2" r="1" fill="white" />
        </svg>
    `;

    return avatar;
}


function copyButton(
    message
) {
    const button =
        createElement(
            "button",
            "copy-response"
        );

    button.type =
        "button";

    button.innerHTML = `
        <svg viewBox="0 0 18 18" aria-hidden="true">
            <rect
                x="5.5"
                y="5.5"
                width="8"
                height="8"
                rx="1.5"
                fill="none"
                stroke="currentColor"
                stroke-width="1.3"
            />
            <path
                d="M4 11.5H3.5A1.5 1.5 0 0 1 2 10V4.5A1.5 1.5 0 0 1 3.5 3H9a1.5 1.5 0 0 1 1.5 1.5V5"
                fill="none"
                stroke="currentColor"
                stroke-width="1.3"
                stroke-linecap="round"
            />
        </svg>
        <span>Copy</span>
    `;

    button.addEventListener(
        "click",
        async () => {
            try {
                await navigator.clipboard.writeText(
                    message
                );

                const label =
                    button.querySelector(
                        "span"
                    );

                label.textContent =
                    "Copied";

                window.setTimeout(
                    () => {
                        label.textContent =
                            "Copy";
                    },
                    1200
                );

            } catch (_error) {
                const label =
                    button.querySelector(
                        "span"
                    );

                label.textContent =
                    "Copy failed";
            }
        }
    );

    return button;
}


function scrollChatToBottom() {
    requestAnimationFrame(
        () => {
            window.scrollTo({
                top:
                    document
                    .documentElement
                    .scrollHeight,

                behavior:
                    "smooth",
            });
        }
    );
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

    if (role === "assistant") {
        row.appendChild(
            assistantAvatar()
        );
    }

    const content =
        createElement(
            "div",
            "message-content"
        );

    const meta =
        createElement(
            "div",
            "message-meta"
        );

    const metaName =
        createElement(
            "strong",
            null,
            role === "user"
                ? "You"
                : "SupportPilot"
        );

    const metaDescription =
        createElement(
            "span",
            null,
            role === "user"
                ? "Customer"
                : "AI support agent"
        );

    meta.appendChild(
        metaName
    );

    meta.appendChild(
        metaDescription
    );

    const bubble =
        createElement(
            "div",
            "message-bubble"
        );

    if (role === "assistant") {
        bubble.classList.add(
            "markdown-content"
        );

        bubble.innerHTML =
            renderSafeMarkdown(
                message
            );

    } else {
        bubble.textContent =
            message;
    }

    content.appendChild(
        meta
    );

    content.appendChild(
        bubble
    );

    if (role === "assistant") {
        const actions =
            createElement(
                "div",
                "message-actions"
            );

        actions.appendChild(
            copyButton(
                message
            )
        );

        content.appendChild(
            actions
        );

    } else {
        const avatar =
            createElement(
                "div",
                "user-avatar",
                "YOU"
            );

        row.appendChild(
            content
        );

        row.appendChild(
            avatar
        );

        chatMessages.appendChild(
            row
        );

        scrollChatToBottom();

        return row;
    }

    row.appendChild(
        content
    );

    chatMessages.appendChild(
        row
    );

    scrollChatToBottom();

    return row;
}


function resetChatToWelcome() {
    chatMessages.replaceChildren();

    addMessage(
        "assistant",
        (
            "Hi! I’m SupportPilot. What can I help "
            + "you with today?"
        )
    );
}


function addLoadingMessage() {
    const row =
        createElement(
            "div",
            "message-row assistant loading"
        );

    row.id =
        "loading-message";

    row.appendChild(
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
            "message-meta"
        );

    meta.appendChild(
        createElement(
            "strong",
            null,
            "SupportPilot"
        )
    );

    meta.appendChild(
        createElement(
            "span",
            null,
            "Investigating"
        )
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
        meta
    );

    content.appendChild(
        bubble
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

    const buttonLabel =
        sendButton.querySelector(
            "span"
        );

    if (buttonLabel) {
        buttonLabel.textContent =
            sending
                ? "Working"
                : "Send";
    }
}


function setSessionState(
    state
) {
    if (!sessionStateLabel) {
        return;
    }

    const labels = {
        new:
            "New session",

        active:
            "Active session",

        restored:
            "Restored session",
    };

    sessionStateLabel.textContent =
        labels[state]
        || state;
}


function clearResolutionBanner() {
    if (!resolutionBanner) {
        return;
    }

    resolutionBanner.hidden =
        true;

    resolutionBanner.dataset.status =
        "";

    resolutionBannerLabel.textContent =
        "";

    resolutionBannerText.textContent =
        "";
}


function renderResolutionBanner(
    resolution
) {
    if (
        !resolutionBanner
        || !resolution
        || !resolution.resolution_status
    ) {
        clearResolutionBanner();
        return;
    }

    const labels = {
        RESOLVED:
            "Resolved",

        NEEDS_INFORMATION:
            "More information needed",

        UNRESOLVED:
            "Investigation incomplete",

        ESCALATION_REQUIRED:
            "Support review required",
    };

    resolutionBanner.dataset.status =
        resolution.resolution_status;

    resolutionBannerLabel.textContent =
        labels[
            resolution.resolution_status
        ]
        || "Support status";

    resolutionBannerText.textContent =
        resolution.summary
        || "";

    resolutionBanner.hidden =
        false;
}


async function restoreConversation() {
    const storedConversationId =
        localStorage.getItem(
            CONVERSATION_STORAGE_KEY
        );

    if (!storedConversationId) {
        setSessionState(
            "new"
        );

        return;
    }

    const storedCustomerId =
        localStorage.getItem(
            CUSTOMER_STORAGE_KEY
        );

    if (storedCustomerId) {
        customerIdInput.value =
            storedCustomerId;
    }

    const queryString =
        storedCustomerId
            ? (
                "?customer_id="
                + encodeURIComponent(
                    storedCustomerId
                )
            )
            : "";

    try {
        const response =
            await fetch(
                (
                    "/api/v1/support/conversations/"
                    + encodeURIComponent(
                        storedConversationId
                    )
                    + queryString
                )
            );

        const data =
            await response.json();

        if (!response.ok) {
            if (
                response.status === 404
                || response.status === 403
            ) {
                clearActiveConversation();

                conversationId =
                    null;

                conversationIdDisplay.textContent =
                    "New";

                setSessionState(
                    "new"
                );

                clearResolutionBanner();

                resetChatToWelcome();

                return;
            }

            throw new Error(
                data.detail
                || "Conversation restoration failed."
            );
        }

        conversationId =
            data.conversation_id;

        conversationIdDisplay.textContent =
            conversationId;

        setSessionState(
            "restored"
        );

        if (data.customer_id) {
            customerIdInput.value =
                data.customer_id;

            localStorage.setItem(
                CUSTOMER_STORAGE_KEY,
                data.customer_id
            );
        }

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
                            storedMessage.content
                        );
                    }
                }
            );

        } else {
            resetChatToWelcome();
        }

        if (data.resolution_status) {
            renderResolutionBanner({
                resolution_status:
                    data.resolution_status,

                summary:
                    data.current_issue
                    ? (
                        "Previous support outcome: "
                        + data.current_issue
                    )
                    : (
                        "Previous support outcome "
                        + "restored."
                    ),
            });

        } else {
            clearResolutionBanner();
        }

    } catch (error) {
        console.error(
            "Conversation restoration failed.",
            error
        );
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
                "system-pill online";

            statusText.textContent =
                "System online";

            return;
        }

        systemStatus.className =
            "system-pill offline";

        statusText.textContent =
            "System degraded";

    } catch (_error) {
        systemStatus.className =
            "system-pill offline";

        statusText.textContent =
            "System offline";
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

        saveActiveConversation(
            conversationId,
            customerId
        );

        conversationIdDisplay.textContent =
            conversationId;

        setSessionState(
            "active"
        );

        if (data.run_id) {
            localStorage.setItem(
                LAST_RUN_STORAGE_KEY,
                data.run_id
            );
        }

        addMessage(
            "assistant",
            data.response
        );

        renderResolutionBanner(
            data.resolution
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
                    118
                )
                + "px"
            );
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

        clearActiveConversation();

        conversationIdDisplay.textContent =
            "New";

        setSessionState(
            "new"
        );

        clearResolutionBanner();

        resetChatToWelcome();

        messageInput.value =
            "";

        messageInput.focus();
    }
);


checkHealth();
restoreConversation();
