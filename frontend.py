import gradio as gr
import uuid

from backend import (
    start_chat,
    chat,
    stream_chat,
    resume_after_permission,
    list_conversations,
    list_memories,
)

from tools import (
    upload_document_impl,
    list_uploaded_documents_impl,
    upload_repository,
    list_repositories,
)
# ---------------------------------------------------
# Theme
# ---------------------------------------------------

LIGHT_THEME = gr.themes.Soft(
    primary_hue="gray",
    secondary_hue="gray",
    neutral_hue="gray",
    radius_size="lg",
)

DARK_THEME = gr.themes.Base(
    primary_hue="gray",
    secondary_hue="gray",
    neutral_hue="gray",
    radius_size="lg",
)


# ---------------------------------------------------
# Helpers
# ---------------------------------------------------

def initialize():

    session_id = str(uuid.uuid4())

    thread_id = start_chat(
        session_id=session_id,
    )

    return (
        session_id,
        thread_id,
        [],
        gr.update(visible=True),
    )


def send_message(
    message,
    history,
    session_id,
    thread_id,
):

    if not message.strip():

        yield history, ""

        return

    history.append(
        (
            message,
            "",
        )
    )

    yield history, ""

    response = ""

    for partial in stream_chat(
        session_id=session_id,
        thread_id=thread_id,
        user_input=message,
    ):

        response = partial

        history[-1] = (
            message,
            response,
        )

        yield history, ""

def clear_chat(
    session_id,
):

    thread_id = start_chat(
        session_id=session_id,
    )

    return (
        [],
        "",
        thread_id,
    )


def uploaded_docs(
    session_id,
):

    documents = list_uploaded_documents_impl(
        session_id=session_id,
    )

    return "\n".join(documents)


def uploaded_repositories(
    session_id,
):

    repositories = list_repositories(
        session_id=session_id,
    )

    if not repositories:
        return ""

    return "\n".join(repositories)


# ---------------------------------------------------
# UI
# ---------------------------------------------------

with gr.Blocks(
    title="Rune",
    theme=DARK_THEME,
) as demo:
    session_id = gr.State()

    thread_id = gr.State()

    permission_state = gr.State(False)

    current_theme = gr.State("dark")

    with gr.Row():

        # ------------------------------------------
        # Sidebar
        # ------------------------------------------

        with gr.Column(
            scale=1,
            min_width=230,
        ) as sidebar:

            gr.Markdown(
                "## Rune"
            )

            new_chat_btn = gr.Button(
                "＋ New Chat",
                variant="secondary",
            )

            gr.Markdown(
                "### Conversations"
            )

            conversation_list = gr.Radio(
                choices=[],
                interactive=True,
                show_label=False,
            )

            gr.Markdown(
                "### Upload Document"
            )

            upload = gr.File(
                file_count="single",
                label="Drag & Drop",
            )

            document_list = gr.Textbox(
                label="Indexed Documents",
                interactive=False,
                lines=8,
            )

            settings_btn = gr.Button(
                "Settings",
            )

        # ------------------------------------------
        # Main Workspace

        # ------------------------------------------

        with gr.Column(scale=5):

            with gr.Row():

                gr.Markdown("# Rune")

                theme_toggle = gr.Button(
                    "🌙",
                    size="sm",
                )
            # ------------------------------------------
            # Home / Chat Area
            # ------------------------------------------

            welcome = gr.Column(visible=True)

            with welcome:

                gr.Markdown(
                    """
                    # What would you like Rune to do?
                    """
                )

                with gr.Row():

                    github_card = gr.Button(
                        "Open a Repository",
                        variant="secondary",
                    )

                    pdf_card = gr.Button(
                        "Summarize a PDF",
                        variant="secondary",
                    )

                    search_card = gr.Button(
                        "Search the Web",
                        variant="secondary",
                    )

                with gr.Row():

                    email_card = gr.Button(
                        "Read my Emails",
                        variant="secondary",
                    )

                    calendar_card = gr.Button(
                        "Plan my Day",
                        variant="secondary",
                    )

                    docs_card = gr.Button(
                        "Explore Documents",
                        variant="secondary",
                    )

            chatbot = gr.Chatbot(
                label="",
                visible=False,
                height=620,
                bubble_full_width=False,
                show_copy_button=True,
            )

            # ------------------------------------------
            # Input
            # ------------------------------------------

            with gr.Row():

                message = gr.Textbox(
                    placeholder="Ask Rune anything...",
                    show_label=False,
                    lines=1,
                    scale=12,
                )

                attach_btn = gr.UploadButton(
                    "📎",
                    file_count="single",
                    scale=1,
                )

                send_btn = gr.Button(
                    "➜",
                    variant="primary",
                    scale=1,
                )

            status = gr.Markdown(
                "",
                visible=False,
            )

    # ---------------------------------------------------
    # Permission Dialog
    # ---------------------------------------------------

    with gr.Group(
        visible=False,
    ) as permission_popup:

        gr.Markdown(
            "## Permission Required"
        )

        permission_action = gr.Textbox(
            label="Action",
            interactive=False,
        )

        permission_target = gr.Textbox(
            label="Target",
            interactive=False,
        )

        permission_reason = gr.Textbox(
            label="Reason",
            interactive=False,
            lines=3,
        )

        remember_permission = gr.Checkbox(
            label="Remember for this session",
        )

        with gr.Row():

            deny_btn = gr.Button(
                "Deny",
                variant="secondary",
            )

            approve_btn = gr.Button(
                "Approve",
                variant="primary",
            )

    # ---------------------------------------------------
    # Settings Dialog
    # ---------------------------------------------------

    with gr.Group(
        visible=False,
    ) as settings_panel:

        gr.Markdown(
            "## Settings"
        )

        theme_selector = gr.Radio(
            choices=["Dark", "Light"],
            value="Dark",
            label="Theme",
        )

        clear_history_btn = gr.Button(
            "Clear Current Conversation",
            variant="secondary",
        )                
# ---------------------------------------------------
# Home → Chat Transition
# ---------------------------------------------------

    def hide_home():

        return (
            gr.update(visible=False),
            gr.update(visible=True),
        )

# ---------------------------------------------------
# Backend Wiring
# ---------------------------------------------------

    send_event = send_btn.click(
         fn=hide_home,
    outputs=[
        welcome,
        chatbot,
    ],
    ).then(
        fn=send_message,
        inputs=[
            message,
            chatbot,
            session_id,
            thread_id,
        ],
        outputs=[
            chatbot,
            message,
        ],
    )

    message.submit(
        fn=hide_home,
    outputs=[
        welcome,
        chatbot,
    ],
    ).then(
        fn=send_message,
        inputs=[
            message,
            chatbot,
            session_id,
            thread_id,
        ],
        outputs=[
            chatbot,
            message,
        ],
    )

    new_chat_btn.click(
        fn=clear_chat,
         inputs=[
        session_id,
    ],
        outputs=[
            chatbot,
            message,
            thread_id,
        ],
    )

    clear_history_btn.click(
        fn=clear_chat,
        inputs=[
            session_id,
        ],
        outputs=[
            chatbot,
            message,
            thread_id,
        ],
    )

# ---------------------------------------------------
# Upload
# ---------------------------------------------------

    upload.upload(
        fn=upload_document_impl,
        inputs=[
        session_id,
        upload,
    ],
        outputs=status,
    )
    demo.load(
        fn=initialize,
        outputs=[
        session_id,
        thread_id,
        chatbot,
        welcome,
    ],
    )

    attach_btn.upload(
        fn=upload_document_impl,
        inputs=[
        session_id,
        upload,
    ],
        outputs=status,
    )

    upload.upload(
        fn=uploaded_docs,
        inputs=[
        session_id,
        upload,
    ], 
        outputs=document_list,
    )

    attach_btn.upload(
        fn=uploaded_docs,
        inputs=[
        session_id,
        upload,
    ],
        outputs=document_list,
    )

# ---------------------------------------------------
# Suggested Actions
# ---------------------------------------------------

    github_card.click(
        lambda: "Open my GitHub repository.",
        outputs=message,
    )

    pdf_card.click(
        lambda: "Summarize this document.",
        outputs=message,
    )

    search_card.click(
        lambda: "Search the web.",
        outputs=message,
    )

    email_card.click(
        lambda: "Read my latest emails.",
        outputs=message,
    )

    calendar_card.click(
        lambda: "Plan my schedule today.",
        outputs=message,
    )

    docs_card.click(
        lambda: "Search my uploaded documents.",
        outputs=message,
    )        