import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


def generate_sql(question, schema):

    prompt = f"""
You are a SQLite expert.

Database Schema:
{schema}

Rules:

- Return ONLY SQL.
- Use SQLite syntax.
- No markdown.
- No explanation.
- Generate ONLY SELECT statements.

Ranking Rules:

- If the user asks for:
  * top topics
  * popular topics
  * highest topics
  * most discussed topics
  * rank topics
  * compare topics
  * most asked topics
  * what topics

  then ALWAYS return ALL relevant rows ranked by share_of_messages DESC,
  using LIMIT 10. NEVER use LIMIT 1 for these queries.

- NEVER use LIMIT 1 unless the user explicitly says:
  * single most
  * highest only
  * number 1 topic
  * best topic

- Use ORDER BY share_of_messages DESC for rankings.

- If user asks for trends, use ORDER BY month ASC.

Question:
{question}
"""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    return response.choices[0].message.content.strip()