from groq import Groq
from dotenv import load_dotenv #loads variables from .env
import os #access environment variables

load_dotenv()  #loads API key

client = Groq(
    api_key=os.getenv("GROQ_API_KEY") #Reads "GROQ_API_KEY" from environment variables
) #creates AI client , now client can send requests to the AI model

messages = [
    {
        "role": "system",
        "content": "You are Rune, a terminal AI assistant."
    }
]
while True: #infinite chat loop

    user = input("You: ") #gets user message

    if user.lower() == "exit": #If user types exit the loop stops(lowercase)
        break
    
    messages.append(
            {
                "role": "user",
                "content": user #substitutes input
            }
        )
    response = client.chat.completions.create( #sends prompt to LLM
        model="llama-3.3-70b-versatile", #Choose Model
        messages=messages
    )

    reply = response.choices[0].message.content
    messages.append(
    {
        "role": "assistant",
        "content": reply
    }
)
    print("\nRune:", reply) #Extract AI Response