from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import auth, contacts, groups, invoices, sales, system, users

app = FastAPI()

# CORS Configuration
origins = [
    "http://192.168.10.200:4321",
    "http://192.168.10.200:8000",
    "http://localhost:4321",
    "https://maplenet-api.com",
    "https://maplenet.com.bo",
    "http://192.168.10.227",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(contacts.router)
app.include_router(sales.router)
app.include_router(system.router)
app.include_router(users.router)
app.include_router(groups.router)
app.include_router(invoices.router)