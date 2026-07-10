from frontend import demo
from backend import startup, shutdown
import asyncio

if __name__ == "__main__":

    asyncio.run(startup())

    try:
        demo.launch(
            server_name="0.0.0.0",
            server_port=7860,
            share=False,
        )
    finally:
        asyncio.run(shutdown())
        