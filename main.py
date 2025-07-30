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

from . import crud, models
from .database import engine, get_db, SessionLocal

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Uptime Monitor")

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

CHECKER_SECRET_TOKEN = os.getenv("CHECKER_SECRET_TOKEN")

async def check_single_url(url_record: models.URL):
    db = SessionLocal()
    start_time = time.time()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url_record.url, timeout=10, follow_redirects=True)
            response.raise_for_status()
            
            response_time = (time.time() - start_time) * 1000
            crud.create_log_and_update_stats(db=db, url_id=url_record.id, is_up=True, status_code=response.status_code, response_time=response_time)
    except httpx.HTTPStatusError as e:
        response_time = (time.time() - start_time) * 1000
        crud.create_log_and_update_stats(db=db, url_id=url_record.id, is_up=False, status_code=e.response.status_code, response_time=response_time, error=f"HTTP Error: {e.response.status_code}")
    except httpx.RequestError as e:
        crud.create_log_and_update_stats(db=db, url_id=url_record.id, is_up=False, error=f"Request Error: {type(e).__name__}")
    finally:
        db.close()

async def run_all_checks():
    db = SessionLocal()
    try:
        urls_to_check = crud.get_all_urls(db)
        if not urls_to_check:
            print("No URLs to check.")
            return
        
        tasks = [check_single_url(url) for url in urls_to_check]
        await asyncio.gather(*tasks)
        print(f"Check cycle finished for {len(urls_to_check)} URLs.")
    finally:
        db.close()

@app.get("/", response_class=HTMLResponse)
def read_root(request: Request, db: Session = Depends(get_db)):
    urls = crud.get_all_urls(db)
    flash_message = request.session.pop('flash_message', None)
    flash_error = request.session.pop('flash_error', None)
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "urls": urls,
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