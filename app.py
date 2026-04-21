import os
import json
import requests
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template, request
from collections import defaultdict

app = Flask(__name__)

# ── ENV VARS (set all in Render) ──────────────────────────────────────────────
APIFY_TOKEN             = os.environ.get("APIFY_TOKEN", "")
APIFY_COMPETITOR_DATASET = os.environ.get("APIFY_COMPETITOR_DATASET", "")  # harvestapi/linkedin-company-posts runs
APIFY_MY_POSTS_DATASET   = os.environ.get("APIFY_MY_POSTS_DATASET", "")    # supreme_coder/linkedin-post runs
APIFY_PROFILE_DATASET    = os.environ.get("APIFY_PROFILE_DATASET", "")     # harvestapi/linkedin-profile-scraper runs

# ── ACTOR IDs ─────────────────────────────────────────────────────────────────
ACTOR_COMPETITOR  = "harvestapi~linkedin-company-posts"
ACTOR_MY_POSTS    = "supreme_coder~linkedin-post"
ACTOR_PROFILE     = "harvestapi~linkedin-profile-scraper"

# ── COMPETITORS ───────────────────────────────────────────────────────────────
COMPETITORS = [
    {"name": "Monday.com", "slug": "mondaydotcom"},
    {"name": "Asana",      "slug": "asana"},
    {"name": "Airtable",   "slug": "airtable"},
    {"name": "Notion",     "slug": "notionhq"},
    {"name": "ClickUp",    "slug": "clickup-app"},
]

MY_LINKEDIN_URL = "https://www.linkedin.com/in/brett-shields-atl/"

# ── PILLAR SYSTEM ─────────────────────────────────────────────────────────────
PILLARS = {
    "Pop Culture":    {"day": "Mon", "color": "#EC4899", "purpose": "Timely cultural hooks. Reach amplifier."},
    "Ops & Pain":     {"day": "Tue", "color": "#F97316", "purpose": "Tool sprawl, broken systems. Seeds the software. ICP magnet."},
    "Personal":       {"day": "Wed", "color": "#14B8A6", "purpose": "Vulnerability, real life. Comment driver."},
    "Hot Take":       {"day": "Thu", "color": "#EF4444", "purpose": "Contrarian views. Only when ready."},
    "Founder Tease":  {"day": "Fri", "color": "#A855F7", "purpose": "Vague but intriguing. Credibility builder."},
}

# ── SEEDED POST DATA (real posts from Brett's scrape) ─────────────────────────
SEEDED_POSTS = [
    {
        "date": "2026-04-01", "day": "Tue", "pillar": "Ops & Pain",
        "hook": "Trade show / experiential marketing — FABTECH 2025",
        "format": "Image", "post_time": "1:30 PM",
        "impressions": 590, "reached": 329, "reactions": 16, "comments": 2,
        "reposts": 1, "saves": 0, "sends": 0, "profile_views": 10, "new_followers": 2,
        "demographics": ["Owner 5%", "Founder 3%", "Sales Manager 2%", "Account Exec 2%", "PM 2%"],
        "locations": ["Atlanta 45%", "NYC 4%", "LA 3%"],
        "seniority": [],
        "notes": "Strong 3.2% engagement rate. Baseline for campaign.",
        "url": "https://www.linkedin.com/posts/brett-shields-atl_tradeshowdesign-experientialmarketing-eventproduction-activity-7445175764712361984-DDhN"
    },
    {
        "date": "2026-04-13", "day": "Mon", "pillar": "Pop Culture",
        "hook": "Coachella — a producer's take on Sabrina Carpenter vs Justin Bieber",
        "format": "Image", "post_time": "10:00 AM",
        "impressions": 3343, "reached": 2246, "reactions": 19, "comments": 2,
        "reposts": 2, "saves": 2, "sends": 1, "profile_views": 20, "new_followers": 2,
        "demographics": ["Founder 3%", "Pastor 2%", "Owner 2%"],
        "locations": [], "seniority": [],
        "notes": "Breakout post. 3,343 impressions — 5x typical reach. Still climbing.",
        "url": "https://www.linkedin.com/posts/brett-shields-atl_eventproducer-coachella2026-justinbieber-activity-7449456492094722048-ZXNb"
    },
    {
        "date": "2026-04-14", "day": "Tue", "pillar": "Ops & Pain",
        "hook": "11 tools to run a single event — this number bothered me",
        "format": "Text", "post_time": "7:30 AM",
        "impressions": 849, "reached": 584, "reactions": 5, "comments": 1,
        "reposts": 0, "saves": 2, "sends": 0, "profile_views": 4, "new_followers": 0,
        "demographics": ["PM 5%", "Event Manager 3%", "Owner 3%"],
        "locations": ["Atlanta 33%"], "seniority": [],
        "notes": "ICP-heavy. 2 saves signal intent. Impressions up 22% since first pull.",
        "url": "https://www.linkedin.com/posts/brett-shields-atl_i-counted-the-tools-my-team-uses-to-run-a-activity-7449781018531827712-2Hsb"
    },
    {
        "date": "2026-04-15", "day": "Wed", "pillar": "Personal",
        "hook": "Runner's high — my mind wanders when I run. Maybe that's the point.",
        "format": "Text", "post_time": "11:03 AM",
        "impressions": 515, "reached": 317, "reactions": 7, "comments": 10,
        "reposts": 0, "saves": 0, "sends": 0, "profile_views": 1, "new_followers": 0,
        "demographics": ["Founder 5%", "Owner 4%", "PM 2%"],
        "locations": ["Atlanta 57%", "NYC 6%"],
        "seniority": ["Senior 24%", "Director 19%", "Entry 15%", "Manager 12%", "CXO 9%"],
        "notes": "Comment monster. 10 comments. 1.9% comment rate. Personal pillar works.",
        "url": "https://www.linkedin.com/posts/brett-shields-atl_ive-heard-runners-say-their-best-ideas-come-activity-7450197008398721024-qjoN"
    },
    {
        "date": "2026-04-17", "day": "Fri", "pillar": "Founder Tease",
        "hook": "When did you do it? When did you stop talking and start building?",
        "format": "Text", "post_time": "7:45 AM",
        "impressions": 117, "reached": 53, "reactions": 2, "comments": 0,
        "reposts": 0, "saves": 0, "sends": 0, "profile_views": 2, "new_followers": 0,
        "demographics": [], "locations": ["Atlanta 76%"],
        "seniority": ["Senior 26%", "Director 23%"],
        "notes": "Lowest performer. 0 comments. Hook too vague. Needs stronger tease.",
        "url": "https://www.linkedin.com/posts/brett-shields-atl_when-did-you-do-it-when-did-you-stop-talking-activity-7450871941462306816-Py4r"
    },
    {
        "date": "2026-04-20", "day": "Mon", "pillar": "Personal",
        "hook": "Last night at dinner — the EQ was wrong. Excellence covers mistakes.",
        "format": "Video", "post_time": "12:26 PM",
        "impressions": 0, "reached": 0, "reactions": 8, "comments": 12,
        "reposts": 0, "saves": 0, "sends": 0, "profile_views": 0, "new_followers": 0,
        "demographics": [], "locations": [],
        "seniority": [],
        "notes": "8 likes, 12 comments — strong early engagement. Impressions not yet pulled.",
        "url": "https://www.linkedin.com/posts/brett-shields-atl_last-night-i-was-at-dinner-with-a-client-activity-7451969654681694208-s1MY"
    },
    {
        "date": "2026-04-21", "day": "Tue", "pillar": "Ops & Pain",
        "hook": "Too many opinions. Not enough clarity. That's on me.",
        "format": "Text", "post_time": "11:30 AM",
        "impressions": 0, "reached": 0, "reactions": 0, "comments": 1,
        "reposts": 0, "saves": 0, "sends": 0, "profile_views": 0, "new_followers": 0,
        "demographics": [], "locations": [],
        "seniority": [],
        "notes": "Posted today. Metrics not yet available.",
        "url": "https://www.linkedin.com/posts/brett-shields-atl_too-many-opinions-not-enough-clarity-thats-activity-7452317751936704512-dWag"
    },
]

IDEA_BACKLOG = {
    "Pop Culture": [
        "Coachella Weekend 2 — why W2 is the real show",
        "Concert as a guest — 'doing the thing again'",
        "Super Bowl halftime from a producer's lens (stash for February)"
    ],
    "Ops & Pain": [
        "The workarounds become the system",
        "No single source of truth — the chaos story (Dropbox/Drive/Sheets anecdote)",
        "What a well-run event looks like from the inside"
    ],
    "Personal": [
        "Finding mentors — why it's harder than anyone admits",
        "Cycling as reset before event weeks",
        "Why producers are bad at being audience members"
    ],
    "Founder Tease": [
        "My co-founder is a developer. I'm an operator.",
        "The moment I decided to stop complaining and start building",
        "I didn't want to build a company. I wanted the tool."
    ],
    "Hot Take": [
        "Event planners are the most undervalued operators in any industry",
        "The best events aren't the biggest ones"
    ]
}

PROFILE_TODOS = [
    {"task": "Feature the Coachella post (3,343 impressions) — your best performer", "done": False},
    {"task": "Review headline — add a hint at the builder/founder side", "done": False},
    {"task": "Refresh banner image — current one is 6+ months old", "done": False},
    {"task": "Add 1-2 Orchestrate production highlights to Experience section", "done": False},
    {"task": "Check connections for anyone who changed roles into ICP (Event Manager, PM, Owner)", "done": False},
]

# ── APIFY HELPERS ─────────────────────────────────────────────────────────────

def apify_trigger(actor_id, payload):
    if not APIFY_TOKEN:
        return None, "No APIFY_TOKEN set."
    url    = f"https://api.apify.com/v2/acts/{actor_id}/runs"
    params = {"token": APIFY_TOKEN}
    try:
        r = requests.post(url, json=payload, params=params, timeout=30)
        if r.status_code in [200, 201]:
            d = r.json().get("data", {})
            return {"dataset_id": d.get("defaultDatasetId"), "run_id": d.get("id")}, None
        return None, f"Apify {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return None, str(e)

def apify_fetch(dataset_id):
    if not APIFY_TOKEN or not dataset_id:
        return None, "Missing token or dataset_id."
    url    = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
    params = {"token": APIFY_TOKEN, "limit": 500}
    try:
        r = requests.get(url, params=params, timeout=30)
        if r.status_code == 200:
            return r.json(), None
        return None, f"Dataset {r.status_code}"
    except Exception as e:
        return None, str(e)

def apify_status(run_id):
    if not APIFY_TOKEN or not run_id:
        return "UNKNOWN"
    url    = f"https://api.apify.com/v2/actor-runs/{run_id}"
    params = {"token": APIFY_TOKEN}
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            return r.json().get("data", {}).get("status", "UNKNOWN")
    except:
        pass
    return "UNKNOWN"

# ── DATA PROCESSORS ───────────────────────────────────────────────────────────

def process_competitors(items):
    company_posts = defaultdict(list)
    for item in items:
        if item.get("type") != "post":
            continue
        slug = item.get("query", {}).get("targetUrl", "").rstrip("/").split("/")[-1]
        if slug:
            company_posts[slug].append(item)

    results = []
    for comp in COMPETITORS:
        posts = company_posts.get(comp["slug"], [])
        if not posts:
            results.append({"name": comp["name"], "slug": comp["slug"], "posts": 0,
                            "likes": 0, "comments": 0, "shares": 0,
                            "followers": "—", "trend": "No data", "top_post": None, "topics": []})
            continue

        followers   = posts[0].get("author", {}).get("info", "").replace(" followers", "").strip() or "—"
        total_likes = sum(p.get("engagement", {}).get("likes", 0) for p in posts)
        total_comments = sum(p.get("engagement", {}).get("comments", 0) for p in posts)
        total_shares   = sum(p.get("engagement", {}).get("shares", 0) for p in posts)
        top_post    = max(posts, key=lambda p: p.get("engagement", {}).get("likes", 0))
        avg_likes   = total_likes / len(posts)
        trend = "↑ Up" if avg_likes >= 50 else ("→ Stable" if avg_likes >= 15 else "↓ Down")

        topics = []
        for p in posts:
            c = p.get("content", "").lower()
            if "ai" in c or "agent" in c:        topics.append("AI")
            if "automat" in c or "no-code" in c: topics.append("Automation")
            if "collaborat" in c or "team" in c: topics.append("Collaboration")
            if "event" in c:                     topics.append("Events")
            if "productiv" in c:                 topics.append("Productivity")
        topics = list(dict.fromkeys(topics))[:3]

        results.append({
            "name": comp["name"], "slug": comp["slug"],
            "posts": len(posts), "likes": total_likes,
            "comments": total_comments, "shares": total_shares,
            "followers": followers, "trend": trend,
            "top_post": {
                "content":    top_post.get("content", "")[:200],
                "likes":      top_post.get("engagement", {}).get("likes", 0),
                "comments":   top_post.get("engagement", {}).get("comments", 0),
                "url":        top_post.get("linkedinUrl", ""),
                "posted_ago": top_post.get("postedAt", {}).get("postedAgoText", ""),
            },
            "topics": topics,
        })
    return results

def process_competitor_trends(items):
    keyword_map = {
        "AI & Agents":                ["ai", "agent", "artificial intelligence", "llm", "gpt"],
        "Automation":                 ["automat", "workflow", "no-code", "nocode"],
        "Event Management":           ["event", "venue", "conference", "webinar"],
        "Team Collaboration":         ["team", "collaborat", "cross-functional"],
        "Productivity Tools":         ["productiv", "efficient", "time-saving", "streamline"],
        "Project Management":         ["project", "deadline", "milestone", "sprint", "task"],
        "Small Business / Freelance": ["small business", "freelance", "startup", "founder"],
    }
    counts = defaultdict(int)
    likes  = defaultdict(int)
    for post in [i for i in items if i.get("type") == "post"]:
        content    = post.get("content", "").lower()
        post_likes = post.get("engagement", {}).get("likes", 0)
        for topic, kws in keyword_map.items():
            for kw in kws:
                if kw in content:
                    counts[topic] += 1
                    likes[topic]  += post_likes
                    break
    if not counts:
        return []
    max_count = max(counts.values())
    return sorted([{
        "name":      t,
        "mentions":  c,
        "avg_likes": round(likes[t] / c, 1) if c else 0,
        "momentum":  "Rising" if c >= 2 else "Stable",
        "relevance": "Very High" if t in ["Event Management", "Small Business / Freelance", "Automation", "AI & Agents"] else "High",
        "pct":       round((c / max_count) * 100),
    } for t, c in counts.items()], key=lambda x: x["mentions"], reverse=True)[:6]

def process_my_posts(items):
    posts = [i for i in items if i.get("authorProfileId") == "brett-shields-atl" or
             i.get("inputUrl", "").find("brett-shields-atl") != -1]
    result = []
    for p in posts:
        result.append({
            "url":        p.get("url", ""),
            "text":       p.get("text", "")[:300],
            "hook":       p.get("text", "").split("\n")[0][:120],
            "likes":      p.get("numLikes", 0),
            "comments":   p.get("numComments", 0),
            "shares":     p.get("numShares", 0),
            "posted_at":  p.get("postedAtISO", ""),
            "time_ago":   p.get("timeSincePosted", ""),
            "type":       p.get("type", "text"),
        })
    return sorted(result, key=lambda x: x.get("posted_at", ""), reverse=True)

def compute_coaching(my_posts_data, competitor_data, trends):
    urgent, this_week, longterm = [], [], []

    # Analyze seeded data
    recent = [p for p in SEEDED_POSTS if p.get("impressions", 0) > 0]
    if recent:
        best = max(recent, key=lambda p: p.get("impressions", 0))
        worst = min(recent, key=lambda p: p.get("impressions", 0))

        if best["impressions"] > 1000:
            urgent.append(f"Your best post this week was <strong>{best['hook'][:60]}...</strong> with {best['impressions']:,} impressions. Reply to every comment — it signals LinkedIn to push it further.")

        if worst["impressions"] < 200:
            this_week.append(f"<strong>{worst['hook'][:60]}...</strong> underperformed at {worst['impressions']} impressions. Diagnose: was the hook too vague? Try repurposing with a stronger opening line.")

    # Check posting cadence
    today = datetime.now()
    week_start = today - timedelta(days=today.weekday())
    posts_this_week = [p for p in SEEDED_POSTS if datetime.strptime(p["date"], "%Y-%m-%d") >= week_start]
    if len(posts_this_week) < 3:
        urgent.append(f"Only <strong>{len(posts_this_week)} posts this week</strong>. Target is 4. Missing slots = missing compound reach. What pillar is due?")

    # Founder Tease performance
    tease_posts = [p for p in SEEDED_POSTS if p["pillar"] == "Founder Tease" and p.get("impressions", 0) > 0]
    if tease_posts and all(p["comments"] == 0 for p in tease_posts):
        this_week.append("<strong>Founder Tease posts are getting zero comments</strong>. The hook needs more intrigue — try 'I'm building something I've needed for 10 years. Not ready to say what yet.' Make them lean in.")

    # Personal pillar is working
    personal_posts = [p for p in SEEDED_POSTS if p["pillar"] == "Personal" and p.get("comments", 0) > 5]
    if personal_posts:
        this_week.append(f"<strong>Personal pillar is your comment driver</strong> — {personal_posts[0]['comments']} comments on your last Personal post. Wednesday is working. Keep it up.")

    # Competitor intel
    if competitor_data:
        top_comp = max(competitor_data, key=lambda c: c.get("likes", 0))
        if top_comp.get("top_post"):
            longterm.append(f"<strong>{top_comp['name']}</strong> is winning engagement this week. Their top post topic: {top_comp['top_post']['content'][:80]}... Study the format and angle your version toward small event teams.")

    # Growth goal alignment
    longterm.append("Your <strong>Ops & Pain posts are reaching Event Managers and PMs</strong> — exactly your ICP. Double down on Tuesday. Every Ops post should end with a question that makes them feel seen.")
    longterm.append("You're ~3 months from software launch. <strong>Start dropping the Founder Tease more consistently</strong> — one strong tease per week, every week, no exceptions. Build the mystery now.")

    if trends:
        top_trend = trends[0]
        this_week.append(f"Industry trend alert: <strong>{top_trend['name']}</strong> is getting {top_trend['mentions']} competitor posts with {top_trend['avg_likes']} avg likes. Write your angle on this for next week.")

    return {"urgent": urgent, "this_week": this_week, "longterm": longterm}

def compute_weekly_benchmarks():
    weeks = defaultdict(lambda: {"posts": 0, "impressions": 0, "reactions": 0, "comments": 0, "reposts": 0, "saves": 0, "followers_gained": 0})
    for p in SEEDED_POSTS:
        d = datetime.strptime(p["date"], "%Y-%m-%d")
        week_start = d - timedelta(days=d.weekday())
        label = f"W/{week_start.strftime('%b %d')}"
        weeks[label]["posts"]           += 1
        weeks[label]["impressions"]     += p.get("impressions", 0)
        weeks[label]["reactions"]       += p.get("reactions", 0)
        weeks[label]["comments"]        += p.get("comments", 0)
        weeks[label]["reposts"]         += p.get("reposts", 0)
        weeks[label]["saves"]           += p.get("saves", 0)
        weeks[label]["followers_gained"]+= p.get("new_followers", 0)

    result = []
    cumulative = 0
    for label in sorted(weeks.keys()):
        w = weeks[label]
        cumulative += w["followers_gained"]
        result.append({**w, "week": label, "cumulative_followers": cumulative})
    return result

# ── ROUTES ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

# Trigger a fresh competitor scrape
@app.route("/api/scan/competitors", methods=["POST"])
def scan_competitors():
    result, err = apify_trigger(ACTOR_COMPETITOR, {
        "startUrls": [{"url": f"https://www.linkedin.com/company/{c['slug']}/"} for c in COMPETITORS],
        "maxPostsPerProfile": 5,
        "postLimit": "this_week",
        "scrapeReactions": True,
        "maxReactionsPerPost": 5,
        "includeReposts": False,
    })
    if err: return jsonify({"error": err}), 500
    return jsonify(result)

# Trigger a fresh my-posts scrape
@app.route("/api/scan/my-posts", methods=["POST"])
def scan_my_posts():
    result, err = apify_trigger(ACTOR_MY_POSTS, {
        "startUrls": [{"url": MY_LINKEDIN_URL}],
        "maxResults": 10,
    })
    if err: return jsonify({"error": err}), 500
    return jsonify(result)

# Check run status
@app.route("/api/status/<run_id>")
def status(run_id):
    return jsonify({"status": apify_status(run_id)})

# Get competitor results from a dataset
@app.route("/api/results/competitors/<dataset_id>")
def competitor_results(dataset_id):
    items, err = apify_fetch(dataset_id)
    if err: return jsonify({"error": err}), 500
    competitors = process_competitors(items)
    trends      = process_competitor_trends(items)
    return jsonify({
        "competitors": competitors,
        "trends":      trends,
        "scanned_at":  datetime.now().strftime("%A, %B %d at %I:%M %p"),
        "data_source": "Live — Apify LinkedIn Company Posts Scraper",
    })

# Get my posts results from a dataset
@app.route("/api/results/my-posts/<dataset_id>")
def my_post_results(dataset_id):
    items, err = apify_fetch(dataset_id)
    if err: return jsonify({"error": err}), 500
    return jsonify({
        "posts":       process_my_posts(items),
        "scanned_at":  datetime.now().strftime("%A, %B %d at %I:%M %p"),
    })

# Main dashboard data — uses seeded data + latest Apify datasets if available
@app.route("/api/dashboard")
def dashboard():
    competitor_data = []
    trend_data      = []
    live_source     = "Seeded data"

    if APIFY_COMPETITOR_DATASET:
        items, err = apify_fetch(APIFY_COMPETITOR_DATASET)
        if items:
            competitor_data = process_competitors(items)
            trend_data      = process_competitor_trends(items)
            live_source     = "Live — Apify"

    coaching  = compute_coaching([], competitor_data, trend_data)
    benchmarks = compute_weekly_benchmarks()

    total_impressions = sum(p.get("impressions", 0) for p in SEEDED_POSTS)
    total_reactions   = sum(p.get("reactions", 0)   for p in SEEDED_POSTS)
    total_comments    = sum(p.get("comments", 0)    for p in SEEDED_POSTS)
    total_saves       = sum(p.get("saves", 0)        for p in SEEDED_POSTS)
    followers_gained  = sum(p.get("new_followers", 0) for p in SEEDED_POSTS)

    return jsonify({
        "profile": {
            "name":             "Brett Shields",
            "headline":         "Managing Director | Event Producer & Strategist",
            "followers":        694,
            "followers_gained": followers_gained,
            "url":              MY_LINKEDIN_URL,
        },
        "this_week": {
            "total_impressions": total_impressions,
            "total_reactions":   total_reactions,
            "total_comments":    total_comments,
            "total_saves":       total_saves,
            "posts_count":       len(SEEDED_POSTS),
        },
        "published_posts":  SEEDED_POSTS,
        "weekly_benchmarks": benchmarks,
        "competitors":      competitor_data,
        "trends":           trend_data,
        "coaching":         coaching,
        "pillars":          PILLARS,
        "idea_backlog":     IDEA_BACKLOG,
        "profile_todos":    PROFILE_TODOS,
        "data_source":      live_source,
        "scanned_at":       datetime.now().strftime("%A, %B %d at %I:%M %p"),
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

# Last scan timestamp — used by frontend 4-hour auto-refresh logic
@app.route("/api/last-scan")
def last_scan():
    return jsonify({
        "last_scan_iso":      datetime.now().isoformat(),
        "has_competitor_data": bool(APIFY_COMPETITOR_DATASET),
    })

# Trigger both scrapers at once
@app.route("/api/scan/all", methods=["POST"])
def scan_all():
    comp_result, comp_err = apify_trigger(ACTOR_COMPETITOR, {
        "startUrls": [{"url": f"https://www.linkedin.com/company/{c['slug']}/"} for c in COMPETITORS],
        "maxPostsPerProfile": 5,
        "postLimit": "this_week",
        "scrapeReactions": True,
        "maxReactionsPerPost": 5,
        "includeReposts": False,
    })
    my_result, my_err = apify_trigger(ACTOR_MY_POSTS, {
        "startUrls": [{"url": MY_LINKEDIN_URL}],
        "maxResults": 10,
    })
    return jsonify({
        "competitors": comp_result,
        "my_posts":    my_result,
        "errors":      [e for e in [comp_err, my_err] if e],
    })
