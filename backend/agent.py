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
    intent: Literal["syllabus", "website"]


agent = Agent(
    "intent_classifier",
    instructions="""You are an intelligent routing agent for SIES GST College. Route the user's question to the correct database by returning the correct intent.

Categories:
1. 'syllabus' - The user is asking about academic courses, curriculum, modules, syllabus content, practicals, textbooks, or credits.
2. 'website' - The user is asking about faculty, HODs, admissions, placements, campus facilities, general college information, or events.""",
    model=OpenAIChatCompletionsModel(
        "",
        openai_client=AsyncOpenAI(
            api_key=os.getenv("LLM_API_KEY"), base_url=os.getenv("LLM_BASE_URL")
        ),
    ),
    output_type=Message,
)


async def main():

    result = await Runner.run(agent, "What are the modu")
    print(result.final_output_as(Message))


if __name__ == "__main__":
    asyncio.run(main())
