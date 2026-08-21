import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai


load_dotenv()

app = FastAPI(title="SIES GPT API")


# Allow React frontend to communicate with FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)


class ChatRequest(BaseModel):
    message: str


@app.get("/")
def root():
    return {
        "message": "SIES GPT backend is running"
    }


@app.post("/chat")
def chat(request: ChatRequest):

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=request.message
    )

    return {
        "answer": response.text
    }