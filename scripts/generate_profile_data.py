#!/usr/bin/env python3
"""
generate_profile_data.py
Fetches native GitHub stats and public events, generates SVG cards,
and updates README.md with recent activity.
Runs seamlessly in GitHub Actions (or locally with fallback data).
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime

# Configuration
USERNAME = os.getenv("GITHUB_USERNAME", "azhar22k")
TOKEN = os.getenv("GITHUB_TOKEN", "")
README_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "README.md")
ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")

# Default fallback language colors if not provided by GraphQL
LANGUAGE_COLORS = {
    "HCL": "#844FBA",
    "Terraform": "#844FBA",
    "Python": "#3572A5",
    "Shell": "#89e051",
    "Bash": "#89e051",
    "Go": "#00ADD8",
    "JavaScript": "#f1e05a",
    "TypeScript": "#3178c6",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "Dockerfile": "#384d54",
    "Makefile": "#427819",
    "YAML": "#cb171e",
}

def make_request(url, headers=None, data=None):
    """Safe HTTP request helper with error handling."""
    req = urllib.request.Request(url, headers=headers or {}, data=data)
    req.add_header("User-Agent", "Profile-Stats-Generator")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as err:
        print(f"Request failed for {url}: {err}", file=sys.stderr)
        return None

def fetch_graphql_stats(username, token):
    """Fetches user repository and contribution statistics via GraphQL API."""
    if not token:
        print("No GITHUB_TOKEN provided, skipping GraphQL stats query.")
        return None

    query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          totalCommitContributions
          restrictedContributionsCount
          totalIssueContributions
          totalPullRequestContributions
          totalPullRequestReviewContributions
        }
        repositories(first: 100, ownerAffiliations: OWNER, isFork: false) {
          totalCount
          nodes {
            name
            stargazerCount
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges {
                size
                node {
                  name
                  color
                }
              }
            }
          }
        }
      }
    }
    """
    url = "https://api.github.com/graphql"
    payload = json.dumps({"query": query, "variables": {"login": username}}).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "Profile-Stats-Generator",
    }

    resp = make_request(url, headers=headers, data=payload)
    if not resp or "data" not in resp or not resp["data"].get("user"):
        print("GraphQL response was empty or contained errors:", resp, file=sys.stderr)
        return None

    user = resp["data"]["user"]
    contribs = user["contributionsCollection"]
    repos = user["repositories"]["nodes"]

    total_stars = sum(repo["stargazerCount"] for repo in repos)
    total_commits = contribs["totalCommitContributions"] + contribs.get("restrictedContributionsCount", 0)
    total_prs = contribs["totalPullRequestContributions"]
    total_issues = contribs["totalIssueContributions"]

    # Language calculation
    lang_sizes = {}
    lang_colors = {}
    for repo in repos:
        for edge in repo.get("languages", {}).get("edges", []):
            name = edge["node"]["name"]
            size = edge["size"]
            color = edge["node"]["color"]
            lang_sizes[name] = lang_sizes.get(name, 0) + size
            if color:
                lang_colors[name] = color

    total_bytes = sum(lang_sizes.values()) or 1
    sorted_langs = sorted(lang_sizes.items(), key=lambda x: x[1], reverse=True)[:5]
    top_languages = []
    for name, size in sorted_langs:
        pct = (size / total_bytes) * 100
        top_languages.append({
            "name": name,
            "percentage": round(pct, 1),
            "color": lang_colors.get(name) or LANGUAGE_COLORS.get(name, "#8b949e")
        })

    return {
        "total_stars": total_stars,
        "total_commits": total_commits,
        "total_prs": total_prs,
        "total_issues": total_issues,
        "total_repos": user["repositories"]["totalCount"],
        "top_languages": top_languages,
    }

def fetch_recent_activities(username):
    """Fetches and formats recent public activities from GitHub REST API."""
    url = f"https://api.github.com/users/{username}/events/public?per_page=20"
    events = make_request(url)

    if not events or not isinstance(events, list):
        print("Unable to fetch events or no events found. Using fallback activity.")
        return [
            "Active on cloud infrastructure, DevOps pipelines, and open-source projects.",
            "Exploring new architectures with AWS, Terraform, and Kubernetes."
        ]

    formatted_activities = []
    seen = set()

    for event in events:
        event_type = event.get("type")
        repo_name = event.get("repo", {}).get("name", "")
        repo_url = f"https://github.com/{repo_name}"
        created_at_str = event.get("created_at", "")

        # Format date if possible
        date_display = ""
        if created_at_str:
            try:
                dt = datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%SZ")
                date_display = dt.strftime("%b %d")
            except Exception:
                pass

        activity_str = None

        if event_type == "PushEvent":
            commits = event.get("payload", {}).get("commits", [])
            count = len(commits)
            msg = f"pushed {count} commit{'s' if count != 1 else ''} to [{repo_name}]({repo_url})"
            key = f"push_{repo_name}"
            if key not in seen:
                activity_str = f"🚀 {msg}"
                seen.add(key)

        elif event_type == "PullRequestEvent":
            action = event.get("payload", {}).get("action", "opened")
            pr = event.get("payload", {}).get("pull_request", {})
            pr_num = pr.get("number", "")
            pr_url = pr.get("html_url", repo_url)
            activity_str = f"🔀 {action} PR [#{pr_num} in {repo_name}]({pr_url})"

        elif event_type == "IssuesEvent":
            action = event.get("payload", {}).get("action", "opened")
            issue = event.get("payload", {}).get("issue", {})
            issue_num = issue.get("number", "")
            issue_url = issue.get("html_url", repo_url)
            activity_str = f"🎯 {action} issue [#{issue_num} in {repo_name}]({issue_url})"

        elif event_type == "CreateEvent":
            ref_type = event.get("payload", {}).get("ref_type", "repository")
            if ref_type == "repository":
                activity_str = f"✨ created repository [{repo_name}]({repo_url})"
            elif ref_type in ("tag", "branch"):
                ref = event.get("payload", {}).get("ref", "")
                activity_str = f"🌱 created {ref_type} `{ref}` in [{repo_name}]({repo_url})"

        elif event_type == "WatchEvent":
            activity_str = f"⭐ starred [{repo_name}]({repo_url})"

        elif event_type == "ForkEvent":
            forkee = event.get("payload", {}).get("forkee", {}).get("full_name", "")
            activity_str = f"🍴 forked [{repo_name}]({repo_url})"

        if activity_str:
            if date_display:
                activity_str += f" `({date_display})`"
            formatted_activities.append(activity_str)

        if len(formatted_activities) >= 6:
            break

    return formatted_activities or [
        "Active on cloud infrastructure, DevOps pipelines, and open-source projects."
    ]

def get_default_stats():
    """Fallback stats when running offline or without credentials."""
    return {
        "total_stars": 12,
        "total_commits": 180,
        "total_prs": 24,
        "total_issues": 10,
        "total_repos": 15,
        "top_languages": [
            {"name": "HCL / Terraform", "percentage": 42.5, "color": "#844FBA"},
            {"name": "Python", "percentage": 28.0, "color": "#3572A5"},
            {"name": "Shell", "percentage": 15.5, "color": "#89e051"},
            {"name": "Go", "percentage": 8.5, "color": "#00ADD8"},
            {"name": "Dockerfile", "percentage": 5.5, "color": "#384d54"},
        ],
    }

def generate_svg(stats, theme="dark"):
    """Generates a clean, modern SVG card for stats and top languages."""
    is_dark = (theme == "dark")
    bg_color = "#0d1117" if is_dark else "#ffffff"
    border_color = "#30363d" if is_dark else "#e1e4e8"
    title_color = "#58a6ff" if is_dark else "#0969da"
    text_color = "#c9d1d9" if is_dark else "#24292f"
    muted_color = "#8b949e" if is_dark else "#57606a"
    bar_bg = "#21262d" if is_dark else "#eaeef2"

    width = 620
    height = 200

    # Build multi-color language progress bar
    languages = stats.get("top_languages", [])
    bar_segments = []
    current_x = 330
    bar_width = 250
    bar_height = 10

    for lang in languages:
        seg_w = (lang["percentage"] / 100.0) * bar_width
        if seg_w > 0:
            bar_segments.append(
                f'<rect x="{current_x:.1f}" y="70" width="{seg_w:.1f}" height="{bar_height}" fill="{lang["color"]}" />'
            )
            current_x += seg_w

    # Build language list
    lang_items = []
    y_start = 105
    for i, lang in enumerate(languages[:4]):
        item_y = y_start + (i * 20)
        lang_items.append(f"""
        <circle cx="335" cy="{item_y - 4}" r="4" fill="{lang['color']}" />
        <text x="348" y="{item_y}" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif" font-size="12" fill="{text_color}">{lang['name']}</text>
        <text x="575" y="{item_y}" text-anchor="end" font-family="-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif" font-size="12" font-weight="600" fill="{muted_color}">{lang['percentage']}%</text>
        """)

    svg_content = f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <style>
    .header {{ font: 600 15px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {title_color}; }}
    .stat-label {{ font: 400 13px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {muted_color}; }}
    .stat-value {{ font: 600 13px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {text_color}; }}
  </style>
  <rect x="0.5" y="0.5" rx="8" width="{width - 1}" height="{height - 1}" fill="{bg_color}" stroke="{border_color}"/>
  
  <!-- Left: Overview Stats -->
  <text x="25" y="40" class="header">GitHub Overview</text>
  
  <g transform="translate(25, 68)">
    <text x="0" y="0" class="stat-label">⭐ Total Stars Earned:</text>
    <text x="180" y="0" class="stat-value">{stats['total_stars']}</text>
    
    <text x="0" y="26" class="stat-label">📦 Total Commits:</text>
    <text x="180" y="26" class="stat-value">{stats['total_commits']}</text>
    
    <text x="0" y="52" class="stat-label">🔀 Pull Requests:</text>
    <text x="180" y="52" class="stat-value">{stats['total_prs']}</text>
    
    <text x="0" y="78" class="stat-label">🎯 Issues Opened:</text>
    <text x="180" y="78" class="stat-value">{stats['total_issues']}</text>
    
    <text x="0" y="104" class="stat-label">📚 Repositories:</text>
    <text x="180" y="104" class="stat-value">{stats['total_repos']}</text>
  </g>

  <!-- Divider Line -->
  <line x1="300" y1="25" x2="300" y2="175" stroke="{border_color}" stroke-width="1" />

  <!-- Right: Top Languages -->
  <text x="330" y="40" class="header">Top Languages</text>
  
  <!-- Background progress bar -->
  <rect x="330" y="70" width="{bar_width}" height="{bar_height}" rx="5" fill="{bar_bg}" />
  <g clip-path="url(#bar-clip)">
    {''.join(bar_segments)}
  </g>
  <clipPath id="bar-clip">
    <rect x="330" y="70" width="{bar_width}" height="{bar_height}" rx="5" />
  </clipPath>

  <!-- Language details -->
  {''.join(lang_items)}
</svg>"""
    return svg_content

def update_readme_activity(readme_path, activities):
    """Updates the activity section between designated markers in README.md."""
    if not os.path.exists(readme_path):
        print(f"README file not found at {readme_path}", file=sys.stderr)
        return

    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    marker_start = "<!-- START_SECTION:activity -->"
    marker_end = "<!-- END_SECTION:activity -->"

    if marker_start not in content or marker_end not in content:
        print("Activity markers not found in README.md. Skipping activity update.")
        return

    bullet_points = "\n".join([f"- {act}" for act in activities])
    new_section = f"{marker_start}\n{bullet_points}\n{marker_end}"

    pattern = re.compile(f"{re.escape(marker_start)}.*?{re.escape(marker_end)}", re.DOTALL)
    updated_content = pattern.sub(new_section, content)

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(updated_content)
    print("README.md recent activity updated successfully.")

def main():
    os.makedirs(ASSETS_DIR, exist_ok=True)

    print(f"Generating profile data for user: {USERNAME}")

    # 1. Fetch Stats
    stats = fetch_graphql_stats(USERNAME, TOKEN)
    if not stats:
        print("Using fallback/cached stats data.")
        stats = get_default_stats()

    # 2. Generate Dark & Light SVGs
    dark_svg = generate_svg(stats, theme="dark")
    light_svg = generate_svg(stats, theme="light")

    dark_path = os.path.join(ASSETS_DIR, "stats-dark.svg")
    light_path = os.path.join(ASSETS_DIR, "stats-light.svg")

    with open(dark_path, "w", encoding="utf-8") as f:
        f.write(dark_svg)
    with open(light_path, "w", encoding="utf-8") as f:
        f.write(light_svg)
    print(f"Generated {dark_path} and {light_path}")

    # 3. Fetch Recent Activities & Update README
    activities = fetch_recent_activities(USERNAME)
    update_readme_activity(README_PATH, activities)

if __name__ == "__main__":
    main()

