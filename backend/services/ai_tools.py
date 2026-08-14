"""AI assistant tools — all mutations go through existing models and business logic."""

import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from models import (
    db,
    Company,
    Employee,
    Task,
    Product,
    Service,
    Earning,
    get_week_bounds,
)
from routes.catalog import _earnings_summary
from utils import create_group_for_company, group_link_for_token, task_link_for_token


def _ok(data):
    return {"success": True, **data}


def _err(message, **extra):
    return {"success": False, "error": message, **extra}


def _needs_confirm(message):
    return {"success": False, "needs_confirmation": True, "message": message}


def _find_companies(name):
    if not name:
        return None, _err("Company name is required.")
    exact = Company.query.filter(Company.name.ilike(name.strip())).all()
    if len(exact) == 1:
        return exact[0], None
    partial = Company.query.filter(Company.name.ilike(f"%{name.strip()}%")).all()
    if len(partial) == 1:
        return partial[0], None
    if len(partial) > 1:
        names = [c.name for c in partial]
        return None, _err(f"Multiple companies match '{name}': {', '.join(names)}. Please be more specific.")
    return None, _err(f"No company found matching '{name}'.")


def _resolve_company(company_name=None, company_id=None):
    if company_id:
        c = Company.query.get(int(company_id))
        if not c:
            return None, _err(f"Company id {company_id} not found.")
        return c, None
    if company_name:
        return _find_companies(company_name)
    return None, _err("Company name or id is required.")


def _find_employee(company, name=None, employee_id=None):
    if employee_id:
        e = Employee.query.get(int(employee_id))
        if not e or e.company_id != company.id:
            return None, _err("Employee not found in that company.")
        return e, None
    if not name:
        return None, _err("Employee name is required.")
    name = name.strip()
    matches = [
        e for e in company.employees
        if e.name.lower() == name.lower() or name.lower() in e.name.lower()
    ]
    if len(matches) == 1:
        return matches[0], None
    if len(matches) > 1:
        return None, _err(f"Multiple employees match '{name}' in {company.name}.")
    return None, _err(f"No employee '{name}' in {company.name}.")


def _week_bounds(week_label="current"):
    return get_week_bounds()


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "list_companies",
            "description": "List all companies with employee counts.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_company",
            "description": "Get details for one company by name or id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "company_id": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_company",
            "description": "Create a new company (and its group chat automatically).",
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
            "name": "update_company",
            "description": "Update company name or description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "company_id": {"type": "integer"},
                    "new_name": {"type": "string"},
                    "description": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_company",
            "description": "Delete a company. Requires confirmed=true after user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "company_id": {"type": "integer"},
                    "confirmed": {"type": "boolean"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_employees",
            "description": "List employees in a company.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "company_id": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_employee",
            "description": "Add an employee to a company.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "company_id": {"type": "integer"},
                    "name": {"type": "string"},
                    "position": {"type": "string"},
                    "email": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_employee",
            "description": "Update employee name, role/position, or email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "employee_name": {"type": "string"},
                    "new_name": {"type": "string"},
                    "position": {"type": "string"},
                    "email": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_employee",
            "description": "Delete an employee. Requires confirmed=true after user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "employee_name": {"type": "string"},
                    "confirmed": {"type": "boolean"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_tasks",
            "description": "Create weekly tasks for an employee. titles is a list of task title strings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "employee_name": {"type": "string"},
                    "titles": {"type": "array", "items": {"type": "string"}},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["employee_name", "titles"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tasks",
            "description": "List tasks for an employee or whole company for the current week.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "employee_name": {"type": "string"},
                    "status": {"type": "string", "enum": ["all", "pending", "completed"]},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Update a task title, description, or priority by task_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": "Delete a task by id. Requires confirmed=true after user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "integer"},
                    "confirmed": {"type": "boolean"},
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_dashboard_summary",
            "description": "Summary stats for all companies for the current week.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pending_work",
            "description": "Who has pending tasks this week, optionally filtered by company.",
            "parameters": {
                "type": "object",
                "properties": {"company_name": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_products",
            "description": "List products for a company.",
            "parameters": {
                "type": "object",
                "properties": {"company_name": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_product",
            "description": "Add a product to a company.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
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
            "name": "delete_product",
            "description": "Delete a product by id. Requires confirmed=true after user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "integer"},
                    "confirmed": {"type": "boolean"},
                },
                "required": ["product_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_services",
            "description": "List services for a company.",
            "parameters": {
                "type": "object",
                "properties": {"company_name": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_service",
            "description": "Add a service to a company.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
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
            "name": "delete_service",
            "description": "Delete a service by id. Requires confirmed=true after user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_id": {"type": "integer"},
                    "confirmed": {"type": "boolean"},
                },
                "required": ["service_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_earnings_summary",
            "description": "Get earnings totals (today, week, month, total) for a company.",
            "parameters": {
                "type": "object",
                "properties": {"company_name": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_earning",
            "description": "Record earnings for an employee. Defaults to today if date not given.",
            "parameters": {
                "type": "object",
                "properties": {
                    "company_name": {"type": "string"},
                    "employee_name": {"type": "string"},
                    "amount": {"type": "number"},
                    "earned_date": {"type": "string", "description": "YYYY-MM-DD"},
                    "note": {"type": "string"},
                },
                "required": ["employee_name", "amount"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_planner_snapshot",
            "description": "Get app snapshot for personal timetable planning (companies, tasks, earnings, goals).",
            "parameters": {
                "type": "object",
                "properties": {"date": {"type": "string", "description": "YYYY-MM-DD"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_timetable",
            "description": "AI-generate admin personal timetable for a date. replace=true clears existing items first (needs confirmed).",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "replace": {"type": "boolean"},
                    "confirmed": {"type": "boolean"},
                    "instructions": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_timetable",
            "description": "List personal timetable items for a date.",
            "parameters": {
                "type": "object",
                "properties": {"date": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_timetable_item",
            "description": "Add a personal timetable item.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "start_time": {"type": "string"},
                    "end_time": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "priority": {"type": "string"},
                    "category": {"type": "string"},
                    "link_type": {"type": "string"},
                    "link_company_name": {"type": "string"},
                    "link_label": {"type": "string"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_timetable_item",
            "description": "Update a timetable item (time, title, move, complete, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "integer"},
                    "start_time": {"type": "string"},
                    "end_time": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "priority": {"type": "string"},
                    "completed": {"type": "boolean"},
                    "plan_date": {"type": "string"},
                },
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_timetable_item",
            "description": "Delete a timetable item. Requires confirmed=true after user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "item_id": {"type": "integer"},
                    "confirmed": {"type": "boolean"},
                },
                "required": ["item_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reset_timetable",
            "description": "Clear all timetable items for a date. Requires confirmed=true.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "confirmed": {"type": "boolean"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "planner_what_next",
            "description": "Suggest what the admin should do now based on timetable and app state.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string"},
                    "current_time": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_planner_goal",
            "description": "Add monthly, weekly, or daily personal goal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "enum": ["monthly", "weekly", "daily"]},
                    "title": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_planner_notes",
            "description": "Update personal planning notes for AI (focus areas, meetings, etc.).",
            "parameters": {
                "type": "object",
                "properties": {"personal_notes": {"type": "string"}},
                "required": ["personal_notes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_communities",
            "description": "List all communities with member and post counts.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_community",
            "description": "Create a new community (audience/students/followers).",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_community_announcement",
            "description": "Post an announcement message to a community (by name or id).",
            "parameters": {
                "type": "object",
                "properties": {
                    "community_name": {"type": "string"},
                    "community_id": {"type": "integer"},
                    "message": {"type": "string"},
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "schedule_community_message",
            "description": "Schedule a recurring or one-time community announcement.",
            "parameters": {
                "type": "object",
                "properties": {
                    "community_name": {"type": "string"},
                    "community_id": {"type": "integer"},
                    "message": {"type": "string"},
                    "schedule_kind": {"type": "string", "enum": ["once", "daily", "weekly"]},
                    "schedule_time": {"type": "string", "description": "HH:MM local time"},
                    "schedule_weekday": {"type": "integer", "description": "0=Monday for weekly"},
                    "scheduled_at": {"type": "string", "description": "ISO datetime for once"},
                },
                "required": ["message"],
            },
        },
    },
]


def execute_tool(name, arguments, context):
    """Run a tool and return a JSON-serializable result. Updates context dict in place."""
    args = arguments or {}

    if name == "list_companies":
        companies = Company.query.order_by(Company.name.asc()).all()
        return _ok({
            "companies": [
                {
                    "id": c.id,
                    "name": c.name,
                    "employee_count": c.employees.count(),
                    "employees": [
                        {"name": e.name, "position": e.position or ""}
                        for e in c.employees.order_by(Employee.name.asc()).all()
                    ],
                }
                for c in companies
            ],
        })

    if name == "get_company":
        company, err = _resolve_company(args.get("company_name"), args.get("company_id"))
        if err:
            return err
        context["last_company_id"] = company.id
        context["last_company_name"] = company.name
        week_start, week_end = _week_bounds()
        stats = company.get_week_stats(week_start, week_end)
        group = company.group
        return _ok({
            "company": {
                "id": company.id,
                "name": company.name,
                "description": company.description,
                "employees": company.employees.count(),
                "week_stats": stats,
                "group_link": group_link_for_token(group.group_token) if group else None,
            },
        })

    if name == "create_company":
        name_val = (args.get("name") or "").strip()
        if not name_val:
            return _err("Company name is required.")
        existing = Company.query.filter(Company.name.ilike(name_val)).first()
        if existing:
            context["last_company_id"] = existing.id
            context["last_company_name"] = existing.name
            group = existing.group
            return _ok({
                "company_id": existing.id,
                "name": existing.name,
                "already_exists": True,
                "group_link": group_link_for_token(group.group_token) if group else None,
                "message": f"Company \"{existing.name}\" already exists — no duplicate created.",
            })
        company = Company(name=name_val, description=(args.get("description") or "").strip())
        db.session.add(company)
        db.session.flush()
        group = create_group_for_company(company)
        db.session.add(group)
        db.session.commit()
        context["last_company_id"] = company.id
        context["last_company_name"] = company.name
        return _ok({
            "company_id": company.id,
            "name": company.name,
            "group_link": group_link_for_token(group.group_token),
            "message": f"Created company {company.name} with group chat.",
        })

    if name == "update_company":
        company, err = _resolve_company(args.get("company_name"), args.get("company_id"))
        if err:
            return err
        if args.get("new_name"):
            company.name = args["new_name"].strip()
        if args.get("description") is not None:
            company.description = args["description"].strip()
        db.session.commit()
        context["last_company_id"] = company.id
        context["last_company_name"] = company.name
        return _ok({"company_id": company.id, "name": company.name})

    if name == "delete_company":
        if not args.get("confirmed"):
            return _needs_confirm(
                "Deleting a company removes all employees, tasks, and group data. "
                "Ask the user to confirm, then call again with confirmed=true."
            )
        company, err = _resolve_company(args.get("company_name"), args.get("company_id"))
        if err:
            return err
        name_saved = company.name
        db.session.delete(company)
        db.session.commit()
        return _ok({"message": f"Deleted company {name_saved}."})

    if name == "list_employees":
        company, err = _resolve_company(
            args.get("company_name") or context.get("last_company_name"),
            args.get("company_id") or context.get("last_company_id"),
        )
        if err:
            return err
        context["last_company_id"] = company.id
        context["last_company_name"] = company.name
        emps = company.employees.order_by(Employee.name.asc()).all()
        return _ok({
            "company": company.name,
            "employees": [
                {"id": e.id, "name": e.name, "position": e.position or ""}
                for e in emps
            ],
        })

    if name == "create_employee":
        company, err = _resolve_company(
            args.get("company_name") or context.get("last_company_name"),
            args.get("company_id") or context.get("last_company_id"),
        )
        if err:
            return err
        name_val = (args.get("name") or "").strip()
        if not name_val:
            return _err("Employee name is required.")
        employee = Employee(
            company_id=company.id,
            name=name_val,
            position=(args.get("position") or "").strip(),
            email=(args.get("email") or "").strip(),
        )
        db.session.add(employee)
        db.session.commit()
        context["last_company_id"] = company.id
        context["last_company_name"] = company.name
        context["last_employee_name"] = employee.name
        return _ok({
            "employee_id": employee.id,
            "name": employee.name,
            "position": employee.position,
            "company": company.name,
            "task_link": task_link_for_token(employee.unique_token),
        })

    if name == "update_employee":
        company, err = _resolve_company(
            args.get("company_name") or context.get("last_company_name"),
            None,
        )
        if err:
            return err
        employee, err = _find_employee(company, args.get("employee_name") or context.get("last_employee_name"))
        if err:
            return err
        if args.get("new_name"):
            employee.name = args["new_name"].strip()
        if args.get("position") is not None:
            employee.position = args["position"].strip()
        if args.get("email") is not None:
            employee.email = args["email"].strip()
        db.session.commit()
        return _ok({"employee_id": employee.id, "name": employee.name, "position": employee.position})

    if name == "delete_employee":
        if not args.get("confirmed"):
            return _needs_confirm(
                "Deleting an employee removes all their tasks. "
                "Ask the user to confirm, then call again with confirmed=true."
            )
        company, err = _resolve_company(args.get("company_name") or context.get("last_company_name"), None)
        if err:
            return err
        employee, err = _find_employee(company, args.get("employee_name"))
        if err:
            return err
        name_saved = employee.name
        db.session.delete(employee)
        db.session.commit()
        return _ok({"message": f"Deleted employee {name_saved} from {company.name}."})

    if name == "create_tasks":
        company, err = _resolve_company(
            args.get("company_name") or context.get("last_company_name"),
            None,
        )
        if err:
            return err
        employee, err = _find_employee(
            company, args.get("employee_name") or context.get("last_employee_name")
        )
        if err:
            return err
        titles = args.get("titles") or []
        if not titles:
            return _err("No task titles provided.")
        priority = (args.get("priority") or "medium").lower()
        if priority not in ("low", "medium", "high"):
            priority = "medium"
        week_start, week_end = _week_bounds()
        created = []
        for title in titles:
            t = (title or "").strip()
            if not t:
                continue
            task = Task(
                employee_id=employee.id,
                title=t,
                week_start=week_start,
                week_end=week_end,
                priority=priority,
                status="pending",
            )
            db.session.add(task)
            created.append(t)
        db.session.commit()
        context["last_employee_name"] = employee.name
        return _ok({
            "employee": employee.name,
            "company": company.name,
            "tasks_created": created,
            "count": len(created),
        })

    if name == "list_tasks":
        company, err = _resolve_company(
            args.get("company_name") or context.get("last_company_name"),
            None,
        )
        if err:
            return err
        week_start, week_end = _week_bounds()
        status = (args.get("status") or "all").lower()
        results = []
        employees = company.employees.all()
        if args.get("employee_name"):
            employee, err = _find_employee(company, args["employee_name"])
            if err:
                return err
            employees = [employee]
        for e in employees:
            query = e.tasks.filter(Task.week_start == week_start, Task.week_end == week_end)
            if status in ("pending", "completed"):
                query = query.filter(Task.status == status)
            for t in query.all():
                results.append({
                    "task_id": t.id,
                    "employee": e.name,
                    "title": t.title,
                    "status": t.status,
                    "priority": t.priority,
                })
        return _ok({"company": company.name, "tasks": results})

    if name == "update_task":
        task = Task.query.get(args.get("task_id"))
        if not task:
            return _err("Task not found.")
        if args.get("title"):
            task.title = args["title"].strip()
        if args.get("description") is not None:
            task.description = args["description"].strip()
        if args.get("priority") and args["priority"].lower() in ("low", "medium", "high"):
            task.priority = args["priority"].lower()
        db.session.commit()
        return _ok({
            "task_id": task.id,
            "title": task.title,
            "status": task.status,
            "priority": task.priority,
        })

    if name == "delete_task":
        if not args.get("confirmed"):
            return _needs_confirm("Ask the user to confirm task deletion, then call with confirmed=true.")
        task = Task.query.get(args.get("task_id"))
        if not task:
            return _err("Task not found.")
        task_id = task.id
        title = task.title
        db.session.delete(task)
        db.session.commit()
        return _ok({"message": f"Deleted task '{title}' (id {task_id})."})

    if name == "get_dashboard_summary":
        week_start, week_end = _week_bounds()
        companies = Company.query.order_by(Company.name.asc()).all()
        rows = []
        for c in companies:
            stats = c.get_week_stats(week_start, week_end)
            rows.append({"name": c.name, "employees": c.employees.count(), **stats})
        return _ok({
            "week": {"start": week_start.isoformat(), "end": week_end.isoformat()},
            "companies": rows,
        })

    if name == "get_pending_work":
        week_start, week_end = _week_bounds()
        company_filter = None
        if args.get("company_name"):
            company_filter, err = _resolve_company(args["company_name"], None)
            if err:
                return err
        pending = []
        companies = [company_filter] if company_filter else Company.query.all()
        for c in companies:
            for e in c.employees:
                tasks = e.tasks.filter(
                    Task.week_start == week_start,
                    Task.week_end == week_end,
                    Task.status == "pending",
                ).all()
                if tasks:
                    pending.append({
                        "employee": e.name,
                        "company": c.name,
                        "pending_count": len(tasks),
                        "tasks": [t.title for t in tasks],
                    })
        return _ok({"pending": pending})

    if name == "list_products":
        company, err = _resolve_company(
            args.get("company_name") or context.get("last_company_name"), None
        )
        if err:
            return err
        items = company.products.order_by(Product.name.asc()).all()
        return _ok({"company": company.name, "products": [p.to_dict() for p in items]})

    if name == "create_product":
        company, err = _resolve_company(
            args.get("company_name") or context.get("last_company_name"), None
        )
        if err:
            return err
        name_val = (args.get("name") or "").strip()
        if not name_val:
            return _err("Product name is required.")
        product = Product(
            company_id=company.id,
            name=name_val,
            description=(args.get("description") or "").strip(),
        )
        db.session.add(product)
        db.session.commit()
        return _ok({"product_id": product.id, "name": product.name, "company": company.name})

    if name == "delete_product":
        if not args.get("confirmed"):
            return _needs_confirm("Ask the user to confirm product deletion, then call with confirmed=true.")
        product = Product.query.get(args.get("product_id"))
        if not product:
            return _err("Product not found.")
        db.session.delete(product)
        db.session.commit()
        return _ok({"message": f"Deleted product '{product.name}'."})

    if name == "list_services":
        company, err = _resolve_company(
            args.get("company_name") or context.get("last_company_name"), None
        )
        if err:
            return err
        items = company.services.order_by(Service.name.asc()).all()
        return _ok({"company": company.name, "services": [s.to_dict() for s in items]})

    if name == "create_service":
        company, err = _resolve_company(
            args.get("company_name") or context.get("last_company_name"), None
        )
        if err:
            return err
        name_val = (args.get("name") or "").strip()
        if not name_val:
            return _err("Service name is required.")
        service = Service(
            company_id=company.id,
            name=name_val,
            description=(args.get("description") or "").strip(),
        )
        db.session.add(service)
        db.session.commit()
        return _ok({"service_id": service.id, "name": service.name, "company": company.name})

    if name == "delete_service":
        if not args.get("confirmed"):
            return _needs_confirm("Ask the user to confirm service deletion, then call with confirmed=true.")
        service = Service.query.get(args.get("service_id"))
        if not service:
            return _err("Service not found.")
        db.session.delete(service)
        db.session.commit()
        return _ok({"message": f"Deleted service '{service.name}'."})

    if name == "get_earnings_summary":
        company, err = _resolve_company(
            args.get("company_name") or context.get("last_company_name"), None
        )
        if err:
            return err
        return _ok({"company": company.name, "summary": _earnings_summary(company.id)})

    if name == "create_earning":
        company, err = _resolve_company(
            args.get("company_name") or context.get("last_company_name"), None
        )
        if err:
            return err
        employee, err = _find_employee(
            company, args.get("employee_name") or context.get("last_employee_name")
        )
        if err:
            return err
        try:
            amount = Decimal(str(args.get("amount")))
        except (InvalidOperation, ValueError):
            return _err("Amount must be a valid number.")
        if amount <= 0:
            return _err("Amount must be greater than zero.")
        earned_date = date.today()
        if args.get("earned_date"):
            try:
                earned_date = datetime.strptime(args["earned_date"], "%Y-%m-%d").date()
            except ValueError:
                return _err("earned_date must be YYYY-MM-DD.")
        earning = Earning(
            company_id=company.id,
            employee_id=employee.id,
            amount=amount,
            earned_date=earned_date,
            note=(args.get("note") or "").strip(),
        )
        db.session.add(earning)
        db.session.commit()
        context["last_employee_name"] = employee.name
        return _ok({
            "employee": employee.name,
            "amount": float(amount),
            "earned_date": earned_date.isoformat(),
            "company": company.name,
            "summary": _earnings_summary(company.id),
        })

    if name == "get_planner_snapshot":
        ref = date.today()
        if args.get("date"):
            try:
                ref = datetime.strptime(args["date"], "%Y-%m-%d").date()
            except ValueError:
                return _err("date must be YYYY-MM-DD.")
        from services.planner_snapshot import build_planner_snapshot

        return _ok({"snapshot": build_planner_snapshot(ref)})

    if name == "generate_timetable":
        replace = bool(args.get("replace"))
        if replace and not args.get("confirmed"):
            return _needs_confirm(
                "This will replace existing timetable items for that day. "
                "Ask the user to confirm, then call with confirmed=true."
            )
        plan_date = date.today()
        if args.get("date"):
            try:
                plan_date = datetime.strptime(args["date"], "%Y-%m-%d").date()
            except ValueError:
                return _err("date must be YYYY-MM-DD.")
        from services.planner_ai import generate_timetable_with_ai
        from services.planner_service import list_timetable_for_date, serialize_item, timetable_progress

        try:
            result = generate_timetable_with_ai(
                plan_date,
                replace_existing=replace,
                extra_instructions=args.get("instructions") or "",
            )
            items = list_timetable_for_date(plan_date)
            result["items"] = [serialize_item(i) for i in items]
            result["progress"] = timetable_progress(items)
            return _ok(result)
        except Exception as exc:
            return _err(str(exc))

    if name == "list_timetable":
        plan_date = date.today()
        if args.get("date"):
            try:
                plan_date = datetime.strptime(args["date"], "%Y-%m-%d").date()
            except ValueError:
                return _err("date must be YYYY-MM-DD.")
        from services.planner_service import list_timetable_for_date, serialize_item, timetable_progress, daily_summary

        items = list_timetable_for_date(plan_date)
        return _ok({
            "date": plan_date.isoformat(),
            "items": [serialize_item(i) for i in items],
            "progress": timetable_progress(items),
            "summary": daily_summary(plan_date),
        })

    if name == "create_timetable_item":
        from services.planner_service import create_timetable_item, serialize_item, resolve_company_id

        plan_date = date.today()
        if args.get("date"):
            try:
                plan_date = datetime.strptime(args["date"], "%Y-%m-%d").date()
            except ValueError:
                return _err("date must be YYYY-MM-DD.")
        link_company_id = resolve_company_id(args.get("link_company_name"))
        try:
            item = create_timetable_item(plan_date, {
                **args,
                "link_company_id": link_company_id,
            })
            return _ok({"item": serialize_item(item)})
        except ValueError as exc:
            return _err(str(exc))

    if name == "update_timetable_item":
        from services.planner_service import update_timetable_item, serialize_item

        if not args.get("item_id"):
            return _err("item_id is required.")
        try:
            item = update_timetable_item(int(args["item_id"]), args)
            return _ok({"item": serialize_item(item)})
        except ValueError as exc:
            return _err(str(exc))

    if name == "delete_timetable_item":
        if not args.get("confirmed"):
            return _needs_confirm("Ask the user to confirm deletion, then call with confirmed=true.")
        from services.planner_service import delete_timetable_item

        if not args.get("item_id"):
            return _err("item_id is required.")
        try:
            delete_timetable_item(int(args["item_id"]))
            return _ok({"message": "Timetable item deleted."})
        except ValueError as exc:
            return _err(str(exc))

    if name == "reset_timetable":
        if not args.get("confirmed"):
            return _needs_confirm("Ask the user to confirm reset, then call with confirmed=true.")
        from services.planner_service import reset_timetable_for_date

        plan_date = date.today()
        if args.get("date"):
            try:
                plan_date = datetime.strptime(args["date"], "%Y-%m-%d").date()
            except ValueError:
                return _err("date must be YYYY-MM-DD.")
        reset_timetable_for_date(plan_date)
        return _ok({"message": f"Timetable cleared for {plan_date.isoformat()}."})

    if name == "planner_what_next":
        from services.planner_ai import suggest_next_activity

        plan_date = date.today()
        if args.get("date"):
            try:
                plan_date = datetime.strptime(args["date"], "%Y-%m-%d").date()
            except ValueError:
                return _err("date must be YYYY-MM-DD.")
        try:
            suggestion = suggest_next_activity(plan_date, args.get("current_time"))
            return _ok({"suggestion": suggestion})
        except Exception as exc:
            return _err(str(exc))

    if name == "create_planner_goal":
        from services.planner_snapshot import period_keys_for
        from services.planner_service import create_goal

        scope = (args.get("scope") or "daily").lower()
        keys = period_keys_for()
        if args.get("date"):
            try:
                ref = datetime.strptime(args["date"], "%Y-%m-%d").date()
                keys = period_keys_for(ref)
            except ValueError:
                return _err("date must be YYYY-MM-DD.")
        period_key = keys.get(scope, keys["daily"])
        try:
            goal = create_goal(scope, period_key, args.get("title"))
            return _ok(goal.to_dict())
        except ValueError as exc:
            return _err(str(exc))

    if name == "update_planner_notes":
        from services.planner_service import get_planner_settings

        settings = get_planner_settings()
        settings.personal_notes = (args.get("personal_notes") or "").strip()
        db.session.commit()
        return _ok({"message": "Personal planning notes updated."})

    if name == "list_communities":
        from services.community_service import list_communities, community_dashboard

        rows = list_communities()
        data = []
        for c in rows:
            dash = community_dashboard(c.id)
            data.append({**c.to_dict(), "stats": dash["stats"]})
        return _ok({"communities": data})

    if name == "create_community":
        from services.community_service import create_community

        try:
            c = create_community(args.get("name"))
            return _ok({"community": c.to_dict(include_link=True)})
        except ValueError as exc:
            return _err(str(exc))

    if name == "send_community_announcement":
        from models import Community
        from services.community_service import create_post

        cid = args.get("community_id")
        if not cid and args.get("community_name"):
            matches = Community.query.filter(
                Community.name.ilike(f"%{args['community_name'].strip()}%"),
                Community.deleted_at.is_(None),
            ).all()
            if len(matches) == 1:
                cid = matches[0].id
            elif len(matches) > 1:
                return _err(f"Multiple communities match: {', '.join(c.name for c in matches)}")
            else:
                return _err("Community not found.")
        if not cid:
            return _err("community_name or community_id is required.")
        message = (args.get("message") or "").strip()
        if not message:
            return _err("message is required.")
        try:
            post = create_post(int(cid), message, admin_id=context.get("admin_id"), is_announcement=True)
            return _ok({"post": post.to_dict(), "message": "Announcement posted."})
        except ValueError as exc:
            return _err(str(exc))

    if name == "schedule_community_message":
        from models import Community
        from services.community_service import create_scheduled_message

        cid = args.get("community_id")
        if not cid and args.get("community_name"):
            matches = Community.query.filter(
                Community.name.ilike(f"%{args['community_name'].strip()}%"),
                Community.deleted_at.is_(None),
            ).all()
            if len(matches) == 1:
                cid = matches[0].id
            elif len(matches) > 1:
                return _err(f"Multiple communities match: {', '.join(c.name for c in matches)}")
            else:
                return _err("Community not found.")
        if not cid:
            return _err("community_name or community_id is required.")
        try:
            row = create_scheduled_message(int(cid), args)
            return _ok({"scheduled_message": row.to_dict()})
        except ValueError as exc:
            return _err(str(exc))

    return _err(f"Unknown tool: {name}")


def execute_tool_call(tool_call, context):
    name, arguments = _normalize_tool_call(
        tool_call.function.name,
        tool_call.function.arguments or "{}",
    )
    try:
        args = json.loads(arguments or "{}")
    except json.JSONDecodeError:
        args = {}
    result = execute_tool(name, args, context)
    return json.dumps(result)


def _normalize_tool_call(name, arguments):
    """Shared normalization for mangled Groq Llama tool names."""
    args = arguments if arguments is not None else ""
    if isinstance(args, str) and args.strip() in ("", "{}"):
        if "=" in name:
            tool_name, rest = name.split("=", 1)
            rest = rest.strip()
            if rest.startswith("{") or rest.startswith("["):
                return tool_name.strip(), rest
        if "," in name:
            tool_name, rest = name.split(",", 1)
            rest = rest.strip()
            if rest.startswith("{") or rest.startswith("["):
                return tool_name.strip(), rest
    if not isinstance(args, str):
        args = json.dumps(args)
    return (name or "").strip(), args.strip() or "{}"
