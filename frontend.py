import gradio as gr
import uuid

from backend import (
    start_chat,
    stream_chat,
    list_conversations,
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

    return list_uploaded_documents_impl(
        session_id=session_id,
    )


def uploaded_repositories(
    session_id,
):

    return list_repositories(
        session_id=session_id,
    )
# ---------------------------------------------------
# UI
# ---------------------------------------------------

with gr.Blocks(
    title="Rune",
    theme=DARK_THEME,
) as demo:

    # ---------------------------------------------------
    # Application State
    # ---------------------------------------------------

    session_id = gr.State()

    thread_id = gr.State()

    permission_state = gr.State(False)

    current_theme = gr.State("dark")

    active_workspace = gr.State("conversation")

    # ---------------------------------------------------
    # Main Layout
    # ---------------------------------------------------

    with gr.Column():

        # ---------------------------------------------------
        # Top Bar
        # ---------------------------------------------------

        with gr.Row():

            title = gr.Markdown(
                "# Rune"
            )

            with gr.Row():

                theme_toggle = gr.Radio(
                    choices=[
                        "Dark",
                        "Light",
                    ],
                    value="Dark",
                    show_label=False,
                    interactive=True,
                    scale=1,
                )

                settings_btn = gr.Button(
                    "Settings",
                    variant="secondary",
                    scale=0,
                )

                new_chat_btn = gr.Button(
                    "New Chat",
                    variant="secondary",
                    scale=0,
                )

        
        # ---------------------------------------------------
        # Chat Area
        # ---------------------------------------------------

        welcome = gr.Column(
            visible=True,
        )

        with welcome:

            gr.Markdown(
                "# What would you like Rune to do today?"
            )

        chatbot = gr.Chatbot(
            label="",
            visible=False,
            height=620,
            bubble_full_width=False,
            show_copy_button=True,
        )

        # ---------------------------------------------------
        # Input
        # ---------------------------------------------------

        with gr.Row():

            message = gr.Textbox(
                placeholder="Ask Rune anything...",
                show_label=False,
                lines=1,
                scale=12,
            )

            send_btn = gr.Button(
                "Send",
                variant="primary",
                scale=1,
            )

        status = gr.Markdown(
            "",
            visible=False,
        )

        # ---------------------------------------------------
        # Workspace Tabs
        # ---------------------------------------------------

        with gr.Row():

            conversation_tab = gr.Button(
                "Conversation",
                variant="secondary",
            )

            documents_tab = gr.Button(
                "Documents",
                variant="secondary",
            )

            repositories_tab = gr.Button(
                "Repositories",
                variant="secondary",
            )

            memory_tab = gr.Button(
                "Rune Memory",
                variant="secondary",
            ) 

        # ---------------------------------------------------
        # Workspace
        # ---------------------------------------------------

        conversation_workspace = gr.Column(
            visible=True,
        )

        with conversation_workspace:

            conversation_search = gr.Textbox(
                placeholder="Search conversations...",
                show_label=False,
            )

            conversation_list = gr.Radio(
                choices=[],
                show_label=False,
                interactive=True,
            )

        documents_workspace = gr.Column(
            visible=False,
        )

        with documents_workspace:

            gr.Markdown(
                "### Documents"
            )

            document_list = gr.Radio(
                choices=[],
                label="Documents",
                interactive=True,
            )

            upload = gr.File(
                label="Drag & Drop Document",
                file_count="single",
            )

        repositories_workspace = gr.Column(
            visible=False,
        )

        with repositories_workspace:

            gr.Markdown(
                "### Repositories"
            )

            repository_list = gr.Radio(
                choices=[],
                label="Repositories",
                interactive=True,
            )

            repository_url = gr.Textbox(
                placeholder="https://github.com/user/repository",
                show_label=False,
            )

            upload_repository_btn = gr.Button(
                "Add Repository",
                variant="primary",
            )

        memory_workspace = gr.Column(
            visible=False,
        )

        with memory_workspace:

            name_box = gr.Textbox(
                label="Name",
            )

            preferences_box = gr.Textbox(
                label="Preferences",
                lines=2,
            )

            skills_box = gr.Textbox(
                label="Skills",
                lines=2,
            )

            projects_box = gr.Textbox(
                label="Projects",
                lines=2,
            )

            other_box = gr.Textbox(
                label="Other",
                lines=3,
            )

            with gr.Row():

                edit_memory_btn = gr.Button(
                    "Edit",
                    variant="secondary",
                )

                save_memory_btn = gr.Button(
                    "Save",
                    variant="primary",
                )

            add_memory_btn = gr.Button(
                "Add Memory",
            )

        # ---------------------------------------------------
        # Settings Panel
        # ---------------------------------------------------

        settings_panel = gr.Column(
            visible=False,
        )

        with settings_panel:

            gr.Markdown(
                "## Settings"
            )

            theme_selector = gr.Radio(
                choices=[
                    "Dark",
                    "Light",
                ],
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
    # Workspace Navigation
    # ---------------------------------------------------

    def show_conversation():

        return (
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
        )


    def show_documents():

        return (
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(visible=False),
        )


    def show_repositories():

        return (
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=False),
        )


    def show_memory():

        return (
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=True),
        )

    conversation_tab.click(
        fn=show_conversation,
        outputs=[
            conversation_workspace,
            documents_workspace,
            repositories_workspace,
            memory_workspace,
        ],
    )

    documents_tab.click(
        fn=show_documents,
        outputs=[
            conversation_workspace,
            documents_workspace,
            repositories_workspace,
            memory_workspace,
        ],
    )

    repositories_tab.click(
        fn=show_repositories,
        outputs=[
            conversation_workspace,
            documents_workspace,
            repositories_workspace,
            memory_workspace,
        ],
    )

    memory_tab.click(
        fn=show_memory,
        outputs=[
            conversation_workspace,
            documents_workspace,
            repositories_workspace,
            memory_workspace,
        ],
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
        fn=list_conversations,
        inputs=[
            session_id,
        ],
        outputs=[
            conversation_list,
        ],
)

    message.submit(
        fn=hide_home,
        outputs=[
            welcome,
            chatbot,
        ],
    ).then(
        fn=list_conversations,
        inputs=[
            session_id,
        ],
        outputs=[
            conversation_list,
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
    ).then(
        fn=list_conversations,
        inputs=[
            session_id,
    ],
        outputs=[
            conversation_list,
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
        outputs=[
            status,
        ],

    ).then(
        fn=uploaded_docs,
        inputs=[
            session_id,
    ],
        outputs=[
            document_list,
    ],
)
    upload_repository_btn.click(
        fn=upload_repository,
        inputs=[
            session_id,
            repository_url,
    ],
        outputs=[
            status,
    ],
    ).then(
        fn=uploaded_repositories,
        inputs=[
            session_id,
    ],
        outputs=[
            repository_list,
    ],
)
    demo.load(
        fn=initialize,
        outputs=[
            session_id,
            thread_id,
            chatbot,
            welcome,
        ],
    ).then(
        fn=uploaded_docs,
        inputs=[
            session_id,
        ],
        outputs=document_list,
    ).then(
        fn=uploaded_repositories,
        inputs=[
            session_id,
        ],
        outputs=repository_list,
    ).then(
        fn=list_conversations,
        inputs=[
            session_id,
    ],
        outputs=[
            conversation_list,
    ],  
)
   
# ---------------------------------------------------
# Suggested Actions
# ---------------------------------------------------
