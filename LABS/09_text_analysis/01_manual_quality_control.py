# 01_manual_quality_control.py
# Manual Text Quality Control with pandas and re
# Tim Fraser

# This script demonstrates how to manually perform quality control on AI-generated text
# by counting concepts, detecting patterns, and creating quality control metrics.
# Students learn to use re (regex) for pattern matching and pandas for data analysis.

# 0. Setup #################################

## 0.1 Load Packages #################################

# If you haven't already, install required packages:
# pip install pandas

import pandas as pd  # for data wrangling
import re  # for string pattern matching and text analysis

## 0.2 Load Sample Text #################################

# Load sample AI-generated report text
# This text should be checked for quality and accuracy
with open("data/sample_reports.txt", "r", encoding="utf-8") as f:
    sample_text = f.read()

# Split text into individual reports (reports are separated by blank lines)
# Remove empty strings and trim whitespace
reports = [r.strip() for r in sample_text.split("\n\n") if r.strip()]

# Select the first report for quality control
report = reports[0]

print("📝 Sample Report for Quality Control:")
print("---")
print(report)
print("---\n")

# 1. Manual Quality Control #################################

## 1.1 Count Concepts and Keywords #################################

# Define concepts/keywords to search for in the text
# These might be required terms, important topics, or quality control criteria
required_concepts = ["emissions", "county", "year", "pollutant", "recommendations", "data"]

# Count occurrences of each concept (case-insensitive)
concept_counts = []
for concept in required_concepts:
    count = len(re.findall(re.escape(concept), report, re.IGNORECASE))
    concept_counts.append({
        "concept": concept,
        "count": count,
        "present": count > 0
    })

concept_counts_df = pd.DataFrame(concept_counts)

print("📊 Concept Counts:")
print(concept_counts_df)
print()

## 1.2 Check for Required Elements #################################

# Check for presence of numbers (indicating data was reported)
has_numbers = bool(re.search(r"\d+", report))
has_percentages = bool(re.search(r"\d+%", report))
has_recommendations = bool(re.search(r"recommend|suggest|should|must", report, re.IGNORECASE))

# Check for problematic patterns
has_contractions = bool(re.search(r"'t|'s|'d|'ll|'ve|'re|'m", report, re.IGNORECASE))
has_hyperbole = bool(re.search(r"crucial|critical|extremely|absolutely", report, re.IGNORECASE))
has_belittling = bool(re.search(r"it is clear that|obviously|as you can see", report, re.IGNORECASE))

# Create quality control checks table
quality_checks = pd.DataFrame({
    "check": [
        "Contains numbers",
        "Contains percentages",
        "Contains recommendations",
        "Has contractions",
        "Has hyperbole",
        "Has belittling phrases"
    ],
    "result": [
        has_numbers,
        has_percentages,
        has_recommendations,
        has_contractions,
        has_hyperbole,
        has_belittling
    ]
})

# Add status column
quality_checks["status"] = quality_checks.apply(
    lambda row: "✅ PASS" if (
        (row["check"] in ["Contains numbers", "Contains percentages", "Contains recommendations"] and row["result"]) or
        (row["check"] not in ["Contains numbers", "Contains percentages", "Contains recommendations"] and not row["result"])
    ) else "❌ FAIL",
    axis=1
)

print("✅ Quality Control Checks:")
print(quality_checks)
print()

## 1.3 Calculate Basic Metrics #################################

# Calculate text metrics
words = report.split()
word_count = len(words)
sentence_count = len(re.findall(r"[.!?]+", report))
avg_words_per_sentence = word_count / max(sentence_count, 1)

# Count specific patterns
numbers = re.findall(r"\d+(?:\.\d+)?", report)
number_count = len(numbers)
percentage_count = len(re.findall(r"\d+%", report))

# Create metrics table
text_metrics = pd.DataFrame({
    "metric": [
        "Word count",
        "Sentence count",
        "Avg words per sentence",
        "Number count",
        "Percentage count"
    ],
    "value": [
        word_count,
        sentence_count,
        round(avg_words_per_sentence, 2),
        number_count,
        percentage_count
    ]
})

print("📈 Text Metrics:")
print(text_metrics)
print()

## 1.4 Create Comprehensive Quality Control Table #################################

# Combine all quality control results into a single table
concept_coverage = concept_counts_df["present"].sum() / len(concept_counts_df)

quality_results = pd.DataFrame({
    "report_id": [1],
    "word_count": [word_count],
    "sentence_count": [sentence_count],
    "avg_words_per_sentence": [round(avg_words_per_sentence, 2)],
    "has_numbers": [has_numbers],
    "has_percentages": [has_percentages],
    "has_recommendations": [has_recommendations],
    "has_contractions": [has_contractions],
    "has_hyperbole": [has_hyperbole],
    "has_belittling": [has_belittling],
    "concept_coverage": [concept_coverage],
    "number_count": [number_count],
    "percentage_count": [percentage_count]
})

print("📋 Comprehensive Quality Control Results:")
print(quality_results)
print()

## 1.5 Quality Control Multiple Reports #################################

# If you have multiple reports, you can check them all at once
if len(reports) > 1:
    print("🔄 Performing Quality Control on Multiple Reports...\n")
    
    # Create a function to check a single report
    def check_report(text, report_id):
        # Count concepts
        concept_present = [
            len(re.findall(re.escape(term), text, re.IGNORECASE)) > 0
            for term in required_concepts
        ]
        
        # Calculate metrics
        words = text.split()
        word_count = len(words)
        sentence_count = len(re.findall(r"[.!?]+", text))
        avg_words = word_count / max(sentence_count, 1)
        
        # Check patterns
        has_numbers = bool(re.search(r"\d+", text))
        has_percentages = bool(re.search(r"\d+%", text))
        has_recommendations = bool(re.search(r"recommend|suggest|should|must", text, re.IGNORECASE))
        has_contractions = bool(re.search(r"'t|'s|'d|'ll|'ve|'re|'m", text, re.IGNORECASE))
        has_hyperbole = bool(re.search(r"crucial|critical|extremely|absolutely", text, re.IGNORECASE))
        has_belittling = bool(re.search(r"it is clear that|obviously|as you can see", text, re.IGNORECASE))
        
        # Return as a DataFrame row
        return pd.DataFrame({
            "report_id": [report_id],
            "word_count": [word_count],
            "sentence_count": [sentence_count],
            "avg_words_per_sentence": [round(avg_words, 2)],
            "has_numbers": [has_numbers],
            "has_percentages": [has_percentages],
            "has_recommendations": [has_recommendations],
            "has_contractions": [has_contractions],
            "has_hyperbole": [has_hyperbole],
            "has_belittling": [has_belittling],
            "concept_coverage": [sum(concept_present) / len(concept_present)]
        })
    
    # Check all reports
    all_results = pd.concat([
        check_report(reports[i], i + 1)
        for i in range(len(reports))
    ], ignore_index=True)
    
    print("📊 Quality Control Results for All Reports:")
    print(all_results)
    print()

print("✅ Manual quality control complete!")
print("💡 Next step: Use AI quality control (02_ai_quality_control.py) to automate this process.")
