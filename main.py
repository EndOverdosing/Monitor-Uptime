from fastapi import FastAPI, Request, Form, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pydantic import HttpUrl
from starlette.middleware.sessions import SessionMiddleware

from . import crud, models
from .database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Uptime Monitor")

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

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
    
    return templates.TemplateResponse("details.html", {
        "request": request,
        "url": db_url,
        "logs": logs
    })

app.add_middleware(SessionMiddleware, secret_key="a_very_secret_key_change_me_in_production")