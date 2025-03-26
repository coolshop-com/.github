import os
import requests

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

GITHUB_API_URL = "https://api.github.com/graphql"
PR_NUMBER = os.getenv("GITHUB_PR_NUMBER")
REPO_OWNER, REPO_NAME = os.getenv("GITHUB_REPOSITORY").split("/")
PR_AUTHOR = os.getenv("GITHUB_PR_AUTHOR")


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


def get_assignees_on_issue(issue_number):
    query = """
        query ($owner: String!, $name: String!, $issueNumber: Int!) {
            repository(owner: $owner, name: $name) {
                issue(number: $issueNumber) {
                    assignees(first: 10) {
                        nodes {
                            login
                        }
                    }
                }
            }
        }
        """
    
    variables = {"owner": REPO_OWNER, "name": REPO_NAME, "issueNumber": issue_number}
    response = requests.post(GITHUB_API_URL, json={"query": query, "variables": variables}, headers=HEADERS)
    data = response.json()
    
    return data.get("data", {}).get("repository", {}).get("issue", {}).get("assignees", {}).get("nodes", [])

def get_user_id(username):
    user_id_query = """
        query ($login: String!) {
            user(login: $login) {
                id
            }
        }
    """
    variables = {"login": username}
    user_id_response = requests.post(GITHUB_API_URL, json={"query": user_id_query, "variables": variables}, headers=HEADERS)
    return user_id_response.json().get("data", {}).get("user", {}).get("id")

def assign_pr_author_to_issue(issue_id, user_id):
    mutation = """
        mutation ($issueId: ID!, $assigneeId: ID!) {
            addAssigneesToAssignable(input: {assignableId: $issueId, assigneeIds: [$assigneeId]}) {
                assignable {
                    ... on Issue {
                        number
                    }
                }
            }
        }
    """
    print("query: ", mutation)
    mutation_variables = {"owner": REPO_OWNER, "name": REPO_NAME, "issueId": issue_id, "assignee": user_id}
    print("variables: ", mutation_variables)
    return requests.post(GITHUB_API_URL, json={"query": mutation, "variables": mutation_variables}, headers=HEADERS)

def main():
    print(f"🔍 Checking linked issues for PR #{PR_NUMBER}")

    linked_issues = get_issues_from_pr()
    if not linked_issues:
        print("No linked issues found.")
        return
    print(f"Linked issues: {linked_issues}")

    for linked_issue in linked_issues:
        issue_id = linked_issue["node"]["id"]
        issue_number = linked_issue["node"]["number"]

        assignees_on_issue = get_assignees_on_issue(issue_number)
        if assignees_on_issue:
            print(f"🔍 Issue #{issue_number} already has an assignee, skipping.")
            return

        user_id = get_user_id(PR_AUTHOR)

        response = assign_pr_author_to_issue(issue_id, user_id)

        print("response: ", response.json())

        if response.status_code == 200:
            print(f"✅ Assigned {PR_AUTHOR} to issue #{issue_number}")
        else:
            print(f"❌ Failed to assign {PR_AUTHOR} to issue #{issue_number}: {response.text}")


if __name__ == "__main__":
    main()
