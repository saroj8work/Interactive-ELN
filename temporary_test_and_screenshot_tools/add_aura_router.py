with open("backend/gateway/app/main.py", "r", encoding="utf-8") as f:
    text = f.read()

crlf = "\r\n" in text
norm = text.replace("\r\n", "\n")

old_import = """from .router import (
    activity_router,
    attachments_router,
    booking_router,
    inventory_router,
    integrations_router,
    notebook_router,
    projects_router,
    search_router,
    templates_router,
)"""

new_import = """from .router import (
    activity_router,
    attachments_router,
    aura_router,
    booking_router,
    inventory_router,
    integrations_router,
    notebook_router,
    projects_router,
    search_router,
    templates_router,
)"""

old_include = """app.include_router(integrations_router)"""
new_include = """app.include_router(integrations_router)
app.include_router(aura_router)"""

if old_import in norm and old_include in norm:
    norm = norm.replace(old_import, new_import, 1)
    norm = norm.replace(old_include, new_include, 1)
    res = norm.replace("\n", "\r\n") if crlf else norm
    with open("backend/gateway/app/main.py", "w", encoding="utf-8") as f:
        f.write(res)
    print("Successfully included aura_router in main.py")
else:
    print("Pattern not matched in main.py")
