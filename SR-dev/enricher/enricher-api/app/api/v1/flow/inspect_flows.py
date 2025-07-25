import asyncio
from prefect.client.orchestration import get_client

async def inspect_flow_run(run_id: str):
    async with get_client() as client:
        run = await client.read_flow_run(run_id)
        print("Flow Run ID:", run.id)
        print("State:", run.state.name)
        print("Parameters:")
        for key, value in run.parameters.items():
            print(f"  {key}: {value}")

# Replace with your actual flow run ID
asyncio.run(inspect_flow_run("55372225-ade0-4a71-88bd-a272c5dc7f10" ))