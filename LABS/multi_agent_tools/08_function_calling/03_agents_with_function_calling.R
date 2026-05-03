# 04_agents.R

# This script demonstrates this course's approach to building agents.

# Load packages
require(ollamar) # for interacting with the LLM
require(dplyr) # for data wrangling
require(stringr) # for string operations

# Select model of interest
MODEL = "smollm2:1.7b"

# Let's write a wrapper function that will run a single agent.

#' @name agent
#' @title Agent Wrapper Function
#' @description A helper wrapper function that will run a single agent, with or without tools.
#' @param messages A list of messages to be sent to the agent. Must be created using \code{ollamar::create_message()}.
#' @param model The model to be used for the agent.
#' @param output The output format to be used for the agent. Options are "text", "jsonlist", "tools", "df", and more. See \code{ollamar::chat} for more options.
#' @param tools A list of tools metadata to be used for the agent.
#' @param all If TRUE, return all responses from the agent (eg. all values of the tool call result list.) If FALSE, return only the last response.
#' @note If the agent has tools, those tools must be named as objects in the **global environment**.
#' @note If the agent has tools, perform a tool call.
#' @note If the agent has NO tools, perform a standard chat.
#' @importFrom ollamar chat
#' @return A list of responses from the agent.
#' @export 
agent = function(messages, model = "smollm2:1.7b", output = "text", tools = NULL, all = FALSE){

    # # Testing values
    # messages = create_message(role = "user", content = "Add 3 + 5.")
    # # Define a function to be used as a tool
    # add_two_numbers = function(x, y){
    #     return(x + y)
    # }

    # # Define the tool metadata as a list
    # tool_add_two_numbers = list(
    #     type = "function",
    #     "function" = list(
    #         name = "add_two_numbers",
    #         description = "Add two numbers",
    #         parameters = list(
    #             type = "object",
    #             required = list("x", "y"),
    #             properties = list(
    #                 x = list(type = "numeric", description = "first number"),
    #                 y = list(type = "numeric", description = "second number")
    #             )
    #         )
    #     )
    # )
    # tools = list(tool_add_two_numbers); 
    # model = "smollm2:1.7b"; 
    # output = "tools";

    # If the agent has NO tools, perform a standard chat
    if(is.null(tools)) {
        resp = chat(model = model, messages = messages, output = output, stream = FALSE)
        return(resp)
    } else {
        
    # If the agent has any tools, perform a tool call
    resp = chat(model = model, messages = messages, tools = tools, output = output, stream = FALSE)

    # For any given tool call, execute the tool call
    n_resp = length(resp)
    if(n_resp > 0){
    for(i in 1:n_resp) {
    # i = 1
    # Save the result of the tool call in an 'output' field 
    resp[[i]]$output = do.call(resp[[i]]$name, resp[[i]]$arguments)
    }
    }
    if(all) { return(resp) } else { return(resp[[n_resp]]$output) }
    }

}


# Define a function to be used as a tool
add_two_numbers = function(x, y){ return(x + y) }

# Define the tool metadata as a list
tool_add_two_numbers = list(
    type = "function",
        "function" = list(
            name = "add_two_numbers",
            description = "Add two numbers",
            parameters = list(
                type = "object",
                required = list("x", "y"),
                properties = list(
                    x = list(type = "numeric", description = "first number"),
                    y = list(type = "numeric", description = "second number")
                )
            )
        )
)

# Define a function to be used as a tool
get_table = function(df){ knitr::kable(df, format = "markdown") }

# Define the tool metadata as a list
tool_get_table = list(
    type = "function",
    "function" = list(
        name = "get_table",
        description = "Convert a data.frame into a markdown table",
        parameters = list(
            type = "object",
            required = list("df"),
            properties = list(
                df = list(
                    type = "data.frame", 
                    description = "The data.frame to convert to a markdown table using knitr::kable()")
            )
        )
    )
)

# tools = list(tool_add_two_numbers); 
model = "smollm2:1.7b"; 

# Trying to call a standard chat
resp = create_message(role = "user", content = "Write a haiku about cheese.") |>
    agent(model = model, output = "text")
resp

# Try calling tool #1
resp = create_message(role = "user", content = "Add 3 + 5.") |>
    agent(model = model, output = "tools", tools = list(tool_add_two_numbers))
resp

resp[[1]]$output

# Try calling tool #2
resp2 = create_message(role = "user", content = paste0("Place the numeric value ", resp[[1]]$output, " into a 1x1 data.frame with column name 'x' and format as a markdown table.")) |>
    agent(model = model, output = "tools", tools = list(tool_get_table))
resp2 

# Compare against manual approach
knitr::kable(data.frame(x = resp[[1]]$output), format = "markdown")

# We can use this agent() function to rapidly build and test out agents with or without tools.


# Clean up shop
rm(list = ls())