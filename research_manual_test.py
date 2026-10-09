from app.tools.research_tool import ResearchTool

query = (
    "Compare cloud computing and edge computing. "
    "Explain the key differences, advantages, disadvantages, "
    "and real-world use cases using reliable sources."
)

print("🔎 Starting TaskPilot Research Agent...")
print()

result = ResearchTool.summarize_information(query)

print("========== DIRECT ANSWER ==========")
print(result["direct_answer"])

print()
print("========== EXECUTIVE SUMMARY ==========")
print(result["executive_summary"])

print()
print("========== KEY CONCEPTS ==========")
for item in result["key_concepts"]:
    print("-", item)

print()
print("========== FINDINGS ==========")
for item in result["findings"]:
    print("-", item)

print()
print("========== BENEFITS ==========")
for item in result["benefits"]:
    print("-", item)

print()
print("========== RISKS ==========")
for item in result["risks"]:
    print("-", item)

print()
print("========== REAL-WORLD EXAMPLES ==========")
for item in result["real_world_examples"]:
    print("-", item)

print()
print("========== ACTION ITEMS ==========")
for item in result["action_items"]:
    print("-", item)

print()
print("========== SOURCES ==========")
for source in result["sources"]:
    print("-", source.get("title"))
    print("  ", source.get("url"))

print()
print("✅ Research Agent test completed.")