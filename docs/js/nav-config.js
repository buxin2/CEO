/* Single source of truth for the admin sidebar. Pages must not redefine menu items. */
window.NAV_GROUPS = [
  {
    id: "work",
    label: "Work",
    items: [
      { id: "dashboard", label: "Dashboard", href: "dashboard.html", icon: "grid", match: ["dashboard.html"] },
      { id: "companies", label: "Companies", href: "dashboard.html#companies", icon: "building", match: ["dashboard.html#companies", "company.html", "employee-tasks.html"] },
      { id: "excel", label: "Excel Lists", href: "excel-lists.html", icon: "list", match: ["excel-lists.html"] },
      { id: "reports", label: "Reports", href: "reports.html", icon: "chart", match: ["reports.html"] },
      {
        id: "communities",
        label: "Communities",
        icon: "users",
        children: [
          { id: "communities-all", label: "All communities", href: "communities.html", match: ["communities.html", "community-admin.html"] },
          { id: "community-orders", label: "Community orders", href: "orders.html", match: ["orders.html"] },
          { id: "community-members", label: "Members", href: "communities.html?view=members", match: ["communities.html?view=members"] },
        ],
      },
    ],
  },
  {
    id: "store",
    label: "Store",
    items: [
      { id: "products", label: "Products", href: "admin-store.html", icon: "box", match: ["admin-store.html"] },
      {
        id: "orders",
        label: "Orders",
        icon: "receipt",
        children: [
          { id: "store-orders", label: "Store orders", href: "admin-store-orders.html", match: ["admin-store-orders.html"] },
          { id: "orders-community", label: "Community orders", href: "orders.html", match: ["orders.html"] },
        ],
      },
      { id: "store-users", label: "Store Users", href: "admin-store-users.html", icon: "user", match: ["admin-store-users.html"] },
      { id: "shipping", label: "Shipping", href: "admin-shipping.html", icon: "truck", match: ["admin-shipping.html"] },
      { id: "payments", label: "Payments", href: "payments.html", icon: "card", match: ["payments.html"] },
    ],
  },
  {
    id: "personal",
    label: "Personal",
    items: [
      {
        id: "ai",
        label: "AI Assistant",
        icon: "spark",
        children: [
          { id: "ai-chat", label: "Chat", href: "ai-assistant.html", match: ["ai-assistant.html"] },
          { id: "ai-manage", label: "Manage", href: "ai-assistant.html?view=manage", match: ["ai-assistant.html?view=manage"] },
          { id: "ai-settings", label: "Settings & API keys", href: "ai-assistant.html?view=settings", match: ["ai-assistant.html?view=settings"] },
        ],
      },
      { id: "mentor", label: "Mentor", href: "mentor.html", icon: "brain", match: ["mentor.html"] },
      { id: "ideas", label: "My Ideas", href: "ideas.html", icon: "lamp", match: ["ideas.html"] },
      { id: "timetable", label: "My Timetable", href: "timetable.html", icon: "cal", match: ["timetable.html"] },
      { id: "news", label: "News", href: "news.html", icon: "news", match: ["news.html"] },
    ],
  },
];
