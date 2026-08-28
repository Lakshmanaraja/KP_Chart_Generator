from fastapi import FastAPI,HTTPException
from fastapi.middleware.cors import CORSMiddleware

from routers.chart import router as chart_router
from routers.btr import router as btr_router
from routers.dasa import router as dasa_router
from routers.transit import router as transit_router
from routers.find_patterns import router as find_patterns_router

# from dotenv import load_dotenv

# load_dotenv()

app = FastAPI() 


# --- CORS for Lovable frontend ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # later restrict to your Lovable domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chart_router)
app.include_router(btr_router)
app.include_router(dasa_router)
app.include_router(transit_router)
app.include_router(find_patterns_router)


@app.get("/")
def home():
    return {"message": "KP API running!"}







