import os
import asyncio
import httpx
import time
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pydantic import HttpUrl
from starlette.middleware.sessions import SessionMiddleware

import crud
import models
from database import engine, get_db, SessionLocal

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Uptime Monitor")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

CHECKER_SECRET_TOKEN = os.getenv("CHECKER_SECRET_TOKEN")

async def check_single_url(db: Session, url_record: models.URL):

    print(f"--- Checking URL ID: {url_record.id}, URL: {url_record.url} ---")
    start_time = time.time()
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=10) as client:
            response = await client.get(url_record.url)
            response.raise_for_status()
            response_time = (time.time() - start_time) * 1000

            print(f"SUCCESS: URL ID {url_record.id} is UP. Status: {response.status_code}. Writing to DB.")
            crud.create_log_and_update_stats(db=db, url_id=url_record.id, is_up=True, status_code=response.status_code, response_time=response_time)
    except httpx.HTTPStatusError as e:
        response_time = (time.time() - start_time) * 1000

        print(f"ERROR: URL ID {url_record.id} is DOWN. HTTP Status Error: {e.response.status_code}. Writing to DB.")
        crud.create_log_and_update_stats(db=db, url_id=url_record.id, is_up=False, status_code=e.response.status_code, response_time=response_time, error=f"HTTP Error: {e.response.status_code}")
    except httpx.RequestError as e:

        print(f"ERROR: URL ID {url_record.id} is DOWN. Request Error: {type(e).__name__}. Writing to DB.")
        crud.create_log_and_update_stats(db=db, url_id=url_record.id, is_up=False, error=f"Request Error: {type(e).__name__}")

    print(f"--- Finished checking URL ID: {url_record.id} ---")

async def run_all_checks():

    print("====== TRIGGERING A NEW CHECK CYCLE ======")
    db = SessionLocal()
    try:
        urls_to_check = crud.get_all_urls(db)
        if not urls_to_check:
            print("No URLs in the database to check.")
            return

        print(f"Found {len(urls_to_check)} URLs to check.")
        tasks = [check_single_url(db, url) for url in urls_to_check]
        await asyncio.gather(*tasks)
        print("====== CHECK CYCLE FINISHED ======")
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host
    urls = crud.get_all_urls(db)
    flash_message = request.session.pop('flash_message', None)
    flash_error = request.session.pop('flash_error', None)

    return templates.TemplateResponse("index.html", {
        "request": request,
        "urls": urls,
        "client_ip": client_ip,
        "flash_message": flash_message,
        "flash_error": flash_error
    })

@app.post("/submit-url", response_class=RedirectResponse)
async def submit_url(request: Request, url: str = Form(...), db: Session = Depends(get_db)):
    client_ip = request.client.host
    try:
        HttpUrl(url)
    except Exception:
        request.session['flash_error'] = "Invalid URL format submitted."
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    if crud.get_url_by_ip(db, ip=client_ip):
        request.session['flash_error'] = "An IP address can only monitor one URL at a time."
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    if crud.get_url_by_url_string(db, url=url):
        request.session['flash_error'] = "This URL is already being monitored."
        return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
    crud.create_url(db=db, url=url, ip=client_ip)
    request.session['flash_message'] = f"Successfully added {url} for monitoring!"
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)

@app.post("/urls/{url_id}/delete", response_class=RedirectResponse)
def delete_url(request: Request, url_id: int, db: Session = Depends(get_db)):
    client_ip = request.client.host
    db_url = crud.delete_url_by_id_and_ip(db=db, url_id=url_id, ip=client_ip)
    if db_url is None:
        request.session['flash_error'] = "Could not delete URL. It might not exist or you may not be the owner."
    else:
        request.session['flash_message'] = f"Successfully stopped monitoring {db_url.url}. You can now add a new one."
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/urls/{url_id}", response_class=HTMLResponse)
def read_url_details(request: Request, url_id: int, db: Session = Depends(get_db)):
    db_url = crud.get_url_by_id(db, url_id=url_id)
    if db_url is None:
        raise HTTPException(status_code=404, detail="URL not found")
    logs = crud.get_logs_for_url(db, url_id=url_id, limit=100)
    return templates.TemplateResponse("details.html", {"request": request, "url": db_url, "logs": logs})

@app.post("/run-check/{secret_token}")
def trigger_check(secret_token: str, background_tasks: BackgroundTasks):
    if not CHECKER_SECRET_TOKEN or secret_token != CHECKER_SECRET_TOKEN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret token")
    background_tasks.add_task(run_all_checks)
    return JSONResponse(content={"message": "Check cycle triggered successfully in the background."})

app.add_middleware(SessionMiddleware, secret_key="a_very_secret_key_change_me_in_production")