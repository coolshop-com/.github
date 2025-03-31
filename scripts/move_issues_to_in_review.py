import os
import requests


GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Content-Type": "application/vnd.github.v3+json"
}

GITHUB_API_URL = "https://api.github.com/graphql"
BACKLOG_PROJECT_ID = "PVT_kwDOANPumc4APBrR"
IN_REVIEW_COLUMN_NAME = "👀 In review"

PR_NUMBER = os.getenv("GITHUB_PR_NUMBER")
REPO_OWNER = os.getenv("GITHUB_REPOSITORY").split("/")[0]
REPO_NAME = os.getenv("GITHUB_REPOSITORY").split("/")[1]

def get_issues_from_pr():
    query = """
        query ($owner: String!, $name: String!, $number: Int!){
            repository(owner: $owner, name: $name) {
                pullRequest(number: $number) {
                    closingIssuesReferences(first: 100) {
                        edges {
                            node {
                                id
                                number
                                title
                                url
                            }
                        }
                    }
                }
            }
        }
    """
    variables = {
        "owner": REPO_OWNER,
        "name": REPO_NAME,
        "number": int(PR_NUMBER)
    }
    response = requests.post(GITHUB_API_URL, json={"query": query, "variables": variables}, headers=HEADERS)
    return response.json()["data"]["repository"]["pullRequest"]["closingIssuesReferences"]["edges"]

def get_project_fields(project_node_id):
    query = """
        query {
            node(id: "%s") {
                ... on ProjectV2 {
                fields(first: 50) {
                    nodes {
                    ... on ProjectV2FieldCommon {
                        id
                        name
                    }
                    ... on ProjectV2SingleSelectField {
                        options {
                        id
                        name
                        }
                    }
                    }
                }
            }
        }
    }""" % (project_node_id)
    response = requests.post(GITHUB_API_URL, json={"query": query}, headers=HEADERS)
    return response.json()["data"]["node"]["fields"]["nodes"]

def get_status_field(project_node_id):
    fields = get_project_fields(project_node_id)
    for field in fields:
        if field["name"] == "Status":
            return field

def get_in_progress_option_id(status_field):
    for option in status_field["options"]:
        if option["name"] == IN_REVIEW_COLUMN_NAME:
            return option["id"]

def get_issues_in_project(project_node_id): ## fjern PRs
    end_cursor = None
    has_next_page = True
    all_items = []

    query = """
    query {
    node(id: "%s") {
        ... on ProjectV2 {
        items(first: 100) {
            nodes {
            id
            content {
                ... on Issue {
                id
                title
                }
            }
            }
            pageInfo {
            endCursor
            hasNextPage
            }
        }
        }
    }
    }""" % (project_node_id)

    while has_next_page:
        # If there's an endCursor, use it to get the next page of items
        paginated_query = query
        if end_cursor:
            paginated_query = query.replace('items(first: 100)', f'items(first: 100, after: "{end_cursor}")')

        response = requests.post(GITHUB_API_URL, json={"query": paginated_query}, headers=HEADERS)
        data = response.json()

        # Extract items and page info from the response
        items = data["data"]["node"]["items"]["nodes"]
        page_info = data["data"]["node"]["items"]["pageInfo"]
        end_cursor = page_info["endCursor"]
        has_next_page = page_info["hasNextPage"]

        # Add the current page's items to the all_items list
        all_items.extend(items)

    return all_items   ## No need to return all items, just return the item that matches the issue ID


def get_issue_item_id_in_project(project_id, issue_id):
    issues_in_project = get_issues_in_project(project_id)
    
    # Filter items to find the specific Issue Item ID
    for item in issues_in_project:        
        if item["content"] and item["content"]["id"] == issue_id:
            issue_item_id = item["id"]
            return issue_item_id

def move_issue_to_in_review(project_id, issue_id, field_id, option_id):
    query = """
        mutation($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
            updateProjectV2ItemFieldValue(
                input: {
                    projectId: $projectId
                    itemId: $itemId
                    fieldId: $fieldId
                    value: { singleSelectOptionId: $optionId }
                }
            ) {
                clientMutationId
            }
        }
    """

    variables = {
        "projectId": project_id,
        "itemId": issue_id,
        "fieldId": field_id,
        "optionId": str(option_id)
    }

    response = requests.post(GITHUB_API_URL, json={"query": query, "variables": variables}, headers=HEADERS)

    return response.json()

def main():
    print(f"Fetching linked issues for PR #{PR_NUMBER} in {REPO_OWNER}/{REPO_NAME}")

    linked_issues = get_issues_from_pr()
    if not linked_issues:
        print("No linked issues found.")
        return
    print(f"Linked issues: {linked_issues}")

    for linked_issue in linked_issues:
        issue_id = linked_issue["node"]["id"]
        issue_number = linked_issue["node"]["number"]

        print("Finding project status field...")
        project_status_field = get_status_field(BACKLOG_PROJECT_ID)
        if not project_status_field:
            print("Status field not found.")
            return
        print(f"Status field: {project_status_field}")
        
        in_progress_option_id = get_in_progress_option_id(project_status_field)

        issue_id_in_project = get_issue_item_id_in_project(BACKLOG_PROJECT_ID, issue_id)

        print("Moving issue to 'In review'...")
        response = move_issue_to_in_review(BACKLOG_PROJECT_ID, issue_id_in_project, project_status_field["id"], in_progress_option_id)

        print(f"Issue {issue_number} moved to status 'In review'.")

        if response.status_code == 200:
            print(f"✅ Issue {issue_number} moved to status 'In review'.")
        else:
            print(f"❌ Issue {issue_number} could not be moved to status 'In review': {response.text}")

if __name__ == "__main__":
    main()
