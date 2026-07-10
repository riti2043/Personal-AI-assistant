import asyncio

from frontend import demo
from backend import startup


# Initialize backend services
asyncio.run(startup())


# Launch Gradio
demo.launch(
    server_name="0.0.0.0",
    server_port=7860,
    share=False,
)