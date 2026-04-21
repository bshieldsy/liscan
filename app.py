import os
import requests
from datetime import datetime
from flask import Flask, jsonify, render_template
from collections import defaultdict

app = Flask(__name__)

APIFY_TOKEN      = os.environ.get("APIFY_TOKEN", "")
APIFY_DATASET_ID = os.environ.get("APIFY_DATASET_ID", "")
APIFY_ACTOR_ID   = "harvestapi~linkedin-company-posts"

COMPETITORS = [
    {"name": "Monday.com",  "slug": "mondaydotcom"},
    {"name": "Asana",       "slug": "asana"},
    {"name": "Airtable",    "slug": "airtable"},
    {"name": "Notion",      "slug": "notionhq"},
    {"name": "ClickUp",     "slug": "clickup-app"},
]

def trigger_fresh_scrape():
    if not APIFY_TOKEN:
        return None, "No APIFY_TOKEN set."
    url     = f"https://api.apify.com/v2/acts/{APIFY_ACTOR_ID}/runs"
    params  = {"token": APIFY_TOKEN}
    payload = {
        "startUrls": [{"url": f"https://www.linkedin.com/company/{c['slug']}/"} for c in COMPETITORS],
        "maxPostsPerProfile": 5,
        "postLimit": "this_week",
        "scrapeReactions": True,
        "maxReactionsPerPost": 5,
        "includeReposts": False,
    }
    try:
        r = requests.post(url, json=payload, params=params, timeout=30)
        if r.status_code in [200, 201]:
            data = r.json().get("data", {})
            return {"dataset_id": data.get("defaultDatasetId"), "run_id": data.get("id")}, None
        return None, f"Apify error {r.status_code}: {r.text[:200]}"
    except Exception as e:
        return None, str(e)

def fetch_dataset(dataset_id):
    if not APIFY_TOKEN or not dataset_id:
        return None, "Missing APIFY_TOKEN or dataset_id."
    url    = f"https://api.apify.com/v2/datasets/{dataset_id}/items"
    params = {"token": APIFY_TOKEN, "limit": 500}
    try:
        r = requests.get(url, params=params, timeout=30)
        if r.status_code == 200:
            return r.json(), None
        return None, f"Dataset error {r.status_code}"
    except Exception as e:
        return None, str(e)

def check_run_status(run_id):
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

def process_competitor_data(items):
    company_posts = defaultdict(list)
    for item in items:
        if item.get("type") != "post":
            continue
        target_url = item.get("query", {}).get("targetUrl", "")
        slug = target_url.rstrip("/").split("/")[-1]
        if slug:
            company_posts[slug].append(item)

    results = []
    for comp in COMPETITORS:
        slug  = comp["slug"]
        posts = company_posts.get(slug, [])
        if not posts:
            results.append({"name": comp["name"], "slug": slug, "posts": 0,
                            "likes": 0, "comments": 0, "shares": 0,
                            "followers": "—", "trend": "No data this week",
                            "top_post": None, "topics": []})
            continue

        author_info = posts[0].get("author", {}).get("info", "")
        followers   = author_info.replace(" followers", "").strip() or "—"
        total_likes    = sum(p.get("engagement", {}).get("likes", 0)    for p in posts)
        total_comments = sum(p.get("engagement", {}).get("comments", 0) for p in posts)
        total_shares   = sum(p.get("engagement", {}).get("shares", 0)   for p in posts)
        top_post       = max(posts, key=lambda p: p.get("engagement", {}).get("likes", 0))
        avg_likes      = total_likes / len(posts)
        trend = "↑ Up" if avg_likes >= 50 else ("→ Stable" if avg_likes >= 15 else "↓ Down")

        topics = []
        for p in posts:
            c = p.get("content", "").lower()
            if "ai" in c or "agent" in c:            topics.append("AI")
            if "automat" in c or "no-code" in c:     topics.append("Automation")
            if "collaborat" in c or "team" in c:     topics.append("Collaboration")
            if "event" in c:                         topics.append("Events")
            if "productiv" in c:                     topics.append("Productivity")
        topics = list(dict.fromkeys(topics))[:3]

        results.append({
            "name": comp["name"], "slug": slug,
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

def process_trend_data(items):
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
    posts  = [i for i in items if i.get("type") == "post"]

    for post in posts:
        content    = post.get("content", "").lower()
        post_likes = post.get("engagement", {}).get("likes", 0)
        for topic, keywords in keyword_map.items():
            for kw in keywords:
                if kw in content:
                    counts[topic] += 1
                    likes[topic]  += post_likes
                    break

    if not counts:
        return []

    max_count = max(counts.values())
    results   = []
    for topic, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
        avg_likes = round(likes[topic] / count, 1) if count else 0
        results.append({
            "name":      topic,
            "mentions":  count,
            "avg_likes": avg_likes,
            "momentum":  "Rising" if count >= 2 else "Stable",
            "relevance": "Very High" if topic in ["Event Management", "Small Business / Freelance", "Automation", "AI & Agents"] else "High",
            "pct":       round((count / max_count) * 100),
        })
    return results[:6]

def generate_action_items(competitors, trends):
    actions = []
    if trends:
        t = trends[0]
        actions.append(f"Post about <strong>{t['name']}</strong> — hottest topic this week with {t['mentions']} competitor posts and {t['avg_likes']} avg likes.")
    if competitors:
        top = max(competitors, key=lambda c: c["likes"])
        if top["top_post"]:
            snippet = top["top_post"]["content"][:80].strip()
            actions.append(f"<strong>{top['name']}</strong> is leading with {top['likes']} likes. Their top post: \"{snippet}…\"")
    avg_posts = round(sum(c["posts"] for c in competitors) / len(competitors), 1) if competitors else 0
    actions.append(f"Competitors averaged <strong>{avg_posts} posts this week</strong>. Match or beat that frequency to stay visible.")
    if len(trends) > 1:
        actions.append(f"<strong>{trends[1]['name']}</strong> is also gaining — connect it to small event business pain points in your next post.")
    actions.append("No competitor is speaking directly to <strong>2–10 person event teams</strong> without systems. That's your lane — own it.")
    return actions

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/trigger", methods=["POST"])
def trigger():
    result, error = trigger_fresh_scrape()
    if error:
        return jsonify({"error": error}), 500
    return jsonify(result)

@app.route("/api/status/<run_id>")
def status(run_id):
    return jsonify({"status": check_run_status(run_id)})

@app.route("/api/results/<dataset_id>")
def results(dataset_id):
    items, error = fetch_dataset(dataset_id)
    if error:
        return jsonify({"error": error}), 500
    if not items:
        return jsonify({"error": "No data in dataset."}), 404

    competitors = process_competitor_data(items)
    trends      = process_trend_data(items)
    actions     = generate_action_items(competitors, trends)

    return jsonify({
        "scanned_at":  datetime.now().strftime("%A, %B %d at %I:%M %p"),
        "competitors": competitors,
        "trends":      trends,
        "actions":     actions,
        "summary": {
            "total_posts":   sum(c["posts"] for c in competitors),
            "total_likes":   sum(c["likes"] for c in competitors),
            "rising_trends": len([t for t in trends if t["momentum"] == "Rising"]),
            "data_source":   "Live — Apify LinkedIn Company Posts Scraper",
        }
    })

@app.route("/api/latest")
def latest():
    if not APIFY_DATASET_ID:
        return jsonify({"error": "No APIFY_DATASET_ID set. Run a scan first."}), 404
    return results(APIFY_DATASET_ID)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
