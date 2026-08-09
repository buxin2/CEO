"""AI assistant tools — all mutations go through existing models and business logic."""

import json
from datetime import datetime

from models import (
    db,
    Company,
    Employee,
    Task,
    get_week_bounds,
)
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
]


def execute_tool(name, arguments, context):
    """Run a tool and return a JSON-serializable result. Updates context dict in place."""
    args = arguments or {}

    if name == "list_companies":
        companies = Company.query.order_by(Company.name.asc()).all()
        return _ok({
            "companies": [
                {"id": c.id, "name": c.name, "employees": c.employees.count()}
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

    return _err(f"Unknown tool: {name}")


def execute_tool_call(tool_call, context):
    name = tool_call.function.name
    try:
        args = json.loads(tool_call.function.arguments or "{}")
    except json.JSONDecodeError:
        args = {}
    result = execute_tool(name, args, context)
    return json.dumps(result)
