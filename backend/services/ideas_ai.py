"""My Ideas AI — conversation, extraction, and workspace tools."""

import json
import re

from services.app_knowledge import build_ai_app_knowledge_text
from services.groq_key_service import get_active_groq_config, is_groq_configured, mark_key_used
from services.ideas_service import (
    add_decision,
    add_event,
    add_link,
    add_list_item,
    add_message,
    add_next_step,
    complete_next_step,
    create_idea,
    detect_new_idea_intent,
    get_idea,
    list_messages,
    merge_structured,
    remove_list_item,
    update_idea,
)
from services.owner_profile_service import build_name_address_rules, resolve_owner_display_name


def build_idea_system(admin_id, idea=None):
    name = resolve_owner_display_name(admin_id)
    base = (
        f"You are {name}'s Idea Development AI inside the My Ideas workspace.\n"
        + build_name_address_rules(admin_id)
        + "\n"
        "Your job: capture ideas fast, remember everything, organize insights, and help turn ideas into action.\n"
        "NEVER silently change decisions — discuss changes first, then update via tools.\n"
        "Use tools to save requirements, decisions, next steps, status, and links as the conversation evolves.\n"
        "Be practical, creative, and honest. Help develop ideas — do not just repeat what the user said.\n"
        "You have access to live app data (companies, tasks, communities, etc.) in context.\n"
    )
    if idea:
        base += f"\nCURRENT IDEA: {idea.title}\nStatus: {idea.status} | Priority: {idea.priority}\n"
        structured = idea.structured()
        base += "STRUCTURED DATA:\n" + json.dumps(structured, ensure_ascii=False)[:6000]
        if idea.narrative_summary:
            base += "\nSUMMARY:\n" + idea.narrative_summary[:3000]
        if idea.original_text:
            base += "\nORIGINAL CAPTURE:\n" + idea.original_text[:2000]
    return base


def build_idea_context_block(admin_id):
    return "LIVE APP KNOWLEDGE:\n" + build_ai_app_knowledge_text()[:8000]


IDEA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "update_idea_fields",
            "description": "Update idea status, priority, tags, or structured text fields (concept, goal, target_users, business_model).",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "priority": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "concept": {"type": "string"},
                    "goal": {"type": "string"},
                    "target_users": {"type": "string"},
                    "target_market": {"type": "string"},
                    "business_model": {"type": "string"},
                    "narrative_summary": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_requirement",
            "description": "Add a requirement to the idea.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remove_requirement",
            "description": "Remove a requirement (e.g. when user changes mind).",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_decision",
            "description": "Record an important decision for this idea.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_problem",
            "description": "Record a problem or risk for this idea.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_open_question",
            "description": "Record an open question to resolve later.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_next_step",
            "description": "Add a next-step action item.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_next_step",
            "description": "Mark a next step as done by id or exact text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "step_id": {"type": "integer"},
                    "text": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "record_timeline_event",
            "description": "Add a timeline/history note for this idea.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "event_type": {"type": "string"},
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "link_entity",
            "description": "Link idea to company, community, product, task, or opportunity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "link_type": {"type": "string", "enum": ["company", "community", "product", "task", "opportunity"]},
                    "link_id": {"type": "integer"},
                    "label": {"type": "string"},
                },
                "required": ["link_type", "link_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_company",
            "description": "Create a new company from this idea.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_tasks",
            "description": "Create employee tasks for this idea's company.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "employee_name": {"type": "string"},
                    "tasks": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["tasks"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_timetable_item",
            "description": "Add a timetable block to work on this idea.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "plan_date": {"type": "string"},
                    "start_time": {"type": "string"},
                    "end_time": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["title"],
            },
        },
    },
]


def _execute_idea_tool(name, args, admin_id, idea_id):
    from models import db

    idea = get_idea(admin_id, idea_id)

    if name == "update_idea_fields":
        patch = {}
        structured_patch = {}
        for key in ("concept", "goal", "target_users", "target_market", "business_model"):
            if args.get(key):
                structured_patch[key] = args[key]
        if structured_patch:
            merge_structured(idea, structured_patch)
        data = {}
        if args.get("status"):
            data["status"] = args["status"]
        if args.get("priority"):
            data["priority"] = args["priority"]
        if args.get("tags"):
            data["tags"] = args["tags"]
        if args.get("narrative_summary"):
            data["narrative_summary"] = args["narrative_summary"]
        if data:
            update_idea(admin_id, idea_id, data)
        db.session.commit()
        return {"success": True}

    if name == "add_requirement":
        add_list_item(idea, "requirements", args.get("text"))
        db.session.commit()
        return {"success": True}

    if name == "remove_requirement":
        remove_list_item(idea, "requirements", args.get("text"))
        db.session.commit()
        return {"success": True}

    if name == "add_decision":
        add_decision(idea, args.get("text"))
        db.session.commit()
        return {"success": True}

    if name == "add_problem":
        add_list_item(idea, "problems", args.get("text"))
        db.session.commit()
        return {"success": True}

    if name == "add_open_question":
        add_list_item(idea, "open_questions", args.get("text"))
        db.session.commit()
        return {"success": True}

    if name == "add_next_step":
        add_next_step(idea, args.get("text"))
        db.session.commit()
        return {"success": True}

    if name == "complete_next_step":
        complete_next_step(idea, step_id=args.get("step_id"), text=args.get("text"))
        db.session.commit()
        return {"success": True}

    if name == "record_timeline_event":
        add_event(idea_id, args.get("event_type") or "note", args.get("description"))
        db.session.commit()
        return {"success": True}

    if name == "link_entity":
        link = add_link(idea_id, args["link_type"], args["link_id"], args.get("label") or "")
        db.session.commit()
        return {"success": True, "link_id": link.id}

    if name == "create_company":
        from services.ai_tools import execute_tool

        ctx = {}
        result = json.loads(
            execute_tool(
                "create_company",
                {"name": args.get("name"), "description": args.get("description") or ""},
                ctx,
            )
        )
        if result.get("success") and result.get("company_id"):
            add_link(idea_id, "company", result["company_id"], args.get("name") or "")
            add_event(idea_id, "linked", f"Created company: {result.get('name')}")
            db.session.commit()
        return result

    if name == "create_tasks":
        from services.ai_tools import execute_tool

        ctx = {}
        result = json.loads(
            execute_tool(
                "create_tasks",
                {
                    "company_name": args.get("company_name"),
                    "employee_name": args.get("employee_name"),
                    "tasks": args.get("tasks") or [],
                },
                ctx,
            )
        )
        if result.get("success"):
            add_event(idea_id, "tasks", "Created tasks from idea.")
            db.session.commit()
        return result

    if name == "create_timetable_item":
        from services.app_time import app_today, parse_date_iso
        from services.planner_service import create_timetable_item

        plan_date = parse_date_iso(args.get("plan_date")) or app_today(admin_id)
        item = create_timetable_item(
            plan_date,
            {
                "title": args.get("title"),
                "start_time": args.get("start_time"),
                "end_time": args.get("end_time"),
                "description": (args.get("description") or "") + f" [Idea: {idea.title}]",
            },
        )
        add_link(idea_id, "timetable", item.id, item.title)
        add_event(idea_id, "timetable", f"Added timetable: {item.title}")
        db.session.commit()
        return {"success": True, "item_id": item.id}

    return {"error": f"Unknown tool: {name}"}


def _parse_json(raw):
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


def generate_idea_from_message(admin_id, message):
    """Create a new idea with AI-generated title and initial structure."""
    if not is_groq_configured():
        raise ValueError("AI is not configured. Add a Groq API key in Admin → AI Assistant.")

    config = get_active_groq_config()
    from groq import Groq

    client = Groq(api_key=config["api_key"])
    prompt = (
        "The user is capturing a new business/product idea in unstructured language.\n"
        "Return JSON only:\n"
        '{"title":"short catchy title","preview":"one line","concept":"...","goal":"...",'
        '"target_users":"...","tags":["..."],"status":"new|exploring","priority":"low|medium|high|critical",'
        '"requirements":[],"next_steps":[],"assistant_reply":"friendly first response to continue discussion"}'
    )
    response = client.chat.completions.create(
        model=config["model"],
        messages=[
            {"role": "system", "content": build_idea_system(admin_id) + build_idea_context_block(admin_id)},
            {"role": "user", "content": message},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=1200,
    )
    mark_key_used(config.get("key_id"))
    data = _parse_json(response.choices[0].message.content or "{}")
    title = (data.get("title") or "New Idea").strip()[:500]
    structured = {
        "concept": data.get("concept") or "",
        "goal": data.get("goal") or "",
        "target_users": data.get("target_users") or "",
        "requirements": data.get("requirements") or [],
        "next_steps": [
            {"id": i + 1, "text": t, "done": False}
            for i, t in enumerate(data.get("next_steps") or [])
        ],
    }
    idea = create_idea(
        admin_id,
        title=title,
        original_text=message,
        status=data.get("status") or "new",
        priority=data.get("priority") or "medium",
        tags=data.get("tags") or [],
        structured=structured,
    )
    idea.preview = (data.get("preview") or idea.preview)[:500]
    from models import db

    db.session.commit()
    reply = (data.get("assistant_reply") or "").strip()
    if reply:
        add_message(idea.id, "assistant", reply)
        db.session.commit()
    return idea, reply


def idea_chat(admin_id, idea_id, message):
    if not is_groq_configured():
        return "Add a Groq API key in Admin → AI Assistant to use My Ideas."

    idea = get_idea(admin_id, idea_id)
    config = get_active_groq_config()
    from groq import Groq

    client = Groq(api_key=config["api_key"])
    system = build_idea_system(admin_id, idea) + "\n" + build_idea_context_block(admin_id)

    prior = list_messages(idea_id, limit=40)
    messages = [{"role": "system", "content": system}]
    for m in prior:
        if m.role in ("user", "assistant"):
            messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": message})

    for _ in range(8):
        response = client.chat.completions.create(
            model=config["model"],
            messages=messages,
            tools=IDEA_TOOLS,
            tool_choice="auto",
            temperature=0.45,
            max_tokens=1400,
        )
        mark_key_used(config.get("key_id"))
        msg = response.choices[0].message

        if msg.tool_calls:
            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments or "{}",
                        },
                    }
                    for tc in msg.tool_calls
                ],
            })
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = _execute_idea_tool(tc.function.name, args, admin_id, idea_id)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                })
            continue

        reply = (msg.content or "").strip()
        add_message(idea_id, "user", message)
        add_message(idea_id, "assistant", reply)
        from models import db

        db.session.commit()
        return reply

    return "Let me think — please try again."


def idea_action(admin_id, idea_id, action):
    """Run a one-shot AI action: summarize, analyze, plan, etc."""
    if not is_groq_configured():
        raise ValueError("AI is not configured.")

    prompts = {
        "summarize": "Write a comprehensive current summary of this entire idea. Use markdown sections.",
        "analyze": "Analyze this idea: strengths, weaknesses, risks, and opportunities.",
        "plan": "Create a practical development plan with phases and milestones.",
        "goals": "Define clear measurable goals for this idea.",
        "requirements": "Extract and list all requirements mentioned or implied.",
        "business_model": "Propose business models and revenue options for this idea.",
        "problems": "List the biggest problems and how to address them.",
        "next_steps": "List the top next steps as a numbered action list.",
    }
    prompt = prompts.get(action)
    if not prompt:
        raise ValueError("Unknown action.")

    idea = get_idea(admin_id, idea_id)
    config = get_active_groq_config()
    from groq import Groq

    client = Groq(api_key=config["api_key"])
    history = "\n".join(f"{m.role}: {m.content}" for m in list_messages(idea_id, limit=30))
    response = client.chat.completions.create(
        model=config["model"],
        messages=[
            {"role": "system", "content": build_idea_system(admin_id, idea)},
            {"role": "user", "content": history + "\n\nTASK: " + prompt},
        ],
        temperature=0.4,
        max_tokens=1500,
    )
    mark_key_used(config.get("key_id"))
    text = (response.choices[0].message.content or "").strip()
    if action == "summarize":
        update_idea(admin_id, idea_id, {"narrative_summary": text})
    add_message(idea_id, "assistant", f"**{action.replace('_', ' ').title()}**\n\n{text}")
    from models import db

    db.session.commit()
    return text


def start_or_continue_chat(admin_id, message, idea_id=None, create_new=False):
    message = (message or "").strip()
    if not message:
        raise ValueError("Message is required.")
    if create_new or (not idea_id and detect_new_idea_intent(message)):
        idea, reply = generate_idea_from_message(admin_id, message)
        return {"idea": idea.to_dict(include_detail=True), "reply": reply, "created": True}
    if not idea_id:
        raise ValueError("Select an idea or start a new one.")
    reply = idea_chat(admin_id, idea_id, message)
    idea = get_idea(admin_id, idea_id)
    return {"idea": idea.to_dict(include_detail=True), "reply": reply, "created": False}
