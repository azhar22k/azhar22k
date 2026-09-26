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

def generate_spine_svg(theme="dark", height=1780):
    """
    Generates the Doctor Strange Mystic Arts Rail vertical spine SVG.
    Includes continuous rotations, laser conduits, rune inscriptions,
    autonomous magnifying lens sweep, and interactive magnifying zoom effects on hover.
    """
    is_dark = theme == "dark"

    beam_grad_id = "mysticBeam" if is_dark else "mysticBeamLight"
    laser_grad_id = "coreLaser" if is_dark else "coreLaserLight"
    glow_filter_id = "intenseGlow" if is_dark else "intenseGlowL"
    laser_filter_id = "laserGlow" if is_dark else "intenseGlowL"

    if is_dark:
        beam_stops = """
      <stop offset="0%" stop-color="#f59e0b" stop-opacity="1"/>
      <stop offset="18%" stop-color="#10b981" stop-opacity="1"/>
      <stop offset="35%" stop-color="#f97316" stop-opacity="1"/>
      <stop offset="58%" stop-color="#a855f7" stop-opacity="1"/>
      <stop offset="80%" stop-color="#06b6d4" stop-opacity="1"/>
      <stop offset="100%" stop-color="#f59e0b" stop-opacity="1"/>"""
        laser_stops = """
      <stop offset="0%" stop-color="#fef08a"/>
      <stop offset="18%" stop-color="#6ee7b7"/>
      <stop offset="35%" stop-color="#fed7aa"/>
      <stop offset="58%" stop-color="#e9d5ff"/>
      <stop offset="80%" stop-color="#a5f3fc"/>
      <stop offset="100%" stop-color="#fef08a"/>"""
        glow_defs = """
    <radialGradient id="vishantiGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#fde047" stop-opacity="0.95"/>
      <stop offset="50%" stop-color="#f59e0b" stop-opacity="0.5"/>
      <stop offset="100%" stop-color="#b45309" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="timeStoneGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#a7f3d0" stop-opacity="1"/>
      <stop offset="40%" stop-color="#10b981" stop-opacity="0.85"/>
      <stop offset="80%" stop-color="#047857" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="#064e3b" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="mandalaGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#fed7aa" stop-opacity="0.95"/>
      <stop offset="40%" stop-color="#f97316" stop-opacity="0.7"/>
      <stop offset="80%" stop-color="#ea580c" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="#7c2d12" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="mirrorGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#e9d5ff" stop-opacity="1"/>
      <stop offset="40%" stop-color="#a855f7" stop-opacity="0.7"/>
      <stop offset="80%" stop-color="#06b6d4" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="#1e1b4b" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="portalGlow" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#fef08a" stop-opacity="1"/>
      <stop offset="45%" stop-color="#f59e0b" stop-opacity="0.8"/>
      <stop offset="80%" stop-color="#ea580c" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="#78350f" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="lensMagnifier" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.35"/>
      <stop offset="60%" stop-color="#38bdf8" stop-opacity="0.15"/>
      <stop offset="90%" stop-color="#f59e0b" stop-opacity="0.6"/>
      <stop offset="100%" stop-color="#f59e0b" stop-opacity="0"/>
    </radialGradient>
    <filter id="intenseGlow" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="3.5" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <filter id="laserGlow" x="-60%" y="-60%" width="220%" height="220%">
      <feGaussianBlur stdDeviation="5" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>"""
        spiral_1_stroke = "#f59e0b"
        spiral_2_stroke = "#10b981"
        sanctum_glow = "url(#vishantiGlow)"
        sanctum_border = "#f59e0b"
        sanctum_ring = "#fde047"
        sanctum_fill = "#140c03"
        sanctum_badge_bg = "#201004"
        sanctum_badge_stroke = "#f59e0b"
        sanctum_badge_txt = "#fde047"

        timestone_glow = "url(#timeStoneGlow)"
        timestone_border = "#f59e0b"
        timestone_eye_fill1 = "#062217"
        timestone_eye_fill2 = "#021c12"
        timestone_eye_stroke = "#34d399"
        timestone_badge_bg = "#042318"
        timestone_badge_stroke = "#10b981"
        timestone_badge_txt = "#a7f3d0"

        mandala_glow = "url(#mandalaGlow)"
        mandala_bg = "#240c03"
        mandala_badge_bg = "#2a0d03"
        mandala_badge_stroke = "#f97316"
        mandala_badge_txt = "#fed7aa"

        mirror_glow = "url(#mirrorGlow)"
        mirror_bg = "#130924"
        mirror_badge_bg = "#1b082e"
        mirror_badge_stroke = "#c084fc"
        mirror_badge_txt = "#e9d5ff"

        astral_glow = "url(#portalGlow)"
        astral_bg = "#091b29"
        astral_badge_bg = "#081824"
        astral_badge_stroke = "#38bdf8"
        astral_badge_txt = "#bae6fd"

        portal_glow = "url(#portalGlow)"
        portal_bg = "#1f0c03"
        portal_badge_bg = "#240e03"
        portal_badge_stroke = "#f59e0b"
        portal_badge_txt = "#fde047"

        spark_1 = ("#ffffff", "#fde047", "#f97316")
        spark_2 = ("#a7f3d0", "#34d399", "#059669")
        spark_3 = ("#ffffff", "#fb923c", "#ea580c")
        spark_4 = ("#e9d5ff", "#c084fc", "#7c3aed")
        spark_5 = ("#67e8f9", "#06b6d4")
    else:
        beam_stops = """
      <stop offset="0%" stop-color="#d97706" stop-opacity="1"/>
      <stop offset="18%" stop-color="#059669" stop-opacity="1"/>
      <stop offset="35%" stop-color="#ea580c" stop-opacity="1"/>
      <stop offset="58%" stop-color="#7c3aed" stop-opacity="1"/>
      <stop offset="80%" stop-color="#0284c7" stop-opacity="1"/>
      <stop offset="100%" stop-color="#d97706" stop-opacity="1"/>"""
        laser_stops = """
      <stop offset="0%" stop-color="#b45309"/>
      <stop offset="18%" stop-color="#047857"/>
      <stop offset="35%" stop-color="#c2410c"/>
      <stop offset="58%" stop-color="#6d28d9"/>
      <stop offset="80%" stop-color="#0369a1"/>
      <stop offset="100%" stop-color="#b45309"/>"""
        glow_defs = """
    <radialGradient id="vishantiGlowLight" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#fef08a" stop-opacity="1"/>
      <stop offset="50%" stop-color="#f59e0b" stop-opacity="0.45"/>
      <stop offset="100%" stop-color="#d97706" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="timeStoneGlowLight" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#a7f3d0" stop-opacity="1"/>
      <stop offset="45%" stop-color="#10b981" stop-opacity="0.6"/>
      <stop offset="80%" stop-color="#059669" stop-opacity="0.2"/>
      <stop offset="100%" stop-color="#047857" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="mandalaGlowLight" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#fed7aa" stop-opacity="1"/>
      <stop offset="50%" stop-color="#f97316" stop-opacity="0.5"/>
      <stop offset="80%" stop-color="#ea580c" stop-opacity="0.2"/>
      <stop offset="100%" stop-color="#c2410c" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="mirrorGlowLight" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#f3e8ff" stop-opacity="1"/>
      <stop offset="50%" stop-color="#c084fc" stop-opacity="0.5"/>
      <stop offset="80%" stop-color="#9333ea" stop-opacity="0.2"/>
      <stop offset="100%" stop-color="#6b21a8" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="portalGlowLight" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#fef3c7" stop-opacity="1"/>
      <stop offset="50%" stop-color="#f59e0b" stop-opacity="0.6"/>
      <stop offset="80%" stop-color="#d97706" stop-opacity="0.2"/>
      <stop offset="100%" stop-color="#b45309" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="lensMagnifierLight" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#ffffff" stop-opacity="0.4"/>
      <stop offset="60%" stop-color="#0284c7" stop-opacity="0.15"/>
      <stop offset="90%" stop-color="#d97706" stop-opacity="0.5"/>
      <stop offset="100%" stop-color="#d97706" stop-opacity="0"/>
    </radialGradient>
    <filter id="intenseGlowL" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>"""
        spiral_1_stroke = "#b45309"
        spiral_2_stroke = "#047857"
        sanctum_glow = "url(#vishantiGlowLight)"
        sanctum_border = "#b45309"
        sanctum_ring = "#d97706"
        sanctum_fill = "#fffbeb"
        sanctum_badge_bg = "#fef3c7"
        sanctum_badge_stroke = "#d97706"
        sanctum_badge_txt = "#92400e"

        timestone_glow = "url(#timeStoneGlowLight)"
        timestone_border = "#047857"
        timestone_eye_fill1 = "#ecfdf5"
        timestone_eye_fill2 = "#d1fae5"
        timestone_eye_stroke = "#059669"
        timestone_badge_bg = "#d1fae5"
        timestone_badge_stroke = "#059669"
        timestone_badge_txt = "#065f46"

        mandala_glow = "url(#mandalaGlowLight)"
        mandala_bg = "#fff7ed"
        mandala_badge_bg = "#ffedd5"
        mandala_badge_stroke = "#ea580c"
        mandala_badge_txt = "#9a3412"

        mirror_glow = "url(#mirrorGlowLight)"
        mirror_bg = "#faf5ff"
        mirror_badge_bg = "#f3e8ff"
        mirror_badge_stroke = "#9333ea"
        mirror_badge_txt = "#581c87"

        astral_glow = "url(#portalGlowLight)"
        astral_bg = "#f0f9ff"
        astral_badge_bg = "#e0f2fe"
        astral_badge_stroke = "#0284c7"
        astral_badge_txt = "#075985"

        portal_glow = "url(#portalGlowLight)"
        portal_bg = "#fffbeb"
        portal_badge_bg = "#fef3c7"
        portal_badge_stroke = "#d97706"
        portal_badge_txt = "#92400e"

        spark_1 = ("#d97706", "#f59e0b", "#fbbf24")
        spark_2 = ("#059669", "#10b981", "#34d399")
        spark_3 = ("#ea580c", "#f97316", "#fed7aa")
        spark_4 = ("#7c3aed", "#a855f7", "#c084fc")
        spark_5 = ("#0284c7", "#38bdf8")

    spiral_d1 = "M45,20 Q30,105 45,190 Q60,275 45,360 Q30,445 45,530 Q60,615 45,700 Q30,785 45,870 Q60,955 45,1040 Q30,1125 45,1210 Q60,1295 45,1380 Q30,1465 45,1550 Q60,1635 45,1720 Q45,1740 45,1750"
    spiral_d2 = "M45,20 Q60,105 45,190 Q30,275 45,360 Q60,445 45,530 Q30,615 45,700 Q60,785 45,870 Q30,955 45,1040 Q60,1125 45,1210 Q30,1295 45,1380 Q60,1465 45,1550 Q30,1635 45,1720 Q45,1740 45,1750"

    badge_fill = "#ffffff" if is_dark else "#1e293b"
    rail_hover_color = "rgba(245, 158, 11, 0.7)" if is_dark else "rgba(217, 119, 6, 0.6)"
    hover_shadow_1 = "#f59e0b" if is_dark else "#d97706"
    hover_shadow_2 = "#10b981" if is_dark else "#059669"
    rune_hover_fill = "#ffffff" if is_dark else "#1e293b"
    rune_hover_glow = "#fde047" if is_dark else "#f59e0b"
    sanctum_sub_stroke = sanctum_ring if is_dark else "#d97706"
    sanctum_dot = "#ffffff" if is_dark else "#f59e0b"
    lens_grad = "lensMagnifier" if is_dark else "lensMagnifierLight"
    lens_stroke = "#fde047" if is_dark else "#d97706"
    lens_inner_stroke = "#38bdf8" if is_dark else "#0284c7"
    lens_cross = "#ffffff" if is_dark else "#d97706"

    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 90 {height}" width="90" height="{height}" fill="none">
  <defs>
    <!-- Doctor Strange Color Gradients -->
    <linearGradient id="{beam_grad_id}" x1="0%" y1="0%" x2="0%" y2="100%">{beam_stops}
    </linearGradient>

    <linearGradient id="{laser_grad_id}" x1="0%" y1="0%" x2="0%" y2="100%">{laser_stops}
    </linearGradient>

    <!-- Node Glow Gradients -->{glow_defs}
  </defs>

  <style>
    <![CDATA[
    /* Continuous High-Speed Keyframe Animations */
    @keyframes fastSpinCW {{
      0% {{ transform: rotate(0deg); }}
      100% {{ transform: rotate(360deg); }}
    }}
    @keyframes fastSpinCCW {{
      0% {{ transform: rotate(360deg); }}
      100% {{ transform: rotate(0deg); }}
    }}
    @keyframes pulseScale {{
      0%, 100% {{ transform: scale(1); opacity: 0.8; }}
      50% {{ transform: scale(1.18); opacity: 1; filter: drop-shadow(0 0 10px #f59e0b); }}
    }}
    @keyframes timeDilationWave {{
      0% {{ r: 8px; opacity: 1; stroke-width: 3px; }}
      50% {{ r: 26px; opacity: 0.7; stroke-width: 2px; }}
      100% {{ r: 42px; opacity: 0; stroke-width: 0.5px; }}
    }}
    @keyframes laserRush {{
      0% {{ stroke-dashoffset: 0; }}
      100% {{ stroke-dashoffset: -120; }}
    }}
    @keyframes sparkCascade1 {{
      0% {{ transform: translateY(0px); opacity: 0; }}
      3% {{ opacity: 1; }}
      97% {{ opacity: 1; }}
      100% {{ transform: translateY(1730px); opacity: 0; }}
    }}
    @keyframes sparkCascade2 {{
      0% {{ transform: translateY(0px); opacity: 0; }}
      3% {{ opacity: 1; }}
      97% {{ opacity: 1; }}
      100% {{ transform: translateY(1730px); opacity: 0; }}
    }}
    @keyframes runeGlow {{
      0%, 100% {{ opacity: 0.45; }}
      50% {{ opacity: 1; }}
    }}
    
    /* Autonomous Magnifying Lens Pulse Sweep */
    @keyframes magnifyingLensSweep {{
      0% {{ transform: translateY(20px) scale(1); opacity: 0.2; }}
      10% {{ opacity: 0.9; }}
      50% {{ transform: translateY(880px) scale(1.15); opacity: 0.95; }}
      90% {{ opacity: 0.9; }}
      100% {{ transform: translateY(1720px) scale(1); opacity: 0.2; }}
    }}

    /* Interactive Hover & Magnifying Zoom Transitions */
    .mystic-rail {{
      transform-origin: center top;
      transition: filter 0.4s ease;
    }}
    svg:hover .mystic-rail {{
      filter: drop-shadow(0 0 12px {rail_hover_color});
    }}
    
    .interactive-node {{
      cursor: pointer;
      transition: transform 0.38s cubic-bezier(0.34, 1.56, 0.64, 1), filter 0.35s ease;
    }}
    .interactive-node:hover {{
      transform: scale(1.24) !important;
      filter: drop-shadow(0 0 18px {hover_shadow_1}) drop-shadow(0 0 32px {hover_shadow_2}) brightness(1.25);
    }}
    
    .node-1 {{ transform-origin: 45px 75px; }}
    .node-2 {{ transform-origin: 45px 380px; }}
    .node-3 {{ transform-origin: 45px 720px; }}
    .node-4 {{ transform-origin: 45px 1080px; }}
    .node-5 {{ transform-origin: 45px 1390px; }}
    .node-6 {{ transform-origin: 45px 1700px; }}

    .interactive-rune {{
      cursor: pointer;
      transform-origin: 45px center;
      transition: transform 0.25s cubic-bezier(0.34, 1.56, 0.64, 1), fill 0.25s ease, filter 0.25s ease;
    }}
    .interactive-rune:hover {{
      transform: scale(1.35);
      fill: {rune_hover_fill} !important;
      filter: drop-shadow(0 0 10px {rune_hover_glow});
    }}

    /* Node Rotations */
    .spin-vishanti {{ transform-origin: 45px 75px; animation: fastSpinCW 7s linear infinite; }}
    .spin-vishanti-rev {{ transform-origin: 45px 75px; animation: fastSpinCCW 4s linear infinite; }}
    .pulse-core-1 {{ transform-origin: 45px 75px; animation: pulseScale 2s ease-in-out infinite; }}

    .pulse-eye-core {{ transform-origin: 45px 380px; animation: pulseScale 1.8s ease-in-out infinite; }}
    .time-wave-1 {{ transform-origin: 45px 380px; animation: timeDilationWave 2.4s cubic-bezier(0.1, 0.7, 0.1, 1) infinite; }}
    .time-wave-2 {{ transform-origin: 45px 380px; animation: timeDilationWave 2.4s cubic-bezier(0.1, 0.7, 0.1, 1) infinite 1.2s; }}
    .spin-eye-runes {{ transform-origin: 45px 380px; animation: fastSpinCCW 6s linear infinite; }}

    .spin-mandala-spokes {{ transform-origin: 45px 720px; animation: fastSpinCW 3.5s linear infinite; }}
    .spin-mandala-squares {{ transform-origin: 45px 720px; animation: fastSpinCCW 2.5s linear infinite; }}
    .spin-mandala-inner {{ transform-origin: 45px 720px; animation: fastSpinCW 1.5s linear infinite; }}
    .pulse-mandala {{ transform-origin: 45px 720px; animation: pulseScale 2s ease-in-out infinite; }}

    .spin-mirror-outer {{ transform-origin: 45px 1080px; animation: fastSpinCW 5s linear infinite; }}
    .spin-mirror-inner {{ transform-origin: 45px 1080px; animation: fastSpinCCW 3s linear infinite; }}
    .pulse-mirror {{ transform-origin: 45px 1080px; animation: pulseScale 2.2s ease-in-out infinite; }}

    .spin-astral {{ transform-origin: 45px 1390px; animation: fastSpinCW 4s linear infinite; }}
    .pulse-astral {{ transform-origin: 45px 1390px; animation: pulseScale 1.6s ease-in-out infinite; }}

    .spin-portal-sparks {{ transform-origin: 45px 1700px; animation: fastSpinCW 2s linear infinite; }}
    .spin-portal-inner {{ transform-origin: 45px 1700px; animation: fastSpinCCW 3s linear infinite; }}
    .pulse-portal {{ transform-origin: 45px 1700px; animation: pulseScale 1.5s ease-in-out infinite; }}

    /* Flowing Laser & Braided Lines */
    .conduit-stream-fast {{ stroke-dasharray: 5 8; animation: laserRush 0.4s linear infinite; }}

    /* High-Frequency Cascading Sparks */
    .cascade-1 {{ animation: sparkCascade1 2.3s linear infinite; }}
    .cascade-2 {{ animation: sparkCascade2 2.7s linear infinite 0.4s; }}
    .cascade-3 {{ animation: sparkCascade1 2.0s linear infinite 0.9s; }}
    .cascade-4 {{ animation: sparkCascade2 2.5s linear infinite 1.3s; }}
    .cascade-5 {{ animation: sparkCascade1 2.1s linear infinite 1.7s; }}

    /* Scanning Magnifier Lens */
    .lens-sweep {{
      animation: magnifyingLensSweep 6s ease-in-out infinite alternate;
      transform-origin: 45px 0px;
      pointer-events: none;
    }}

    /* Typography */
    .badge-pill {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; font-size: 6.5px; font-weight: 800; letter-spacing: 1px; fill: {badge_fill}; text-anchor: middle; }}
    .rune-symbol {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; font-size: 7.5px; font-weight: bold; text-anchor: middle; animation: runeGlow 2.5s ease-in-out infinite; }}
    ]]>
  </style>

  <g class="mystic-rail">
    <!-- ==================== VERTICAL CONDUIT SPINE ({height}PX) ==================== -->
    <line x1="45" y1="20" x2="45" y2="1750" stroke="url(#{beam_grad_id})" stroke-width="6" stroke-linecap="round" opacity="0.45" filter="url(#{glow_filter_id})"/>

    <!-- Braided Eldritch energy spirals -->
    <path d="{spiral_d1}" 
          stroke="{spiral_1_stroke}" stroke-width="1.5" fill="none" opacity="0.6" stroke-dasharray="6 6"/>
    <path d="{spiral_d2}" 
          stroke="{spiral_2_stroke}" stroke-width="1.5" fill="none" opacity="0.6" stroke-dasharray="6 6"/>

    <!-- Core laser channel -->
    <line x1="45" y1="20" x2="45" y2="1750" stroke="url(#{laser_grad_id})" stroke-width="2.5" stroke-linecap="round" opacity="0.9"/>
    <line x1="45" y1="20" x2="45" y2="1750" stroke="#ffffff" stroke-width="2" stroke-linecap="round" class="conduit-stream-fast" opacity="0.95"/>

    <!-- Cascading Sling Ring Sparks -->
    <g class="cascade-1">
      <circle cx="45" cy="20" r="4" fill="{spark_1[0]}" filter="url(#{glow_filter_id})"/>
      <circle cx="44" cy="11" r="2.5" fill="{spark_1[1]}"/>
      <circle cx="46" cy="3" r="1.5" fill="{spark_1[2]}"/>
    </g>
    <g class="cascade-2">
      <circle cx="45" cy="20" r="3.8" fill="{spark_2[0]}" filter="url(#{glow_filter_id})"/>
      <circle cx="46" cy="11" r="2.2" fill="{spark_2[1]}"/>
      <circle cx="44" cy="3" r="1.4" fill="{spark_2[2]}"/>
    </g>
    <g class="cascade-3">
      <circle cx="45" cy="20" r="4.2" fill="{spark_3[0]}" filter="url(#{laser_filter_id})"/>
      <circle cx="43" cy="10" r="2.5" fill="{spark_3[1]}"/>
      <circle cx="46" cy="2" r="1.5" fill="{spark_3[2]}"/>
    </g>
    <g class="cascade-4">
      <circle cx="45" cy="20" r="3.6" fill="{spark_4[0]}" filter="url(#{glow_filter_id})"/>
      <circle cx="45" cy="11" r="2.2" fill="{spark_4[1]}"/>
      <circle cx="44" cy="3" r="1.4" fill="{spark_4[2]}"/>
    </g>
    <g class="cascade-5">
      <circle cx="45" cy="20" r="3.5" fill="{spark_5[0]}" filter="url(#{glow_filter_id})"/>
      <circle cx="46" cy="11" r="2" fill="{spark_5[1]}"/>
    </g>

    <!-- ==================== NODE 1: SANCTUM SANCTORUM (Y ≈ 75) ==================== -->
    <g id="node-1-sanctum" class="interactive-node node-1">
      <circle cx="45" cy="75" r="36" fill="{sanctum_glow}" class="pulse-core-1"/>
      <circle cx="45" cy="75" r="32" stroke="{sanctum_border}" stroke-width="1.6" stroke-dasharray="5 5" class="spin-vishanti"/>
      <circle cx="45" cy="75" r="27" stroke="{sanctum_ring}" stroke-width="1" opacity="0.8"/>

      <g class="spin-vishanti-rev" filter="url(#{glow_filter_id})">
        <circle cx="45" cy="75" r="22" stroke="{sanctum_border}" stroke-width="2.5" fill="{sanctum_fill}" fill-opacity="0.85"/>
        <path d="M23,75 C35,75 45,65 45,53 C45,65 55,75 67,75 C55,75 45,85 45,97 C45,85 35,75 23,75 Z" 
              fill="none" stroke="{sanctum_sub_stroke}" stroke-width="2.6" stroke-linecap="round"/>
        <path d="M27,75 C37,75 45,67 45,57 C45,67 53,75 63,75 C53,75 45,83 45,93 C45,83 37,75 27,75 Z" 
              fill="none" stroke="{sanctum_border}" stroke-width="1.3"/>
        <circle cx="45" cy="75" r="4.5" fill="{sanctum_dot}"/>
      </g>

      <rect x="15" y="113" width="60" height="15" rx="7.5" fill="{sanctum_badge_bg}" stroke="{sanctum_badge_stroke}" stroke-width="1.3"/>
      <text x="45" y="123.5" class="badge-pill" fill="{sanctum_badge_txt}">SANCTUM</text>
    </g>

    <!-- RUNES SEGMENT 1 -> 2 -->
    <g opacity="0.9">
      <text x="45" y="165" class="rune-symbol interactive-rune" fill="{'#f59e0b' if is_dark else '#d97706'}">✦ ᚛ ᛟ ᚜ ✦</text>
      <text x="45" y="215" class="rune-symbol interactive-rune" fill="{'#10b981' if is_dark else '#059669'}">◇ K8S ◇</text>
      <text x="45" y="265" class="rune-symbol interactive-rune" fill="{'#f59e0b' if is_dark else '#d97706'}">✦ AWS ✦</text>
      <text x="45" y="315" class="rune-symbol interactive-rune" fill="{'#10b981' if is_dark else '#059669'}">◇ TF ◇</text>
    </g>

    <!-- ==================== NODE 2: EYE OF AGAMOTTO / TIME STONE (Y ≈ 380) ==================== -->
    <g id="node-2-time-stone" class="interactive-node node-2">
      <circle cx="45" cy="380" r="12" stroke="{'#34d399' if is_dark else '#10b981'}" fill="none" class="time-wave-1"/>
      <circle cx="45" cy="380" r="12" stroke="{'#10b981' if is_dark else '#059669'}" fill="none" class="time-wave-2"/>

      <circle cx="45" cy="380" r="38" fill="{timestone_glow}"/>
      <circle cx="45" cy="380" r="28" stroke="{'#10b981' if is_dark else '#059669'}" stroke-width="1.4" stroke-dasharray="4 4" class="spin-eye-runes"/>

      <path d="M16,380 C26,362 64,362 74,380 C64,398 26,398 16,380 Z" 
            fill="{timestone_eye_fill1}" stroke="{timestone_border}" stroke-width="2.5" filter="url(#{glow_filter_id})"/>
      <path d="M23,380 C31,366 59,366 67,380 C59,394 31,394 23,380 Z" 
            fill="{timestone_eye_fill2}" stroke="{timestone_eye_stroke}" stroke-width="1.8"/>

      <g class="pulse-eye-core" filter="url(#{laser_filter_id})">
        <circle cx="45" cy="380" r="9" fill="{'#10b981' if is_dark else '#059669'}"/>
        <circle cx="45" cy="380" r="6" fill="{'#6ee7b7' if is_dark else '#34d399'}"/>
        <circle cx="45" cy="380" r="3" fill="#ffffff"/>
      </g>

      <rect x="12" y="415" width="66" height="15" rx="7.5" fill="{timestone_badge_bg}" stroke="{timestone_badge_stroke}" stroke-width="1.3"/>
      <text x="45" y="425.5" class="badge-pill" fill="{timestone_badge_txt}">TIME STONE</text>
    </g>

    <!-- RUNES SEGMENT 2 -> 3 -->
    <g opacity="0.9">
      <text x="45" y="475" class="rune-symbol interactive-rune" fill="{'#10b981' if is_dark else '#059669'}">✦ ᛏ ᛖ ᚱ ✦</text>
      <text x="45" y="535" class="rune-symbol interactive-rune" fill="{'#f97316' if is_dark else '#ea580c'}">◇ ARCH ◇</text>
      <text x="45" y="595" class="rune-symbol interactive-rune" fill="{'#fbbf24' if is_dark else '#d97706'}">✦ ᛒ ᚫ ᛞ ✦</text>
      <text x="45" y="655" class="rune-symbol interactive-rune" fill="{'#f97316' if is_dark else '#ea580c'}">◇ DATA ◇</text>
    </g>

    <!-- ==================== NODE 3: DOCTOR STRANGE TAO MANDALA (Y ≈ 720) ==================== -->
    <g id="node-3-tao-mandala" class="interactive-node node-3">
      <circle cx="45" cy="720" r="42" fill="{mandala_glow}" class="pulse-mandala"/>

      <g class="spin-mandala-spokes" filter="url(#{glow_filter_id})">
        <circle cx="45" cy="720" r="36" stroke="{'#f97316' if is_dark else '#ea580c'}" stroke-width="1.8" stroke-dasharray="8 6" fill="none"/>
        <line x1="45" y1="680" x2="45" y2="760" stroke="{'#fde047' if is_dark else '#f59e0b'}" stroke-width="2"/>
        <line x1="5" y1="720" x2="85" y2="720" stroke="{'#fde047' if is_dark else '#f59e0b'}" stroke-width="2"/>
        <line x1="17" y1="692" x2="73" y2="748" stroke="{'#f97316' if is_dark else '#ea580c'}" stroke-width="1.5"/>
        <line x1="17" y1="748" x2="73" y2="692" stroke="{'#f97316' if is_dark else '#ea580c'}" stroke-width="1.5"/>
      </g>

      <g class="spin-mandala-squares" filter="url(#{glow_filter_id})">
        <circle cx="45" cy="720" r="27" stroke="{'#ea580c' if is_dark else '#c2410c'}" stroke-width="1.6" fill="{mandala_bg}" fill-opacity="0.8"/>
        <rect x="26" y="701" width="38" height="38" fill="none" stroke="{'#fde047' if is_dark else '#f59e0b'}" stroke-width="1.6"/>
        <rect x="26" y="701" width="38" height="38" fill="none" stroke="{'#f97316' if is_dark else '#ea580c'}" stroke-width="1.6" transform="rotate(45 45 720)"/>
      </g>

      <g class="spin-mandala-inner">
        <circle cx="45" cy="720" r="16" stroke="{'#fbbf24' if is_dark else '#d97706'}" stroke-width="1.6" stroke-dasharray="3 3" fill="none"/>
        <polygon points="45,706 56,725 34,725" fill="none" stroke="#ffffff" stroke-width="1.4"/>
        <polygon points="45,734 34,715 56,715" fill="none" stroke="{'#fde047' if is_dark else '#f59e0b'}" stroke-width="1.4"/>
      </g>

      <circle cx="45" cy="720" r="6" fill="{'#ffffff' if is_dark else '#ea580c'}" filter="url(#{laser_filter_id})"/>

      <rect x="12" y="768" width="66" height="15" rx="7.5" fill="{mandala_badge_bg}" stroke="{mandala_badge_stroke}" stroke-width="1.3"/>
      <text x="45" y="778.5" class="badge-pill" fill="{mandala_badge_txt}">TAO SHIELD</text>
    </g>

    <!-- RUNES SEGMENT 3 -> 4 -->
    <g opacity="0.9">
      <text x="45" y="825" class="rune-symbol interactive-rune" fill="{'#f97316' if is_dark else '#ea580c'}">✦ ᛗ ᛖ ᛊ ✦</text>
      <text x="45" y="875" class="rune-symbol interactive-rune" fill="{'#c084fc' if is_dark else '#7c3aed'}">◇ CLOUD ◇</text>
      <text x="45" y="925" class="rune-symbol interactive-rune" fill="{'#06b6d4' if is_dark else '#0284c7'}">✦ PEAK ✦</text>
      <text x="45" y="975" class="rune-symbol interactive-rune" fill="{'#c084fc' if is_dark else '#7c3aed'}">◇ LOCAL ◇</text>
      <text x="45" y="1025" class="rune-symbol interactive-rune" fill="{'#06b6d4' if is_dark else '#0284c7'}">✦ APACHE ✦</text>
    </g>

    <!-- ==================== NODE 4: MIRROR DIMENSION & MULTIVERSE (Y ≈ 1080) ==================== -->
    <g id="node-4-mirror-dimension" class="interactive-node node-4">
      <circle cx="45" cy="1080" r="42" fill="{mirror_glow}" class="pulse-mirror"/>

      <g class="spin-mirror-outer" filter="url(#{glow_filter_id})">
        <polygon points="45,1040 74,1052 86,1080 74,1108 45,1120 16,1108 4,1080 16,1052" 
                 fill="{mirror_bg}" fill-opacity="0.85" stroke="{'#a855f7' if is_dark else '#7c3aed'}" stroke-width="2.2"/>
        <polygon points="45,1048 70,1098 20,1098" fill="none" stroke="{'#06b6d4' if is_dark else '#0284c7'}" stroke-width="1.6"/>
        <polygon points="45,1112 20,1062 70,1062" fill="none" stroke="{'#e879f9' if is_dark else '#a855f7'}" stroke-width="1.6"/>
      </g>

      <g class="spin-mirror-inner">
        <circle cx="45" cy="1080" r="18" stroke="{'#38bdf8' if is_dark else '#0284c7'}" stroke-width="1.8" stroke-dasharray="6 4" fill="none"/>
        <circle cx="45" cy="1080" r="12" stroke="{'#c084fc' if is_dark else '#7c3aed'}" stroke-width="1.5" stroke-dasharray="3 3" fill="none"/>
      </g>

      <circle cx="45" cy="1080" r="6.5" fill="{'#e879f9' if is_dark else '#7c3aed'}" filter="url(#{laser_filter_id})"/>
      <circle cx="45" cy="1080" r="3" fill="#ffffff"/>

      <rect x="10" y="1130" width="70" height="15" rx="7.5" fill="{mirror_badge_bg}" stroke="{mirror_badge_stroke}" stroke-width="1.3"/>
      <text x="45" y="1140.5" class="badge-pill" fill="{mirror_badge_txt}">MULTIVERSE</text>
    </g>

    <!-- RUNES SEGMENT 4 -> 5 -->
    <g opacity="0.9">
      <text x="45" y="1185" class="rune-symbol interactive-rune" fill="{'#c084fc' if is_dark else '#7c3aed'}">✦ ᚲ ᛟ ᛞ ✦</text>
      <text x="45" y="1235" class="rune-symbol interactive-rune" fill="{'#38bdf8' if is_dark else '#0284c7'}">◇ REPO ◇</text>
      <text x="45" y="1285" class="rune-symbol interactive-rune" fill="{'#f43f5e' if is_dark else '#e11d48'}">✦ COMMITS ✦</text>
      <text x="45" y="1335" class="rune-symbol interactive-rune" fill="{'#38bdf8' if is_dark else '#0284c7'}">◇ PULL ◇</text>
    </g>

    <!-- ==================== NODE 5: ASTRAL BEACON & CLOAK OF LEVITATION (Y ≈ 1390) ==================== -->
    <g id="node-5-astral-beacon" class="interactive-node node-5">
      <circle cx="45" cy="1390" r="38" fill="{astral_glow}" opacity="0.4" class="pulse-astral"/>

      <g class="spin-astral" filter="url(#{glow_filter_id})">
        <polygon points="45,1354 81,1390 45,1426 9,1390" 
                 fill="{astral_bg}" fill-opacity="0.85" stroke="{'#38bdf8' if is_dark else '#0284c7'}" stroke-width="2.4"/>
        <polygon points="45,1362 73,1390 45,1418 17,1390" 
                 fill="none" stroke="{'#f43f5e' if is_dark else '#e11d48'}" stroke-width="1.6"/>
      </g>

      <path d="M18,1390 C26,1380 36,1390 45,1376 C54,1390 64,1380 72,1390" 
            fill="none" stroke="{'#e11d48' if is_dark else '#be123c'}" stroke-width="2.5" stroke-linecap="round"/>

      <circle cx="45" cy="1390" r="7.5" fill="{'#38bdf8' if is_dark else '#0284c7'}" filter="url(#{laser_filter_id})"/>
      <circle cx="45" cy="1390" r="3.5" fill="#ffffff"/>

      <rect x="10" y="1436" width="70" height="15" rx="7.5" fill="{astral_badge_bg}" stroke="{astral_badge_stroke}" stroke-width="1.3"/>
      <text x="45" y="1446.5" class="badge-pill" fill="{astral_badge_txt}">ASTRAL LINK</text>
    </g>

    <!-- RUNES SEGMENT 5 -> 6 -->
    <g opacity="0.9">
      <text x="45" y="1495" class="rune-symbol interactive-rune" fill="{'#38bdf8' if is_dark else '#0284c7'}">✦ ACTIVITY ✦</text>
      <text x="45" y="1555" class="rune-symbol interactive-rune" fill="{'#f59e0b' if is_dark else '#d97706'}">◇ RUNTIME ◇</text>
      <text x="45" y="1615" class="rune-symbol interactive-rune" fill="{'#34d399' if is_dark else '#059669'}">✦ SUPREME ✦</text>
    </g>

    <!-- ==================== TERMINAL NODE 6: SLING RING PORTAL GATEWAY (Y ≈ 1700) ==================== -->
    <g id="node-6-portal" class="interactive-node node-6">
      <circle cx="45" cy="1700" r="38" fill="{portal_glow}" class="pulse-portal"/>

      <g class="spin-portal-sparks" filter="url(#{laser_filter_id})">
        <circle cx="45" cy="1700" r="28" stroke="{'#f59e0b' if is_dark else '#d97706'}" stroke-width="3.5" stroke-dasharray="12 6 3 6" fill="none"/>
        <circle cx="73" cy="1700" r="3.5" fill="#ffffff"/>
        <circle cx="17" cy="1700" r="3" fill="{'#fde047' if is_dark else '#f59e0b'}"/>
        <circle cx="45" cy="1672" r="3.5" fill="{'#f97316' if is_dark else '#ea580c'}"/>
        <circle cx="45" cy="1728" r="3" fill="#ffffff"/>
      </g>

      <g class="spin-portal-inner">
        <circle cx="45" cy="1700" r="21" stroke="{'#ea580c' if is_dark else '#c2410c'}" stroke-width="2.5" stroke-dasharray="7 8 4 4" fill="{portal_bg}" fill-opacity="0.9"/>
        <circle cx="63" cy="1690" r="2.2" fill="{'#fde047' if is_dark else '#f59e0b'}"/>
        <circle cx="27" cy="1710" r="2.2" fill="{'#fb923c' if is_dark else '#f97316'}"/>
      </g>

      <circle cx="45" cy="1700" r="12" fill="{'#ffffff' if is_dark else '#f59e0b'}" filter="url(#{glow_filter_id})"/>
      <circle cx="45" cy="1700" r="6" fill="{'#fed7aa' if is_dark else '#fde047'}"/>

      <rect x="15" y="1740" width="60" height="15" rx="7.5" fill="{portal_badge_bg}" stroke="{portal_badge_stroke}" stroke-width="1.3"/>
      <text x="45" y="1750.5" class="badge-pill" fill="{portal_badge_txt}">PORTAL</text>
    </g>

    <!-- ==================== MAGNIFYING LENS FOCUS RING (AUTONOMOUS SWEEP) ==================== -->
    <g class="lens-sweep">
      <circle cx="45" cy="0" r="38" fill="url(#{lens_grad})" stroke="{lens_stroke}" stroke-width="1.5" stroke-dasharray="6 4" opacity="0.8"/>
      <circle cx="45" cy="0" r="32" stroke="{lens_inner_stroke}" stroke-width="1" opacity="0.6"/>
      <line x1="15" y1="0" x2="75" y2="0" stroke="{lens_cross}" stroke-width="1" stroke-dasharray="3 3" opacity="0.5"/>
    </g>
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

    # 4b. Generate Doctor Strange Mystic Spine Dark & Light SVGs
    dark_spine_svg = generate_spine_svg(theme="dark", height=1780)
    light_spine_svg = generate_spine_svg(theme="light", height=1780)

    dark_spine_path = os.path.join(ASSETS_DIR, "dr-strange-spine-dark.svg")
    light_spine_path = os.path.join(ASSETS_DIR, "dr-strange-spine-light.svg")

    with open(dark_spine_path, "w", encoding="utf-8") as f:
        f.write(dark_spine_svg)
    with open(light_spine_path, "w", encoding="utf-8") as f:
        f.write(light_spine_svg)
    print(f"Generated {dark_spine_path} and {light_spine_path}")

    # 5. Update README Organizations Showcase
    orgs_markdown = generate_orgs_markdown(orgs)
    update_readme_organizations(README_PATH, orgs_markdown)

    # 6. Fetch Recent Activities & Update README
    activities = fetch_recent_activities(USERNAME)
    update_readme_activity(README_PATH, activities)

    print("Profile generation completed successfully!")

if __name__ == "__main__":
    main()
