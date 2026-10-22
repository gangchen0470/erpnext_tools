# Tools

An independent Frappe v16 app that provides a single, permission-aware entry
point for internal tools. It does not patch Frappe or ERPNext.

Version 0.1.0 includes:

- a Tools app entry on the v16 apps screen;
- a dynamic `/app/tools` Desk page;
- Tool Category and Tool Definition registries;
- Tools User and Tools Manager roles;
- per-tool role filtering and safe route validation;
- install-time creation of roles and a default General category.

New business tools should live in their own module/package and register a Tool
Definition instead of modifying the homepage. External URLs must use HTTPS.
