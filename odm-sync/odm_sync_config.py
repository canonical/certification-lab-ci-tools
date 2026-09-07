# projects to scan for new bugs
odm_projects = ["civet-cat", "flying-fox", "pygmy-possum", "white-whale"]
# project that should contain bugs from all projects
umbrella_project = "somerville"

# bug title prefix that's added to bugs replicated in the umbrella project
umbrella_prefix = "[ODM bug] "

# mapping between names found in AR column of the management spreadsheet
# and LP usernames
lp_names = {
    "Cyrus": "cyruslien",
    "Fourdollars": "fourdollars",
    "Leon": "lihow731",
    "Kai-Heng": "kaihengfeng",
    "Maciej": "kissiel",
}

# Google Sheet ID with the project tracking information
tracking_doc_id = ""

# sync_odm will work on bugs filed filed after or on this date:
start_date = "2019-07-02"
