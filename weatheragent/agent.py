# Chain Of Thought Prompting
from dotenv import load_dotenv
from openai import OpenAI
import requests
from pydantic import BaseModel, Field
from typing import Optional
import json
import os

load_dotenv()

client = OpenAI()

def run_command(cmd: str):
    result = os.system(cmd)
    return result


def get_weather(city: str):
    url = f"https://wttr.in/{city.lower()}?format=%C+%t"
    response = requests.get(url)

    if response.status_code == 200:
        return f"The weather in {city} is {response.text}"
    
    return "Something went wrong"

available_tools = {
    "get_weather": get_weather,
    "run_command": run_command
}


SYSTEM_PROMPT = """
    You're an expert AI Assistant in resolving user queries using chain of thought.
    You work on START, PLAN and OUPUT steps.
    You need to first PLAN what needs to be done. The PLAN can be multiple steps.
    Once you think enough PLAN has been done, finally you can give an OUTPUT.
    You can also call a tool if required from the list of available tools.
    for every tool call wait for the observe step which is the output from the called tool.

    Rules:
    - Strictly Follow the given JSON output format
    - Only run one step at a time.
    - The sequence of steps is START (where user gives an input), PLAN (That can be multiple times) and finally OUTPUT (which is going to the displayed to the user).

    Output JSON Format:
    { "step": "START" | "PLAN" | "OUTPUT" | "TOOL", "content": "string", "tool": "string", "input": "string" }

    Available Tools:
    - get_weather(city: str): Takes city name as an input string and returns the weather info about the city.
    - run_command(cmd: str): Takes a system linux command as string and executes the command on user's system and returns the output from that command
    

    Example 2:
    START: What is the weather of Delhi?
    PLAN: { "step": "PLAN": "content": "Seems like user is interested in getting weather of Delhi in India" }
    PLAN: { "step": "PLAN": "content": "Lets see if we have any available tool from the list of available tools" }
    PLAN: { "step": "PLAN": "content": "Great, we have get_weather tool available for this query." }
    PLAN: { "step": "PLAN": "content": "I need to call get_weather tool for delhi as input for city" }
    PLAN: { "step": "TOOL": "tool": "get_weather", "input": "delhi" }
    PLAN: { "step": "OBSERVE": "tool": "get_weather", "output": "The temp of delhi is cloudy with 20 C" }
    PLAN: { "step": "PLAN": "content": "Great, I got the weather info about delhi" }
    OUTPUT: { "step": "OUTPUT": "content": "The cuurent weather in delhi is 20 C with some cloudy sky." }
    
"""

print("\n\n\n")

#LLM would follow the structure that we have given here and not some random string
class MyOutputFormat(BaseModel):
    step: str = Field(..., description="The ID of the step. Example: PLAN, OUTPUT, TOOL, etc")
    content: Optional[str] = Field(None, description="The optional string content for the step")
    tool: Optional[str] = Field(None, description="The ID of the tool to call.")
    input: Optional[str] = Field(None, description="The input params for the tool")

message_history = [
    { "role": "system", "content": SYSTEM_PROMPT },
]

while True:
    user_query = input("👉🏻 ")
    message_history.append({ "role": "user", "content": user_query })

    while True:
        response = client.chat.completions.parse(
            model="gpt-4o",
            response_format=MyOutputFormat,
            messages=message_history
        )

        raw_result = response.choices[0].message.content
        message_history.append({"role": "assistant", "content": raw_result})
        
        parsed_result = response.choices[0].message.parsed

        if parsed_result.step == "START":#
            print("🔥", parsed_result.content)
            continue

        # Handle the tool call step. Call the tool and get the response and then add that response to the message history with OBSERVE step. Why observe step? Because we want the model to see the output from the tool call before it can make the next decision. This is important because the model might want to call multiple tools in a sequence and it needs to see the output from each tool call before it can decide what to do next.
        if parsed_result.step == "TOOL": # Call the tool and get the response and then add that response to the message history with OBSERVE step.
            tool_to_call = parsed_result.tool # Get the tool to call from the parsed result
            tool_input = parsed_result.input # Get the tool input from the parsed result
            print(f"🛠️: {tool_to_call} ({tool_input})")

            tool_response = available_tools[tool_to_call](tool_input) # Call the tool function with the input and get the response
            print(f"🛠️: {tool_to_call} ({tool_input}) = {tool_response}")
            message_history.append({ "role": "developer", "content": json.dumps(
                { "step": "OBSERVE", "tool": tool_to_call, "input": tool_input, "output": tool_response}
            ) })
            continue



        if parsed_result.step == "PLAN":
            print("🧠", parsed_result.content)
            continue

        if parsed_result.step == "OUTPUT":
            print("🤖", parsed_result.content)
            break

print("\n\n\n")


'''
The "call" happens in three distinct phases:
Phase A: The Decision (AI)The AI analyzes your query. If you ask for the weather in Berlin, the AI realizes it doesn't have real-time data. 
Because of your SYSTEM_PROMPT, it knows it should use the get_weather tool. It outputs a JSON object where step is "TOOL".

Phase B: The Bridge (Python)Your Python code sees that parsed_result.step == "TOOL". It then uses these two lines to act as the "hands" for the AI:Pythontool_to_call = parsed_result.tool  # e.g., "get_weather"
tool_input = parsed_result.input    # e.g., "berlin"

# This looks up the function in your dictionary and runs it:
tool_response = available_tools[tool_to_call](tool_input) 

Phase C: The Execution (Function)The function get_weather("berlin") runs, makes a request to the internet, and returns a string like "The weather in Berlin is 12°C".2. 

Why do we need the "OBSERVE" step?
The AI model itself cannot run Python code. It only generates text. Once the Python function finishes, the AI has no idea what the result was unless you tell it.It provides "Eyes" to the AI The OBSERVE step is you sending a message back to the AI saying: "Hey, I ran that tool for you, and here is what I found."Pythonmessage_history.append({ 
    "role": "developer", 
    "content": json.dumps({ "step": "OBSERVE", "output": tool_response }) 
})

It prevents Hallucinations Without the observation, the AI would "forget" it just called a tool. It might try to call the tool again, or worse, it might guess (hallucinate) the weather. By adding the result to the message_history, the AI now "sees" the weather data in its memory.

'''