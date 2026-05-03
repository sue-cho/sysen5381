# 05_multiple_agents.R

# Load packages
library(dplyr)
library(stringr)
library(httr2)
library(jsonlite)
library(ollamar)
library(purrr)
library(lubridate)

source("08_agents/functions.R")

# In this script, we will build a graph of agents and their interactions,
# to query data, perform analysis, and interpret it.

# We will use the FDA Drug Shortages API to get data on drug shortages.
# https://open.fda.gov/apis/drug/drugshortages/

# Select model of interest
MODEL = "smollm2:1.7b"


get_shortages = function(category = "Psychiatry", limit = 500){
  # Testing values
  # category = "Psychiatry"

  # Create request object
  req = request("https://api.fda.gov/drug/shortages.json") |>
      req_headers(Accept = "application/json")  |>
      req_method("GET") |>
      # Sort by initial posting date, most recent first
      req_url_query(sort="initial_posting_date:desc") |>
      # Search for capsule medications, Psychiatric medications, and current shortages
      req_url_query(search = paste0('dosage_form:"Capsule"+status:"Current"+therapeutic_category:"', category, '"')) |>
      # Limit to N results
      req_url_query(limit = limit) 


    # Perform the request
    resp = req |> req_perform()
    # Parse the response as JSON
    data = resp_body_json(resp)

    # Process the data into a tidy dataframe
    processed_data = data |> 
      with(results) |> 
      map_dfr(~tibble(
        therapeutic_category = paste0(.x$therapeutic_category, collapse = ", "),
        generic_name = .x$generic_name,
        update_type = .x$update_type,
        update_date = .x$update_date,
        availability = .x$availability,
        related_info = .x$related_info,
          )
      )  %>%
      mutate(update_date = lubridate::mdy(update_date))
      return(processed_data)
}

# Context the tool needs to know
categories = c(
  "Analgesia/Addiction",
  "Anesthesia",
  "Anti-Infective",   
  "Antiviral",
  "Cardiovascular",
  "Dental",
  "Dermatology",
  "Endocrinology/Metabolism",
  "Gastroenterology",
  "Hematology",
  "Inborn Errors",
  "Medical Imaging",
  "Musculoskeletal",
  "Neurology",
  "Oncology",
  "Ophthalmology",
  "Other",
  "Pediatric",
  "Psychiatry",
  "Pulmonary/Allergy",
  "Renal",
  "Reproductive",
  "Rheumatology",
  "Total Parenteral Nutrition",
  "Transplant",
  "Urology"
)

# Define the tool metadata as a list
tool_get_shortages = list(
    type = "function",
    "function" = list(
        name = "get_shortages",
        description = "Get data on drug shortages",
        parameters = list(
            type = "object",
            required = list("category", "limit"),
            properties = list(
                category = list(type = "string", description = paste0("the therapeutic category of the drug. Options are: ", paste(categories, collapse = ", "), ".")),
                limit = list(type = "numeric", description = "the max number of results to return. Default is 500.")
            )
        )
    )
)



# Get data from an API
# data = get_shortages("Psychiatry")



# Let's create an agentic workflow.
task = "Get data on drug shortages for the category Psychiatry"
role1 = "I fetch information from the FDA Drug Shortages API"
result1 = agent_run(role = role1, task = task, model = MODEL, output = "tools", tools = list(tool_get_shortages))

role2 = "I analyze data in a table format and return a markdown table of currently ongoing shortages."
result2 = agent_run(role =  role2, task = df_as_text(result1), model = MODEL, output = "text", tools = NULL)


role3 = "I write a 1-page press release on the currently ongoing shortages."
result3 = agent_run(role = role3, task = result2, model = MODEL, output = "text", tools = NULL)


