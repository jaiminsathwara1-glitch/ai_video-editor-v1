#!/usr/bin/env python
"""
Root entry point — run with: python main.py
Or via uvicorn: uvicorn app.main:app --reload
"""
import uvicorn
from app.config import get_settings

settings = get_settings()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
        access_log=True,
        # For production: use multiple workers
        # workers=4,
    )
