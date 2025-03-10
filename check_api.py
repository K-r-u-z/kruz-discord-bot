import aiohttp
import asyncio
from config import TOKEN

async def check_api_status():
    async with aiohttp.ClientSession() as session:
        headers = {'Authorization': f'Bot {TOKEN}'}
        try:
            async with session.get('https://discord.com/api/v10/users/@me', headers=headers) as response:
                if response.status == 200:
                    print("✅ API is accessible! Block has been lifted.")
                    return True
                elif response.status == 429:
                    retry_after = int(response.headers.get('Retry-After', 0))
                    print(f"❌ Still rate limited. Retry after {retry_after} seconds")
                    return False
                else:
                    print(f"❌ API returned status code: {response.status}")
                    return False
        except Exception as e:
            print(f"❌ Error checking API: {e}")
            return False

if __name__ == "__main__":
    asyncio.run(check_api_status()) 