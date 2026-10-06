import os

from dotenv import load_dotenv

from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel

from rag.rag_pipeline import ask_sies_gpt

load_dotenv()


app = FastAPI(title="SIES GPT API")


# -----------------------------------------
# CORS
# -----------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -----------------------------------------
# Request model
# -----------------------------------------


class ChatRequest(BaseModel):

    message: str


# -----------------------------------------
# Root
# -----------------------------------------


@app.get("/")
def root():

    return {"message": "SIES GPT backend is running"}


# -----------------------------------------
# RAG Chat
# -----------------------------------------


@app.post("/chat")
def chat(request: ChatRequest):

    result = ask_sies_gpt(request.message)

    return result

class SIESChatRequest(BaseModel):
    message: str
