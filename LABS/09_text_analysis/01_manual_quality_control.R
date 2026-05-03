# 01_manual_quality_control.R
# Manual Text Quality Control with stringr and dplyr
# Tim Fraser

# This script demonstrates how to manually perform quality control on AI-generated text
# by counting concepts, detecting patterns, and creating quality control metrics.
# Students learn to use stringr for pattern matching and dplyr for data analysis.

# 0. SETUP ###################################

## 0.1 Load Packages #################################

# If you haven't already, install required packages:
# install.packages(c("dplyr", "stringr", "readr"))

library(dplyr)   # for data wrangling and pipelines
library(stringr) # for string pattern matching and text analysis
library(readr)   # for reading text files

## 0.2 Load Sample Text ####################################

# Load sample AI-generated report text
# This text should be checked for quality and accuracy
sample_text = read_file("09_text_analysis/data/sample_reports.txt")

# Split text into individual reports (reports are separated by blank lines)
# Remove empty strings and trim whitespace
reports = strsplit(sample_text, "\n\n")[[1]]
reports = trimws(reports)
reports = reports[reports != ""]  # Remove empty strings

# Select the first report for quality control
report = reports[1]

cat("📝 Sample Report for Quality Control:\n")
cat("---\n")
cat(report)
cat("\n---\n\n")

# 1. MANUAL QUALITY CONTROL ###################################

## 1.1 Count Concepts and Keywords #################################

# Define concepts/keywords to search for in the text
# These might be required terms, important topics, or quality control criteria
required_concepts = c("emissions", "county", "year", "pollutant", "recommendations", "data")

# Count occurrences of each concept (case-insensitive)
concept_counts = tibble(
  concept = required_concepts,
  count = sapply(required_concepts, function(term) {
    str_count(report, regex(term, ignore_case = TRUE))
  }),
  present = count > 0
)

cat("📊 Concept Counts:\n")
print(concept_counts)
cat("\n")

## 1.2 Check for Required Elements #################################

# Check for presence of numbers (indicating data was reported)
has_numbers = str_detect(report, "\\d+")
has_percentages = str_detect(report, "\\d+%")
has_recommendations = str_detect(report, regex("recommend|suggest|should|must", ignore_case = TRUE))

# Check for problematic patterns
has_contractions = str_detect(report, regex("'t|'s|'d|'ll|'ve|'re|'m", ignore_case = TRUE))
has_hyperbole = str_detect(report, regex("crucial|critical|extremely|absolutely", ignore_case = TRUE))
has_belittling = str_detect(report, regex("it is clear that|obviously|as you can see", ignore_case = TRUE))

# Create quality control checks table
quality_checks = tibble(
  check = c("Contains numbers", "Contains percentages", "Contains recommendations", 
           "Has contractions", "Has hyperbole", "Has belittling phrases"),
  result = c(has_numbers, has_percentages, has_recommendations,
             has_contractions, has_hyperbole, has_belittling),
  status = ifelse(c(has_numbers, has_percentages, has_recommendations,
                    !has_contractions, !has_hyperbole, !has_belittling),
                  "✅ PASS", "❌ FAIL")
)

cat("✅ Quality Control Checks:\n")
print(quality_checks)
cat("\n")

## 1.3 Calculate Basic Metrics #################################

# Calculate text metrics
word_count = str_count(report, "\\S+")
sentence_count = str_count(report, "[.!?]+")
avg_words_per_sentence = word_count / max(sentence_count, 1)

# Count specific patterns
number_count = length(str_extract_all(report, "\\d+(\\.\\d+)?")[[1]])
percentage_count = str_count(report, "\\d+%")

# Create metrics table
text_metrics = tibble(
  metric = c("Word count", "Sentence count", "Avg words per sentence", 
             "Number count", "Percentage count"),
  value = c(word_count, sentence_count, round(avg_words_per_sentence, 2),
            number_count, percentage_count)
)

cat("📈 Text Metrics:\n")
print(text_metrics)
cat("\n")

## 1.4 Create Comprehensive Quality Control Table #################################

# Combine all quality control results into a single table
quality_results = tibble(
  report_id = 1,
  word_count = word_count,
  sentence_count = sentence_count,
  avg_words_per_sentence = round(avg_words_per_sentence, 2),
  has_numbers = has_numbers,
  has_percentages = has_percentages,
  has_recommendations = has_recommendations,
  has_contractions = has_contractions,
  has_hyperbole = has_hyperbole,
  has_belittling = has_belittling,
  concept_coverage = sum(concept_counts$present) / nrow(concept_counts),
  number_count = number_count,
  percentage_count = percentage_count
)

cat("📋 Comprehensive Quality Control Results:\n")
print(quality_results)
cat("\n")

## 1.5 Quality Control Multiple Reports #################################

# If you have multiple reports, you can check them all at once
if (length(reports) > 1) {
  cat("🔄 Performing Quality Control on Multiple Reports...\n\n")
  
  # Create a function to check a single report
  check_report = function(text, report_id) {
    # Count concepts
    concept_present = sapply(required_concepts, function(term) {
      str_count(text, regex(term, ignore_case = TRUE)) > 0
    })
    
    # Calculate metrics
    word_count = str_count(text, "\\S+")
    sentence_count = str_count(text, "[.!?]+")
    avg_words = word_count / max(sentence_count, 1)
    
    # Check patterns
    has_numbers = str_detect(text, "\\d+")
    has_percentages = str_detect(text, "\\d+%")
    has_recommendations = str_detect(text, regex("recommend|suggest|should|must", ignore_case = TRUE))
    has_contractions = str_detect(text, regex("'t|'s|'d|'ll|'ve|'re|'m", ignore_case = TRUE))
    has_hyperbole = str_detect(text, regex("crucial|critical|extremely|absolutely", ignore_case = TRUE))
    has_belittling = str_detect(text, regex("it is clear that|obviously|as you can see", ignore_case = TRUE))
    
    # Return as a tibble row
    tibble(
      report_id = report_id,
      word_count = word_count,
      sentence_count = sentence_count,
      avg_words_per_sentence = round(avg_words, 2),
      has_numbers = has_numbers,
      has_percentages = has_percentages,
      has_recommendations = has_recommendations,
      has_contractions = has_contractions,
      has_hyperbole = has_hyperbole,
      has_belittling = has_belittling,
      concept_coverage = mean(concept_present)
    )
  }
  
  # Check all reports
  all_results = bind_rows(
    lapply(1:length(reports), function(i) {
      check_report(reports[i], i)
    })
  )
  
  cat("📊 Quality Control Results for All Reports:\n")
  print(all_results)
  cat("\n")
}

cat("✅ Manual quality control complete!\n")
cat("💡 Next step: Use AI quality control (02_ai_quality_control.R) to automate this process.\n")
