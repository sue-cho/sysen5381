# functions.R

# This script contains functions used for multi-agent orchestration in R.

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

agent_run = function(role, task, tools = NULL, output = "text",model = MODEL){
  # Testing values
  # role = role2; task = df_as_text(result1); 
  # tools = NULL; output = "text"; model = MODEL;

  # Define the messages to be sent to the agent
  messages = create_messages(
    create_message(role = "system", content = role),
    create_message(role = "user", content = task)
  )

  # Run the agent
  resp = agent(messages = messages, model = model, output = output, tools = tools)
  return(resp)

}


#' @name df_as_text
#' @title Convert a data.frame to a text string
#' @description Converts a data.frame to a text string using knitr::kable().
#' @param df The data.frame to convert to a text string.
#' @return A text string.
#' @export
df_as_text = function(df){
  tab = knitr::kable(df, format = "markdown")
  tab = as.character(tab)
  tab = paste0(tab, collapse = "\n")
  return(tab)
}
