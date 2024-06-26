import asyncio

def func_sync():
    return 25

async def func_async():
    return await 
    

asyncio.run(func_async())

print(func_sync())