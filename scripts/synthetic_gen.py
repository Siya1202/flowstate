import json
import random
import uuid
import argparse

TEAM_MEMBERS = ["Siya", "Srishti", "Malhar", "Gargi", "Atharva"]
TASKS = [
    ("Complete the API endpoint", "EOD"),
    ("Write unit tests", "Friday"),
    ("Review the pull request", "tomorrow"),
    ("Update the documentation", "next Monday"),
    ("Fix the login bug", "today"),
    ("Deploy to staging", "Wednesday"),
    ("Prepare the demo", "April 5th"),
    ("Set up the database", "tomorrow night"),
    ("Design the wireframes", "Thursday"),
    ("Integrate the payment gateway", "next Friday"),
]

FILLER_MESSAGES = [
    "ok sounds good",
    "sure",
    "got it",
    "👍",
    "will do",
    "on it",
    "makes sense",
    "agreed",
    "let me check",
    "yeah that works",
]

def generate_chat(ground_truth_tasks):
    messages = []
    for task, deadline in ground_truth_tasks:
        owner = random.choice(TEAM_MEMBERS)
        assigner = random.choice([m for m in TEAM_MEMBERS if m != owner])
        messages.append(f"[31/03/2026, {random.randint(9,17)}:{random.randint(0,59):02d}:00] {assigner}: hey {owner} can you {task} by {deadline}?")
        messages.append(f"[31/03/2026, {random.randint(9,17)}:{random.randint(0,59):02d}:00] {owner}: {random.choice(FILLER_MESSAGES)}")
        # Add some filler
        for _ in range(random.randint(1, 3)):
            speaker = random.choice(TEAM_MEMBERS)
            messages.append(f"[31/03/2026, {random.randint(9,17)}:{random.randint(0,59):02d}:00] {speaker}: {random.choice(FILLER_MESSAGES)}")
    return "\n".join(messages)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=200, help="Number of samples to generate")
    parser.add_argument("--output", type=str, default="data/synthetic_hackathon.json", help="Output file")
    args = parser.parse_args()

    dataset = []
    for _ in range(args.count):
        # Pick 3-6 random tasks
        selected = random.sample(TASKS, random.randint(3, 6))
        chat_text = generate_chat(selected)
        dataset.append({
            "id": str(uuid.uuid4()),
            "chat": chat_text,
            "ground_truth": [
                {"title": task, "deadline": deadline}
                for task, deadline in selected
            ]
        })

    with open(args.output, "w") as f:
        json.dump(dataset, f, indent=2)

    print(f"✅ Generated {args.count} samples → {args.output}")

if __name__ == "__main__":
    main()