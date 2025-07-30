import asyncio
import httpx
from sqlalchemy.orm import Session
from database import SessionLocal
import crud
import time

async def check_url(client: httpx.AsyncClient, url_record: crud.models.URL, db: Session):
    start_time = time.time()
    try:
        response = await client.get(url_record.url, timeout=10, follow_redirects=True)
        response.raise_for_status()
        
        response_time = (time.time() - start_time) * 1000
        crud.create_log_and_update_stats(
            db=db,
            url_id=url_record.id,
            is_up=True,
            status_code=response.status_code,
            response_time=response_time
        )
        print(f"SUCCESS: {url_record.url} - Status: {response.status_code}")

    except httpx.HTTPStatusError as e:
        response_time = (time.time() - start_time) * 1000
        crud.create_log_and_update_stats(
            db=db,
            url_id=url_record.id,
            is_up=False,
            status_code=e.response.status_code,
            response_time=response_time,
            error=f"HTTP Error: {e.response.status_code}"
        )
        print(f"FAIL: {url_record.url} - Status: {e.response.status_code}")

    except httpx.RequestError as e:
        crud.create_log_and_update_stats(
            db=db,
            url_id=url_record.id,
            is_up=False,
            error=f"Request Error: {type(e).__name__}"
        )
        print(f"FAIL: {url_record.url} - Error: {type(e).__name__}")


async def main():
    print("Starting URL check cycle...")
    db = SessionLocal()
    try:
        urls_to_check = crud.get_all_urls(db)
        if not urls_to_check:
            print("No URLs to check. Exiting.")
            return

        async with httpx.AsyncClient() as client:
            tasks = [check_url(client, url, db) for url in urls_to_check]
            await asyncio.gather(*tasks)

    finally:
        db.close()
    print("URL check cycle finished.")


if __name__ == "__main__":
    asyncio.run(main())