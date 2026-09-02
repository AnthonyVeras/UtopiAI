import asyncio
import sys

if sys.platform == "win32":

    def pytest_asyncio_loop_factories():
        return {"windows-selector": asyncio.SelectorEventLoop}
