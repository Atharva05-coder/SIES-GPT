import asyncio
from rich import print
from typing import Literal
from dotenv import load_dotenv
import os

from openai import AsyncOpenAI
from agents import Agent, Runner, set_tracing_disabled, OpenAIChatCompletionsModel
from pydantic import BaseModel

set_tracing_disabled(True)
load_dotenv()


class Message(BaseModel):
    text: str
    intent: Literal["syllabus", "website", "document"]


agent = Agent(
    "intent_classifier",
    instructions="""You are an intelligent routing agent for SIES GST College. Route the user's question to the correct database by returning the correct intent.

Categories:
1. 'syllabus' - The user is asking about academic courses, curriculum, modules, syllabus content, practicals, textbooks, or credits. This includes core subjects, lab courses, and all elective/minor subjects (e.g. Robotics and Applications, Machine Vision, Data Structures, Computer Networks, IoT, NLP, Cloud Computing, Sensor Technology, Digital Forensics, etc.) or course codes (e.g. CEC501, FEC101, CEPEC6012, CEL402).
2. 'document' - The user is asking about official PDF documents, institutional policies, brochures (e.g. Epsilon), guidelines, internship policies, emergency exits, floor plans, IPR team, accreditation letters (NBA), rules, or circulars.
3. 'website' - The user is asking about faculty profiles, HODs, admissions, fees, placements, recruiters, campus facilities, events, OR any institutional cell/committee/council/club (e.g. IIIC = Industry Institute Interaction Cell, IQAC, TPC, ISTE, NSS, Rotaract, IEEE, CSI, WEP, CDC, alumni, grievance committee, anti-ragging, POSH, etc.). When asking about a teacher, faculty member, or committee, choose 'website'.""",
    model=OpenAIChatCompletionsModel(
        "llama3.2:3b",
        openai_client=AsyncOpenAI(
            api_key=os.getenv("LLM_API_KEY", "V7mQ2xL9pR4kT8nC"),
            base_url=os.getenv("LLM_BASE_URL", "https://llama.atharva-amrutkar.in/v1"),
            timeout=10.0,
        ),
    ),
    output_type=Message,
)


async def main():

    result = await Runner.run(agent, "What are the modu")
    print(result.final_output_as(Message))


if __name__ == "__main__":
    asyncio.run(main())
