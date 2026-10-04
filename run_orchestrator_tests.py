import asyncio

# Import the orchestrator scenario runner
from app.orchestrator.test_20_scenarios import run_tests

if __name__ == "__main__":
    # Execute the async test suite
    asyncio.run(run_tests())
