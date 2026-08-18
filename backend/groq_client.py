import os

from dotenv import load_dotenv
from groq import Groq

load_dotenv()

_client = Groq(api_key=os.environ["GROQ_API_KEY"])
_model = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


def ask_groq(message: str) -> str:
    response = _client.chat.completions.create(
        model=_model,
        messages=[{"role": "user", "content": message}],
    )
    return response.choices[0].message.content
