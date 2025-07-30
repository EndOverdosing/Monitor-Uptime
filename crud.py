from sqlalchemy.orm import Session
from . import models

def get_url_by_ip(db: Session, ip: str):
    return db.query(models.URL).filter(models.URL.submitted_by_ip == ip).first()

def get_url_by_url_string(db: Session, url: str):
    return db.query(models.URL).filter(models.URL.url == url).first()

def get_all_urls(db: Session):
    return db.query(models.URL).order_by(models.URL.created_at.desc()).all()

def get_url_by_id(db: Session, url_id: int):
    return db.query(models.URL).filter(models.URL.id == url_id).first()

def create_url(db: Session, url: str, ip: str):
    db_url = models.URL(url=url, submitted_by_ip=ip)
    db.add(db_url)
    db.commit()
    db.refresh(db_url)
    return db_url

def create_log_and_update_stats(db: Session, url_id: int, is_up: bool, status_code: int = None, response_time: float = None, error: str = None):
    db_url = db.query(models.URL).filter(models.URL.id == url_id).with_for_update().first()
    if not db_url:
        return

    db_log = models.Log(
        url_id=url_id,
        is_up=is_up,
        status_code=status_code,
        response_time_ms=response_time,
        error_message=error,
    )
    db.add(db_log)

    db_url.last_status_code = status_code
    if is_up:
        db_url.uptime_count += 1
    else:
        db_url.downtime_count += 1
    
    db.commit()

def get_logs_for_url(db: Session, url_id: int, limit: int = 100):
    return db.query(models.Log).filter(models.Log.url_id == url_id).order_by(models.Log.timestamp.desc()).limit(limit).all()