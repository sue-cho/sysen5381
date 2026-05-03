# 03_agents_with_function_calling.py
# Agents with Function Calling
# Pairs with 03_agents_with_function_calling.R
# Tim Fraser

# This script demonstrates how to build agents that can use function calling.
# Students will learn how to create agent wrapper functions and use multiple tools.

# 0. SETUP ###################################

## 0.1 Load Packages #################################

import requests  # for HTTP requests
import json      # for working with JSON
import pandas as pd  # for data manipulation

# If you haven't already, install these packages...
# pip install requests pandas

## 0.2 Load Functions #################################

# Load helper functions for agent orchestration
from functions import agent

## 0.3 Configuration #################################

# Select model of interest
MODEL = "smollm2:1.7b"

# 1. DEFINE FUNCTIONS TO BE USED AS TOOLS ###################################

# Define a function to be used as a tool
def add_two_numbers(x, y):
    """Add two numbers together."""
    return x + y

# Define another function to be used as a tool
def _dataframe_from_tool_arg(df):
    """
    Build a DataFrame from tool arguments. Ollama may pass df as a dict, list,
    or occasionally a JSON string (same payload, not yet parsed).
    """
    if isinstance(df, pd.DataFrame):
        return df
    if isinstance(df, str):
        s = df.strip()
        if not s:
            raise ValueError("get_table: empty df string")
        try:
            parsed = json.loads(s)
        except json.JSONDecodeError as e:
            raise ValueError(f"get_table: df is not valid JSON: {e}") from e
        return _dataframe_from_tool_arg(parsed)
    if isinstance(df, dict):
        vals = df.values()
        if df and all(not isinstance(v, (list, tuple)) for v in vals):
            return pd.DataFrame([df])
        return pd.DataFrame(df)
    if isinstance(df, list):
        return pd.DataFrame(df)
    raise TypeError(
        f"get_table expected DataFrame, dict, list, or JSON str; got {type(df)}"
    )


def get_table(df=None, string=None, **kwargs):
    """
    Convert tabular data into a markdown table.
    
    Parameters:
    -----------
    df : pandas.DataFrame or dict or list or str
        Table data. If the model uses a wrong argument name, `string` or a
        single extra keyword may carry the payload (see tool schema).
    """
    if df is None:
        df = string or kwargs.get("data")
    if df is None and kwargs:
        df = kwargs.get("df") or (next(iter(kwargs.values())) if len(kwargs) == 1 else None)
    if df is None:
        raise TypeError("get_table() missing tabular data (expected df=...)")
    tab = _dataframe_from_tool_arg(df)
    return tab.to_markdown(index=False)


def format_capitalize(string):
    """Capitalize the first letter of each word (title case)."""
    return str(string).title()

# 2. DEFINE TOOL METADATA ###################################

# Define the tool metadata for add_two_numbers
tool_add_two_numbers = {
    "type": "function",
    "function": {
        "name": "add_two_numbers",
        "description": "Add two numbers",
        "parameters": {
            "type": "object",
            "required": ["x", "y"],
            "properties": {
                "x": {
                    "type": "number",
                    "description": "first number"
                },
                "y": {
                    "type": "number",
                    "description": "second number"
                }
            }
        }
    }
}

# Define the tool metadata for get_table
# tool_get_table = {
#     "type": "function",
#     "function": {
#         "name": "get_table",
#         "description": "Convert tabular data to a markdown table string.",
#         "parameters": {
#             "type": "object",
#             "required": ["df"],
#             "properties": {
#                 "df": {
#                     "type": "object",
#                     "description": (
#                         "JSON table: column names map to lists, e.g. "
#                         '{"x": [8]} or {"a": [1], "b": [2]}.'
#                     ),
#                 }
#             },
#         },
#     },
# }

# Define the tool metadata for format_capitalize
tool_format_capitalize = {
    "type": "function",
    "function": {
        "name": "format_capitalize",
        "description": "Capitalize the first letter of each word in a string",
        "parameters": {
            "type": "object",
            "required": ["string"],
            "properties": {
                "string": {
                    "type": "string",
                    "description": "The string to capitalize",
                }
            },
        },
    },
}
# # 3. EXAMPLE 1: STANDARD CHAT (NO TOOLS) ###################################

# # Trying to call a standard chat without tools
# # The agent() function from functions.py handles this automatically
# messages = [
#     {"role": "user", "content": "Write a haiku about cheese."}
# ]

# resp = agent(messages=messages, model=MODEL, output="text")
# print("📝 Standard Chat Response:")
# print(resp)
# print()

# # 4. EXAMPLE 2: TOOL CALL #1 ###################################

# # Try calling tool #1 (add_two_numbers)
# messages = [
#     {"role": "user", "content": "Add 3 + 5."}
# ]

# resp = agent(
#     messages=messages,
#     model=MODEL,
#     output="tools",
#     tools=[tool_add_two_numbers],
#     namespace=globals(),
# )
# print("🔧 Tool Call #1 Result:")
# print(resp)
# print()

# # Access the output from the tool call
# if isinstance(resp, list) and len(resp) > 0:
#     print(f"Tool output: {resp[0].get('output', 'No output')}")
#     print()

# # 5. EXAMPLE 3: TOOL CALL #2 ###################################

# # Try calling tool #2 (get_table)
# # First, create a simple DataFrame with the result from tool #1
# if not isinstance(resp, list) or not resp:
#     result_value = 0
# else:
#     result_value = resp[0].get("output", 0)
# # JSON-serializable scalar for the tool payload
# try:
#     result_value = int(result_value)
# except (TypeError, ValueError):
#     result_value = result_value

# df = pd.DataFrame({"x": [result_value]})
# df_payload = df.to_dict(orient="list")

# # Small models often skip tool_calls if the prompt is vague; be explicit and
# # give the exact JSON shape the tool expects (dict / list columns).
# messages = [
#     {
#         "role": "system",
#         "content": "You must call the get_table tool. Do not answer with plain text.",
#     },
#     {
#         "role": "user",
#         "content": (
#             "Call get_table once. Set argument df to exactly this JSON: "
#             + json.dumps(df_payload)
#         ),
#     },
# ]

# resp2 = agent(
#     messages=messages,
#     model=MODEL,
#     output="tools",
#     tools=[tool_get_table],
#     namespace=globals(),
# )

# # If the model returned assistant text instead of tool_calls, agent() returns
# # that string (e.g. 'lacks the parameters'). Fall back so the demo still runs.
# if isinstance(resp2, str):
#     print("(Model returned text instead of tool_calls; running get_table locally with the same df.)")
#     out2 = get_table(df_payload)
#     resp2 = [
#         {
#             "function": {
#                 "name": "get_table",
#                 "arguments": {"df": df_payload},
#             },
#             "output": out2,
#         }
#     ]

# print("🔧 Tool Call #2 Result:")
# print(resp2)
# print()

# Compare against manual approach
# print("📊 Manual Table Creation:")
# manual_table = df.to_markdown(index=False)
# print(manual_table)
# print()

# Note: We can use the agent() function to rapidly build and test out agents with or without tools.

# EXAMPLE 3: TOOL CALL #3 

# Try calling tool #3 (format_capitalize)
messages = [
    {"role": "user", "content": "Capitalize the first letter of each word in the string 'rebecca by daphne du maurier'."}
]

resp = agent(
    messages=messages,
    model=MODEL,
    output="tools",
    tools=[tool_format_capitalize],
    namespace=globals(),
)
print("🔧 Tool Call #3 Result:")
print(resp)
print()