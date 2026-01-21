# If you haven't yet, install these two packages:
install.packages(c("gert", "credentials"))
# Load packages
library(usethis) # for coding management helper functions
library(gert) # for github operations like commit, pull, and push
library(credentials) # for authenticating with github

# You might want to put your Personal Access Token in a .env file
# Create a .env 'environmental variables' file
file.create(".env")
# open the file and add: GITHUB_PAT=whatever_it_was_here

# and then add the .env file to the .gitignore file,
# which lists which files should NEVER be uploaded to a github repository for security reasons.
usethis::use_git_ignore(".env")
# Also 'vaccinate' your computer's global .gitignore file - which helps keep sensitive files out. 
# Won't change your repository's .gitignore
usethis::git_vaccinate()


# Set your Github Personal Access Token
credentials::set_github_pat()
# this will prompt a popup that asks you to enter your GitHub Personal Access Token.


# pull most recent changes from GitHub
gert::git_pull() 

# select any and all new files created or edited to be 'staged'
# 'staged' files are to be saved anew on GitHub 
# dir(all.files = TRUE) selects ALL files to be added.
gert::git_add(dir(all.files = TRUE)) 

# save your record of file edits - called a commit
gert::git_commit_all("my first commit") 

# push your commit to GitHub
gert::git_push() 
