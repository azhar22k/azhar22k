#!/usr/bin/env python3
"""
generate_profile_data.py
Fetches native GitHub stats, public events, and all organizations contributed
to over the years via GitHub GraphQL & REST APIs.
Generates dark/light SVG cards and updates README.md with:
  1. Overview Stats & Languages SVG
  2. Organizations Contributed To (Over the Years) Showcase & SVG Card
  3. Recent Public Activity Timeline
Runs seamlessly in GitHub Actions (or locally with token or fallback data).
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

# Fallback to local gh CLI token if available and TOKEN is not set
if not TOKEN:
    try:
        import subprocess
        token_out = subprocess.check_output(
            ["gh", "auth", "token"],
            stderr=subprocess.DEVNULL,
            timeout=3
        ).decode("utf-8").strip()
        if token_out:
            TOKEN = token_out
    except Exception:
        pass

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

# Curated high-impact taglines for recognized organizations
ORGANIZATION_TAGLINES = {
    "peak-ai": "Enterprise AI & Cloud Infrastructure",
    "The-PR-Agent": "AI-Powered Automated PR Code Reviews",
    "localstack": "Local AWS Cloud Development Platform",
    "aws-cloudformation": "AWS Infrastructure as Code (IaC)",
    "camptocamp": "Open Source DevOps & Terraform State",
    "apache": "Open-Source Data Exploration (Superset)",
    "simple-icons": "Developer Tech & Brand SVG Icons",
    "npm": "JavaScript Package Manager Ecosystem",
}

# Clean display names for SVG card pill badges (concise to prevent overlap)
ORGANIZATION_SVG_NAMES = {
    "peak-ai": "Peak AI",
    "The-PR-Agent": "PR Agent",
    "localstack": "LocalStack",
    "aws-cloudformation": "AWS Cloud",
    "camptocamp": "Camptocamp",
    "apache": "Apache",
    "simple-icons": "Simple Icons",
    "npm": "npm",
}

def make_request(url, headers=None, data=None):
    """Safe HTTP request helper with error handling."""
    req_headers = headers.copy() if headers else {}
    if "User-Agent" not in req_headers:
        req_headers["User-Agent"] = "Profile-Stats-Generator"
    if TOKEN and "Authorization" not in req_headers:
        req_headers["Authorization"] = f"Bearer {TOKEN}"

    req = urllib.request.Request(url, headers=req_headers, data=data)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as err:
        print(f"Request failed for {url}: {err}", file=sys.stderr)
        return None

def format_year_ranges(years):
    """Formats a list/set of integer years into clean human-readable ranges, e.g. '2019 — 2026'."""
    if not years:
        return ""
    sorted_years = sorted(list(years))
    ranges = []
    start = sorted_years[0]
    prev = sorted_years[0]
    for y in sorted_years[1:]:
        if y == prev + 1:
            prev = y
        else:
            if start == prev:
                ranges.append(str(start))
            else:
                ranges.append(f"{start} — {prev}")
            start = y
            prev = y
    if start == prev:
        ranges.append(str(start))
    else:
        ranges.append(f"{start} — {prev}")
    return ", ".join(ranges)

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
    headers = {"Content-Type": "application/json"}

    resp = make_request(url, headers=headers, data=payload)
    if not resp or "data" not in resp or not resp["data"].get("user"):
        print("GraphQL stats response was empty or contained errors:", resp, file=sys.stderr)
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

def get_default_stats():
    """Fallback stats when running offline or without credentials."""
    return {
        "total_stars": 14,
        "total_commits": 328,
        "total_prs": 20,
        "total_issues": 10,
        "total_repos": 14,
        "top_languages": [
            {"name": "HCL / Terraform", "percentage": 42.5, "color": "#844FBA"},
            {"name": "Python", "percentage": 28.0, "color": "#3572A5"},
            {"name": "Shell", "percentage": 15.5, "color": "#89e051"},
            {"name": "Go", "percentage": 8.5, "color": "#00ADD8"},
            {"name": "Dockerfile", "percentage": 5.5, "color": "#384d54"},
        ],
    }

def get_default_organizations():
    """Comprehensive fallback list of organizations contributed to over the years."""
    return [
        {
            "login": "peak-ai",
            "name": "Peak AI",
            "avatar_url": "https://avatars.githubusercontent.com/u/52752607?v=4",
            "url": "https://github.com/peak-ai",
            "description": "Enterprise Decision Intelligence & Cloud Infrastructure",
            "tagline": "Enterprise AI & Cloud Infrastructure",
            "years": [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026],
            "years_display": "2019 — 2026",
            "total_contributions": 141,
            "repos": [
                {"name": "jedlik", "url": "https://github.com/peak-ai/jedlik"},
                {"name": "eks-token", "url": "https://github.com/peak-ai/eks-token"},
                {"name": "terraform-modules", "url": "https://github.com/peak-ai/terraform-modules"},
            ],
            "more_repos_count": 6,
        },
        {
            "login": "The-PR-Agent",
            "name": "The PR Agent",
            "avatar_url": "https://avatars.githubusercontent.com/u/264152072?v=4",
            "url": "https://github.com/The-PR-Agent",
            "description": "AI-powered tool for automated PR code reviews",
            "tagline": "AI-Powered Automated PR Code Reviews",
            "years": [2026],
            "years_display": "2026",
            "total_contributions": 8,
            "repos": [
                {"name": "pr-agent", "url": "https://github.com/The-PR-Agent/pr-agent"},
            ],
            "more_repos_count": 0,
        },
        {
            "login": "localstack",
            "name": "LocalStack",
            "avatar_url": "https://avatars.githubusercontent.com/u/28732122?v=4",
            "url": "https://github.com/localstack",
            "description": "The leading platform for local cloud development",
            "tagline": "Local AWS Cloud Development Platform",
            "years": [2026],
            "years_display": "2026",
            "total_contributions": 3,
            "repos": [
                {"name": "pulumi-local", "url": "https://github.com/localstack/pulumi-local"},
                {"name": "rolo", "url": "https://github.com/localstack/rolo"},
            ],
            "more_repos_count": 0,
        },
        {
            "login": "aws-cloudformation",
            "name": "AWS CloudFormation",
            "avatar_url": "https://avatars.githubusercontent.com/u/19900777?v=4",
            "url": "https://github.com/aws-cloudformation",
            "description": "Public coverage roadmap for AWS CloudFormation",
            "tagline": "AWS Infrastructure as Code (IaC)",
            "years": [2022],
            "years_display": "2022",
            "total_contributions": 1,
            "repos": [
                {"name": "coverage-roadmap", "url": "https://github.com/aws-cloudformation/cloudformation-coverage-roadmap"},
            ],
            "more_repos_count": 0,
        },
        {
            "login": "apache",
            "name": "The Apache Software Foundation",
            "avatar_url": "https://avatars.githubusercontent.com/u/47359?v=4",
            "url": "https://github.com/apache",
            "description": "Open-source data exploration & visualization platform",
            "tagline": "Open-Source Data Exploration (Superset)",
            "years": [2020],
            "years_display": "2020",
            "total_contributions": 2,
            "repos": [
                {"name": "superset", "url": "https://github.com/apache/superset"},
            ],
            "more_repos_count": 0,
        },
        {
            "login": "camptocamp",
            "name": "Camptocamp",
            "avatar_url": "https://avatars.githubusercontent.com/u/28109?v=4",
            "url": "https://github.com/camptocamp",
            "description": "Innovative Solutions by Open Source Experts",
            "tagline": "Open Source DevOps & Terraform State",
            "years": [2020, 2021],
            "years_display": "2020 — 2021",
            "total_contributions": 3,
            "repos": [
                {"name": "terraboard", "url": "https://github.com/camptocamp/terraboard"},
            ],
            "more_repos_count": 0,
        },
        {
            "login": "simple-icons",
            "name": "Simple Icons",
            "avatar_url": "https://avatars.githubusercontent.com/u/29872746?v=4",
            "url": "https://github.com/simple-icons",
            "description": "Free SVG icons for popular brands",
            "tagline": "Developer Tech & Brand SVG Icons",
            "years": [2020],
            "years_display": "2020",
            "total_contributions": 1,
            "repos": [
                {"name": "simple-icons", "url": "https://github.com/simple-icons/simple-icons"},
            ],
            "more_repos_count": 0,
        },
        {
            "login": "npm",
            "name": "npm",
            "avatar_url": "https://avatars.githubusercontent.com/u/6078720?v=4",
            "url": "https://github.com/npm",
            "description": "JavaScript package manager registry & website",
            "tagline": "JavaScript Package Manager Ecosystem",
            "years": [2020],
            "years_display": "2020",
            "total_contributions": 1,
            "repos": [
                {"name": "npm-expansions", "url": "https://github.com/npm/npm-expansions"},
            ],
            "more_repos_count": 0,
        },
    ]

def fetch_contributed_organizations(username, token):
    """
    Fetches all organizations contributed to across all available contribution years
    via GitHub GraphQL API. Aggregates years, repositories, and contribution events.
    """
    if not token:
        print("No GITHUB_TOKEN provided, using fallback organizations data.")
        return get_default_organizations()

    url = "https://api.github.com/graphql"

    # Step 1: Discover all contribution years for the user
    years_query = """
    query($login: String!) {
      user(login: $login) {
        contributionsCollection {
          contributionYears
        }
      }
    }
    """
    payload = json.dumps({"query": years_query, "variables": {"login": username}}).encode("utf-8")
    resp = make_request(url, headers={"Content-Type": "application/json"}, data=payload)

    if not resp or "data" not in resp or not resp["data"].get("user"):
        print("Failed to fetch contribution years via GraphQL. Using fallback organizations.")
        return get_default_organizations()

    contribution_years = resp["data"]["user"]["contributionsCollection"].get("contributionYears", [])
    if not contribution_years:
        return get_default_organizations()

    # Step 2: Build batched subqueries across all contribution years
    subqueries = []
    for y in contribution_years:
        subqueries.append(f"""
        y_{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{y}-12-31T23:59:59Z") {{
          commitContributionsByRepository(maxRepositories: 100) {{
            contributions {{ totalCount }}
            repository {{
              name
              nameWithOwner
              url
              owner {{
                __typename
                login
                avatarUrl
                url
                ... on Organization {{
                  name
                  description
                }}
              }}
            }}
          }}
          pullRequestContributionsByRepository(maxRepositories: 100) {{
            contributions {{ totalCount }}
            repository {{
              name
              nameWithOwner
              url
              owner {{
                __typename
                login
                avatarUrl
                url
                ... on Organization {{
                  name
                  description
                }}
              }}
            }}
          }}
          issueContributionsByRepository(maxRepositories: 100) {{
            contributions {{ totalCount }}
            repository {{
              name
              nameWithOwner
              url
              owner {{
                __typename
                login
                avatarUrl
                url
                ... on Organization {{
                  name
                  description
                }}
              }}
            }}
          }}
          pullRequestReviewContributionsByRepository(maxRepositories: 100) {{
            contributions {{ totalCount }}
            repository {{
              name
              nameWithOwner
              url
              owner {{
                __typename
                login
                avatarUrl
                url
                ... on Organization {{
                  name
                  description
                }}
              }}
            }}
          }}
        }}
        """)

    batched_query = f"""
    query($login: String!) {{
      user(login: $login) {{
        repositoriesContributedTo(first: 100, contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY, PULL_REQUEST_REVIEW]) {{
          nodes {{
            name
            nameWithOwner
            url
            owner {{
              __typename
              login
              avatarUrl
              url
              ... on Organization {{
                name
                description
              }}
            }}
          }}
        }}
        organizations(first: 100) {{
          nodes {{
            login
            name
            avatarUrl
            url
            description
          }}
        }}
        {" ".join(subqueries)}
      }}
    }}
    """

    payload_full = json.dumps({"query": batched_query, "variables": {"login": username}}).encode("utf-8")
    resp_full = make_request(url, headers={"Content-Type": "application/json"}, data=payload_full)

    if not resp_full or "data" not in resp_full or not resp_full["data"].get("user"):
        print("Failed to fetch detailed contribution tree. Using fallback organizations.")
        return get_default_organizations()

    user_data = resp_full["data"]["user"]
    orgs_map = {}

    def process_item(owner, repo=None, year=None, count=1):
        if not owner or owner.get("__typename") != "Organization":
            return
        login = owner.get("login")
        if not login or login.lower() == username.lower():
            return

        if login not in orgs_map:
            raw_name = owner.get("name") or login
            raw_desc = (owner.get("description") or "").strip()
            orgs_map[login] = {
                "login": login,
                "name": raw_name,
                "avatar_url": owner.get("avatarUrl", ""),
                "url": owner.get("url") or f"https://github.com/{login}",
                "description": raw_desc,
                "repos": {},  # name -> {"url": ..., "count": ...}
                "years": set(),
                "total_contributions": 0,
            }

        if year:
            orgs_map[login]["years"].add(year)
        orgs_map[login]["total_contributions"] += count

        if repo:
            r_name = repo.get("name", "")
            r_url = repo.get("url", "")
            if r_name and r_url:
                if r_name not in orgs_map[login]["repos"]:
                    orgs_map[login]["repos"][r_name] = {"name": r_name, "url": r_url, "count": 0}
                orgs_map[login]["repos"][r_name]["count"] += count

    # 1. Process yearly contributions
    for key, coll in user_data.items():
        if not key.startswith("y_"):
            continue
        try:
            year = int(key.replace("y_", ""))
        except ValueError:
            continue

        for ctype in [
            "commitContributionsByRepository",
            "pullRequestContributionsByRepository",
            "issueContributionsByRepository",
            "pullRequestReviewContributionsByRepository",
        ]:
            for item in coll.get(ctype, []):
                cnt = item.get("contributions", {}).get("totalCount", 1)
                repo = item.get("repository", {})
                owner = repo.get("owner", {})
                process_item(owner, repo=repo, year=year, count=cnt)

    # 2. Process repositoriesContributedTo
    for repo in user_data.get("repositoriesContributedTo", {}).get("nodes", []):
        owner = repo.get("owner", {})
        process_item(owner, repo=repo, count=1)

    # 3. Process direct public organization memberships
    for org_node in user_data.get("organizations", {}).get("nodes", []):
        login = org_node.get("login")
        if login and login.lower() != username.lower():
            if login not in orgs_map:
                orgs_map[login] = {
                    "login": login,
                    "name": org_node.get("name") or login,
                    "avatar_url": org_node.get("avatarUrl", ""),
                    "url": org_node.get("url") or f"https://github.com/{login}",
                    "description": (org_node.get("description") or "").strip(),
                    "repos": {},
                    "years": set(),
                    "total_contributions": 1,
                }

    if not orgs_map:
        return get_default_organizations()

    # Convert to structured list with display fields
    final_orgs = []
    for login, item in orgs_map.items():
        years_list = sorted(list(item["years"]))
        years_display = format_year_ranges(years_list) if years_list else "Contributor"

        # Determine concise tagline
        tagline = ORGANIZATION_TAGLINES.get(login)
        if not tagline:
            desc = item["description"]
            if desc:
                tagline = desc if len(desc) <= 50 else desc[:47] + "…"
            else:
                tagline = "Open Source Ecosystem"

        # Sort repositories by contribution count descending
        sorted_repos = sorted(item["repos"].values(), key=lambda r: r["count"], reverse=True)
        displayed_repos = [{"name": r["name"], "url": r["url"]} for r in sorted_repos[:3]]
        more_count = max(0, len(sorted_repos) - 3)

        final_orgs.append({
            "login": login,
            "name": item["name"],
            "avatar_url": item["avatar_url"],
            "url": item["url"],
            "description": item["description"],
            "tagline": tagline,
            "years": years_list,
            "years_display": years_display,
            "total_contributions": item["total_contributions"],
            "repos": displayed_repos,
            "more_repos_count": more_count,
        })

    # Sort organizations by most recent active year descending, then total contributions descending
    final_orgs.sort(
        key=lambda x: (max(x["years"]) if x["years"] else 0, x["total_contributions"]),
        reverse=True
    )

    return final_orgs

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

def generate_orgs_svg(orgs, theme="dark"):
    """
    Generates a high-quality SVG overview card highlighting:
      Executive overview metrics for Organizations & Open Source contributions.
    """
    is_dark = (theme == "dark")
    bg_color = "#0d1117" if is_dark else "#ffffff"
    border_color = "#30363d" if is_dark else "#e1e4e8"
    title_color = "#58a6ff" if is_dark else "#0969da"
    text_color = "#c9d1d9" if is_dark else "#24292f"
    muted_color = "#8b949e" if is_dark else "#57606a"
    tile_bg = "#161b22" if is_dark else "#f6f8fa"
    tile_border = "#30363d" if is_dark else "#d0d7de"

    width = 620
    height = 140

    total_orgs = len(orgs)
    all_years = set()
    for o in orgs:
        for y in o.get("years", []):
            all_years.add(y)

    min_year = min(all_years) if all_years else 2019
    max_year = max(all_years) if all_years else 2026
    year_span = f"{min_year} — {max_year}"
    year_diff = (max_year - min_year + 1) if min_year and max_year else 7
    total_contribs = sum(o.get("total_contributions", 1) for o in orgs)

    svg_content = f"""<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
  <style>
    .header {{ font: 600 15px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {title_color}; }}
    .sub-header {{ font: 400 11px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {muted_color}; }}
    .tile-title {{ font: 600 13px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {text_color}; }}
    .tile-sub {{ font: 400 11px -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; fill: {muted_color}; }}
  </style>
  <rect x="0.5" y="0.5" rx="8" width="{width - 1}" height="{height - 1}" fill="{bg_color}" stroke="{border_color}"/>
  
  <!-- Header -->
  <text x="25" y="36" class="header">Organizations &amp; Open Source</text>
  <text x="25" y="53" class="sub-header">Multi-year engineering contributions across open-source ecosystems</text>
  
  <!-- Tile 1: Organizations -->
  <g transform="translate(25, 68)">
    <rect width="180" height="52" rx="6" fill="{tile_bg}" stroke="{tile_border}" stroke-width="1" />
    <text x="14" y="22" class="tile-title">🏢 {total_orgs} Organizations</text>
    <text x="14" y="39" class="tile-sub">Active OSS &amp; industry partners</text>
  </g>

  <!-- Tile 2: Active Timeline -->
  <g transform="translate(220, 68)">
    <rect width="180" height="52" rx="6" fill="{tile_bg}" stroke="{tile_border}" stroke-width="1" />
    <text x="14" y="22" class="tile-title">📅 {year_span}</text>
    <text x="14" y="39" class="tile-sub">{year_diff}+ years continuous activity</text>
  </g>

  <!-- Tile 3: Contributions & Focus -->
  <g transform="translate(415, 68)">
    <rect width="180" height="52" rx="6" fill="{tile_bg}" stroke="{tile_border}" stroke-width="1" />
    <text x="14" y="22" class="tile-title">⚡ {total_contribs}+ Activities</text>
    <text x="14" y="39" class="tile-sub">Cloud • AI • IaC • DevOps</text>
  </g>
</svg>"""
    return svg_content

def generate_orgs_markdown(orgs):
    """
    Generates a picture card and an inline row of org avatar links.
    Uses a <p> of inline <a><img></a> elements instead of a table —
    GitHub wraps every <table> in <markdown-accessiblity-table> which
    creates a full-width block that terminates the right-side float.
    Inline images in a <p> flow correctly beside the spine image.
    """
    picture_banner = """<picture>
  <source media="(prefers-color-scheme: dark)" srcset="./assets/orgs-dark.svg" />
  <source media="(prefers-color-scheme: light)" srcset="./assets/orgs-light.svg" />
  <img alt="Organizations Contributed To" src="./assets/orgs-dark.svg" width="620" />
</picture>"""

    # Inline org avatars — flows beside right-side spine float
    orgs_p_lines = ['<p align="left">']
    for i, org in enumerate(orgs):
        name = org["name"]
        url = org["url"]
        avatar = org["avatar_url"]
        years_disp = org.get("years_display", "")
        tagline = org.get("tagline", "")
        title_text = f"{name} · {years_disp} · {tagline}" if tagline else f"{name} · {years_disp}"
        # Escape & in title attribute
        title_text = title_text.replace("&", "&amp;")
        separator = "&nbsp;" if i < len(orgs) - 1 else ""
        orgs_p_lines.append(
            f'  <a href="{url}" target="_blank">'
            f'<img src="{avatar}" width="54" height="54" alt="{name}" title="{title_text}" /></a>{separator}'
        )
    orgs_p_lines.append("</p>")

    orgs_p = "\n".join(orgs_p_lines)
    return f"{picture_banner}\n\n{orgs_p}"

def update_readme_organizations(readme_path, orgs_markdown):
    """
    Inserts or updates the organizations section between designated markers in README.md.
    If the section does not yet exist, seamlessly adds it before Contribution Graph.
    """
    if not os.path.exists(readme_path):
        print(f"README file not found at {readme_path}", file=sys.stderr)
        return

    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()

    marker_start = "<!-- START_SECTION:organizations -->"
    marker_end = "<!-- END_SECTION:organizations -->"

    if marker_start in content and marker_end in content:
        # Update existing section
        pattern = re.compile(f"{re.escape(marker_start)}.*?{re.escape(marker_end)}", re.DOTALL)
        new_block = f"{marker_start}\n{orgs_markdown}\n{marker_end}"
        updated_content = pattern.sub(new_block, content)
    else:
        # Insert new section before Contribution Graph or Recent Activity
        section_to_insert = f"""---

### 🏢 Organizations Contributed To

{marker_start}
{orgs_markdown}
{marker_end}
"""
        target_heading = "### 🐍 Contribution Graph"
        if target_heading in content:
            updated_content = content.replace(target_heading, f"{section_to_insert}\n{target_heading}")
        else:
            recent_heading = "### ⚡ Recent Activity"
            if recent_heading in content:
                updated_content = content.replace(recent_heading, f"{section_to_insert}\n{recent_heading}")
            else:
                updated_content = content + "\n\n" + section_to_insert

    # Clean up any potential duplicate separator lines
    updated_content = re.sub(r"\n---\s*\n\s*---\n", "\n---\n\n", updated_content)

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(updated_content)
    print("README.md organizations section updated successfully.")

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

    # 1. Fetch Overview Stats
    stats = fetch_graphql_stats(USERNAME, TOKEN)
    if not stats:
        print("Using fallback/cached stats data.")
        stats = get_default_stats()

    # 2. Generate Stats Dark & Light SVGs
    dark_svg = generate_svg(stats, theme="dark")
    light_svg = generate_svg(stats, theme="light")

    dark_stats_path = os.path.join(ASSETS_DIR, "stats-dark.svg")
    light_stats_path = os.path.join(ASSETS_DIR, "stats-light.svg")

    with open(dark_stats_path, "w", encoding="utf-8") as f:
        f.write(dark_svg)
    with open(light_stats_path, "w", encoding="utf-8") as f:
        f.write(light_svg)
    print(f"Generated {dark_stats_path} and {light_stats_path}")

    # 3. Fetch Contributed Organizations Over the Years
    orgs = fetch_contributed_organizations(USERNAME, TOKEN)
    print(f"Loaded {len(orgs)} organizations contributed to over the years.")

    # 4. Generate Organizations Dark & Light SVGs
    dark_orgs_svg = generate_orgs_svg(orgs, theme="dark")
    light_orgs_svg = generate_orgs_svg(orgs, theme="light")

    dark_orgs_path = os.path.join(ASSETS_DIR, "orgs-dark.svg")
    light_orgs_path = os.path.join(ASSETS_DIR, "orgs-light.svg")

    with open(dark_orgs_path, "w", encoding="utf-8") as f:
        f.write(dark_orgs_svg)
    with open(light_orgs_path, "w", encoding="utf-8") as f:
        f.write(light_orgs_svg)
    print(f"Generated {dark_orgs_path} and {light_orgs_path}")

    # 5. Update README Organizations Showcase
    orgs_markdown = generate_orgs_markdown(orgs)
    update_readme_organizations(README_PATH, orgs_markdown)

    # 6. Fetch Recent Activities & Update README
    activities = fetch_recent_activities(USERNAME)
    update_readme_activity(README_PATH, activities)

    print("Profile generation completed successfully!")

if __name__ == "__main__":
    main()
