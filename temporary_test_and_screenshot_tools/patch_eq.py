with open("temporary_test_and_screenshot_tools/seed_full_microservices.py", "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace(
    'status="operational",',
    'status="operational",\n                created_by_user_id=user_sarah_id,'
)

with open("temporary_test_and_screenshot_tools/seed_full_microservices.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Updated EquipmentResource with created_by_user_id.")

