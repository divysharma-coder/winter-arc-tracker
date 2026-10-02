"""Built-in smart coach. Pure Python rules, no API key and no internet needed."""
import json
import re


def _t(v):
    if not v or ":" not in str(v):
        return None
    h, m = str(v).split(":")[:2]
    return int(h) * 60 + int(m)


def _fm(m):
    m = int(round(m)) % 1440
    h, mm = divmod(m, 60)
    return f"{(h + 11) % 12 + 1}:{mm:02d} {'AM' if h < 12 else 'PM'}"


def _avg(xs):
    xs = [x for x in xs if x]
    return sum(xs) / len(xs) if xs else 0


def _parse(prompt):
    goals, days = {}, []
    g = re.search(r"Goals: (\{.*?\})\n", prompt, re.S)
    d = re.search(r"Last 7 days[^\n]*?: (\[.*?\])\nRequest:", prompt, re.S)
    try:
        goals = json.loads(g.group(1)) if g else {}
        days = json.loads(d.group(1)) if d else []
    except ValueError:
        pass
    question = prompt.split("Request:", 1)[-1].strip().lower()
    return goals, days, question


ACTIONS = {
    "habits": "Lock in 4 habits first (study, exercise, reading, diet) before anything optional, and tick them off the same day.",
    "water": "Keep a bottle on your desk and finish one glass right after waking, one before each meal.",
    "sleep": "Set a fixed bedtime alarm 30 minutes early and put your phone away when it rings.",
    "wake": "Place your alarm across the room and stand up the moment it rings, then drink water.",
    "study": "Book one 90-minute study block at the same time every day and protect it.",
}


def review(goals, days):
    wg, sg = goals.get("w", 8) or 8, goals.get("s", 7) or 7
    wake_goal = _t(goals.get("k", "06:00")) or 360
    logged = [d for d in days if d.get("habitsDone") or d.get("water") or d.get("sleepH")]
    if not logged:
        return ("No data yet this week, so start small today: tick one habit, log your water and note the time "
                "you wake up. Come back after a few days and I will review your pattern.")
    score = {
        "habits": _avg([d.get("habitsDone", 0) / 6 for d in days]),
        "water": min(1, _avg([d.get("water", 0) for d in days]) / wg),
        "sleep": min(1, _avg([d.get("sleepH", 0) for d in days]) / sg),
        "study": min(1, _avg([d.get("studyH", 0) for d in days]) / 2),
    }
    wakes = [_t(d.get("wake")) for d in days if _t(d.get("wake")) is not None]
    if wakes:
        score["wake"] = sum(1 for w in wakes if w <= wake_goal) / len(wakes)
    names = {"habits": "daily habits", "water": "water", "sleep": "sleep", "study": "study time", "wake": "early wake-ups"}
    best, worst = max(score, key=score.get), min(score, key=score.get)
    full = sum(1 for d in days if d.get("habitsDone", 0) >= 5)
    out = [f"Win: your strongest area is {names[best]} ({round(score[best] * 100)}% of target), "
           f"and {full} of the last 7 days hit 5 or more habits.",
           f"Weak spot: {names[worst]} is at {round(score[worst] * 100)}% of target.",
           "Do this next:",
           f"1. {ACTIONS[worst]}"]
    second = sorted(score, key=score.get)[1] if len(score) > 1 else best
    out.append(f"2. {ACTIONS[second]}")
    return "\n".join(out)


def plan(goals, days):
    wake = _t(goals.get("k", "06:00")) or 360
    sg = goals.get("s", 7) or 7
    bed = (wake - int(sg * 60)) % 1440
    rows = [(wake, "Wake up, drink a glass of water, no phone for 10 minutes"),
            (wake + 30, "Exercise or stretch (30 to 45 minutes)"),
            (wake + 120, "Study block 1 (90 minutes, one topic only)"),
            (wake + 240, "Healthy meal, one glass of water"),
            (wake + 330, "Study block 2 or project work (60 minutes)"),
            (wake + 480, "Reading (30 minutes)"),
            (wake + 600, "Light dinner, log your meals and water"),
            ((bed - 60) % 1440, "Wind down: tomorrow's goal, screens off"),
            (bed, "Bedtime")]
    return "Plan for tomorrow:\n" + "\n".join(f"{_fm(t)}  {x}" for t, x in rows)


def sleep_tips(goals, days):
    sg = goals.get("s", 7) or 7
    sl = _avg([d.get("sleepH", 0) for d in days])
    wakes = [_t(d.get("wake")) for d in days if _t(d.get("wake")) is not None]
    out = []
    if sl:
        out.append(f"You average {sl:.1f} hours of sleep against a goal of {sg}.")
    else:
        out.append("Log your wake-up time and bedtime so I can see your sleep.")
    if len(wakes) >= 2:
        spread = max(wakes) - min(wakes)
        out.append(f"Your wake-up time moved by {spread} minutes this week (average {_fm(sum(wakes) / len(wakes))}). "
                   + ("That is steady, keep it." if spread <= 45 else "Aim to keep it within 45 minutes every day."))
    out.append("Tips: same bedtime daily, no screens for the last 30 minutes, light and water in the morning, "
               "and no caffeine after 3 PM.")
    return "\n".join(out)


def diet_tips(goals, days):
    wg, cg = goals.get("w", 8) or 8, goals.get("c", 2200) or 2200
    water = _avg([d.get("water", 0) for d in days])
    kcal = _avg([d.get("kcal", 0) for d in days])
    out = [f"Water: you average {water:.1f} glasses a day against a goal of {wg}."
           + (" Good work." if water >= wg else " Add one glass after waking and one before each meal.")]
    if kcal:
        diff = kcal - cg
        out.append(f"Calories: you average {round(kcal)} kcal against {cg}, "
                   + ("close to your goal." if abs(diff) <= 150 else f"about {abs(round(diff))} kcal {'over' if diff > 0 else 'under'}."))
    else:
        out.append("Log your meals so I can compare your calories with your goal.")
    out.append("Tip: build each meal around protein and vegetables, and plan tomorrow's meals tonight.")
    return "\n".join(out)


def caption(prompt):
    m = re.search(r"Write an? (\w+) post", prompt)
    plat = m.group(1) if m else "LinkedIn"

    def num(label):
        r = re.search(label + r"\D*?(\d+)", prompt)
        return r.group(1) if r else "0"

    day, streak, best = num(r"day"), num(r"current streak"), num(r"best streak")
    perfect, level, water, study = num(r"perfect days"), num(r"level"), num(r"glasses of water logged"), num(r"study hours")
    tags = "#WinterArc #Consistency #Habits #BuildInPublic"
    if plat == "X":
        return f"Day {day}/90 of my Winter Arc. {streak}-day streak, level {level}. Built my own tracker to stay honest. #WinterArc #Consistency"
    if plat == "Instagram":
        return (f"❄️ Day {day} of 90 \n\n🔥 {streak}-day streak (best: {best})\n💧 {water} glasses of water logged\n"
                f"📚 {study} study hours\n\nNo shortcuts, just showing up daily.\n\n{tags}")
    if plat == "Facebook":
        return (f"Day {day} of my 90-day Winter Arc! 🔥 Current streak: {streak} days (best {best}). "
                f"I have logged {water} glasses of water and {study} study hours so far. "
                f"I built my own tracker with Python and a database to stay accountable. Wish me luck!\n\n{tags}")
    return (f"Day {day} of my 90-day Winter Arc.\n\nMy current streak is {streak} days (best: {best}), with "
            f"{perfect} perfect days so far, {study} study hours and {water} glasses of water logged.\n\n"
            "To stay accountable I built my own habit tracker with Python, a database, charts and a built-in coach "
            "that reviews my week. Consistency beats motivation.\n\nWhat habit are you building this season?\n\n" + tags)


def answer(prompt):
    if re.search(r"Write an? \w+ post", prompt):
        return caption(prompt)
    goals, days, q = _parse(prompt)
    if "plan" in q or "tomorrow" in q:
        return plan(goals, days)
    if "sleep" in q or "wake" in q:
        return sleep_tips(goals, days)
    if "diet" in q or "water" in q or "calor" in q or "food" in q:
        return diet_tips(goals, days)
    return review(goals, days)
